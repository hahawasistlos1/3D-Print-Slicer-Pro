"""Find areas shared by opposing planar faces of different color parts."""
from collections import defaultdict
from itertools import product

import manifold3d as md
import numpy as np

from manual_planes import frame


# Keep an optional scan of densely curved models from exhausting memory.
MAX_CONTACT_TRIANGLES = 500_000
MAX_CONTACT_COMPARISONS = 100_000


def face_groups(body, normal_step, distance_step, origin):
    mesh = body.to_mesh64()
    triangles = np.asarray(mesh.vert_properties)[:, :3][np.asarray(mesh.tri_verts)] - origin
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 0
    triangles = triangles[valid]
    normals = normals[valid] / lengths[valid, None]
    # Keep opposing normals in separate groups. Their offsets also have opposite signs.
    planes = np.column_stack((normals, np.einsum('ij,ij->i', normals, triangles[:, 0])))
    keys = np.rint(planes / [normal_step, normal_step, normal_step, distance_step]).astype(np.int64)
    order = np.lexsort(keys.T[::-1])
    ordered = keys[order]
    starts = np.r_[0, np.flatnonzero(np.any(ordered[1:] != ordered[:-1], axis=1)) + 1, len(order)]
    for start, end in zip(starts, starts[1:]):
        if start != end:
            rows = order[start:end]
            yield tuple(ordered[start]), planes[rows[0]], triangles[rows]


def contact_interfaces(parts, boxes, epsilon, min_area, progress):
    referenced = set()
    neighbors = defaultdict(set)
    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            if parts[i]['color'] == parts[j]['color']:
                continue
            b = boxes[j]
            overlap = np.minimum(a[3:], b[3:]) - np.maximum(a[:3], b[:3])
            if np.all(overlap >= -epsilon) and np.count_nonzero(overlap > epsilon) >= 2:
                neighbors[j].add(i)
                referenced.update((i, j))
    if sum(parts[i]['base'].num_tri() for i in referenced) > MAX_CONTACT_TRIANGLES:
        raise ValueError('Zu viele Dreiecke für die Suche nach Farbkontaktflächen. „Verbinder zwischen Farbgruppen“ ausschalten oder das Modell vereinfachen.')
    if not referenced:
        return

    origin = np.min(np.asarray(boxes)[:, :3], axis=0)
    normal_step = 1e-7
    distance_step = epsilon * 2
    by_normal = defaultdict(lambda: defaultdict(list))
    nearby = tuple(product((-1, 0, 1), repeat=3))
    contacts = {}
    comparisons = 0
    # Process parts in stable order so interface IDs remain stable on recomputation.
    for i in sorted(referenced):
        progress(39, f'Kontaktflächen zwischen Farben suchen · Teil {i+1}/{len(parts)}')
        groups = list(face_groups(parts[i]['base'], normal_step, distance_step, origin))
        for key, plane, triangles in groups:
            if not neighbors[i]:
                break
            x, y, z, distance = key
            for dx, dy, dz in nearby:
                offsets = by_normal.get((dx-x, dy-y, dz-z))
                if offsets is None:
                    continue
                possible = (entry for d in range(-distance-1, -distance+2) for entry in offsets.get(d, ()))
                for j, other, other_triangles in possible:
                    if j not in neighbors[i] or np.linalg.norm(plane[:3] + other[:3]) > normal_step:
                        continue
                    comparisons += 1
                    if comparisons > MAX_CONTACT_COMPARISONS:
                        raise ValueError('Zu viele mögliche Farbkontaktflächen. „Verbinder zwischen Farbgruppen“ ausschalten oder das Modell vereinfachen.')
                    # The bounds/keys are just a search index. Confirm coplanarity
                    # and intersect only the actual facing triangle polygons.
                    normal = other[:3]
                    local_offset = other[3]
                    if (np.max(np.abs(triangles @ normal - local_offset)) > epsilon or
                            np.max(np.abs(other_triangles @ normal - local_offset)) > epsilon):
                        continue
                    rotation = frame(normal)
                    left = md.CrossSection(list(other_triangles @ rotation[:2].T))
                    right = md.CrossSection(list(triangles[:, ::-1] @ rotation[:2].T))
                    region = left ^ right
                    if region.area() <= min_area:
                        continue
                    # Merge matching groups across a quantization boundary so
                    # the configured connector count still applies per face.
                    offset = float(local_offset + normal @ origin)
                    face = {'normal': normal.tolist(), 'offset': offset, 'colorBoundary': True}
                    region = region.translate(tuple(rotation[:2] @ origin))
                    matches = contacts.setdefault((j, i), [])
                    for index, (previous, basis, details) in enumerate(matches):
                        if np.linalg.norm(normal - basis[2]) <= normal_step and abs(offset - details['offset']) <= epsilon:
                            projected = region.transform(np.column_stack((basis[:2] @ rotation[:2].T, offset * (basis[:2] @ normal))))
                            matches[index] = (previous + projected, basis, details)
                            break
                    else:
                        matches.append((region, rotation, face))
        for key, plane, triangles in groups:
            by_normal[key[:3]][key[3]].append((i, plane, triangles))
    for (a, b), faces in sorted(contacts.items()):
        for region, rotation, face in faces:
            yield a, b, 2, face['offset'], region, rotation, face
