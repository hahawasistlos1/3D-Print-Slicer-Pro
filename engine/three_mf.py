"""Read the geometry of Core and multipart Production 3MF packages."""
import json
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import trimesh


CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
MATERIAL = 'http://schemas.microsoft.com/3dmanufacturing/material/2015/02'
PRODUCTION_PATH = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path'
MODEL_RELATION = 'http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel'
UNIT_FACTORS = {'micron': .001, 'millimeter': 1, 'centimeter': 10, 'inch': 25.4, 'foot': 304.8, 'meter': 1000}
MAX_XML_BYTES = 300_000_000
MAX_SETTINGS_BYTES = 8_000_000
RGB = re.compile(r'#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?')


def normalize_color(value):
    return value[:7].upper() if isinstance(value,str) and RGB.fullmatch(value) else False


def model_path(value, *, absolute):
    if value is None or (absolute and not value.startswith('/')):
        raise ValueError('3MF-Referenz benötigt einen absoluten Modellpfad im Archiv.')
    decoded = unquote(value, errors='strict')
    for path in (value, decoded):
        name = path.removeprefix('/')
        if (any(c in name for c in '\\:?#') or any(ord(c)<32 for c in name)
                or any(segment in ('', '.', '..') for segment in name.split('/'))
                or not name.lower().endswith('.model')):
            raise ValueError('Ungültiger 3MF-Modellpfad. Referenzen müssen im selben Archiv liegen.')
    return value.removeprefix('/'), decoded.removeprefix('/')


def transform(element, unit):
    matrix = np.eye(4)
    if text := element.get('transform'):
        values = np.asarray(text.split(), dtype=float)
        if len(values) != 12 or not np.isfinite(values).all():
            raise ValueError('Ungültige 3MF-Transformation.')
        matrix[:3, :] = values.reshape(4, 3).T
        matrix[:3, 3] *= unit
    return matrix


def color_resources(root):
    groups = {}
    resources = root.find(f'{{{CORE}}}resources')
    for node in resources if resources is not None else ():
        if node.tag == f'{{{CORE}}}basematerials':
            entries = (base.get('displaycolor','') for base in node.findall(f'{{{CORE}}}base'))
        elif node.tag == f'{{{MATERIAL}}}colorgroup':
            entries = (color.get('color','') for color in node.findall(f'{{{MATERIAL}}}color'))
        else:
            continue
        if node.get('id'):
            groups[node.get('id')] = [normalize_color(value) for value in entries]
    return groups


def face_colors(obj, triangles, groups):
    pid, index = obj.get('pid'), obj.get('pindex')

    def resolve(group, position):
        if group is None:
            return None
        colors = groups.get(group,[])
        if not position or not position.isascii() or not position.isdigit() or len(position)>10:
            return False
        i = int(position)
        return colors[i] if i<len(colors) else False

    if not any(len(t.attrib)>3 for t in triangles):
        color = resolve(pid,index)
        return None if color is False else {color: None}
    partitions = {}
    for i,t in enumerate(triangles):
        if any(key.rsplit('}',1)[-1] in ('paint_color','mmu_segmentation') for key in t.attrib):
            return None
        group = t.get('pid',pid)
        first = t.get('p1',index)
        color = resolve(group,first)
        if color is False or any(resolve(group,t.get(key,first)) != color for key in ('p2','p3')):
            return None
        partitions.setdefault(color,[]).append(i)
    if len(partitions)==1:
        return {next(iter(partitions)): None}
    return {color: np.asarray(rows,dtype=np.int64) for color,rows in partitions.items()}


def filament_assignments(archive):
    """Read Bambu Studio and OrcaSlicer per-object filament assignments."""
    try:
        project = archive.getinfo('Metadata/project_settings.config')
        model = archive.getinfo('Metadata/model_settings.config')
        if project.file_size+model.file_size>MAX_SETTINGS_BYTES:
            return {}
        settings = json.loads(archive.read(project))
        colors = settings.get('filament_colour') if isinstance(settings,dict) else None
        if not isinstance(colors,list) or not colors:
            return {}
        root = ET.fromstring(archive.read(model))
    except (KeyError,ValueError,ET.ParseError):
        return {}
    palette = [normalize_color(color) for color in colors]

    def filament(node, default):
        entry = node.find("metadata[@key='extruder']")
        if entry is None:
            return default
        value = entry.get('value','')
        if not re.fullmatch(r'[0-9]{1,5}',value):
            return False
        index = int(value)-1
        if index==-1:
            return default
        return palette[index] if index<len(palette) else False

    result = {}
    for obj in root.findall('object'):
        base = filament(obj,None)
        parts = {}
        for part in obj.findall('part'):
            key = part.get('id')
            shade = filament(part,base) if part.get('subtype','normal_part')=='normal_part' else False
            parts[key] = shade if key not in parts or parts[key]==shade else False
        result[obj.get('id')] = base, parts
    return result


def read_meshes(path, max_triangles, *, color_data=None):
    with zipfile.ZipFile(path) as archive:
        filaments = filament_assignments(archive) if color_data is not None else {}
        entries = {}
        for info in archive.infolist():
            key = info.filename.casefold()
            if key.endswith('.model') or key == '_rels/.rels':
                if key in entries:
                    raise ValueError(f'Mehrdeutige 3MF-Modelldatei: {info.filename}')
                entries[key] = info

        xml_bytes = 0

        def read_xml(entry):
            nonlocal xml_bytes
            xml_bytes += entry.file_size
            if xml_bytes > MAX_XML_BYTES:
                raise ValueError('3MF-Modelldateien sind zusammen größer als 300 MB XML.')
            with archive.open(entry) as stream:
                return ET.parse(stream).getroot()

        def archive_model(value, *, absolute):
            names = model_path(value, absolute=absolute)
            matches = {entries[name.casefold()] for name in names if name.casefold() in entries}
            if len(matches) != 1:
                raise ValueError(f'3MF-Modelldatei fehlt oder ist mehrdeutig: {value}')
            return matches.pop().filename

        root_name = None
        if rels := entries.get('_rels/.rels'):
            relationships = read_xml(rels)
            for relationship in relationships:
                if relationship.get('Type') != MODEL_RELATION:
                    continue
                if root_name is not None or relationship.get('TargetMode','Internal') != 'Internal':
                    raise ValueError('3MF benötigt genau ein internes Hauptmodell.')
                root_name = archive_model(relationship.get('Target'), absolute=False)
        if root_name is None:
            root_entry = entries.get('3d/3dmodel.model')
            if root_entry is None:
                root_entry = next((e for k,e in entries.items() if k.endswith('.model')), None)
            if root_entry is None:
                raise ValueError('3MF enthält kein Modell.')
            root_name = root_entry.filename

        models = {}
        local_meshes = {}
        palettes = {}
        local_colors = {}

        def model(name):
            if name not in models:
                root = read_xml(entries[name.casefold()])
                if root.tag != f'{{{CORE}}}model':
                    raise ValueError(f'Ungültiges 3MF-Modell: {name}')
                unit = UNIT_FACTORS.get(root.get('unit', 'millimeter'))
                if unit is None:
                    raise ValueError(f'Unbekannte 3MF-Maßeinheit in {name}.')
                objects = {}
                for obj in root.findall('m:resources/m:object', {'m': CORE}):
                    oid = obj.get('id')
                    if not oid or oid in objects:
                        raise ValueError(f'Fehlende oder doppelte 3MF-Objekt-ID in {name}.')
                    objects[oid] = obj
                models[name] = root, unit, objects
            return models[name]

        ns = {'m': CORE}
        meshes = []
        face_count = 0
        multipart = False

        def add_mesh(key, obj, node, unit, placement, filament):
            nonlocal face_count
            if key not in local_meshes:
                triangles = node.findall('m:triangles/m:triangle', ns)
                if not triangles:
                    raise ValueError('Leeres 3MF-Netz.')
                if len(triangles) > max_triangles - face_count:
                    raise ValueError(f'Zu viele Dreiecke in den referenzierten 3MF-Netzen (Grenze: {max_triangles:,}).')
                vertices = np.asarray([[float(v.attrib[k]) for k in 'xyz']
                                       for v in node.iterfind('m:vertices/m:vertex', ns)], dtype=float)*unit
                faces = np.asarray([[int(t.attrib[k]) for k in ('v1','v2','v3')] for t in triangles], dtype=np.int64)
                if not len(vertices) or not np.isfinite(vertices).all() or faces.min()<0 or faces.max()>=len(vertices):
                    raise ValueError('Ungültige 3MF-Netzkoordinaten oder Dreiecksindizes.')
                used = np.zeros(len(vertices), dtype=bool)
                used[faces] = True
                if not used.all():
                    faces = (np.cumsum(used)-1)[faces]
                    vertices = vertices[used]
                local_meshes[key] = vertices, faces
                if color_data is not None:
                    name = key[0]
                    if name not in palettes:
                        palettes[name] = color_resources(model(name)[0])
                    local_colors[key] = face_colors(obj,triangles,palettes[name])
            vertices, faces = local_meshes[key]
            face_count += len(faces)
            if face_count > max_triangles:
                raise ValueError(f'Zu viele Dreiecke in den referenzierten 3MF-Netzen (Grenze: {max_triangles:,}).')
            points = trimesh.transform_points(vertices, placement)
            if not np.isfinite(points).all():
                raise ValueError('Ungültige transformierte 3MF-Koordinaten.')
            if np.linalg.det(placement[:3, :3]) < 0:
                faces = faces[:, ::-1]
            meshes.append((points, faces))
            if color_data is not None:
                palette = local_colors[key]
                if palette == {None:None} and filament is not None:
                    palette = None if filament is False else {filament:None}
                color_data.append(palette)

        def resolve(name, reference, placement, stack=(), filament=None):
            nonlocal multipart
            path = reference.get(PRODUCTION_PATH)
            if path is not None:
                if name != root_name:
                    raise ValueError('Nur das 3MF-Hauptmodell darf andere Modelldateien referenzieren.')
                target = archive_model(path, absolute=True)
                multipart |= target != name
            else:
                target = name
            oid = reference.get('objectid')
            key = target, oid
            if key in stack or len(stack)>32:
                raise ValueError('Zyklische oder zu tief verschachtelte 3MF-Komponenten.')
            _, parent_unit, _ = model(name)
            _, unit, objects = model(target)
            obj = objects.get(oid)
            if obj is None:
                raise ValueError(f'3MF-Objekt {oid} fehlt in {target}.')
            placement = placement @ transform(reference, parent_unit)
            if not np.isfinite(placement).all():
                raise ValueError('Ungültige kombinierte 3MF-Transformation.')
            if not stack:
                filament,part_filaments = filaments.get(oid,(None,{}))
            else:
                part_filaments = {}
            node = obj.find('m:mesh', ns)
            if node is not None:
                add_mesh(key, obj, node, unit, placement, filament)
                return
            components = obj.findall('m:components/m:component', ns)
            if not components:
                raise ValueError('Leere 3MF-Komponente.')
            for child in components:
                resolve(target, child, placement, stack+(key,),part_filaments.get(child.get('objectid'),filament))

        root, _, _ = model(root_name)
        for item in root.iterfind('m:build/m:item', ns):
            resolve(root_name, item, np.eye(4))
        if not meshes:
            raise ValueError('3MF enthält keine druckbaren Build-Objekte.')
        return meshes, multipart


def combine_meshes(meshes):
    face_blocks = []
    offset = 0
    for vertices, faces in meshes:
        face_blocks.append(faces+offset)
        offset += len(vertices)
    return trimesh.Trimesh(np.concatenate([v for v,_ in meshes]), np.concatenate(face_blocks), process=False)


def read_3mf(path, max_triangles):
    meshes, _ = read_meshes(path, max_triangles)
    return combine_meshes(meshes)
