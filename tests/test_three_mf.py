from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import manifold3d as md
import numpy as np

from color_slicing import import_colors, load_colors
from geometry import load_model, mesh_of, read_3mf, write_stl
from three_mf import CORE, MATERIAL, MODEL_RELATION, read_3mf as read_geometry


def model(objects, build='', unit='millimeter'):
    return (f'<model xmlns="{CORE}" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
            f'unit="{unit}"><resources>{objects}</resources><build>{build}</build></model>')


def mesh_object(oid, dimensions):
    mesh = mesh_of(md.Manifold.cube(dimensions))
    vertices = ''.join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x,y,z in mesh.vertices)
    faces = ''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in mesh.faces)
    return f'<object id="{oid}" type="model"><mesh><vertices>{vertices}</vertices><triangles>{faces}</triangles></mesh></object>'


def components(oid, entries):
    return f'<object id="{oid}" type="model"><components>{entries}</components></object>'


def package(path, models, root='3D/assembly.model'):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('_rels/.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         f'<Relationship Id="root" Type="{MODEL_RELATION}" Target="/{root}"/></Relationships>')
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        for name, content in models.items():
            archive.writestr(name,content)


def example(path):
    children = ('<component p:path="/3D/Objects/Quader%20A.model" objectid="1"/>'
                '<component p:path="/3D/Objects/QuaderB.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 90 0 0"/>')
    package(path, {
        '3D/Objects/Quader A.model': model(mesh_object(1,(70,40,30))),
        '3D/Objects/QuaderB.model': model(mesh_object(1,(30,25,20))),
        '3D/assembly.model': model(components(1,children), '<item objectid="1"/>'),
    })


PALETTE = '<basematerials id="3"><base name="Rot" displaycolor="#EE2244"/><base name="Blau" displaycolor="#2266EE"/></basematerials>'


def color_example(path,x=30):
    a=mesh_object(1,(x,20,20)).replace('type="model"','type="model" pid="3" pindex="0"')
    b=mesh_object(2,(30,20,20)).replace('type="model"','type="model" pid="3" pindex="1"')
    build=f'<item objectid="1"/><item objectid="2" transform="1 0 0 0 1 0 0 0 1 {x} 0 0"/>'
    package(path,{'3D/assembly.model':model(PALETTE+a+b,build)})


class ThreeMfTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).resolve().parents[1]/'artifacts/test-temp'
        folder.mkdir(parents=True,exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)/'multi.3mf'

    def test_external_components_share_id_without_sharing_geometry(self):
        example(self.path)
        solid = load_model(self.path)
        np.testing.assert_allclose(solid.bounding_box(), [0,0,0,120,40,30])
        self.assertAlmostEqual(solid.volume(), 99_000)
        self.assertEqual(len(solid.decompose()),2)

    def test_build_path_nested_components_units_and_reflection(self):
        child = model(mesh_object(1,(1,2,3))+components(2,'<component objectid="1" transform="1 0 0 0 1 0 0 0 1 2 0 0"/>'),
                      '<item objectid="404"/>',unit='centimeter')
        root = model('', '<item p:path="/3D/child.model" objectid="2" transform="-1 0 0 0 1 0 0 0 1 2 0 0"/>',unit='inch')
        package(self.path, {'3D/child.model':child,'3D/assembly.model':root})
        mesh = read_3mf(self.path)
        np.testing.assert_allclose(mesh.bounds,[[20.8,0,0],[30.8,20,30]])
        self.assertAlmostEqual(load_model(self.path).volume(),6000)

    def test_reused_object_instances_are_transformed_independently(self):
        root = model('', '<item p:path="/3D/child.model" objectid="1"/>'
                         '<item p:path="/3D/child.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 20 0 0"/>')
        package(self.path, {'3D/assembly.model':root,'3D/child.model':model(mesh_object(1,(10,5,3)))})
        solid = load_model(self.path)
        np.testing.assert_allclose(solid.bounding_box(), [0,0,0,30,5,3])
        self.assertAlmostEqual(solid.volume(),300)
        with self.assertRaisesRegex(ValueError,'zu viele Dreiecke|Zu viele Dreiecke'):
            read_geometry(self.path,23)

    def test_touching_and_overlapping_parts_form_one_solid(self):
        root = model('', '<item p:path="/3D/child.model" objectid="1"/>'
                         '<item p:path="/3D/child.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 10 0 0"/>'
                         '<item p:path="/3D/child.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 15 0 0"/>')
        package(self.path, {'3D/assembly.model':root,'3D/child.model':model(mesh_object(1,(10,5,3)))})
        solid = load_model(self.path, scale=2)
        self.assertEqual(len(solid.decompose()),1)
        np.testing.assert_allclose(solid.bounding_box(), [0,0,0,50,10,6])
        self.assertAlmostEqual(solid.volume(),3000)

    def test_union_face_growth_is_counted_and_kept_for_stl_reimport(self):
        root = model('', '<item p:path="/3D/child.model" objectid="1"/>'
                         '<item p:path="/3D/child.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 3 2 1"/>')
        package(self.path, {'3D/assembly.model':root,'3D/child.model':model(mesh_object(1,(10,5,3)))})
        self.assertEqual(len(read_3mf(self.path).faces),24)
        solid = load_model(self.path)
        self.assertGreater(solid.num_tri(),24)
        with patch('geometry.MAX_TRIANGLES',24):
            with self.assertRaisesRegex(ValueError,r'Zusammengefügtes 3MF hat \d+ Dreiecke \(Grenze: 24\)'):
                load_model(self.path)
        stl = self.path.with_suffix('.stl')
        write_stl(solid,stl)
        restored = load_model(stl)
        self.assertEqual(restored.num_tri(),solid.num_tri())
        self.assertAlmostEqual(restored.volume(),solid.volume())

    def test_missing_or_nonarchive_path_is_rejected(self):
        for target in ('/3D/missing.model','https://example.com/m.model','file:///C:/m.model',
                       '/3D/../m.model','/3D/%2e%2e/m.model','//3D/m.model'):
            with self.subTest(target=target):
                root = model('',f'<item p:path="{target}" objectid="1"/>')
                package(self.path,{'3D/assembly.model':root})
                with self.assertRaisesRegex(ValueError,'Modellpfad|Modelldatei fehlt'):
                    read_3mf(self.path)

    def test_missing_external_object_and_local_cycle_are_rejected(self):
        root = model('', '<item p:path="/3D/child.model" objectid="1"/>')
        for child,pattern in ((model(mesh_object(2,(1,1,1))),'Objekt 1 fehlt'),
                              (model(components(1,'<component objectid="1"/>')),'Zyklische')):
            with self.subTest(pattern=pattern):
                package(self.path,{'3D/assembly.model':root,'3D/child.model':child})
                with self.assertRaisesRegex(ValueError,pattern):
                    read_3mf(self.path)

    def test_xml_limit_is_cumulative(self):
        example(self.path)
        with zipfile.ZipFile(self.path) as archive:
            largest = max(entry.file_size for entry in archive.infolist())
        with patch('three_mf.MAX_XML_BYTES',largest):
            with self.assertRaisesRegex(ValueError,'zusammen größer'):
                read_3mf(self.path)

    def find_colors(self):
        source={}
        solid=load_model(self.path,repair_report={},color_source=source)
        metadata,bodies=import_colors(source,solid,1,False)
        return solid,metadata,bodies

    def test_bambu_filament_assignments_for_external_components(self):
        example(self.path)
        with zipfile.ZipFile(self.path,'a') as archive:
            archive.writestr('Metadata/project_settings.config',json.dumps({'filament_colour':['#aa0011','#1122ff']}))
            # This fixture uses ID 1 in each external model. Its assignments
            # would be ambiguous if the same ID named two different colors.
            archive.writestr('Metadata/model_settings.config',
                             '<config><object id="1"><part id="1"><metadata key="extruder" value="2"/></part></object></config>')
        _,metadata,bodies=self.find_colors()
        self.assertEqual((metadata,bodies),({},[]))
        staging=self.path.with_name('filaments.3mf')
        child=mesh_object(1,(20,20,20))+mesh_object(2,(20,20,20))
        references=('<component objectid="1" p:path="/3D/child.model"/>'
                    '<component objectid="2" p:path="/3D/child.model" transform="1 0 0 0 1 0 0 0 1 20 0 0"/>')
        package(staging,{'3D/assembly.model':model(components(5,references),'<item objectid="5"/>'),
                         '3D/child.model':model(child)})
        with zipfile.ZipFile(staging,'a') as archive:
            archive.writestr('Metadata/project_settings.config',json.dumps({'filament_colour':['#aa0011','#1122ff']}))
            archive.writestr('Metadata/model_settings.config',
                             '<config><object id="5"><metadata key="extruder" value="1"/>'
                             '<part id="2" subtype="normal_part"><metadata key="extruder" value="2"/></part></object></config>')
        self.path=staging
        solid,metadata,bodies=self.find_colors()
        self.assertEqual(metadata,{})
        self.assertEqual([(c,round(s.volume())) for c,s in bodies],[('#1122FF',8000),('#AA0011',8000)])
        self.assertAlmostEqual(solid.volume(),16000)

    def test_painted_open_color_partition_does_not_block_normal_import(self):
        cube=mesh_object(1,(20,20,20)).replace('type="model"','type="model" pid="3" pindex="0"')
        cube=cube.replace('<triangle v1=', '<triangle pid="3" p1="1" v1=',1)
        palette=f'<m:colorgroup xmlns:m="{MATERIAL}" id="3"><m:color color="#FF0000"/><m:color color="#00FF00"/></m:colorgroup>'
        package(self.path,{'3D/assembly.model':model(palette+cube,'<item objectid="1"/>')})
        solid,metadata,bodies=self.find_colors()
        self.assertAlmostEqual(solid.volume(),8000)
        self.assertEqual(bodies,[])
        self.assertIn('keine getrennten geschlossenen',metadata['issue'])

    def test_worker_splits_color_to_bed_size_after_scaling_and_rotation_and_exports_color(self):
        color_example(self.path,x=55)
        root=Path(__file__).resolve().parents[1]
        def run(name,**request):
            output=self.path.parent/name
            job=self.path.parent/(name+'.json')
            job.write_text(json.dumps({**request,'output':str(output)}),encoding='utf-8')
            r=subprocess.run([sys.executable,'-B',str(root/'engine/worker.py'),str(job)],
                             capture_output=True,encoding='utf-8',errors='replace')
            self.assertEqual(r.returncode,0,r.stderr+r.stdout)
            return output

        original=run('imported',command='import',input=str(self.path))
        _,original_colors=load_colors(original)
        self.assertEqual([color for color,_ in original_colors],['#2266EE','#EE2244'])
        scaled=run('scaled',command='scale',input=str(original/'original.stl'),scale=2)
        rotated=run('rotated',command='rotate',input=str(scaled/'original.stl'),angles=[0,0,90])
        outcome=run('sliced',command='slice',input=str(rotated/'original.stl'),
                    settings={'strategy':'color','bedX':65,'bedY':65,'bedZ':65,'mode':'none'})
        result=json.loads((outcome/'result.json').read_text(encoding='utf-8'))
        self.assertTrue(result['valid'])
        self.assertEqual([p['color'] for p in result['parts']].count('#2266EE'),1)
        self.assertGreater([p['color'] for p in result['parts']].count('#EE2244'),1)
        self.assertAlmostEqual(sum(p['volume'] for p in result['parts']),85*20*20*8,places=4)
        part=result['parts'][0]
        dest=self.path.parent/'blue.3mf'
        run('exported',command='export',items=[{'input':str(outcome/part['file']),'output':str(dest),
                                               'order':part['printOrder'],'color':part['color']}])
        with zipfile.ZipFile(dest) as archive:
            self.assertIn(b'displaycolor="#2266EE"',archive.read('3D/3dmodel.model'))


if __name__ == '__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--example':
        example(Path(sys.argv[2]))
    elif len(sys.argv)==3 and sys.argv[1]=='--color-example':
        color_example(Path(sys.argv[2]))
    else:
        unittest.main()
