"""Side-loaded dovetails with solid wall reserves up to one open end."""
import itertools
import numpy as np
import manifold3d as md


def rail(axis, tangent, center, width, depth, start, stop, clearance=0):
    """Extrude a double dovetail in a right-handed frame along the slide axis."""
    across = 3-axis-tangent
    half = width/2
    flare = half * 1.5
    profile = [(-flare,-depth),(flare,-depth),(half,0),(flare,depth),(-flare,depth),(-half,0)]
    section = md.CrossSection([profile])
    if clearance:
        section = section.offset(clearance, md.JoinType.Miter)
    basis = np.eye(3)[:, [across,axis,tangent]]
    if np.linalg.det(basis)<0:
        basis[:,0] *= -1
    origin = np.asarray(center) + np.eye(3)[tangent]*start
    return section.extrude(stop-start).transform(np.column_stack((basis,origin)))


def dovetail_candidates(region, axis, offset, settings, search):
    length=settings['tongueLength']
    reserve=settings['tolerance']/2+settings['wall']
    tangents=[(axis+1)%3,(axis+2)%3]
    # Interleave the two orientations to avoid exhausting a face on one axis.
    sources=[]
    for i,tangent in enumerate(tangents):
        half=[settings['diameter']*.75+reserve]*2
        half[i]=length/2+reserve
        sources.append(zip(search(region,axis,offset,0,limit=40,half_extents=half),itertools.repeat(tangent)))
    for row in itertools.zip_longest(*sources):
        for proposal in row:
            if proposal is not None:
                yield proposal


def make_dovetail(a, b, axis, tangent, center, offset, rotation, settings, mode, transform):
    """Return geometry only for a closed cross-section with a planar entry end.

    Wall probes stop at the entry plane. The cutting tool continues outside it.
    A separate key uses the same open side of both grooves for preinsertion.
    """
    model=lambda shape: shape if rotation is None else transform(shape,rotation.T)
    local=lambda shape: shape if rotation is None else transform(shape,rotation)
    normal = np.eye(3)[axis] if rotation is None else rotation[axis]
    width,depth,length=settings['diameter'],settings['depth'],settings['tongueLength']
    tolerance,wall=settings['tolerance'],settings['wall']
    half=length/2
    pin=model(rail(axis,tangent,center,width,depth,-half,half))
    end_box={side:local(part['base']).bounding_box() for side,part in ((-1,a),(1,b))}
    for direction in (1,-1):
        probes=[];sockets={}
        for side,part in ((-1,a),(1,b)):
            if side<0 and mode=='integrated':
                # A root with the specified reserve must remain inside A.
                end=direction*(half+tolerance/2+wall)
            else:
                extreme=end_box[side][tangent+(3 if direction>0 else 0)]
                end=extreme-center[tangent]
            tail=-direction*(half+tolerance/2+wall)
            if direction*(end-tail)<length+tolerance+wall:
                break
            tool=model(rail(axis,tangent,center,width,depth,*sorted((tail,end)),tolerance/2+wall))
            pos,neg=tool.split_by_plane(normal,offset)
            probe=pos if side>0 else neg
            if probe.is_empty() or (probe-part['base']).volume()>max(1e-6,probe.volume()*1e-7):
                break
            probes.append(probe)
            if side<0 and mode=='integrated':
                continue
            start=-direction*(half+tolerance/2)
            stop=end+direction*max(1,wall)
            sockets[side]=model(rail(axis,tangent,center,width,depth,*sorted((start,stop)),tolerance/2))
        else:
            travel=np.eye(3)[tangent]*direction
            if rotation is not None:
                travel=rotation.T @ travel
            return pin,sockets.get(-1),sockets[1],probes,travel
    return None
