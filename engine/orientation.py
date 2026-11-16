"""Rigid model reorientation before axis-aligned cutting.

Column-vector convention: Rz @ Ry @ Rx, then translate the new minimum to 0.
Native affine transform: https://manifoldcad.org/docs/html/classmanifold_1_1_manifold.html
"""
import math
from pathlib import Path
import numpy as np
import manifold3d as md
from geometry import load_model,write_stl,info
from preview import topology
from indexed_mesh import indexed_path


def rotation_matrix(angles):
    if not isinstance(angles,(list,tuple,np.ndarray)) or len(angles)!=3:
        raise ValueError('Drei Drehwinkel für X, Y und Z angeben.')
    try:values=np.asarray(angles,dtype=float)
    except (TypeError,ValueError):raise ValueError('Ungültige Drehwinkel.')
    if values.shape!=(3,) or not np.isfinite(values).all() or np.abs(values).max()>360:
        raise ValueError('Drehwinkel müssen zwischen -360 und 360 Grad liegen.')
    x,y,z=np.radians(values);cx,cy,cz=np.cos((x,y,z));sx,sy,sz=np.sin((x,y,z))
    rx=np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
    ry=np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]])
    rz=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])
    matrix=rz@ry@rx;matrix[np.abs(matrix)<1e-14]=0
    return matrix


def rotate_model(solid,angles):
    matrix=rotation_matrix(angles)
    if solid.is_empty() or solid.status()!=md.Error.NoError or solid.volume()<=0:
        raise ValueError('Nur gültige geschlossene Modelle können ausgerichtet werden.')
    result=solid.transform(np.column_stack((matrix,np.zeros(3))))
    result=result.translate(-np.asarray(result.bounding_box()[:3]))
    if result.is_empty() or result.status()!=md.Error.NoError or not math.isfinite(result.volume()):
        raise ValueError('Die Modellausrichtung hat keine gültige Geometrie erzeugt.')
    if abs(result.volume()/solid.volume()-1)>1e-8 or topology(result)!=topology(solid):
        raise ValueError('Volumen oder Topologie bei der Ausrichtung verändert.')
    return result


def write_rotated_model(input_path,folder,angles):
    source=load_model(input_path,use_indexed=True);result=rotate_model(source,angles)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    write_stl(result,folder/'original.stl',indexed=indexed_path(input_path).is_file())
    checked=load_model(folder/'original.stl',normalize=False,use_indexed=True)
    data=info(checked)
    if not data['watertight'] or not data['normalsConsistent'] or abs(checked.volume()/source.volume()-1)>1e-5 or topology(checked)!=topology(source):
        raise ValueError('Die gespeicherte Modellausrichtung konnte nicht bestätigt werden.')
    if not np.allclose(checked.bounding_box(),result.bounding_box(),rtol=2e-6,atol=1e-5):
        raise ValueError('Maße oder Ursprung bei der Ausrichtung verändert.')
    return data,{'angles':[float(v) for v in angles],'order':'XYZ','matrix':rotation_matrix(angles).tolist(),
                 'previousDimensions':info(source)['dimensions'],'volumeError':abs(checked.volume()/source.volume()-1)}
