"""Offline geometry kernel. All coordinates are mm; meshes are real closed solids.

Manifold (Apache-2.0) performs all Boolean operations, never triangle clipping
without caps. Invalid input is rejected rather than silently approximated.
"""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import numpy as np
import manifold3d as md
import trimesh
from planning import adaptive_partition, common_interface, envelope_radius, face_candidates, section_body
from components import material_components
from color_contacts import contact_interfaces
from motion import analyze_assembly
from manual_planes import apply_edits, merged_axis_interfaces, oblique_interfaces, part_key, transform
from dovetail import dovetail_candidates, make_dovetail
from placements import interface_surface, selected_positions, trials, SURFACE_VERTEX_BUDGET
from print_checks import print_checks, wall_sample_budgets
from special_connectors import make_clip, make_screw, sample_screw_insertion, SCREW_SAMPLE_BUDGET
from three_mf import combine_meshes, read_meshes, read_3mf as read_3mf_geometry
from mesh_repair import ExtendedPlanarRepairAvailable, repair_surface, stitch_boundary
from indexed_mesh import indexed_path, read_indexed, write_indexed

MAX_TRIANGLES = 4_000_000
MAX_PARTS = 512


def mesh_of(solid):
    mesh = solid.to_mesh64()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)


def native_mesh(mesh):
    return md.Mesh64(np.ascontiguousarray(mesh.vertices,dtype=np.float64),
                     np.ascontiguousarray(mesh.faces,dtype=np.uint64))


def weld_exact_vertices(mesh):
    """Join STL facet vertices only when all stored coordinates match."""
    points,indices=np.unique(mesh.vertices,axis=0,return_inverse=True)
    return trimesh.Trimesh(points,indices[mesh.faces],process=False)


def solid_of(mesh, *, preserve_indices=False, repair_report=None, extended_repair=False, repair_neighbors=None):
    mesh = mesh.copy()
    if not (preserve_indices and mesh.is_watertight and mesh.is_winding_consistent):
        mesh.merge_vertices(digits_vertex=7)
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("Das Modell enthält ungültige Koordinaten.")
    if repair_report is not None and (not mesh.is_watertight or not mesh.is_winding_consistent):
        if not mesh.is_watertight and mesh.is_winding_consistent and len(mesh.faces):
            # Round-off seams need no invented surface if existing boundary
            # edges can be paired within numerical tolerance.
            if (candidate := stitch_boundary(mesh)) is not None:
                if candidate.volume<0:
                    candidate.invert()
                repaired = md.Manifold(native_mesh(candidate))
                if repaired.status()==md.Error.NoError and not repaired.is_empty() and repaired.volume()>0:
                    repair_report['seamsJoined'] = repair_report.get('seamsJoined',0)+1
                    return repaired
        changes = repair_surface(mesh,extended=extended_repair,other_meshes=repair_neighbors)
        if len(mesh.faces)>MAX_TRIANGLES:
            raise ValueError('Die Netzreparatur würde die Dreiecksgrenze überschreiten.')
        for key,count in changes.items():
            if count:
                repair_report[key] = repair_report.get(key,0)+count
    if not mesh.is_watertight:
        raise ValueError("Das Netz ist offen oder nicht mannigfaltig. Bitte zuerst im CAD-/Reparaturprogramm schließen.")
    if not mesh.is_winding_consistent:
        raise ValueError("Uneinheitliche Flächennormalen. Bitte das Modell vor dem Import reparieren.")
    if mesh.volume < 0:
        mesh.invert()
    solid = md.Manifold(native_mesh(mesh))
    if solid.status() != md.Error.NoError or solid.is_empty() or solid.volume() <= 0:
        raise ValueError(f"Kein gültiger geschlossener Volumenkörper: {solid.status()}")
    return solid


def read_3mf(path):
    return read_3mf_geometry(path, MAX_TRIANGLES)


def load_model(path, scale=1, normalize=True, *, repair_report=None, use_indexed=False, color_source=None,
               extended_repair=False):
    path = Path(path)
    if path.stat().st_size > 500_000_000:
        raise ValueError("Datei über 500 MB. Bitte zunächst die Dreieckszahl reduzieren.")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Der Skalierungsfaktor muss positiv sein.")
    if use_indexed and indexed_path(path).is_file():
        solid=read_indexed(indexed_path(path),MAX_TRIANGLES)
        if scale!=1:
            solid=solid.scale((scale,scale,scale))
        return solid.translate(-np.asarray(solid.bounding_box()[:3])) if normalize else solid
    if path.suffix.lower() == '.3mf':
        colors = [] if color_source is not None else None
        meshes, multipart = read_meshes(path, MAX_TRIANGLES,color_data=colors)
        if color_source is not None:
            color_source.update(meshes=meshes,colors=colors)
        has_color = colors is not None and any(group and any(c is not None for c in group) for group in colors)
        if multipart or (has_color and len(meshes)>1):
            # Preserve independent closed components before fusing touching
            # or overlapping bodies. A global vertex weld loses that topology.
            solids = []
            for index,(vertices,faces) in enumerate(meshes,1):
                def neighbors():
                    return ((v,f,scale) for other,(v,f) in enumerate(meshes,1) if other!=index)
                try:
                    solids.append(solid_of(trimesh.Trimesh(vertices*scale,faces,process=False),
                                           preserve_indices=True,repair_report=repair_report,
                                           extended_repair=extended_repair,repair_neighbors=neighbors))
                except ExtendedPlanarRepairAvailable as error:
                    raise ExtendedPlanarRepairAvailable(f'3MF-Netz {index}/{len(meshes)}: {error}') from error
                except ValueError as error:
                    raise ValueError(f'3MF-Netz {index}/{len(meshes)}: {error}') from error
            solid = md.Manifold.batch_boolean(solids, md.OpType.Add)
            if solid.status()!=md.Error.NoError or solid.is_empty() or solid.volume()<=0:
                raise ValueError('3MF-Komponenten ergeben zusammen keinen gültigen Volumenkörper.')
            if solid.num_tri()>MAX_TRIANGLES:
                raise ValueError(f'Zusammengefügtes 3MF hat {solid.num_tri():,} Dreiecke (Grenze: {MAX_TRIANGLES:,}). '
                                 'Das Modell in getrennte Dateien aufteilen oder das Quellnetz vereinfachen.')
            lo = np.asarray(solid.bounding_box()[:3])
            if color_source is not None:
                color_source['origin']=lo
            return solid.translate(-lo) if normalize else solid
        mesh = combine_meshes(meshes)
    elif path.suffix.lower() == '.stl':
        raw = trimesh.load(path, force='mesh', process=False, skip_materials=True)
        if len(raw.faces) > MAX_TRIANGLES:
            raise ValueError(f"Mehr als {MAX_TRIANGLES:,} Dreiecke. Bitte vor dem Import vereinfachen.")
        mesh = weld_exact_vertices(raw)
        if mesh.is_watertight and mesh.is_winding_consistent:
            mesh.apply_scale(scale)
            try:
                solid = solid_of(mesh,preserve_indices=True)
            except ValueError:
                pass
            else:
                lo = np.asarray(solid.bounding_box()[:3])
                return solid.translate(-lo) if normalize else solid
        mesh = raw.process() if repair_report is None else raw
    elif path.suffix.lower() == '.obj':
        # Explicitly disable materials. OBJ imports must never access MTL/texture URLs.
        mesh = trimesh.load(path, force='mesh', process=repair_report is None, skip_materials=True)
    else:
        raise ValueError("Unterstützt werden STL, OBJ und 3MF.")
    if len(mesh.faces) > MAX_TRIANGLES:
        raise ValueError(f"Mehr als {MAX_TRIANGLES:,} Dreiecke. Bitte vor dem Import vereinfachen.")
    mesh.apply_scale(scale)
    solid = solid_of(mesh,preserve_indices=repair_report is not None,repair_report=repair_report,
                     extended_repair=extended_repair)
    lo = np.array(solid.bounding_box()[:3])
    if color_source is not None and path.suffix.lower()=='.3mf':
        color_source['origin']=lo
    return solid.translate(-lo) if normalize else solid


def mesh_for_export(solid, origin=False, order=None):
    if solid.is_empty() or solid.status()!=md.Error.NoError or solid.volume()<=0:
        raise ValueError('Leere oder ungültige Geometrie kann nicht exportiert werden.')
    mesh = mesh_of(solid)
    if order is not None:
        if len(order)!=3 or any(not isinstance(v,(int,np.integer)) or isinstance(v,bool) for v in order) or sorted(order)!=[0,1,2]:
            raise ValueError('Druckausrichtung muss jede XYZ-Achse genau einmal enthalten.')
        # Even/odd permutation must preserve the mesh orientation.
        mesh.vertices = mesh.vertices[:, order]
        if np.linalg.det(np.eye(3)[list(order)]) < 0:
            mesh.faces = mesh.faces[:, ::-1]
    if origin:
        mesh.vertices = mesh.vertices-mesh.vertices.min(axis=0)
    return mesh


def write_stl(solid, path, origin=False, order=None, *, indexed=False):
    mesh=mesh_for_export(solid,origin,order)
    Path(path).write_bytes(trimesh.exchange.stl.export_stl(mesh))
    if indexed:
        if origin or order is not None:
            raise ValueError('Indizierte interne Netze verwenden Montagekoordinaten.')
        write_indexed(solid,indexed_path(path))


def info(solid):
    b = np.array(solid.bounding_box())
    mesh = mesh_of(solid)
    return {'dimensions': (b[3:] - b[:3]).tolist(), 'bounds': b.tolist(),
            'triangles': solid.num_tri(), 'volume': solid.volume(),
            'watertight': bool(mesh.is_watertight), 'normalsConsistent': bool(mesh.is_winding_consistent),
            'components': len(material_components(solid))}


def cylinder(axis, center, radius, depth):
    shape = md.Manifold.cylinder(2 * depth, radius, circular_segments=32, center=True)
    if axis == 0:
        shape = shape.rotate((0, 90, 0))
    elif axis == 1:
        shape = shape.rotate((90, 0, 0))
    return shape.translate(center)


def connector(axis, center, radius, depth, kind='round', length=None, tangent_axis=None):
    if kind == 'round':
        return cylinder(axis, center, radius, depth)
    size = [2 * radius, 2 * radius, 2 * radius]
    size[axis] = 2 * depth
    if kind == 'tongue' or (kind == 'rect' and length is not None):
        if tangent_axis not in range(3) or tangent_axis == axis or length is None or length <= 0:
            raise ValueError('Ungültige Ausrichtung oder Länge der Feder.')
        size[tangent_axis] = length
    return md.Manifold.cube(size, center=True).translate(center)


def connector_candidates(region, axis, offset, settings):
    if settings.get('kind') == 'dovetail':
        yield from dovetail_candidates(region, axis, offset, settings, face_candidates)
        return
    length = connector_face_length(settings)
    if length is None:
        for center in face_candidates(region,axis,offset,envelope_radius(settings),limit=48 if settings.get('kind')=='screw' else 320):
            yield center,None
        return
    tangents=[(axis+1)%3,(axis+2)%3]
    reserve=settings['tolerance']/2+settings['wall']
    for tangent in tangents:
        half=[settings['diameter']/2+reserve]*2
        half[tangents.index(tangent)]=length/2+reserve
        for center in face_candidates(region,axis,offset,0,half_extents=half):
            yield center,tangent


def connector_face_length(settings):
    if settings.get('kind') in ('tongue','dovetail'):
        return settings['tongueLength']
    if settings.get('kind') == 'rect' and settings.get('rectHeight', 0) > 0:
        return settings['rectHeight']
    if settings.get('kind') == 'clip':
        return settings['diameter']*.60
    return None



def connector_sizes(settings):
    requested=(settings['diameter'],settings['depth'])
    if not settings.get('autoSize',False):return [requested]
    minimum=settings['minDiameter']
    diameters=sorted(set([requested[0],minimum]+[max(minimum,round(requested[0]*r,4)) for r in (.75,.5,.35)]),reverse=True)
    return [(d,max(settings['minDepth'],min(requested[1],requested[1]*d/requested[0]))) for d in diameters]


def connector_wall_probe(axis, center, tangent, length, settings):
    radius=settings['diameter']/2+settings['tolerance']/2+settings['wall']
    depth=settings['depth']+settings['tolerance']+settings['wall']
    span=None if length is None else length+settings['tolerance']+2*settings['wall']
    return connector(axis,center,radius,depth,settings.get('kind','round'),span,tangent)


def planning_connector_probe(shape, axis, offset, limit, settings):
    """Check candidate wall envelopes before choosing a cut."""
    region=section_body(shape,axis).slice(float(offset))
    sizes=connector_sizes(settings)
    trials_per_size=max(1,limit//len(sizes))
    checked=0
    for diameter,depth in sizes:
        sized=dict(settings,diameter=diameter,depth=depth,rectHeight=settings['rectHeight']*diameter/settings['diameter'])
        length=connector_face_length(sized)
        candidates=connector_candidates(region,axis,offset,sized)
        for center,tangent in itertools.islice(candidates,trials_per_size):
            probe=connector_wall_probe(axis,center,tangent,length,sized)
            checked+=1
            outside=probe-shape
            if outside.status()==md.Error.NoError and outside.volume()<=max(1e-6,probe.volume()*1e-7):
                return True,checked
            if checked>=limit:
                return False,checked
    return False,checked


def fit_order(solid, usable):
    if solid.is_empty() or solid.status()!=md.Error.NoError:return None
    box = np.asarray(solid.bounding_box())
    if not np.isfinite(box).all():return None
    dims = box[3:] - box[:3]
    options = [p for p in itertools.permutations(range(3)) if np.all(dims[list(p)] <= np.array(usable) + 1e-5)]
    return min(options, key=lambda p: dims[p[2]]) if options else None


def validate_settings(s):
    for key, default in [('bedX',220),('bedY',220),('bedZ',250),('margin',.2),('diameter',10),('depth',15),('tolerance',.2),('wall',2),('target',220),('minDiameter',3),('minDepth',3),('tongueLength',40),('rectHeight',0)]:
        s[key] = float(s.get(key, default))
        if not math.isfinite(s[key]):
            raise ValueError(f"Ungültiger Zahlenwert: {key}")
    if min(s['bedX'], s['bedY'], s['bedZ']) <= 0 or s['margin'] < 0:
        raise ValueError("Druckraum muss positiv sein, Sicherheitsabstand mindestens 0.")
    if min(s['diameter'], s['depth'], s['wall'], s['target']) <= 0 or not 0 <= s['tolerance'] <= 2:
        raise ValueError("Verbinderabmessungen/Wandstärke müssen positiv sein; Toleranz 0 bis 2 mm.")
    if min(s['minDiameter'],s['minDepth'])<=0:
        raise ValueError('Mindestmaße der Verbinder müssen positiv sein.')
    if s.get('autoSize',False) and (s['minDiameter']>s['diameter'] or s['minDepth']>s['depth']):
        raise ValueError('Automatische Mindestmaße dürfen die gewählten Verbindermaße nicht überschreiten.')
    s['count'] = int(s.get('count', 2))
    if not 1 <= s['count'] <= 8:
        raise ValueError("Pro Schnittfläche sind 1 bis 8 Verbinder zulässig.")
    s['thinWallThreshold'] = float(s.get('thinWallThreshold',1))
    if not math.isfinite(s['thinWallThreshold']) or not 0 <= s['thinWallThreshold'] <= 50:
        raise ValueError('Dünnwandschwelle muss zwischen 0 und 50 mm liegen.')
    if not isinstance(s.get('detailedWallCheck',False),bool):
        raise ValueError('Ungültige Einstellung für die ausführliche Dünnwandprüfung.')
    if s.get('kind', 'round') not in ('round', 'rect', 'tongue', 'dovetail', 'clip', 'screw'):
        raise ValueError("Dieser Verbindertyp ist noch nicht freigegeben.")
    if s['tongueLength'] <= 0 or (s.get('kind') in ('tongue','dovetail') and s['tongueLength'] < s['diameter']):
        raise ValueError('Die Länge muss positiv und mindestens so groß wie die Verbinderbreite sein.')
    if s['rectHeight'] < 0:
        raise ValueError('Zapfenhöhe muss positiv sein oder 0 für einen quadratischen Zapfen.')
    for key,default in (('clipStrainPercent',3),('threadPitch',2),('threadLength',12)):
        s[key]=float(s.get(key,default))
        if not math.isfinite(s[key]) or s[key]<=0:
            raise ValueError(f'Positiver Zahlenwert erforderlich: {key}')
    if s.get('kind')=='screw' and s.get('mode','separate') not in ('separate','none'):
        raise ValueError('Außenschrauben werden separat gedruckt.')
    if s.get('kind')=='screw' and not (2<=s['threadLength']/s['threadPitch']<=20 and s['threadPitch']*.4<s['diameter']*.325 and s['tolerance']<s['threadPitch']*.4):
        raise ValueError('Gewinde benötigt 2 bis 20 Gänge und ausreichend Durchmesser und Flankenhöhe für das Spiel.')
    if s.get('mode', 'separate') not in ('separate', 'integrated', 'mixed', 'none'):
        raise ValueError("Unbekannte Verbinder-Variante.")
    if s.get('strategy', 'equal') not in ('equal','few','custom','adaptive','color'):
        raise ValueError('Unbekannte Schnittstrategie.')
    if not isinstance(s.get('connectAcrossColors',False),bool):
        raise ValueError('Ungültige Einstellung für Verbinder zwischen Farbgruppen.')
    usable = np.array([s['bedX'],s['bedY'],s['bedZ']]) - 2 * s['margin']
    if usable.min() <= 1:
        raise ValueError("Sicherheitsabstand lässt keinen nutzbaren Druckraum übrig.")
    return usable


def plan(solid, s, usable):
    dims = np.array(info(solid)['dimensions'])
    reserve = s['depth'] if s.get('mode') in ('integrated','mixed') else 0
    options = list(itertools.permutations(range(3))) if s.get('optimize',True) else [(0,1,2)]
    def dimensions(p):
        d = usable[list(p)] - reserve
        if s.get('strategy','equal') == 'custom':
            d = np.minimum(d, s['target'])
        return d
    options = [p for p in options if dimensions(p).min() > 1]
    if not options:
        raise ValueError("Einstecktiefe ist zu groß für diesen Druckraum.")
    perm = min(options, key=lambda p: math.prod(np.ceil(dims / dimensions(p))))
    cell = dimensions(perm)
    raw_counts=np.maximum(1,np.ceil(dims/cell))
    if not np.isfinite(raw_counts).all() or math.prod(float(v) for v in raw_counts)>MAX_PARTS:
        raise ValueError(f'Mehr als {MAX_PARTS} Rasterzellen. Größeren Druckraum/Teilmaß wählen.')
    counts = np.maximum(1, np.ceil(dims / cell).astype(int))
    cuts = []
    for axis in range(3):
        if s.get('strategy') == 'few':
            values = [float(cell[axis]*i) for i in range(1, int(counts[axis]))]
        else:
            values = [float(dims[axis]*i/counts[axis]) for i in range(1,int(counts[axis]))]
        manual = s.get('cuts', {}).get('xyz'[axis])
        if manual is not None:
            values = sorted(set(float(v) for v in manual))
            if any(not math.isfinite(v) or v <= 0 or v >= dims[axis] for v in values):
                raise ValueError("Manuelle Schnitte müssen innerhalb des Modells liegen.")
        limits = [0] + values + [float(dims[axis])]
        if max(np.diff(limits)) > cell[axis] + 1e-6:
            raise ValueError(f"Die manuellen Schnitte auf {'XYZ'[axis]} erzeugen zu große Teile.")
        cuts.append(values)
    if math.prod(len(c)+1 for c in cuts) > MAX_PARTS:
        raise ValueError(f"Mehr als {MAX_PARTS} Rasterzellen. Größeren Druckraum/Teilmaß wählen.")
    return cuts


def slice_model(solid, settings, folder, progress=lambda p,m: None, *, indexed=False, color_bodies=None):
    s = dict(settings)
    usable = validate_settings(s)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    parts = []
    score_probe=None
    if s.get('mode','separate')!='none' and s.get('kind','round') in ('round','rect','tongue'):
        score_probe=lambda shape,axis,offset,limit: planning_connector_probe(shape,axis,offset,limit,s)
    progress(5, 'Schnittplan aus tatsächlicher Geometrie ermitteln …')
    if s.get('strategy') == 'color':
        if not color_bodies:
            raise ValueError('Für „Nach Farbe trennen“ ein 3MF mit mindestens zwei geschlossenen Farbgruppen laden.')
        cuts = [[],[],[]]
        planning = {'algorithm':'color-adaptive-v1','evaluatedPlanes':0,'localCuts':[],'budgetReached':False,
                    'connectorProbeChecks':0,'connectorProbeCuts':0,'connectorProbeBudgetReached':False}
        if s.get('cuts'):
            raise ValueError('Nach Farbe trennen unterstützt freie Schnittebenen. Bitte zuvor die Raster-Schnitte löschen.')
        for color,body in color_bodies:
            capacity = MAX_PARTS - len(parts)
            if capacity <= 0:
                raise ValueError(f'Mehr als {MAX_PARTS} Druckteile nach Farbtrennung.')
            leaves,color_cuts,detail = adaptive_partition(body,s,usable,capacity,progress,
                probe=score_probe,probe_used=planning['connectorProbeChecks'])
            planning['evaluatedPlanes'] += detail['evaluatedPlanes']
            planning['localCuts'].extend(detail['localCuts'])
            planning['budgetReached'] |= detail['budgetReached']
            for key in ('connectorProbeChecks','connectorProbeCuts'):
                planning[key] += detail[key]
            planning['connectorProbeBudgetReached'] |= detail['connectorProbeBudgetReached']
            for axis in range(3):
                cuts[axis] = sorted(set(cuts[axis]+color_cuts[axis]))
            for shape,faces in leaves:
                parts.append({'solid':shape,'base':shape,'color':color,'cell':(),
                              'neighbors':[],'connectedNeighbors':[],'connectors':[],'cutFaces':faces})
        for part in parts:
            box=np.asarray(part['base'].bounding_box())
            part['cell']=tuple(int(np.searchsorted(cuts[a],(box[a]+box[a+3])/2)) for a in range(3))
    elif s.get('strategy') == 'adaptive':
        leaves,cuts,planning = adaptive_partition(solid,s,usable,MAX_PARTS,progress,probe=score_probe)
        for shape,faces in leaves:
            box=np.asarray(shape.bounding_box())
            cell=tuple(int(np.searchsorted(cuts[a],(box[a]+box[a+3])/2)) for a in range(3))
            parts.append({'solid':shape,'base':shape,'cell':cell,'neighbors':[], 'connectedNeighbors':[], 'connectors':[],'cutFaces':faces})
    else:
        cuts = plan(solid, s, usable)
        planning={'algorithm':'grid-axis-v1','evaluatedPlanes':0,'localCuts':[], 'budgetReached':False}
        nodes = [(solid, (0,0,0))]
        progress(8, "Geschlossene Volumenkörper schneiden …")
        for axis, values in enumerate(cuts):
            n = [0,0,0]; n[axis] = 1
            out = []
            for shape, cell in nodes:
                remainder = shape
                for i, v in enumerate(values):
                    high, low = remainder.split_by_plane(n, v)
                    if not low.is_empty() and low.volume() > 1e-7:
                        c = list(cell); c[axis] = i; out.append((low, tuple(c)))
                    remainder = high
                if not remainder.is_empty() and remainder.volume() > 1e-7:
                    c = list(cell); c[axis] = len(values); out.append((remainder, tuple(c)))
            nodes = out
            progress(15 + axis*10, f"Schnittachse {'XYZ'[axis]} abgeschlossen")
        for shape, cell in nodes:
            for component in material_components(shape):
                if component.volume() > 1e-7:
                    box=np.asarray(component.bounding_box())
                    faces=[{'axis':a,'offset':v} for a in range(3) for v in cuts[a]
                           if abs(box[a]-v)<1e-5 or abs(box[a+3]-v)<1e-5]
                    parts.append({'solid':component, 'base':component, 'cell':cell, 'neighbors':[], 'connectedNeighbors':[], 'connectors':[],'cutFaces':faces})
    model_size=max(info(solid)['dimensions'])
    epsilon=max(1e-7,model_size*1e-8)
    for i, part in enumerate(parts):
        part['key'] = part_key(part['base'], i+1)
        part['planeSides'] = {}
    parts, planes = apply_edits(parts, s, MAX_PARTS, lambda shape: fit_order(shape, usable) is not None, progress)
    if planes:
        planning['manualPlanes'] = [face for face, _ in planes.values()]
    if len(parts) > MAX_PARTS:
        raise ValueError("Zu viele zusammenhanglose Einzelteile.")
    if not parts:
        raise ValueError("Keine druckbaren Volumenkörper nach dem Schnitt. Modellmaß/Genauigkeit prüfen.")
    # Verify conservation before adding pins/holes.
    before = sum(p['solid'].volume() for p in parts)
    if abs(before-solid.volume()) > max(1e-4, solid.volume()*1e-7):
        raise ValueError("Volumenprüfung nach der Teilung fehlgeschlagen.")
    joints, separate, probes, warnings, interfaces = [], [], [], [], []
    if planning['budgetReached']:
        warnings.append('Bewertungsbudget der adaptiven Planung erreicht. Weitere Schnitte wurden geometrisch geprüft, aber ohne Querschnittbewertung gewählt.')
    if planning.get('connectorProbeBudgetReached'):
        warnings.append('Budget für Verbinderproben bei der Schnittplanung erreicht. Verbinder werden in der anschließenden Platzierung weiterhin geprüft.')
    color_strategy = s.get('strategy') == 'color'
    across_colors = color_strategy and s.get('connectAcrossColors',False)
    if color_strategy and not across_colors and s.get('mode','separate')!='none':
        warnings.append('Verbinder zwischen Farbgruppen sind ausgeschaltet.')
    candidates = []
    min_area = max(1e-8,model_size*model_size*1e-12)
    boxes=[np.asarray(p['base'].bounding_box()) for p in parts]
    for ia in range(len(parts)):
        for ib in range(ia+1,len(parts)):
            if parts[ia].get('merged') or parts[ib].get('merged'):
                continue
            if parts[ia].get('color') != parts[ib].get('color'):
                continue
            ba,bb=boxes[ia],boxes[ib]
            for axis in range(3):
                if abs(ba[axis+3]-bb[axis])<=epsilon:
                    low,high=ia,ib;offset=float((ba[axis+3]+bb[axis])/2)
                elif abs(bb[axis+3]-ba[axis])<=epsilon:
                    low,high=ib,ia;offset=float((bb[axis+3]+ba[axis])/2)
                else: continue
                if not any(abs(offset-v)<=epsilon for v in cuts[axis]): continue
                tangents=[t for t in range(3) if t!=axis]
                if any(min(ba[t+3],bb[t+3])-max(ba[t],bb[t])<=epsilon for t in tangents):continue
                region=common_interface(parts[low]['base'],parts[high]['base'],axis,offset,epsilon)
                if region.area()<=min_area:continue
                candidates.append((low,high,axis,offset,region,None,{}))
    candidates.extend(oblique_interfaces(parts, planes, epsilon, min_area))
    if any(part.get('merged') for part in parts):
        candidates.extend(merged_axis_interfaces(parts, cuts, epsilon, min_area))
    if color_strategy:
        candidates=[c for c in candidates if parts[c[0]].get('color')==parts[c[1]].get('color')]
    if across_colors and s.get('mode','separate') != 'none':
        boundary_faces = list(contact_interfaces(parts,boxes,epsilon,min_area,progress))
        candidates.extend(boundary_faces)
        if not boundary_faces:
            warnings.append('Keine gemeinsamen ebenen Kontaktflächen zwischen Farbgruppen gefunden.')
    positions=selected_positions(s,candidates,parts) if s.get('mode','separate')!='none' else {}
    candidate_order=sorted(range(len(candidates)),key=lambda index:index not in positions)
    surface_budget=SURFACE_VERTEX_BUDGET
    for step,pair_idx in enumerate(candidate_order,1):
        ia,ib,axis,offset,region,rotation,face=candidates[pair_idx]
        progress(40 + int(42*step/max(1,len(candidates))), f"Verbinder prüfen · Schnittstelle {step}/{len(candidates)}")
        a,b = parts[ia],parts[ib]
        if ib+1 not in a['neighbors']:a['neighbors'].append(ib+1)
        if ia+1 not in b['neighbors']:b['neighbors'].append(ia+1)
        fixed_positions=positions.get(pair_idx)
        requested=len(fixed_positions) if fixed_positions else s['count'] if s.get('mode','separate')!='none' else 0
        interface={'id':f'S{pair_idx+1:03}','a':ia+1,'b':ib+1,'axis':axis,'offset':offset,**face,
                   'area':float(region.area()),'requested':requested,'placed':0,'connectors':[]}
        surface=interface_surface(region,axis,offset,rotation,surface_budget)
        if surface is not None:
            interface['surface']=surface
            surface_budget-=len(surface['vertices'])
        interfaces.append(interface)
        if s.get('mode','separate') == 'none':
            continue
        normal = np.eye(3)[axis] if rotation is None else rotation[2]
        def make_connector(center,radius,depth,kind,length,tangent):
            shape = connector(axis,center,radius,depth,kind,length,tangent)
            return shape if rotation is None else transform(shape,rotation.T)
        chosen = []
        kind=s.get('kind','round')
        placed_slots=set()
        # Explicit round-dowel locations keep the full wall envelope plus
        # 0.5 mm between envelopes. Automatic placement leaves 1 mm.
        spacing = .5 if fixed_positions and kind == 'round' else 1.
        for slot,sized,center,tangent,length in trials(s,axis,offset,region,fixed_positions,connector_sizes,connector_candidates,connector_face_length):
            if len(chosen)>=requested:break
            if fixed_positions and slot in placed_slots:continue
            diameter,depth=sized['diameter'],sized['depth']
            radius = sized['diameter']/2
            envelope_r = radius + s['tolerance']/2 + s['wall']
            if any(np.linalg.norm(center-c) < envelope_r+old_radius+spacing for c,old_radius in chosen):
                continue
            mode = s.get('mode','separate')
            if mode == 'mixed':
                mode = 'integrated' if len(joints)%2 == 0 else 'separate'
            travel=None
            extra={}
            if kind=='dovetail':
                rail=make_dovetail(a,b,axis,tangent,center,offset,rotation,sized,mode,transform)
                if rail is None:continue
                pin,socket_a,socket_b,reserves,travel=rail
                threshold=max(1e-6,sum(probe.volume() for probe in reserves)*1e-7)
            elif kind=='screw':
                support=min(float(np.where(normal>=0,box[:3],box[3:])@normal) for box in boxes)
                screw=make_screw(a,b,axis,center,offset,rotation,sized,support-offset-s['wall'])
                if screw is None:continue
                pin,socket_a,socket_b,reserves,extra=screw
                threshold=max(1e-6,pin.volume()*1e-7)
                access=reserves[-1]
                if any((access ^ part['solid']).volume()>threshold for i,part in enumerate(parts) if i!=ia):
                    continue
            else:
                if kind=='clip':
                    clip=make_clip(center,axis,tangent,rotation,sized)
                    if clip is None:continue
                    pin,socket_a,probe,extra=clip
                    socket_b=socket_a
                else:
                    probe = connector_wall_probe(axis,center,tangent,length,sized)
                    if rotation is not None:probe=transform(probe,rotation.T)
                    pin = make_connector(center,radius,sized['depth'],kind,length,tangent)
                    socket_a=socket_b=make_connector(center,radius+s['tolerance']/2,sized['depth']+s['tolerance'],kind,
                                                     None if length is None else length+s['tolerance'],tangent)
                if probe.is_empty() or probe.status()!=md.Error.NoError or probe.volume()<=0:continue
                pos,neg = probe.split_by_plane(normal,offset)
                threshold = max(1e-6, probe.volume()*1e-7)
                if (neg-a['base']).volume() > threshold or (pos-b['base']).volume() > threshold:
                    continue
                reserves=[probe]
            if any(shape.is_empty() or shape.status()!=md.Error.NoError for shape in (pin,socket_b) if shape is not None):
                continue
            if any((reserve ^ previous).volume() > threshold for reserve in reserves for previous in probes):
                continue
            if mode == 'separate' and fit_order(pin,usable) is None:continue
            if mode == 'integrated':
                changed_a = a['solid'] + pin
            else:
                changed_a = a['solid'] - socket_a
            changed_b = b['solid'] - socket_b
            if fit_order(changed_a,usable) is None or fit_order(changed_b,usable) is None:
                continue
            if len(material_components(changed_a)) != 1 or len(material_components(changed_b)) != 1:
                continue
            if (changed_a ^ changed_b).volume() > threshold:
                continue
            if mode == 'separate' and ((pin ^ changed_a).volume() > threshold or (pin ^ changed_b).volume() > threshold):
                continue
            a['solid'], b['solid'] = changed_a,changed_b
            jid = f"V{len(joints)+1:03}"
            model_center = center if rotation is None else rotation.T @ center
            joint = {'id':jid,'a':ia+1,'b':ib+1,'axis':axis,'center':model_center.tolist(),'mode':mode,
                     'diameter':sized['diameter'],'depth':sized['depth'],'tolerance':s['tolerance'],'kind':kind,'autoSized':diameter<s['diameter']-1e-6 or depth<s['depth']-1e-6}
            joint.update(extra)
            if length is not None:joint.update(length=length,tangentAxis=tangent)
            if rotation is not None:joint.update(normal=normal.tolist(),frame=rotation.tolist())
            if travel is not None:joint.update(removalDirection=(-travel).tolist(),pinWithdrawal=travel.tolist())
            if fixed_positions:joint['manualPosition']=True
            joints.append(joint)
            for p,neighbor in ((a,ib+1),(b,ia+1)):
                p['connectors'].append(jid)
                if neighbor not in p['connectedNeighbors']: p['connectedNeighbors'].append(neighbor)
            interface['connectors'].append(jid)
            interface['placed']+=1
            if mode == 'separate': separate.append((jid,pin))
            chosen.append((center,envelope_r)); probes.extend(reserves)
            placed_slots.add(slot)
        if len(chosen) < requested:
            reason={'dovetail':'Keine weitere seitlich offene Nut mit durchgehender Wandreserve gefunden.',
                    'clip':'Keine weitere Position mit Wandreserve und passender berechneter Armdehnung gefunden.',
                    'screw':'Keine weitere Position mit freiem Außenzugang und ausreichender Wandreserve gefunden.'}.get(kind,'Keine weitere Position mit Wandreserve gefunden.')
            if fixed_positions:
                missing=', '.join(str(i+1) for i in range(requested) if i not in placed_slots)
                raise ValueError(f"{interface['id']}: Manuelle Position(en) {missing} passen nicht zur Geometrie oder kollidieren. {reason}")
            warnings.append(f"Teil {ia+1:03} ↔ {ib+1:03}: {len(chosen)}/{requested} Verbinder. {reason}")
    interfaces.sort(key=lambda f:int(f['id'][1:]))
    progress(85, "Druckraum, Netze und Exportgeometrie prüfen …")
    records=[]
    wall_bodies = [p['solid'] for p in parts] + [pin for _,pin in separate]
    wall_budgets = wall_sample_budgets(wall_bodies,s.get('detailedWallCheck',False))
    if (s.get('detailedWallCheck',False) and s['thinWallThreshold'] > 0 and
            any(budget < body.num_tri() for budget,body in zip(wall_budgets,wall_bodies))):
        warnings.append('Ausführliche Dünnwandprüfung: Stichproben auf insgesamt 200.000 Dreiecke begrenzt.')
    for i,p in enumerate(parts,1):
        shape=p['solid']; data=info(shape); order=fit_order(shape,usable)
        errors=[]
        if not data['watertight'] or not data['normalsConsistent'] or shape.status()!=md.Error.NoError: errors.append('Ungültiges Netz')
        if order is None: errors.append('Druckraum überschritten')
        if len(parts)>1 and not p['connectors'] and s.get('mode')!='none': warnings.append(f"Teil {i:03}: keine Verbindung. Montage manuell prüfen.")
        name=f"Teil_{i:03}.stl"
        write_stl(shape,folder/name,indexed=indexed)
        checks=print_checks(shape,order,s['thinWallThreshold'],wall_budgets[i-1])
        if checks['thinSamples']:
            warnings.append(f"Teil {i:03}: Dünnwand-Hinweis, Stichprobe bis {checks['minimumSample']:.3f} mm bei Schwelle {s['thinWallThreshold']:g} mm.")
        color = p.get('color')
        name_label = f"Teil {i:03}"
        if s.get('strategy') == 'color':
            name_label += f" · {color or 'Ohne Farbe'}"
        records.append({'id':i,'key':p['key'],'file':name,'name':name_label,**data,'cell':list(p['cell']),
                        'neighbors':p['neighbors'],'connectedNeighbors':p['connectedNeighbors'],'cutFaces':p['cutFaces'],
                        'requestedConnectors':sum(f['requested'] for f in interfaces if i in (f['a'],f['b'])),'connectors':p['connectors'],'printOrder':list(order) if order else None,
                        'errors':errors,'printable':not errors,'printChecks':checks})
        if color is not None:
            records[-1]['color'] = color
    connectors=[]
    for index,(jid,pin) in enumerate(separate,len(parts)):
        order=fit_order(pin,usable)
        if order is None:
            raise ValueError(f"Separater Verbinder {jid} passt nicht in den Druckraum.")
        name=f"Verbinder_{jid}.stl"; write_stl(pin,folder/name,indexed=indexed)
        checks=print_checks(pin,order,s['thinWallThreshold'],wall_budgets[index])
        if checks['thinSamples']:
            warnings.append(f"Verbinder {jid}: Dünnwand-Hinweis, Stichprobe bis {checks['minimumSample']:.3f} mm.")
        connectors.append({'id':jid,'file':name,'printOrder':list(order),**info(pin),'printChecks':checks})
    # Keep connection topology separate from the restricted motion proof below.
    unseen=set(range(1,len(parts)+1));groups=[]
    while unseen:
        first=min(unseen);unseen.remove(first);pending=[first];group=[]
        while pending:
            item=pending.pop();group.append(item)
            for n in parts[item-1]['connectedNeighbors']:
                if n in unseen:unseen.remove(n);pending.append(n)
        groups.append(sorted(group))
    unconnected=sum(1 for f in interfaces if f['requested']>0 and f['placed']==0)
    if len(groups)>1 and s.get('mode','separate')!='none':
        warnings.append(f'Montagegraph nicht vollständig verbunden: {len(groups)} lose Baugruppen. {unconnected} Schnittstellen ohne Verbinder.')
    assembly={'connected':len(groups)==1 if s.get('mode','separate')!='none' else None,
              'groups':groups,'unconnectedInterfaces':unconnected,'pathVerified':False}
    motion={'checked':False,'status':'not-checked','pathVerified':False,'reason':'disabled' if not s.get('pathCheck',True) else 'no-connectors-mode'}
    special=any(j['kind'] in ('clip','screw') for j in joints)
    if s.get('pathCheck',True) and s.get('mode','separate')!='none' and not special:
        motion=analyze_assembly(parts,joints,separate,progress)
        assembly['pathVerified']=motion['pathVerified']
        if not motion['pathVerified']:
            warnings.append(f"Geradlinige Montagewege nicht vollständig nachgewiesen: {len(motion['remainingParts'])} verbleibende Teile, {len(motion['unresolvedPins'])} ungeprüfte separate Verbinder.")
        if motion['budgetReached']:warnings.append('Rechenbudget der Montageprüfung erreicht. Ungeprüfte Wege wurden nicht freigegeben.')
    if any(j.get('autoSized') for j in joints):
        warnings.append('Verbinder wurden innerhalb der Mindestmaße verkleinert. Tatsächliche Einzelmaße stehen in der Zuordnung. Keine Festigkeitsfreigabe.')
    if any(j['kind']=='dovetail' for j in joints):
        warnings.append('Schwalbenschwanznuten bleiben auf einer Seite offen. Die Verbindung benötigt bei Last in Einschubrichtung eine separate Sicherung.')
    if any(j['kind']=='clip' for j in joints):
        warnings.append('Steckclip: Armdehnung aus vereinfachtem Biegemodell. Material, Druckrichtung, Einrasten und Haltekraft per Passprobe prüfen.')
    screws = [j for j in joints if j['kind']=='screw']
    if screws:
        warnings.append('Außenschraube: Teile zuerst anlegen, dann vom Sechskantkopf aus eindrehen. Gewindefestigkeit und Passung am Druckteil prüfen.')
        if s.get('pathCheck',True):
            remaining = SCREW_SAMPLE_BUDGET
            bodies = [(f'Teil {i:03}',p['solid']) for i,p in enumerate(parts,1)]
            pins = dict(separate)
            for index,joint in enumerate(screws,1):
                progress(94,f'Schraubenweg prüfen · {index}/{len(screws)}')
                obstacles = bodies + [(key,pin) for key,pin in separate if key!=joint['id']]
                check = sample_screw_insertion(pins[joint['id']],obstacles,joint,remaining)
                joint['screwInsertion'] = check
                remaining -= check['testedPoses']
                if check['status']=='collision':
                    warnings.append(f"{joint['id']}: Einschraubweg kollidiert bei {check['remainingTravel']:.2f} mm Restweg mit {check['obstacle']}.")
                elif check['status']=='geometry-error':
                    warnings.append(f"{joint['id']}: Geometriefehler bei der Prüfung des Einschraubwegs. Passprobe erforderlich.")
            if any(joint['screwInsertion']['status']=='budget' for joint in screws):
                warnings.append('Rechenbudget der Schraubenprüfung erreicht. Einige Einschraubwege blieben unvollständig geprüft.')
    if special:
        motion['reason']='flexible-or-rotational-joints'
    if not motion['checked']:warnings.append('Die geradlinige Montagefolge der Teile wurde nicht geprüft.')
    for pair in motion.get('initialCollisions',[]):
        warnings.append('Überschneidung in der Montageposition: '+' ↔ '.join(pair))
        for name in pair:
            part_id=int(name.split(':')[1]) if name.startswith('part:') else next(j['a'] for j in joints if j['id']==name.split(':')[1])
            if 'Überschneidung in Montageposition' not in records[part_id-1]['errors']:
                records[part_id-1]['errors'].append('Überschneidung in Montageposition');records[part_id-1]['printable']=False
    warnings.append('Montageprüfung umfasst geradlinige Bewegungen entlang XYZ oder der jeweiligen Verbinderrichtung mit vorbestückten separaten Verbindern. Keine Reibungs-, Verformungs- oder Festigkeitsprüfung. Passprobe erforderlich.')
    order=[step['part'] for step in motion.get('assemblySteps',[])] if motion['pathVerified'] else [p['id'] for p in sorted(records,key=lambda p:(p['cell'][2],p['cell'][1],p['cell'][0]))]

    result={'version':1,'parts':records,'connectors':connectors,'joints':joints,'cuts':cuts,'settings':s,
            'warnings':warnings,'original':info(solid),'cutVolume':before,'planning':planning,'interfaces':interfaces,'assembly':assembly,'motion':motion,
            'valid':all(p['printable'] for p in records),'assemblyOrder':order}
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    progress(100, f"{len(parts)} echte Druckteile · {len(joints)} Verbinder · Hinweise beachten")
    return result


def demo_dragon():
    """A deliberately identifiable procedural dragon, not the reference artwork."""
    def ball(pos, scale): return md.Manifold.sphere(1,32).scale(scale).translate(pos)
    def bone(a,b,r1,r2):
        a,b=np.array(a,float),np.array(b,float); v=b-a; length=np.linalg.norm(v); z=v/length
        x=np.cross([0,1,0],z)
        if np.linalg.norm(x)<.01: x=np.cross([1,0,0],z)
        x/=np.linalg.norm(x); y=np.cross(z,x)
        return md.Manifold.cylinder(length,r1,r2,16).transform(np.column_stack((x,y,z,a)))
    pieces=[md.Manifold.cylinder(18,148,156,64).scale((1,.65,1)), ball((0,0,104),(57,42,78)),ball((-19,0,165),(38,30,42)),
            bone((-19,0,166),(-55,0,235),25,18),ball((-57,0,244),(33,22,26)),ball((-88,-1,236),(37,18,14)),
            ball((-93,-1,220),(29,16,7)),ball((-48,-20,250),(9,4,7)),ball((-48,20,250),(9,4,7))]
    for side in (-1,1):
        pieces += [bone((-41,side*13,258),(-14,side*26,287),10,0),bone((8,side*28,98),(-37,side*58,41),20,13),
                   ball((-45,side*55,27),(38,19,13)),bone((-17,side*28,150),(-65,side*43,115),11,8),bone((-65,side*43,115),(-76,side*43,62),8,5)]
        # Broad vertical wings: extruded polygon membranes and structural ribs.
        points=[(9,151),(57,270),(121,305),(105,243),(153,208),(111,202),(142,154),(95,175),(80,125),(53,150),(31,110)]
        membrane=md.CrossSection([list(reversed(points))]).extrude(4).rotate((90,0,0)).translate((0,side*31,0))
        # Give each wing a visible outward sweep.
        membrane=membrane.rotate((0,0,side*18))
        pieces.append(membrane)
        for end in [(121,side*55,305),(153,side*65,208),(142,side*65,154)]: pieces.append(bone((9,side*29,151),end,6,2))
    tail=[((34,0,78),(88,0,51),22,17),((88,0,51),(130,0,66),17,11),((130,0,66),(160,0,104),11,6),((160,0,104),(155,0,143),6,0)]
    for a,b,r1,r2 in tail: pieces.append(bone(a,b,r1,r2))
    for i in range(7): pieces.append(bone((-30+i*13,0,190-i*15),(-19+i*14,0,215-i*15),9,0))
    solid=md.Manifold.batch_boolean(pieces,md.OpType.Add)
    return solid.translate(-np.array(solid.bounding_box()[:3])).scale((1.6,1.6,1.6))
