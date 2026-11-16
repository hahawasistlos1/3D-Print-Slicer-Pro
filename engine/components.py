"""Connected material components, with enclosed negative cavity shells retained.

Manifold.decompose() separates connected boundary surfaces. A sealed cavity
therefore appears as a negative-volume shell, not as a separate physical part.
Dropping those shells would silently fill holes. Reattach each cavity to its
enclosing positive shell before returning printable components.
"""
import numpy as np
import manifold3d as md


def _contains(shell, point):
    box=np.asarray(shell.bounding_box()); extent=max(1.,float((box[3:]-box[:3]).max()))
    for direction in ((1,.371,.694),(.417,1,.231),( .293,.593,1)):
        end=point+np.asarray(direction)*extent*5
        hits=shell.ray_cast(point,end)
        distances=sorted(float(h.distance) for h in hits)
        unique=[]
        for distance in distances:
            if not unique or abs(distance-unique[-1])>1e-8:unique.append(distance)
        # Avoid ambiguous exact edge/vertex hits by trying another ray.
        if len(unique)==len(distances):return len(unique)%2==1
    return len(unique)%2==1


def material_components(solid):
    shells=[s for s in solid.decompose() if not s.is_empty() and abs(s.volume())>1e-10]
    positive=[s for s in shells if s.volume()>0]
    negative=[s for s in shells if s.volume()<0]
    if not negative:return positive
    groups=[[s] for s in positive]
    for cavity in negative:
        cb=np.asarray(cavity.bounding_box());mesh=cavity.to_mesh64()
        point=np.asarray(mesh.vert_properties[0,:3],dtype=float)
        parents=[]
        for index,shell in enumerate(positive):
            box=np.asarray(shell.bounding_box())
            if np.any(cb[:3]<box[:3]-1e-7) or np.any(cb[3:]>box[3:]+1e-7):continue
            if _contains(shell,point):parents.append(index)
        if not parents:
            raise ValueError('Geschlossener Hohlraum konnte keinem äußeren Volumenkörper zugeordnet werden.')
        parent=min(parents,key=lambda i:positive[i].volume())
        groups[parent].append(cavity)
    result=[]
    for group in groups:
        if len(group)==1:result.append(group[0]);continue
        vertices=[];triangles=[];offset=0
        for shell in group:
            mesh=shell.to_mesh64();v=np.asarray(mesh.vert_properties)[:,:3];t=np.asarray(mesh.tri_verts)
            vertices.append(v);triangles.append(t+offset);offset+=len(v)
        combined=md.Manifold(md.Mesh64(np.ascontiguousarray(np.concatenate(vertices),dtype=np.float64),np.ascontiguousarray(np.concatenate(triangles),dtype=np.uint64)))
        if combined.status()!=md.Error.NoError or combined.volume()<=0:
            raise ValueError('Hohlraumzuordnung erzeugt kein gültiges Materialvolumen.')
        result.append(combined)
    if abs(sum(s.volume() for s in result)-solid.volume())>max(1e-6,abs(solid.volume())*1e-8):
        raise ValueError('Volumenerhaltung bei der Hohlraumzuordnung fehlgeschlagen.')
    return result
