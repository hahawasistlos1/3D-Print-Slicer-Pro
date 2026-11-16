"""Additional, independently oriented cuts in model coordinates."""
import hashlib
import numpy as np
import manifold3d as md
from components import material_components


def part_key(shape, lineage):
    signature = [round(v, 6) + 0.0 for v in (*shape.bounding_box(), shape.volume())]
    return f'{lineage}-' + hashlib.sha256(repr(signature).encode()).hexdigest()[:16]


def frame(normal):
    """Right-handed orthonormal rows, with the plane normal along local Z."""
    reference = np.eye(3)[int(np.argmin(np.abs(normal)))]
    u = np.cross(reference, normal)
    u /= np.linalg.norm(u)
    return np.stack((u, np.cross(normal, u), normal))


def transform(shape, rotation):
    return shape.transform(np.column_stack((rotation, np.zeros(3))))


def vector(value):
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError('Schnittebene erfordert drei endliche Koordinaten.') from error
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError('Schnittebene erfordert drei endliche Koordinaten.')
    return result


def merge_parts(parts, keys, index, fits):
    if not isinstance(keys, list) or len(keys) < 2 or any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
        raise ValueError('Zum Zusammenfügen mindestens zwei verschiedene Teile wählen.')
    members = [part for part in parts if part['key'] in keys]
    if len(members) != len(keys):
        raise ValueError(f'Bearbeitung {index}: Zielteile zum Zusammenfügen sind nach einer Planänderung nicht mehr vorhanden.')
    first = members[0]
    if any(part.get('color') != first.get('color') for part in members):
        raise ValueError('Teile unterschiedlicher Farben können im Farbmodus nicht zusammengefügt werden.')
    bodies = [part['base'] for part in members]
    union = md.Manifold.batch_boolean(bodies, md.OpType.Add)
    volume = sum(body.volume() for body in bodies)
    if union.status() != md.Error.NoError or union.is_empty() or abs(union.volume()-volume) > max(1e-5, volume*1e-7) or len(material_components(union)) != 1:
        raise ValueError('Die gewählten Teile bilden keinen zusammenhängenden Volumenkörper.')
    if not fits(union):
        raise ValueError('Das zusammengefügte Teil überschreitet den nutzbaren Druckraum.')
    faces = []
    for part in members:
        for face in part['cutFaces']:
            if face not in faces:
                faces.append(face)
    signature = hashlib.sha256('|'.join(sorted(keys)).encode()).hexdigest()[:16]
    merged = {**first, 'solid': union, 'base': union, 'key': f'm{index}-{signature}',
              'cutFaces': faces, 'planeSides': {}, 'merged': True}
    return [merged if part is first else part for part in parts if part is first or part['key'] not in keys]


def apply_edits(parts, settings, max_parts, fits, progress):
    raw = settings.get('edits', [])
    if not isinstance(raw, list) or len(raw) > 64:
        raise ValueError('Bis zu 64 zusätzliche Schnittebenen sind zulässig.')
    planes = {}
    for index, definition in enumerate(raw):
        if not isinstance(definition, dict):
            raise ValueError('Ungültige Schnittebene.')
        if definition.get('merge') is not None:
            parts = merge_parts(parts, definition['merge'], index + 1, fits)
            continue
        normal = vector(definition.get('normal'))
        magnitude = np.linalg.norm(normal)
        if not np.isfinite(magnitude) or magnitude < 1e-9:
            raise ValueError('Die Schnittebene benötigt eine Richtung ungleich Null.')
        normal /= magnitude
        offset = float(vector(definition.get('point')) @ normal)
        if not np.isfinite(offset):
            raise ValueError('Ungültige Position der Schnittebene.')
        target = definition.get('target')
        if target is not None and (not isinstance(target, str) or not target):
            raise ValueError('Ungültiges Zielteil für die Schnittebene.')
        face = {'normal': normal.tolist(), 'offset': offset, 'plane': index + 1}
        next_parts = []
        matched = False
        for part in parts:
            if target is not None and target != part['key']:
                next_parts.append(part)
                continue
            high, low = part['base'].split_by_plane(normal, offset)
            if min(high.volume(), low.volume()) <= 1e-7:
                next_parts.append(part)
                continue
            matched = True
            for sign, side in ((-1, low), (1, high)):
                components = sorted(material_components(side), key=lambda body: tuple(body.bounding_box()))
                for child_index, component in enumerate(components):
                    if component.volume() <= 1e-7:
                        continue
                    next_parts.append({
                        **part, 'solid': component, 'base': component,
                        'key': part_key(component, f"{part['key']}/{index + 1}.{sign}.{child_index + 1}"),
                        'planeSides': {**part['planeSides'], index: sign},
                        'cutFaces': part['cutFaces'] + [face],
                        'neighbors': [], 'connectedNeighbors': [], 'connectors': [],
                    })
        if not matched:
            raise ValueError(f'Ebene {index + 1} trennt keinen Volumenkörper im gewählten Bereich. Position und Zielteil prüfen.')
        if len(next_parts) > max_parts:
            raise ValueError(f'Mehr als {max_parts} Teile durch zusätzliche Schnittebenen.')
        parts = next_parts
        planes[index] = (face, frame(normal))
        progress(36, f'Manuelle Geometriebearbeitung {index + 1}/{len(raw)}')
    return parts, planes


def oblique_interfaces(parts, planes, epsilon, min_area):
    for index, (face, rotation) in planes.items():
        offset = face['offset']
        sides = {-1: [], 1: []}
        for i, part in enumerate(parts):
            if part.get('merged'):
                if face not in part['cutFaces']:
                    continue
                for sign in (-1, 1):
                    region = cap_section(part['base'], rotation, offset, sign, epsilon)
                    if region.area() > min_area:
                        sides[sign].append((i, region))
                continue
            sign = part['planeSides'].get(index)
            if sign is None:
                continue
            region = transform(part['base'], rotation).slice(offset + sign * epsilon)
            if region.area() > min_area:
                sides[sign].append((i, region))
        for low, a in sides[-1]:
            for high, b in sides[1]:
                if low == high:
                    continue
                region = a ^ b
                if region.area() > min_area:
                    yield low, high, 2, offset, region, rotation, face


def cap_section(body, rotation, offset, side, epsilon):
    """Actual outward cap polygons, including holes, in the plane frame."""
    mesh = body.to_mesh64()
    triangles = np.asarray(mesh.vert_properties)[:, :3][np.asarray(mesh.tri_verts)] @ rotation.T
    flat = triangles[np.all(abs(triangles[:, :, 2]-offset) <= epsilon, axis=1), :, :2]
    u, v = flat[:, 1]-flat[:, 0], flat[:, 2]-flat[:, 0]
    signed_area = u[:, 0]*v[:, 1]-u[:, 1]*v[:, 0]
    outward = flat[signed_area * side < 0]
    if side > 0:
        outward = outward[:, ::-1]
    return md.CrossSection(list(outward))


def merged_axis_interfaces(parts, cuts, epsilon, min_area):
    for axis, offsets in enumerate(cuts):
        rotation = np.eye(3)[[(axis+1)%3, (axis+2)%3, axis]]
        for offset in offsets:
            regions = {-1: [], 1: []}
            for i, part in enumerate(parts):
                if not any(face.get('axis') == axis and abs(face['offset']-offset) <= epsilon for face in part['cutFaces']):
                    continue
                for sign in (-1, 1):
                    region = cap_section(part['base'], rotation, offset, sign, epsilon)
                    if region.area() > min_area:
                        regions[sign].append((i, region))
            for low, a in regions[-1]:
                for high, b in regions[1]:
                    if low == high or not (parts[low].get('merged') or parts[high].get('merged')):
                        continue
                    region = a ^ b
                    if region.area() > min_area:
                        yield low, high, axis, offset, region, None, {}
