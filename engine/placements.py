"""User-defined connector positions tied to a previously computed interface."""
import manifold3d as md
import numpy as np
from manual_planes import vector


SURFACE_VERTEX_BUDGET = 80_000
MAX_SURFACE_VERTICES = 4_000


def interface_surface(region, axis, offset, rotation, budget):
    """Serialize the actual contact, including holes, for 3D point picking."""
    if not 3<=region.num_vert()<=min(MAX_SURFACE_VERTICES,budget):
        return None
    contours = region.to_polygons()
    vertices = np.concatenate(contours)
    triangles = np.asarray(md.triangulate(contours),dtype=np.int64)
    if not triangles.size or np.min(triangles)<0 or np.max(triangles)>=len(vertices):
        return None
    xy = vertices[triangles]
    a,b = xy[:,1]-xy[:,0],xy[:,2]-xy[:,0]
    area = (a[:,0]*b[:,1]-a[:,1]*b[:,0]).sum()/2
    if not np.isclose(area,region.area(),rtol=1e-7,atol=1e-8):
        return None
    points = np.empty((len(vertices),3))
    points[:,[(axis+1)%3,(axis+2)%3]] = vertices
    points[:,axis] = offset
    if rotation is not None:
        points = points @ rotation
    return {'vertices':points.tolist(),'indices':triangles.ravel().tolist()}


def selected_positions(settings, candidates, parts):
    raw = settings.get('placements', [])
    if not isinstance(raw,list) or len(raw)>4096:
        raise ValueError('Ungültige Liste manueller Verbinderpositionen.')
    selected={}
    for item in raw:
        if not isinstance(item,dict):
            raise ValueError('Ungültige manuelle Verbinderposition.')
        if item.get('colorBoundary') is True and not (settings.get('strategy') == 'color' and settings.get('connectAcrossColors')):
            continue
        name=item.get('interfaceId')
        if not isinstance(name,str) or not name.startswith('S') or not name[1:].isascii() or not name[1:].isdigit() or len(name)>10:
            raise ValueError('Manuelle Verbinderposition benötigt eine Schnittstelle.')
        index=int(name[1:])-1
        if not 0<=index<len(candidates):
            raise ValueError(f'{name}: Schnittstelle der manuellen Position ist nicht mehr vorhanden.')
        a,b,axis,offset,_,rotation,_=candidates[index]
        if parts[a]['key']!=item.get('aKey') or parts[b]['key']!=item.get('bKey'):
            raise ValueError(f'{name}: Die Teile für die manuelle Position haben sich geändert.')
        center=vector(item.get('center'))
        if rotation is not None:
            center=rotation@center
        if abs(center[axis]-offset)>1e-4:
            raise ValueError(f'{name}: Manuelle Position liegt außerhalb der Schnittfläche. XYZ-Koordinaten prüfen.')
        center[axis]=offset
        group=selected.setdefault(index,[])
        if len(group)>=8:
            raise ValueError(f'{name}: Bis zu acht manuelle Verbinder pro Schnittstelle.')
        group.append(center)
    return selected


def trials(settings, axis, offset, region, requested, sizes, candidates, face_length):
    """Try requested centers in order, including both tangent alignments."""
    for slot, fixed in enumerate(requested or [None]):
        for diameter,depth in sizes(settings):
            sized=dict(settings,diameter=diameter,depth=depth,rectHeight=settings['rectHeight']*diameter/settings['diameter'])
            length=face_length(sized)
            if fixed is None:
                proposals=candidates(region,axis,offset,sized)
            else:
                tangents=(None,) if length is None else ((axis+1)%3,(axis+2)%3)
                proposals=((fixed,tangent) for tangent in tangents)
            for center,tangent in proposals:
                yield slot,sized,center,tangent,length
