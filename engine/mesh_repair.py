"""Conservative source-mesh repair. Internal preview and export stay strict."""
from collections import deque

import manifold3d as md
import numpy as np


MAX_HOLES = 64
MAX_LOOP_EDGES = 32
EXTENDED_LOOP_EDGES = 96
MAX_WINDING_FACES = 500_000


class ExtendedPlanarRepairAvailable(ValueError):
    """A larger planar opening can be examined in the expanded import mode."""


def edge_groups(mesh):
    inverse = mesh.edges_unique_inverse
    counts = np.bincount(inverse)
    order = np.argsort(inverse, kind='stable')
    starts = np.cumsum(counts)-counts
    return order, starts, counts


def stitch_boundary(mesh):
    """Pair unambiguous, microscopically separated boundary vertices."""
    order,starts,counts=edge_groups(mesh)
    boundary=order[starts[counts==1]]
    if not len(boundary) or len(boundary)>MAX_HOLES*MAX_LOOP_EDGES or np.any(counts>2):
        return None
    vertices=np.unique(mesh.edges[boundary])
    points=mesh.vertices[vertices]
    tolerance=min(.0001,float(mesh.extents.max())*1e-7)
    indices=np.argsort(points[:,0],kind='stable')
    matches=[[] for _ in vertices]
    for position,a in enumerate(indices):
        for b in indices[position+1:]:
            if points[b,0]-points[a,0]>tolerance:
                break
            if np.linalg.norm(points[b]-points[a])<=tolerance:
                matches[a].append(b)
                matches[b].append(a)
    if any(len(group)!=1 for group in matches):
        return None
    mapping=np.arange(len(mesh.vertices))
    for a,group in enumerate(matches):
        mapping[vertices[a]]=min(vertices[a],vertices[group[0]])
    candidate=mesh.copy()
    candidate.faces=mapping[mesh.faces]
    candidate.remove_unreferenced_vertices()
    if candidate.is_watertight and candidate.is_winding_consistent:
        return candidate
    return None


def fix_winding(mesh):
    if len(mesh.faces)>MAX_WINDING_FACES:
        raise ValueError('Flächennormalen sind uneinheitlich. Das Netz ist für die automatische Ausrichtung zu groß.')
    order, starts, counts = edge_groups(mesh)
    pairs = order[starts[counts==2,None]+[0,1]]
    edges = mesh.edges
    neighbors = np.full(len(edges),-1,dtype=np.int32)
    neighbors[pairs[:,0]], neighbors[pairs[:,1]] = pairs[:,1]//3,pairs[:,0]//3
    parity = np.zeros(len(edges),dtype=bool)
    same = edges[pairs[:,0],0]==edges[pairs[:,1],0]
    parity[pairs[:,0]] = parity[pairs[:,1]] = same
    flips = np.full(len(mesh.faces),-1,dtype=np.int8)
    for seed in range(len(flips)):
        if flips[seed]!=-1:
            continue
        flips[seed]=0
        group=[]
        pending=deque([seed])
        while pending:
            face=pending.popleft()
            group.append(face)
            for edge in range(3*face,3*face+3):
                neighbor=neighbors[edge]
                if neighbor<0:
                    continue
                expected=flips[face]^parity[edge]
                if flips[neighbor]==-1:
                    flips[neighbor]=expected
                    pending.append(neighbor)
                elif flips[neighbor]!=expected:
                    raise ValueError('Die Flächen lassen sich nicht widerspruchsfrei ausrichten.')
        # Preserve the majority orientation of each shell, including cavities.
        if np.count_nonzero(flips[group])*2>len(group):
            flips[group]^=1
    mask=flips==1
    faces=mesh.faces.copy()
    faces[mask]=faces[mask,::-1]
    mesh.faces=faces
    return int(mask.sum())


def boundary_loops(mesh, indices):
    # Reverse the boundary halfedges so the new face winds against its neighbors.
    edges=mesh.edges[indices,::-1]
    sources={int(a):(int(b),int(i//3)) for (a,b),i in zip(edges,indices)}
    if len(sources)!=len(edges) or len(np.unique(edges[:,1]))!=len(edges) or set(edges[:,1])!=sources.keys():
        raise ValueError('Die offenen Kanten bilden keine eindeutigen, geschlossenen Randlinien.')
    while sources:
        start=next(iter(sources))
        vertex=start
        points=[]
        faces=[]
        while vertex in sources:
            points.append(vertex)
            vertex,face=sources.pop(vertex)
            faces.append(face)
        if vertex!=start or len(points)<3:
            raise ValueError('Die offenen Kanten bilden keine eindeutigen, geschlossenen Randlinien.')
        yield np.asarray(points),np.asarray(faces)


def cross2(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def validate_simple_polygon(polygon, vectors, lengths, tolerance):
    for i, (a, u) in enumerate(zip(polygon, vectors)):
        b = a + u
        for j in range(i+2, len(polygon)):
            if i == 0 and j == len(polygon)-1:
                continue
            c, v = polygon[j], vectors[j]
            d = c + v
            if np.any(np.minimum(np.maximum(a,b),np.maximum(c,d)) <
                      np.maximum(np.minimum(a,b),np.minimum(c,d))-tolerance):
                continue
            ab = cross2(u,np.asarray([c,d])-a)/lengths[i]
            cd = cross2(v,np.asarray([a,b])-c)/lengths[j]
            if (ab.min()<=tolerance and ab.max()>=-tolerance and
                    cd.min()<=tolerance and cd.max()>=-tolerance):
                raise ValueError('Offene Randlinie überschneidet sich oder berührt sich selbst.')


def clip_section(section, polygon, sign, margin):
    for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
        edge=b-a
        distance=sign*cross2(edge,np.asarray(section)-a)/np.linalg.norm(edge)-margin
        clipped=[]
        for i,p in enumerate(section):
            q=section[i-1]
            dp,dq=distance[i],distance[i-1]
            if (dp>=0)!=(dq>=0):
                clipped.append(p+(q-p)*dp/(dp-dq))
            if dp>=0:
                clipped.append(p)
        section=clipped
        if not section:
            break
    return section


def hits_patch(section, polygon, vectors, lengths, triangles, convex, tolerance):
    if not section:
        return False
    if convex:
        return bool(clip_section(section,polygon,1,tolerance))
    for triangle in triangles:
        clipped=clip_section(section,polygon[triangle],1,0)
        if not clipped:
            continue
        # Contacts only on the original hole rim are allowed. A hit along a
        # triangulation diagonal still crosses the interior of the patch.
        points=np.vstack((clipped,np.mean(clipped,axis=0)))
        delta=points[:,None,:]-polygon
        t=np.clip(np.einsum('ijk,jk->ij',delta,vectors)/lengths**2,0,1)
        if np.any(np.linalg.norm(delta-t[:,:,None]*vectors,axis=2).min(axis=1)>tolerance):
            return True
    return False


def patch_for_loop(mesh, ids, surrounding, tolerance, *, extended, extent, other_meshes):
    points=mesh.vertices[ids]
    origin=points.mean(axis=0)
    shifted=points-origin
    small_limit=min(10.,extent*.12)
    large_limit=min(40.,extent*.35)
    if len(points)>EXTENDED_LOOP_EDGES:
        raise ValueError(f'Offene Randlinie zu groß für die Netzreparatur (maximal {EXTENDED_LOOP_EDGES} Kanten).')
    diameter=np.linalg.norm(points[:,None]-points[None,:],axis=2).max()
    if diameter>large_limit:
        raise ValueError(f'Offene Randlinie zu groß für die Netzreparatur (maximal {large_limit:.2f} mm).')
    large = diameter>small_limit or len(points)>MAX_LOOP_EDGES
    _,_,basis=np.linalg.svd(shifted,full_matrices=False)
    normal=basis[2]
    adjacent=mesh.vertices[mesh.faces[surrounding]]
    if np.max(abs(shifted@normal))>tolerance or np.max(abs((adjacent-origin)@normal))>tolerance:
        raise ValueError('Offene Randlinie liegt nicht in einer ebenen vorhandenen Fläche.')
    polygon=shifted@basis[:2].T
    vectors=np.roll(polygon,-1,axis=0)-polygon
    lengths=np.linalg.norm(vectors,axis=1)
    area2=cross2(polygon,np.roll(polygon,-1,axis=0)).sum()
    if abs(area2)<tolerance**2 or np.any(lengths<=tolerance):
        raise ValueError('Offene Randlinie ist geometrisch uneindeutig.')
    if area2<0:
        polygon[:,1]*=-1
        vectors[:,1]*=-1
        basis[1]*=-1
        area2=-area2
    validate_simple_polygon(polygon,vectors,lengths,tolerance)
    if large and not extended:
        raise ExtendedPlanarRepairAvailable(
            f'Ebene Öffnung mit {diameter:.2f} mm und {len(points)} Randkanten. '
            'Sie überschreitet die Grenze der normalen Importreparatur.')
    triangles=np.asarray(md.triangulate([polygon],tolerance,False))
    if triangles.shape!=(len(ids)-2,3) or np.any(triangles<0) or np.any(triangles>=len(ids)):
        raise ValueError('Offene Randlinie kann nicht eindeutig trianguliert werden.')
    flat_triangles=polygon[triangles]
    areas=cross2(flat_triangles[:,1]-flat_triangles[:,0],flat_triangles[:,2]-flat_triangles[:,0])
    if np.any(areas<=tolerance**2) or abs(areas.sum()-area2)>max(tolerance**2,area2*1e-8):
        raise ValueError('Offene Randlinie kann nicht eindeutig trianguliert werden.')
    convex=bool(np.all(cross2(vectors,np.roll(vectors,-1,axis=0))>0))

    lower=points.min(axis=0)-tolerance
    upper=points.max(axis=0)+tolerance
    possible=[]
    sources=[(mesh.vertices,mesh.faces,1)]
    if large and other_meshes is not None:
        sources.extend(other_meshes())
    for vertices,faces,scale in sources:
        for start in range(0,len(faces),65536):
            chunk=vertices[faces[start:start+65536]]*scale
            overlap=np.all(chunk.max(axis=1)>=lower,axis=1)&np.all(chunk.min(axis=1)<=upper,axis=1)
            possible.extend(chunk[overlap])
            if len(possible)>20000:
                raise ValueError('Zu viele nahe Flächen für eine eindeutige Reparatur.')
    # Clip each triangle against the interior of the cap and its plane.
    # Boundary contacts are allowed, crossings of the interior are ambiguous.
    for face in possible:
        triangle=face-origin
        flat=triangle@basis[:2].T
        height=triangle@normal
        if np.min(height)>tolerance or np.max(height)<-tolerance:
            continue
        if np.max(abs(height))<=tolerance:
            section=list(flat)
        else:
            section=[flat[i] for i in range(3) if abs(height[i])<=tolerance]
            for i,j in ((0,1),(1,2),(2,0)):
                if height[i]*height[j]<0:
                    section.append(flat[i]+(flat[j]-flat[i])*(height[i]/(height[i]-height[j])))
        if hits_patch(section,polygon,vectors,lengths,triangles,convex,tolerance):
            raise ValueError('Eine vorhandene Fläche kreuzt die geplante Reparatur.')
    return ids[triangles],large


def repair_surface(mesh, *, extended=False, other_meshes=None):
    order,starts,counts=edge_groups(mesh)
    if np.any(counts>2):
        raise ValueError(f'Nicht mannigfaltiges Netz: {int((counts>2).sum()):,} Kanten gehören zu mehr als zwei Flächen.')
    opened=int((counts==1).sum())
    if opened>MAX_HOLES*EXTENDED_LOOP_EDGES:
        raise ValueError(f'Das Netz ist offen ({opened:,} Randkanten). Zu viele offene Stellen für die automatische Reparatur.')
    flipped=0 if mesh.is_winding_consistent else fix_winding(mesh)
    if not opened:
        return {'holesClosed':0,'facesReoriented':flipped}
    order,starts,counts=edge_groups(mesh)
    extent=float(mesh.extents.max())
    tolerance=min(.001,max(1e-7,extent*1e-7))
    closed=large_closed=0
    try:
        for ids,faces in boundary_loops(mesh,order[starts[counts==1]]):
            if closed>=MAX_HOLES:
                raise ValueError('Zu viele einzelne offene Stellen.')
            cap,large=patch_for_loop(mesh,ids,faces,tolerance,extended=extended,extent=extent,other_meshes=other_meshes)
            closed+=1
            large_closed+=int(large)
            # Include each accepted cap when checking later caps for crossings.
            mesh.faces=np.vstack((mesh.faces,cap))
    except ValueError as error:
        error_type=ExtendedPlanarRepairAvailable if isinstance(error,ExtendedPlanarRepairAvailable) else ValueError
        raise error_type(f'Das Netz ist offen ({opened:,} Randkanten). {error}') from error
    return {'holesClosed':closed,'largeHolesClosed':large_closed,'facesReoriented':flipped}
