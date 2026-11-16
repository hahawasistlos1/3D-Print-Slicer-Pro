"""Continuous translational disassembly proofs using swept leading triangles.

This verifies one rigid translational strategy; it is not a general assembly
solver. Separate dowels are carried by their lower (A) host after preinsertion.
Those preinsertion paths are checked as well. A budget exhaustion is unknown,
never a proof of success. No sampling of intermediate positions is used.
"""
from dataclasses import dataclass
import math
import numpy as np
import manifold3d as md

MAX_BOOLEAN_TESTS = 12000
MAX_SWEEP_FACES = 60000
VOLUME_TOLERANCE = 1e-6  # mm^3; contacts without penetration are permitted.
PRISM_FACES = np.array([[0,2,1],[3,4,5],[0,1,4],[0,4,3],
                        [1,2,5],[1,5,4],[2,0,3],[2,3,5]],dtype=np.uint64)


@dataclass
class Body:
    name: str
    solid: object

    @property
    def box(self):return np.asarray(self.solid.bounding_box(),dtype=float)


class BudgetExceeded(Exception):pass


class MotionChecker:
    def __init__(self,max_tests=MAX_BOOLEAN_TESTS,max_faces=MAX_SWEEP_FACES):
        self.max_tests=max_tests;self.max_faces=max_faces
        self.tests=0;self.faces=0;self.initial_pairs={};self.initial_collisions=set();self.meshes={};self.exhausted=False

    def intersection_volume(self,a,b):
        if self.tests>=self.max_tests:raise BudgetExceeded()
        self.tests+=1
        result=a^b
        volume=float(result.volume())
        if result.status()!=md.Error.NoError or not math.isfinite(volume):
            raise ValueError('Ungültige Geometrie bei der Bewegungsprüfung.')
        return volume

    @staticmethod
    def overlaps(a,b):
        return bool(np.all(np.minimum(a[3:],b[3:])-np.maximum(a[:3],b[:3])>0))

    def check(self,moving,stationary,direction,distance):
        direction=np.asarray(direction,dtype=float)
        if direction.shape!=(3,) or not np.isfinite(direction).all() or not np.isclose(np.linalg.norm(direction),1,rtol=0,atol=1e-9):
            raise ValueError('Der Bewegungsweg benötigt eine Einheitsrichtung.')
        if not math.isfinite(distance) or distance<=0:raise ValueError('Bewegungsweg muss positiv sein.')
        delta=direction*distance
        residual_bounds={}
        def accumulate(obstacle,volume):
            residual_bounds[obstacle.name]=residual_bounds.get(obstacle.name,0.)+max(0.,volume)
            return residual_bounds[obstacle.name]>VOLUME_TOLERANCE
        try:
            if any(b.solid.is_empty() or b.solid.status()!=md.Error.NoError or not np.isfinite(b.box).all() for b in moving+stationary):
                return {'status':'unknown','reason':'invalid-body'}
            for body in moving:
                if body.solid.is_empty() or body.solid.status()!=md.Error.NoError:
                    return {'status':'unknown','reason':'invalid-body','body':body.name}
                box=body.box
                swept_box=np.r_[np.minimum(box[:3],box[:3]+delta),np.maximum(box[3:],box[3:]+delta)]
                obstacles=[o for o in stationary if self.overlaps(swept_box,o.box)]
                if not obstacles:continue
                for obstacle in obstacles:
                    pair=frozenset((body.solid,obstacle.solid))
                    if pair not in self.initial_pairs:
                        self.initial_pairs[pair]=self.intersection_volume(body.solid,obstacle.solid) if self.overlaps(box,obstacle.box) else 0.
                    if self.initial_pairs[pair]>VOLUME_TOLERANCE:
                        self.initial_collisions.add(tuple(sorted((body.name,obstacle.name))))
                        return {'status':'collision','reason':'initial-overlap','body':body.name,'obstacle':obstacle.name}
                # A conservative convex sweep can prove a free path cheaply.
                # Its overlap is never used alone to declare a collision.
                hull=md.Manifold.batch_hull([body.solid,body.solid.translate(delta)])
                uncertain=[]
                for obstacle in obstacles:
                    volume=self.intersection_volume(hull,obstacle.solid)
                    if volume>VOLUME_TOLERANCE:
                        uncertain.append(obstacle)
                        volume=self.initial_pairs[frozenset((body.solid,obstacle.solid))]
                    if accumulate(obstacle,volume):return {'status':'unknown','reason':'numerical-overlap-limit','obstacle':obstacle.name}
                if not uncertain:continue
                if body.solid not in self.meshes:
                    mesh=body.solid.to_mesh64()
                    verts=np.asarray(mesh.vert_properties)[:,:3];faces=np.asarray(mesh.tri_verts)
                    self.meshes[body.solid]=verts[faces]
                triangles=self.meshes[body.solid]
                normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
                leading=triangles[np.einsum('ij,j->i',normals,direction)>0]
                if self.faces+len(leading)>self.max_faces:raise BudgetExceeded()
                self.faces+=len(leading)
                for triangle in leading:
                    lo=triangle.min(axis=0);hi=triangle.max(axis=0)
                    prism_box=np.r_[np.minimum(lo,lo+delta),np.maximum(hi,hi+delta)]
                    relevant=[o for o in uncertain if self.overlaps(prism_box,o.box)]
                    if not relevant:continue
                    maximum_volume=float(np.dot(np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0]),delta)/2)
                    if maximum_volume<=VOLUME_TOLERANCE:
                        for obstacle in relevant:
                            if accumulate(obstacle,maximum_volume):return {'status':'unknown','reason':'numerical-overlap-limit','obstacle':obstacle.name}
                        continue
                    vertices=np.ascontiguousarray(np.vstack((triangle,triangle+delta)),dtype=np.float64)
                    prism=md.Manifold(md.Mesh64(vertices,PRISM_FACES))
                    if prism.status()!=md.Error.NoError or prism.is_empty():
                        return {'status':'unknown','reason':'invalid-sweep-prism','body':body.name}
                    for obstacle in relevant:
                        volume=self.intersection_volume(prism,obstacle.solid)
                        if volume>VOLUME_TOLERANCE:
                            return {'status':'collision','reason':'continuous-sweep-overlap','body':body.name,
                                    'obstacle':obstacle.name,'sweptOverlapVolume':volume}
                        if accumulate(obstacle,volume):return {'status':'unknown','reason':'numerical-overlap-limit','obstacle':obstacle.name}
            return {'status':'clear','reason':'continuous-sweep-proof'}
        except BudgetExceeded:
            self.exhausted=True
            return {'status':'unknown','reason':'budget-exhausted'}
        except ValueError:
            return {'status':'unknown','reason':'invalid-sweep-geometry'}


def removal_distance(moving,stationary,direction):
    moving_box=np.array([b.box for b in moving])
    if not stationary:return max(1.,float((moving_box[:,3:]-moving_box[:,:3]).max()))
    fixed_box=np.array([b.box for b in stationary])
    gap=max(1.,float((fixed_box[:,3:].max(axis=0)-fixed_box[:,:3].min(axis=0)).max())*.005)
    normal=np.asarray(direction)
    moving_min=(np.where(normal>=0,moving_box[:,:3],moving_box[:,3:])@normal).min()
    fixed_max=(np.where(normal>=0,fixed_box[:,3:],fixed_box[:,:3])@normal).max()
    distance=fixed_max-moving_min+gap
    return max(gap,float(distance))


def joint_direction(joint):
    if 'removalDirection' in joint:return joint['removalDirection']
    return joint['normal'] if 'normal' in joint else [int(a==joint['axis']) for a in range(3)]


def allowed_directions(part,joints,remaining):
    constraints=[]
    for joint in joints:
        if joint['a'] not in remaining or joint['b'] not in remaining:continue
        if part not in (joint['a'],joint['b']):continue
        sign=1 if part==joint['b'] else -1
        direction=[v*sign for v in joint_direction(joint)]
        if not any(np.allclose(direction, previous, atol=1e-9, rtol=0) for previous in constraints):
            constraints.append(direction)
    if len(constraints)>1:return []
    return constraints or [[sign if a==axis else 0 for a in range(3)] for axis in range(3) for sign in (1,-1)]


def analyze_assembly(parts,joints,separate,progress=lambda p,m:None,max_tests=MAX_BOOLEAN_TESTS,max_faces=MAX_SWEEP_FACES):
    """Parts are in assembly coordinates. `separate` contains (joint-id,solid)."""
    checker=MotionChecker(max_tests,max_faces)
    bodies={i+1:Body(f'part:{i+1}',p['solid']) for i,p in enumerate(parts)}
    pins={name:Body(f'pin:{name}',solid) for name,solid in separate}
    hosts={j['id']:j['a'] for j in joints if j['mode']=='separate'}
    joint_by_id={j['id']:j for j in joints}
    preinsert=[];unresolved_pins=[]
    for host in sorted(set(hosts.values())):
        todo=sorted(name for name,h in hosts.items() if h==host)
        removals=[]
        while todo:
            found=False
            for name in list(todo):
                joint=joint_by_id[name]
                direction=joint.get('pinWithdrawal', joint_direction(joint))
                fixed=[bodies[host]]+[pins[n] for n in todo if n!=name]
                distance=removal_distance([pins[name]],fixed,direction)
                check=checker.check([pins[name]],fixed,direction,distance)
                if check['status']=='clear':
                    removals.append({'connector':name,'host':host,'direction':direction,'distance':distance})
                    todo.remove(name);found=True;break
                if check['status']=='unknown' and check['reason']=='budget-exhausted':break
            if not found:unresolved_pins.extend(todo);break
        preinsert.extend({'connector':s['connector'],'host':host,'distance':s['distance'],
                          'fromOffset':[v*s['distance'] for v in s['direction']],
                          'insertionDirection':[-v for v in s['direction']]} for s in reversed(removals))
    remaining=set(bodies);removed=[];last_failures=[]
    while len(remaining)>1:
        found=False;last_failures=[]
        # Parts with fewer active joints are often removable first. Stable
        # ordering makes the proof reproducible, without claiming an optimum.
        order=sorted(remaining,key=lambda p:(sum(1 for j in joints if j['a'] in remaining and j['b'] in remaining and p in (j['a'],j['b'])),p))
        for part in order:
            directions=allowed_directions(part,joints,remaining)
            if not directions:
                last_failures.append({'part':part,'status':'unknown','reason':'multiple-insertion-directions'});continue
            moving=[bodies[part]]+[pin for name,pin in pins.items() if hosts[name]==part]
            fixed=[bodies[p] for p in sorted(remaining) if p!=part]+[pin for name,pin in pins.items() if hosts[name] in remaining and hosts[name]!=part]
            for direction in directions:
                distance=removal_distance(moving,fixed,direction)
                check=checker.check(moving,fixed,direction,distance)
                if check['status']=='clear':
                    removed.append({'part':part,'direction':direction,'distance':distance,
                                    'carriedConnectors':[name for name,h in hosts.items() if h==part],
                                    'proof':'continuous-swept-triangles-v1'})
                    remaining.remove(part);found=True;break
                last_failures.append({'part':part,'direction':direction,**check})
                if check['status']=='unknown' and check['reason']=='budget-exhausted':break
            if found:break
            if checker.exhausted:break
        progress(min(94,86+len(removed)//2),f'Montagewege prüfen · {len(removed)}/{max(0,len(parts)-1)} Teile gelöst')
        if not found:break
    verified=len(remaining)==1 and not unresolved_pins
    base=sorted(remaining)
    assembly_steps=[{'part':p,'base':True} for p in base]+[
        {'part':s['part'],'base':False,'fromOffset':[v*s['distance'] for v in s['direction']],
         'insertionDirection':[-v for v in s['direction']],'distance':s['distance'],
         'carriedConnectors':s['carriedConnectors']} for s in reversed(removed)]
    return {'checked':True,'status':'verified' if verified else 'unresolved','pathVerified':verified,
            'method':'continuous-swept-triangles-v1','scope':'joint-direction-and-axis-translations-with-preinserted-pins',
            'volumeTolerance':VOLUME_TOLERANCE,'booleanTests':checker.tests,'sweptFaces':checker.faces,
            'budgetReached':checker.exhausted,
            'remainingParts':base,'unresolvedPins':unresolved_pins,'preinsertSteps':preinsert,
            'initialCollisions':[list(p) for p in sorted(checker.initial_collisions)],
            'disassemblySteps':removed,'assemblySteps':assembly_steps,'lastFailures':last_failures,
            'limitations':['Geradlinige Einzelteilbewegungen entlang XYZ oder der Verbinderrichtung; keine Drehungen oder flexiblen Verformungen.',
                           'Vorgegebene Teilepositionen, vorbestückte Dübel und numerische Volumentoleranz; keine Reibungs- oder Festigkeitsprüfung.']}
