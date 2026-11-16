"""Printable snap clips and exterior-access screws in a seam-local frame."""
import math
from functools import lru_cache
import numpy as np
import manifold3d as md

from manual_planes import transform


def seam_frame(axis, rotation):
    return rotation if rotation is not None else np.eye(3)[[(axis+1)%3,(axis+2)%3,axis]]


def make_clip(center, axis, tangent, rotation, settings):
    frame = seam_frame(axis, rotation)
    if tangent == (axis+2)%3:
        frame = np.stack((frame[1],-frame[0],frame[2]))
    origin = center if rotation is None else rotation.T @ center
    def place(shape):
        return transform(shape,frame.T).translate(origin)
    width,depth=settings['diameter'],settings['depth']
    play,wall=settings['tolerance'],settings['wall']
    outer=.40*width
    hook=.50*width
    half_span=.30*width
    thickness=max(1.2,.15*width)
    root=.14*depth
    shoulder=.72*depth
    deflection=hook-outer-play/2
    span=shoulder-root
    strain=150*thickness*deflection/span**2
    tip_deflection=deflection*(1+1.5*(depth-shoulder)/span)
    if deflection<=0 or outer-thickness-tip_deflection<.15 or strain>settings['clipStrainPercent'] or play>=span:
        return None
    profile=[(outer-thickness,root*.80),(outer,root*.80),(outer,shoulder),
             (hook,shoulder),(outer,depth),(outer-thickness,depth)]
    # Map profile coordinates (X,Z) and extrusion to (X,-Y,Z).
    arm=md.CrossSection([profile]).extrude(2*half_span).rotate((90,0,0)).translate((0,half_span,0))
    root_body=md.Manifold.cube((outer*2,half_span*2,root*2),center=True)
    arms=[arm,arm.mirror((1,0,0))]
    pin=md.Manifold.batch_boolean([root_body,*arms,*(a.mirror((0,0,1)) for a in arms)],md.OpType.Add)
    throat=md.Manifold.cube((outer*2+play,half_span*2+play,2*(depth+play)),center=True)
    pocket_start=shoulder-play
    pocket=md.Manifold.cube((hook*2+play,half_span*2+play,depth+play-pocket_start)).translate((-hook-play/2,-half_span-play/2,pocket_start))
    socket=throat+pocket+pocket.mirror((0,0,1))
    probe=md.Manifold.cube((width+play+2*wall,half_span*2+play+2*wall,2*(depth+play+wall)),center=True)
    return place(pin),place(socket),place(probe),{'clipStrainPercent':strain,'clipDeflection':deflection}


@lru_cache(maxsize=12)
def thread_profile(radius, pitch, start, stop, flank, clearance=0., lead=False):
    """Closed, single-start right-hand thread sampled around one analytic helix."""
    segments=64
    step=pitch/24
    levels=np.r_[start,np.arange(math.floor(start/step)+1,math.ceil(stop/step))*step,stop]
    levels=np.unique(levels[(levels>=start)&(levels<=stop)])
    angle=np.arange(segments)*2*np.pi/segments
    phase=(levels[:,None]/pitch-angle[None,:]/(2*np.pi))%1
    profile=np.clip((.44-abs(phase-.5))/.24,0,1)
    taper=np.minimum(1,np.minimum(levels-start,stop-levels)/(pitch*.7))[:,None] if lead else 1
    radii=radius-flank+clearance+profile*flank*taper
    vertices=np.stack((radii*np.cos(angle),radii*np.sin(angle),np.broadcast_to(levels[:,None],radii.shape)),axis=-1).reshape(-1,3)
    count=len(vertices)
    vertices=np.vstack((vertices,[0,0,start],[0,0,stop]))
    i=np.arange(segments)
    following=np.roll(i,-1)
    row=np.arange(len(levels)-1)[:,None]*segments
    a,b=row+i,row+following
    sides=np.stack((a,b,a+segments,b,b+segments,a+segments),axis=-1).reshape(-1,3)
    bottom=np.stack((np.full(segments,count),following,i),axis=-1)
    top=np.stack((np.full(segments,count+1),i+count-segments,following+count-segments),axis=-1)
    return md.Manifold(md.Mesh64(np.ascontiguousarray(vertices,dtype=np.float64),
                                  np.ascontiguousarray(np.vstack((sides,bottom,top)),dtype=np.uint64)))


def make_screw(a, b, axis, center, offset, rotation, settings, outside):
    frame=seam_frame(axis,rotation)
    origin=center if rotation is None else rotation.T @ center
    def place(shape):
        return transform(shape,frame.T).translate(origin)
    def tube(z,height,radius,segments=64):
        return md.Manifold.cylinder(height,radius,circular_segments=segments).translate((0,0,z))
    radius=settings['diameter']/2
    length,pitch=settings['threadLength'],settings['threadPitch']
    play,wall=settings['tolerance'],settings['wall']
    flank=.40*pitch
    if flank>=radius*.65 or play>=flank or not 2<=length/pitch<=20:
        return None
    entry=transform(a['base'],frame).bounding_box()[2]-offset
    if entry> -wall:
        return None
    head_radius=radius*1.55
    head_height=max(2.,pitch*1.2)
    reserve=radius+play/2+wall
    through_probe=place(tube(entry,-entry,reserve))
    tap_probe=place(tube(0,length+play+wall,reserve))
    for part,probe in ((a,through_probe),(b,tap_probe)):
        if (probe-part['base']).volume()>max(1e-6,probe.volume()*1e-7):
            return None
    head=place(tube(entry-head_height,head_height,head_radius,6))
    # Reserve a full cylinder around the hex head for tool access near A.
    outside=min(outside,entry-head_height-wall)
    head_space=place(tube(outside,entry-outside,head_radius+wall))
    if (head_space^a['base']).volume()>1e-6:
        return None
    shank=place(tube(entry-.05,-entry+.10,radius-flank))
    male=place(thread_profile(radius,pitch,0,length,flank,lead=True))
    pin=head+shank+male
    bore=place(tube(entry-head_height,-entry+head_height+.02,radius+play/2))
    female=place(thread_profile(radius,pitch,-.02*pitch,length+play,flank,clearance=play/2))
    return pin,bore,female,[through_probe,tap_probe,head_space],{
        'pitch':pitch,'threadLength':length,'gripLength':-entry,'headDiameter':head_radius*2}
