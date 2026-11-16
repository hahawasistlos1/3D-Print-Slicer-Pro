"""Offline STL/OBJ/Core-3MF export with atomic replacement and re-import checks.

3MF package structure follows the 3MF Consortium Core specification:
https://3mf.io/spec/core-v1-3-0/
One mesh object per file; no printer settings, textures or extension dependency.
"""
from pathlib import Path
import uuid
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
import manifold3d as md
from geometry import mesh_for_export, read_3mf, solid_of, weld_exact_vertices
from indexed_mesh import from_arrays
from preview import topology
from color_slicing import COLOR_PATTERN

CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
TYPES='http://schemas.openxmlformats.org/package/2006/content-types'
START='http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel'
MODEL_TYPE='application/vnd.ms-package.3dmanufacturing-3dmodel+xml'
FORMATS=('stl','obj','3mf')
STL_RETRY_TOLERANCES=(.00002,.00005,.0001,.00025,.0005)


def xml_bytes(element):
    return ET.tostring(element,encoding='utf-8',xml_declaration=True)


def write_obj(mesh,path):
    # OBJ has no normative unit field: annotate mm, never reference an MTL.
    with Path(path).open('w',encoding='utf-8',newline='\n') as stream:
        stream.write('# 3D Print Slicer Pro\n# units: millimeter\n# print orientation, minimum XYZ = 0\no Druckteil\n')
        for vertex in mesh.vertices:
            stream.write('v '+' '.join(format(float(v),'.17g') for v in vertex)+'\n')
        for face in mesh.faces:
            stream.write('f '+' '.join(str(int(v)+1) for v in face)+'\n')


def write_3mf(mesh,path,color=None):
    # A small fixed package shell; stream geometry to avoid a second large XML tree.
    types=ET.Element('Types',xmlns=TYPES)
    ET.SubElement(types,'Default',Extension='rels',ContentType='application/vnd.openxmlformats-package.relationships+xml')
    ET.SubElement(types,'Default',Extension='model',ContentType=MODEL_TYPE)
    relationships=ET.Element('Relationships',xmlns=REL)
    ET.SubElement(relationships,'Relationship',Id='rel0',Type=START,Target='/3D/3dmodel.model')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        archive.writestr('[Content_Types].xml',xml_bytes(types))
        archive.writestr('_rels/.rels',xml_bytes(relationships))
        material = (f'<basematerials id="2"><base name="{color}" displaycolor="{color}"/></basematerials>'
                    if color else '')
        prop = ' pid="2" pindex="0"' if color else ''
        with archive.open('3D/3dmodel.model','w') as stream:
            stream.write(('<?xml version="1.0" encoding="utf-8"?>\n'
                f'<model xmlns="{CORE}" unit="millimeter" xml:lang="de-DE">'
                '<metadata name="Application">3D Print Slicer Pro</metadata>'
                f'<resources>{material}<object id="1" type="model" name="Druckteil"{prop}><mesh><vertices>').encode('utf-8'))
            for vertex in mesh.vertices:
                stream.write(('<vertex '+' '.join(f'{axis}="{format(float(v),".17g")}"' for axis,v in zip('xyz',vertex))+'/>').encode('ascii'))
            stream.write(b'</vertices><triangles>')
            for face in mesh.faces:
                stream.write(f'<triangle v1="{int(face[0])}" v2="{int(face[1])}" v3="{int(face[2])}"/>'.encode('ascii'))
            stream.write(b'</triangles></mesh></object></resources><build><item objectid="1"/></build></model>')


def read_export(path,format):
    if format=='stl':
        mesh=trimesh.load(path,file_type=format,force='mesh',process=False,skip_materials=True)
        # Weld identical coordinates only. A looser weld can hide gaps or
        # combine distinct edges that a receiving slicer would keep separate.
        mesh=weld_exact_vertices(mesh)
        if not mesh.is_watertight or not mesh.is_winding_consistent:
            raise ValueError('Das gespeicherte STL-Netz hat offene oder uneinheitlich orientierte Kanten.')
        return solid_of(mesh,preserve_indices=True)
    mesh=read_3mf(path) if format=='3mf' else trimesh.load(path,file_type=format,force='mesh',process=True,skip_materials=True)
    return solid_of(mesh,preserve_indices=format=='3mf')


def write_ascii_stl(mesh, stage):
    # Use round-trip precision and bound memory independently of mesh size.
    with stage.open('w',encoding='ascii',newline='\n') as stream:
        stream.write('solid SlicerPro\n')
        for start in range(0,len(mesh.faces),8192):
            batch=mesh.faces[start:start+8192]
            triangles=mesh.vertices[batch]
            normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
            lengths=np.linalg.norm(normals,axis=1,keepdims=True)
            np.divide(normals,lengths,out=normals,where=lengths>0)
            for normal,triangle in zip(normals,triangles):
                stream.write('facet normal {:.17g} {:.17g} {:.17g}\nouter loop\n'.format(*normal))
                for vertex in triangle:
                    stream.write('vertex {:.17g} {:.17g} {:.17g}\n'.format(*vertex))
                stream.write('endloop\nendfacet\n')
        stream.write('endsolid SlicerPro\n')


def write_checked_stl(solid, mesh, stage, order):
    signature=topology(solid)
    stage.write_bytes(trimesh.exchange.stl.export_stl(mesh))
    try:
        checked=read_export(stage,'stl')
    except ValueError:
        pass
    else:
        if topology(checked)==signature:
            return checked

    # Collapse numerically tiny triangles on a copy, then rebuild with the
    # exact Float32 coordinates STL will store. Keep the original shell layout.
    for tolerance in STL_RETRY_TOLERANCES:
        candidate=solid.simplify(tolerance)
        if candidate.status()!=md.Error.NoError or candidate.is_empty() or topology(candidate)!=signature:
            continue
        oriented=mesh_for_export(candidate,origin=True,order=order)
        rounded=from_arrays(oriented.vertices.astype(np.float32),oriented.faces)
        if rounded.status()!=md.Error.NoError or rounded.is_empty() or topology(rounded)!=signature:
            continue
        prepared=mesh_for_export(rounded)
        stage.write_bytes(trimesh.exchange.stl.export_stl(prepared))
        try:
            checked=read_export(stage,'stl')
        except ValueError:
            continue
        if topology(checked)==signature:
            return checked
    # ASCII STL can retain closely spaced vertices that Float32 collapses.
    # Use the unmodified mesh and keep the same strict read-back checks.
    write_ascii_stl(mesh,stage)
    try:
        checked=read_export(stage,'stl')
    except ValueError:
        pass
    else:
        if topology(checked)==signature:
            return checked
    raise ValueError('STL-Prüfung: Die geschriebene Datei ergibt keinen geschlossenen Volumenkörper mit der ursprünglichen Topologie. Bitte als 3MF exportieren, um die Dreiecksindizes zu erhalten.')


def export_file(solid,path,order=None,format=None,*,color=None):
    path=Path(path)
    kind=(format or path.suffix.lstrip('.')).lower()
    if kind not in FORMATS:raise ValueError('Exportformat muss STL, OBJ oder 3MF sein.')
    if color is not None and (not isinstance(color,str) or not COLOR_PATTERN.fullmatch(color)):
        raise ValueError('Ungültiger Farbwert für den Export.')
    mesh=mesh_for_export(solid,origin=True,order=order)
    stage=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex+'.'+kind)
    try:
        if kind=='stl':
            checked=write_checked_stl(solid,mesh,stage,order)
        else:
            if kind=='obj':write_obj(mesh,stage)
            else:write_3mf(mesh,stage,color)
            try:
                checked=read_export(stage,kind)
            except ValueError as error:
                hint=' Bitte als 3MF exportieren, um die Dreiecksindizes zu erhalten.' if kind=='obj' else ''
                raise ValueError(f'{kind.upper()}-Prüfung: Die geschriebene Datei ergibt keinen geschlossenen Volumenkörper.{hint}') from error
        if abs(checked.volume()-solid.volume())>max(1e-4,solid.volume()*1e-5):
            raise ValueError(f'{kind.upper()}-Prüfung nach dem Export fehlgeschlagen: Volumen verändert.')
        expected=np.r_[mesh.bounds[0],mesh.bounds[1]]
        if not np.allclose(checked.bounding_box(),expected,rtol=2e-6,atol=1e-5):
            raise ValueError(f'{kind.upper()}-Prüfung nach dem Export fehlgeschlagen: Maße oder Ursprung verändert.')
        stage.replace(path)
        return kind
    finally:
        stage.unlink(missing_ok=True)
