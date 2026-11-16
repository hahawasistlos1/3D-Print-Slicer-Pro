"""Bounded thickness indications and face-angle estimates in print orientation."""
import math
import numpy as np


def print_checks(solid, order, wall_limit, ray_budget):
    mesh=solid.to_mesh64()
    vertices=np.asarray(mesh.vert_properties)[:,:3]
    faces=np.asarray(mesh.tri_verts)
    box=solid.bounding_box()
    epsilon=max(1e-7, max(box[i+3]-box[i] for i in range(3))*1e-8)
    count=min(len(faces),ray_budget) if wall_limit>epsilon*10 else 0
    samples=vertices[faces[np.linspace(0,len(faces)-1,count,dtype=int)]]
    thin=[]
    measured=0
    for triangle in samples:
        normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0])
        length=np.linalg.norm(normal)
        if length<=epsilon**2:
            continue
        normal/=length
        center=triangle.mean(axis=0)
        start=center+normal*epsilon
        hits=solid.ray_cast(start,center-normal*wall_limit)
        if not hits or np.linalg.norm(np.asarray(hits[0].position)-center)>epsilon*3:
            continue
        if np.dot(hits[0].normal,normal)<.5:
            continue
        measured+=1
        for hit in hits[1:]:
            if np.linalg.norm(np.asarray(hit.position)-center)<=epsilon*3:
                continue
            if np.dot(hit.normal,normal)<=-.5:
                thickness=float((center-np.asarray(hit.position))@normal)
                if thickness<wall_limit-epsilon:
                    thin.append((thickness,center.tolist()))
            break

    overhang_area=0.
    if order is not None:
        up=order[2]
        for start in range(0,len(faces),32768):
            triangles=vertices[faces[start:start+32768]]
            normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
            double_area=np.linalg.norm(normals,axis=1)
            above_bed=np.max(triangles[:,:,up],axis=1)>box[up]+epsilon
            overhang=above_bed & (normals[:,up]<-math.sqrt(.5)*double_area)
            overhang_area+=double_area[overhang].sum()/2

    thin.sort(key=lambda entry: entry[0])
    return {'wallThreshold':wall_limit,'testedRays':count,'validRays':measured,
            'thinSamples':len(thin),'minimumSample':thin[0][0] if thin else None,
            'samplePoints':[{'thickness':v,'point':p} for v,p in thin[:8]],
            'overhangArea':float(overhang_area) if order is not None else None,
            'overhangAngle':45}
