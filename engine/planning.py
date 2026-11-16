"""Geometry-aware, bounded axis-aligned partition planning.

Each connected body is processed independently. Cuts are local to a branch of
the partition tree, never a global grid. Scores are heuristics, not strength or
assembly proofs. All selected cuts still go through Manifold's real Booleans.
"""
import itertools
import math
import numpy as np
import manifold3d as md
from components import material_components

MAX_EVALUATIONS = 1024
EPS_VOLUME = 1e-7


def bounds(solid):
    return np.asarray(solid.bounding_box(), dtype=float)


def section_body(solid, axis):
    """Map XYZ to a right-handed cyclic frame whose Z is the cut normal."""
    axes = [(axis+1) % 3, (axis+2) % 3, axis]
    matrix = np.column_stack((np.eye(3)[axes], np.zeros(3)))
    return solid.transform(matrix)


def envelope_radius(settings):
    radius = settings['diameter']/2 + settings['tolerance']/2 + settings['wall']
    if settings.get('kind') == 'dovetail':
        return radius + settings['diameter']/4
    # A circle enclosing a square is conservative; the final 3D probe uses
    # the actual square and is always checked separately.
    if settings.get('kind') != 'rect':
        return radius
    height = settings.get('rectHeight', 0) or settings['diameter']
    return math.hypot(radius, height/2 + settings['tolerance']/2 + settings['wall'])


def capacity_options(settings, usable):
    reserve = settings['depth'] if settings.get('mode') in ('integrated', 'mixed') else 0
    permutations = itertools.permutations(range(3)) if settings.get('optimize', True) else [(0, 1, 2)]
    options = [np.asarray(usable)[list(p)] - reserve for p in permutations]
    options = [c for c in options if c.min() > 1]
    if not options:
        raise ValueError('Einstecktiefe ist zu groß für diesen Druckraum.')
    return options


def estimate_count(solid, options):
    box = bounds(solid)
    return min(math.prod(np.maximum(1, np.ceil((box[3:]-box[:3])/c-1e-10)).astype(int)) for c in options)


def section_quality(rotated, offset, settings, scale):
    cross = rotated.slice(float(offset))
    area = cross.area()
    if area <= max(1e-10, scale*scale*1e-12):
        return None
    components = cross.decompose()
    radius = envelope_radius(settings)
    inner = cross.offset(-radius, circular_segments=16)
    # Penalise faces made up of thin islands, rather than favouring a tiny
    # cross-sectional area that cannot carry any selected connector.
    weak = sum(1 for c in components if c.offset(-radius, circular_segments=16).is_empty())
    core = inner
    if settings.get('mode', 'separate') != 'none':
        reach = settings['depth']+settings['tolerance']+settings['wall']
        for direction in (-1, 1):
            at_depth = rotated.slice(float(offset+direction*reach)).offset(-radius, circular_segments=16)
            core = core ^ at_depth
    core_area = max(0.0, core.area())
    has_core = core_area > max(1e-9, scale*scale*1e-12)
    score = 18 * max(0, len(components)-1) + 28 * weak
    if settings.get('mode', 'separate') != 'none' and not has_core:
        score += 180
    # Area and balance are subordinate to avoiding thin/disconnected islands.
    score += 3 * area/max(scale*scale, 1e-8)
    if has_core:
        score += 8 * (1-min(1, core_area/area))
    return {'score':float(score), 'area':float(area), 'regions':len(components),
            'weakRegions':weak, 'connectorCoreArea':float(core_area)}


def adaptive_partition(solid, settings, usable, max_parts, progress=lambda p,m: None):
    options = capacity_options(settings, usable)
    pending = [(s, [], 0) for s in reversed(material_components(solid)) if s.volume() > EPS_VOLUME]
    leaves, selected = [], []
    evaluated = 0
    budget_reached = False
    model_box = bounds(solid)
    if any((np.asarray(s.bounding_box())[3:]-np.asarray(s.bounding_box())[:3]).max()>max(float(c.max()) for c in options)*max_parts for s,_,_ in pending):
        raise ValueError(f'Modellspanne erfordert mehr als {max_parts} Druckteile.')
    for axis, key in enumerate('xyz'):
        values = sorted(set(float(v) for v in settings.get('cuts',{}).get(key,[])))
        if any(not math.isfinite(v) or v<=model_box[axis] or v>=model_box[axis+3] for v in values):
            raise ValueError('Manuelle Schnitte müssen innerhalb des Modells liegen.')
        for offset in values:
            next_pending=[]
            normal=[0,0,0];normal[axis]=1
            for shape,ancestors,depth in pending:
                box=bounds(shape)
                if not box[axis]+1e-7 < offset < box[axis+3]-1e-7:
                    next_pending.append((shape,ancestors,depth));continue
                high,low=shape.split_by_plane(normal,offset)
                face={'axis':axis,'offset':float(offset)}
                selected.append({**face,'bounds':box.tolist(),'manual':True})
                for side in (low,high):
                    for child in material_components(side):
                        if not child.is_empty() and child.volume()>EPS_VOLUME:
                            next_pending.append((child,ancestors+[face],depth+1))
            pending=next_pending
            if len(pending)>max_parts:
                raise ValueError('Zu viele Teilkörper durch manuelle Schnittvorgaben.')
    while pending:
        shape, ancestors, depth = pending.pop()
        if len(leaves)+len(pending) >= max_parts:
            raise ValueError(f'Adaptive Teilung überschreitet {max_parts} Teile. Größeren Druckraum wählen.')
        box = bounds(shape); dims = box[3:]-box[:3]
        if any(np.all(dims <= cap+1e-6) for cap in options):
            faces = [f for f in ancestors if abs(box[f['axis']]-f['offset']) < 1e-5 or abs(box[f['axis']+3]-f['offset']) < 1e-5]
            leaves.append((shape, faces))
            continue
        if depth >= 32:
            raise ValueError('Adaptive Planung erreicht die maximale Tiefe. Modell/Druckraum prüfen.')
        capacity = min(options, key=lambda c: (math.prod(np.maximum(1,np.ceil(dims/c-1e-10))), sum(dims/c)))
        oversized = sorted([a for a in range(3) if dims[a] > capacity[a]+1e-6], key=lambda a:-dims[a]/capacity[a])
        proposals = []
        for axis in oversized[:2]:
            count = int(math.ceil(dims[axis]/capacity[axis]-1e-10))
            low_count = count//2
            nominal = box[axis] + dims[axis]*low_count/count
            lower = max(box[axis]+dims[axis]-(count-low_count)*capacity[axis], box[axis]+dims[axis]*.08)
            upper = min(box[axis]+low_count*capacity[axis], box[axis+3]-dims[axis]*.08)
            if lower > upper:
                # An exact capacity multiple can round its two bounds in
                # opposite directions when the body is far from the origin.
                if lower-upper > max(1e-9, max(abs(lower),abs(upper))*1e-14):
                    continue
                lower = upper = (lower+upper)/2
            rotated = section_body(shape, axis)
            positions = sorted(set([float(nominal)] + [float(v) for v in np.linspace(lower,upper,7)]))
            for offset in positions:
                if evaluated >= MAX_EVALUATIONS:
                    budget_reached = True
                    # Preserve deterministic progress after the scoring budget.
                    quality = {'score':0., 'area':0., 'regions':0, 'weakRegions':0, 'connectorCoreArea':0.}
                    if abs(offset-nominal) > 1e-6:
                        continue
                else:
                    quality = section_quality(rotated, offset, settings, float(dims.max()))
                    evaluated += 1
                if quality is None:
                    continue
                balance = abs(offset-nominal)/max(dims[axis],1e-8)
                proposals.append((quality['score']+3*balance, axis, offset, quality))
        if not proposals:
            raise ValueError('Kein gültiger adaptiver Schnitt gefunden. Rasterteilung oder manuelle Ebenen verwenden.')
        candidates = []
        # Exact splitting is more expensive than cross sections. Evaluate the
        # best few proposals, including all resulting disconnected components.
        for score, axis, offset, quality in sorted(proposals,key=lambda c:(c[0],c[1],c[2]))[:4]:
            normal = [0,0,0]; normal[axis] = 1
            high, low = shape.split_by_plane(normal, offset)
            low_parts = [s for s in material_components(low) if s.volume() > EPS_VOLUME]
            high_parts = [s for s in material_components(high) if s.volume() > EPS_VOLUME]
            children = low_parts+high_parts
            if not low_parts or not high_parts:
                continue
            fragments = max(0,len(children)-2)
            count_estimate = sum(estimate_count(s,options) for s in children)
            # Fragmentation is explicitly penalised so a small detail cannot
            # win merely by offering a small cutting area.
            total_score = score + 45*fragments + 7*count_estimate
            candidates.append((total_score,axis,offset,quality,children))
        if not candidates:
            raise ValueError('Adaptive Schnitte erzeugen keine gültigen Teilkörper. Bitte Rasterteilung verwenden.')
        _, axis, offset, quality, children = min(candidates,key=lambda c:(c[0],c[1],c[2]))
        face = {'axis':axis,'offset':float(offset)}
        selected.append({**face,'bounds':box.tolist(),**quality})
        for child in reversed(children):
            pending.append((child,ancestors+[face],depth+1))
        progress(min(33,8+len(selected)//2),f'Adaptive Schnittplanung · {len(selected)} lokale Schnitte · {evaluated} Querschnitte')
    cuts = [sorted(set(c['offset'] for c in selected if c['axis']==a)) for a in range(3)]
    return leaves, cuts, {'algorithm':'adaptive-axis-v1','evaluatedPlanes':evaluated,
                          'localCuts':selected,'budgetReached':budget_reached}


def common_interface(a, b, axis, offset, epsilon):
    """Intersect actual cross sections just inside both adjacent solids."""
    return section_body(a,axis).slice(float(offset-epsilon)) ^ section_body(b,axis).slice(float(offset+epsilon))


def face_candidates(region, axis, offset, radius, limit=320, half_extents=None):
    """Search each eroded connected face, including narrow ring boundaries.

    These are proposals only. The caller must check a full 3D containment probe
    across the complete insertion length before drilling or adding geometry.
    """
    if half_extents is None:
        safe = region.offset(-radius,circular_segments=24)
    else:
        # Necessary centre/corner constraints for a rectangular footprint.
        # Concave bridges and holes are rejected by the full 3D probe later.
        hx,hy=half_extents
        safe=region
        for x,y in itertools.product((-hx,hx),(-hy,hy)):
            safe=safe ^ region.translate((-x,-y))
    if safe.is_empty() or safe.area()<=1e-10:
        return
    pieces = sorted([c for c in safe.decompose() if not c.is_empty() and c.area()>1e-10],key=lambda c:-c.area())
    seen = set()
    tangents = [(axis+1)%3,(axis+2)%3]
    proposed = 0
    for component in pieces:
        lo_x,lo_y,hi_x,hi_y = component.bounds()
        points = [((lo_x+hi_x)/2,(lo_y+hi_y)/2)]
        contours = component.to_polygons()
        for polygon in contours:
            if len(polygon)<2: continue
            stride = max(1,int(math.ceil(len(polygon)/48)))
            for i in range(0,len(polygon),stride):
                points.append(tuple(polygon[i]))
                points.append(tuple((polygon[i]+polygon[(i+1)%len(polygon)])/2))
        fractions = [.25,.75,.5,.125,.875]
        points.extend((lo_x+u*(hi_x-lo_x),lo_y+v*(hi_y-lo_y)) for u,v in itertools.product(fractions,repeat=2))
        for u,v in points:
            if not math.isfinite(u) or not math.isfinite(v):continue
            key=(round(float(u),6),round(float(v),6))
            if key in seen: continue
            seen.add(key)
            center=np.zeros(3); center[axis]=offset;center[tangents[0]]=u;center[tangents[1]]=v
            yield center
            proposed += 1
            if proposed >= limit: return
