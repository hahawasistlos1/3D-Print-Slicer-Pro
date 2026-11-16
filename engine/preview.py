"""Separate closed display meshes; never a source for slicing or export.

Native simplification uses a subset of source vertices within its tolerance:
https://manifoldcad.org/docs/html/classmanifold_1_1_manifold.html
Display candidates must additionally preserve signed shells/handles, volume
and bounds. A missed triangle budget retains the best complete mesh.
"""
from pathlib import Path
import json
import math
import manifold3d as md
import numpy as np
from geometry import load_model, mesh_of
from indexed_mesh import write_indexed

MAX_VOLUME_ERROR=.005
MAX_TOLERANCE=.25
MAX_ITEMS=513


def topology(solid):
    return sorted((1 if s.volume()>0 else -1,int(s.genus())) for s in solid.decompose())


def simplify_preview(solid,budget):
    if not isinstance(budget,int) or isinstance(budget,bool) or not 12<=budget<=2_000_000:
        raise ValueError('Vorschauziel muss zwischen 12 und 2 Millionen Dreiecken liegen.')
    if solid.is_empty() or solid.status()!=md.Error.NoError or not math.isfinite(solid.volume()) or solid.volume()<=0:
        raise ValueError('Vorschau benötigt einen gültigen geschlossenen Körper.')
    original_mesh=mesh_of(solid)
    if not original_mesh.is_watertight or not original_mesh.is_winding_consistent:
        raise ValueError('Die Vorschauquelle ist kein geschlossenes konsistentes Netz.')
    source_count=solid.num_tri();volume=float(solid.volume());box=np.asarray(solid.bounding_box())
    if not np.isfinite(box).all():raise ValueError('Ungültige Vorschaukoordinaten.')
    size=float((box[3:]-box[:3]).max());limit=min(MAX_TOLERANCE,size*.001)
    best=solid;used=0.;volume_error=0.;bounds_error=0.;attempts=0
    if source_count>budget:
        signature=topology(solid)
        for tolerance in (0.,limit*.01,limit*.04,limit*.16,limit*.4,limit):
            attempts+=1
            candidate=solid.simplify(tolerance)
            if candidate.is_empty() or candidate.status()!=md.Error.NoError:continue
            candidate_volume=float(candidate.volume())
            error=abs(candidate_volume/volume-1)
            candidate_box=np.asarray(candidate.bounding_box());delta=float(np.max(np.abs(candidate_box-box)))
            if not math.isfinite(error) or not np.isfinite(candidate_box).all() or candidate_volume<=0:continue
            if error>MAX_VOLUME_ERROR or delta>tolerance*1.01+size*1e-7:continue
            if candidate.num_tri()>=best.num_tri() or topology(candidate)!=signature:continue
            mesh=mesh_of(candidate)
            if not mesh.is_watertight or not mesh.is_winding_consistent:continue
            best=candidate;used=float(tolerance);volume_error=float(error);bounds_error=delta
            if best.num_tri()<=budget:break
    return best,{'sourceTriangles':source_count,'triangles':best.num_tri(),'budget':budget,
        'budgetReached':best.num_tri()<=budget,'reduced':best.num_tri()<source_count,
        'tolerance':used,'maxTolerance':limit,'volumeError':volume_error,'boundsError':bounds_error,
        'watertight':True,'topologyPreserved':True,'attempts':attempts,
        'method':'closed-manifold-simplify-v1','reason':'complete' if best.num_tri()==source_count else 'simplified'}


def prepare_previews(items,folder,progress=lambda p,m:None):
    if not isinstance(items,list) or not 1<=len(items)<=MAX_ITEMS:
        raise ValueError('Ungültige Anzahl Vorschauquellen.')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    records=[];keys=set()
    for i,item in enumerate(items):
        key=item['key']
        if not isinstance(key,str) or not key or key in keys:raise ValueError('Vorschaukennungen müssen eindeutig sein.')
        keys.add(key)
        progress(int(90*i/len(items)),f'Geschlossene Vorschau aufbauen · {i+1}/{len(items)}')
        # Internal part STLs use assembly coordinates: never normalise them.
        solid=load_model(item['input'],normalize=False,use_indexed=True)
        shape,record=simplify_preview(solid,item['budget'])
        name=f'Anzeige_{i:03}.mesh'
        # The viewport draws these arrays directly. Rebuilding a Manifold can
        # retriangulate identical input and does not verify what WPF will read.
        write_indexed(shape,folder/name,verify=True)
        records.append({'key':key,'file':name,**record})
    # Publish only complete batches. The caller caches results after success.
    (folder/'preview.json').write_text(json.dumps({'items':records},ensure_ascii=False,indent=2),encoding='utf-8')
    progress(100,'Geschlossene Vorschau bereit')
    return records
