"""Persist printable material groups separately from the assembled model."""
import json
from pathlib import Path
import re

import manifold3d as md
import numpy as np
import trimesh

from geometry import MAX_TRIANGLES, solid_of
from indexed_mesh import read_indexed, write_indexed


MAX_GROUPS = 64
COLOR_PATTERN = re.compile(r'#[0-9A-Fa-f]{6}')


def volume_matches(bodies, original):
    volume = original.volume()
    return abs(sum(body.volume() for _,body in bodies)-volume) <= max(1e-6,volume*1e-8)


def import_colors(source, original, scale, repaired):
    palettes = source['colors']
    if any(palette is None for palette in palettes):
        return {'issue':'Das 3MF enthält nicht unterstützte Farbzuweisungen, Texturen oder Verläufe.'}, []
    colors = {color for palette in palettes for color in palette}
    if len(colors)<2:
        return {}, []
    if len(colors)>MAX_GROUPS:
        return {'issue':f'Farbtrennung unterstützt bis zu {MAX_GROUPS} Farbgruppen.'}, []
    if repaired:
        return {'issue':'Die 3MF-Importreparatur konnte keine eindeutigen geschlossenen Farbgruppen erhalten.'}, []

    blocks = {}
    try:
        for (vertices,faces),palette in zip(source['meshes'],palettes,strict=True):
            points = vertices*scale-source['origin']
            for color,rows in palette.items():
                mesh = trimesh.Trimesh(points,faces if rows is None else faces[rows],process=False)
                mesh.remove_unreferenced_vertices()
                # A negative cavity assigned to a different color is not a
                # separately printable object. Never invert it into one.
                if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
                    raise ValueError('Farbgruppe ist kein geschlossener positiver Körper.')
                blocks.setdefault(color,[]).append(solid_of(mesh,preserve_indices=True))
        bodies = [(color,md.Manifold.batch_boolean(solids,md.OpType.Add)) for color,solids in blocks.items()]
        if any(body.is_empty() or body.status()!=md.Error.NoError or body.num_tri()>MAX_TRIANGLES
               for _,body in bodies):
            raise ValueError('Ungültiges Farbnetz.')
    except ValueError:
        return {'issue':'Die Farbflächen bilden keine getrennten geschlossenen Volumenkörper.'}, []
    if not volume_matches(bodies,original):
        return {'issue':'Die Farbgruppen überlappen sich oder ergeben zusammen nicht das Modellvolumen.'}, []
    return {}, sorted(bodies,key=lambda entry: entry[0] or '')


def group_path(folder, index):
    return folder/f'color_{index:03}.mesh'


def save_colors(folder, metadata, bodies):
    if bodies:
        metadata['groups'] = [color for color,_ in bodies]
        for i,(_,body) in enumerate(bodies):
            write_indexed(body,group_path(folder,i))
    return metadata


def load_colors(folder):
    path = folder/'model.json'
    if not path.is_file():
        return {}, []
    metadata = json.loads(path.read_text(encoding='utf-8-sig')).get('colorSeparation') or {}
    colors = metadata.get('groups',[])
    if not colors:
        return metadata, []
    if not isinstance(colors,list) or not 2<=len(colors)<=MAX_GROUPS or any(
            color is not None and (not isinstance(color,str) or not COLOR_PATTERN.fullmatch(color))
            for color in colors) or len(set(colors))!=len(colors):
        raise ValueError('Ungültige Farbgruppen im Projekt.')
    return metadata, [(color,read_indexed(group_path(folder,i),MAX_TRIANGLES)) for i,color in enumerate(colors)]
