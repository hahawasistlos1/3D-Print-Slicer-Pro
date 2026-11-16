"""One isolated process per job; stdout contains newline-delimited JSON events."""
import json
import sys
import traceback
from pathlib import Path
import numpy as np
from geometry import load_model, write_stl, info, slice_model, demo_dragon
from exporting import export_file
from preview import prepare_previews
from orientation import write_rotated_model
from indexed_mesh import indexed_path
from color_slicing import import_colors, load_colors, save_colors, volume_matches


def emit(progress, message):
    print(json.dumps({'progress':progress,'message':message},ensure_ascii=False),flush=True)


def save_model(folder,data,metadata,bodies):
    if metadata or bodies:
        data['colorSeparation']=save_colors(folder,metadata,bodies)
    (folder/'model.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    folder=Path(request['output']);folder.mkdir(parents=True,exist_ok=True)
    command=request['command']
    if command in ('import','demo','scale'):
        emit(5,'3D-Geometrie einlesen und prüfen …')
        repair={} if command=='import' else None
        source=Path(request['input']) if command!='demo' else None
        indexed=source is not None and (source.suffix.lower()=='.3mf' or (command=='scale' and indexed_path(source).is_file()))
        if command=='import' and source.suffix.lower()=='.stl':
            # ASCII can store coordinates more precisely than the internal STL.
            with source.open('rb') as stream:
                indexed=stream.read(80).lstrip().lower().startswith(b'solid')
        scale=request.get('scale',1)
        source_colors={} if command=='import' and source.suffix.lower()=='.3mf' else None
        shape=demo_dragon() if command=='demo' else load_model(source,scale,repair_report=repair,use_indexed=command=='scale',color_source=source_colors)
        write_stl(shape,folder/'original.stl',indexed=indexed or bool(repair))
        data={'name':request.get('name',Path(request.get('input','Demo-Drache')).stem),'original':info(shape)}
        if repair:
            data['repair']=repair
        metadata,bodies={},[]
        if source_colors is not None:
            metadata,bodies=import_colors(source_colors,shape,scale,repair)
        if command=='scale':
            metadata,bodies=load_colors(source.parent)
            if bodies:
                low=np.asarray(load_model(source,normalize=False,use_indexed=True).bounding_box()[:3])
                bodies=[(color,body.scale((scale,)*3).translate(-low*scale)) for color,body in bodies]
        save_model(folder,data,metadata,bodies)
        emit(100,'Modell geladen · Netz repariert und geprüft' if repair else 'Modell geladen · geschlossenes Netz')
    elif command=='rotate':
        emit(5,'Vollständiges Modell neu ausrichten …')
        data,orientation=write_rotated_model(request['input'],folder,request['angles'])
        source=Path(request['input'])
        metadata,bodies=load_colors(source.parent)
        if bodies:
            affine=np.column_stack((orientation['matrix'],np.zeros(3)))
            assembled=load_model(source,normalize=False,use_indexed=True)
            low=np.asarray(assembled.transform(affine).bounding_box()[:3])
            bodies=[(color,body.transform(affine).translate(-low)) for color,body in bodies]
        save_model(folder,{'name':request.get('name','Ausgerichtetes Modell'),'original':data,'orientation':orientation},metadata,bodies)
        emit(100,'Modellausrichtung gespeichert · geschlossenes Netz und Volumen geprüft')
    elif command=='preview':
        prepare_previews(request['items'],folder,emit)
    elif command=='slice':
        source=Path(request['input'])
        shape=load_model(source,use_indexed=True)
        bodies=None
        if request['settings'].get('strategy')=='color':
            metadata,bodies=load_colors(source.parent)
            if not bodies and metadata.get('issue'):
                raise ValueError(metadata['issue'])
            if bodies and not volume_matches(bodies,shape):
                raise ValueError('Die gespeicherten Farbgruppen stimmen nicht mit dem Modellvolumen überein.')
        slice_model(shape,request['settings'],folder,emit,indexed=indexed_path(source).is_file(),color_bodies=bodies)
    elif command=='export':
        # Reorientation is applied to the exported solid, never just metadata.
        for i,item in enumerate(request['items']):
            shape=load_model(item['input'],use_indexed=True)
            try:
                kind=export_file(shape,item['output'],order=item.get('order'),format=item.get('format'),color=item.get('color'))
            except ValueError as error:
                raise ValueError(f"{Path(item['input']).stem} · {error}") from error
            emit(int(100*(i+1)/len(request['items'])),kind.upper()+' in Druckausrichtung exportieren …')
    else: raise ValueError('Unbekannter Geometrieauftrag.')


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
