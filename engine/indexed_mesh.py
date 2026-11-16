"""Fixed-size binary storage for internal mesh vertices and triangle indices."""
from pathlib import Path
import struct

import manifold3d as md
import numpy as np


MAGIC = b'SPMESH01'
HEADER = struct.Struct('<8sII')


def indexed_path(stl_path):
    return Path(stl_path).with_suffix('.mesh')


def from_arrays(vertices, triangles):
    return md.Manifold(md.Mesh64(np.require(vertices,dtype=np.float64,requirements=['C','W']),
                                 np.require(triangles,dtype=np.uint64,requirements=['C','W'])))


def write_indexed(solid, path, *, verify=False):
    mesh = solid.to_mesh64()
    vertices = np.asarray(mesh.vert_properties)[:,:3]
    faces = np.asarray(mesh.tri_verts)
    with Path(path).open('wb') as stream:
        stream.write(HEADER.pack(MAGIC,len(vertices),len(faces)))
        vertices.astype('<f8',copy=False).tofile(stream)
        faces.astype('<u4',copy=False).tofile(stream)
    if verify:
        saved_vertices,saved_faces=_read_arrays(path,len(faces))
        if not np.array_equal(saved_vertices,vertices) or not np.array_equal(saved_faces,faces):
            raise ValueError('Die gespeicherten Eckpunkte oder Dreiecksindizes weichen vom geprüften Anzeigenetz ab.')


def _read_arrays(path, triangle_limit):
    with Path(path).open('rb') as stream:
        header = stream.read(HEADER.size)
        if len(header)!=HEADER.size:
            raise ValueError('Interne Netzdatei ist unvollständig.')
        magic, vertices, faces = HEADER.unpack(header)
        if (magic!=MAGIC or not 0<faces<=triangle_limit or not 0<vertices<=faces*3
                or Path(path).stat().st_size!=HEADER.size+vertices*24+faces*12):
            raise ValueError('Interne Netzdatei hat ungültige Abmessungen.')
        points=np.fromfile(stream,dtype='<f8',count=vertices*3).reshape(-1,3)
        triangles=np.fromfile(stream,dtype='<u4',count=faces*3).reshape(-1,3)
    if len(points)!=vertices or len(triangles)!=faces or not np.isfinite(points).all() or triangles.max()>=vertices:
        raise ValueError('Interne Netzdatei enthält ungültige Koordinaten oder Indizes.')
    return points,triangles


def read_indexed(path, triangle_limit):
    points,triangles=_read_arrays(path,triangle_limit)
    shape=from_arrays(points,triangles)
    if shape.status()!=md.Error.NoError or shape.is_empty() or not np.isfinite(shape.volume()) or shape.volume()<=0:
        raise ValueError('Die indizierte Geometrie ist kein gültiger geschlossener Körper.')
    return shape
