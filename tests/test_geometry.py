"""Real integration tests, including re-import of generated geometry."""
import json
import math
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
import numpy as np
import manifold3d as md
import trimesh
from geometry import (solid_of, mesh_of, write_stl, load_model, slice_model,
                      demo_dragon, info, fit_order, read_3mf, validate_settings)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts'/'test-temp'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(root.resolve())

    def tearDown(self): self.temp.cleanup()

    def calculate(self,solid,**settings):
        return slice_model(solid,{'mode':'separate',**settings},self.folder)

    def assert_valid_exports(self,result):
        for item in result['parts']+result['connectors']:
            solid=load_model(self.folder/item['file'])
            self.assertTrue(info(solid)['watertight'])
            self.assertGreater(solid.volume(),0)
            self.assertIsNotNone(fit_order(solid,[219.6,219.6,249.6]))

    def test_box_volume_and_closed_caps(self):
        solid=md.Manifold.cube((300,100,80))
        r=self.calculate(solid,mode='none')
        self.assertEqual(len(r['parts']),2)
        self.assertAlmostEqual(r['cutVolume'],solid.volume(),places=5)
        self.assert_valid_exports(r)
        self.assertEqual(r['cuts'][0],[150.0])

    def test_separate_dowels_and_real_recesses(self):
        solid=md.Manifold.cube((300,100,80));r=self.calculate(solid)
        self.assertEqual(len(r['joints']),2);self.assertEqual(len(r['connectors']),2)
        self.assertLess(sum(p['volume'] for p in r['parts']),solid.volume())
        # In assembly coordinates, the pin must fit both holes without intersection.
        pin=solid_of(trimesh.load(self.folder/r['connectors'][0]['file'],force='mesh'))
        for part in r['parts']:
            shape=solid_of(trimesh.load(self.folder/part['file'],force='mesh'))
            self.assertLess((pin^shape).volume(),1e-4)
        self.assert_valid_exports(r)

    def test_integrated_pins_stay_connected_and_fit(self):
        r=self.calculate(md.Manifold.cube((300,100,80)),mode='integrated')
        self.assertEqual(len(r['connectors']),0);self.assertEqual(len(r['joints']),2)
        self.assertGreater(r['parts'][0]['dimensions'][0],150)
        self.assertTrue(all(p['components']==1 for p in r['parts']))
        self.assert_valid_exports(r)

    def test_mixed_mode_contains_both_variants(self):
        r=self.calculate(md.Manifold.cube((300,100,80)),mode='mixed')
        self.assertEqual({j['mode'] for j in r['joints']},{'integrated','separate'})
        self.assertEqual(len(r['connectors']),1)

    def test_rectangular_connectors(self):
        r=self.calculate(md.Manifold.cube((300,100,80)),kind='rect')
        self.assertEqual(len(r['joints']),2)
        self.assert_valid_exports(r)

    def test_hollow_mesh_does_not_fill_cavity(self):
        outer=md.Manifold.cube((300,100,80))
        hollow=outer-md.Manifold.cube((280,80,60)).translate((10,10,10))
        r=self.calculate(hollow,diameter=4,depth=6,wall=1)
        self.assertAlmostEqual(r['cutVolume'],hollow.volume(),places=4)
        self.assertTrue(r['valid']);self.assert_valid_exports(r)

    def test_cylinder_and_tolerance_geometry(self):
        solid=md.Manifold.cylinder(330,45,circular_segments=64)
        solid=solid.translate((45,45,0))
        r=self.calculate(solid,tolerance=.4)
        self.assertTrue(r['valid']);self.assertGreater(len(r['joints']),0)
        self.assert_valid_exports(r)

    def test_complex_demo_closed_and_sliceable(self):
        solid=demo_dragon();self.assertTrue(info(solid)['watertight'])
        self.assertGreater(solid.num_tri(),1000)
        r=self.calculate(solid,mode='none')
        self.assertGreater(len(r['parts']),4)
        self.assertAlmostEqual(r['cutVolume']/solid.volume(),1,places=6)
        self.assertTrue(r['valid']);self.assert_valid_exports(r)

    def test_open_mesh_rejected(self):
        mesh=mesh_of(md.Manifold.cube((20,20,20)))
        mesh.update_faces(np.arange(len(mesh.faces)-1))
        with self.assertRaisesRegex(ValueError,'offen'):solid_of(mesh)

    def test_thin_interface_reports_missing_connectors(self):
        r=self.calculate(md.Manifold.cube((300,5,5)),diameter=8)
        self.assertEqual(len(r['joints']),0)
        self.assertTrue(any('keine Verbindung' in w for w in r['warnings']))

    def test_manual_cut_and_oversized_rejection(self):
        solid=md.Manifold.cube((300,100,80))
        r=self.calculate(solid,cuts={'x':[100,200]},mode='none')
        self.assertEqual(len(r['parts']),3)
        with self.assertRaisesRegex(ValueError,'zu große'):
            self.calculate(solid,cuts={'x':[20]})

    def test_invalid_numeric_settings_rejected(self):
        for key,value in [('bedX',0),('margin',200),('diameter',-1),('depth',float('nan')),('count',9),('kind','thread')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):validate_settings({key:value})

    def test_stl_obj_import_and_scale(self):
        shape=md.Manifold.cube((12,25,30))
        write_stl(shape,self.folder/'box.stl')
        mesh_of(shape).export(self.folder/'box.obj')
        for suffix in ('stl','obj'):
            self.assertTrue(np.allclose(info(load_model(self.folder/f'box.{suffix}',2))['dimensions'],[24,50,60]))

    def test_3mf_units_component_transform(self):
        mesh=mesh_of(md.Manifold.cube((1,2,3)))
        vertices=''.join(f'<vertex x="{v[0]}" y="{v[1]}" z="{v[2]}"/>' for v in mesh.vertices)
        faces=''.join(f'<triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>' for t in mesh.faces)
        xml=f'''<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" unit="inch"><resources><object id="1" type="model"><mesh><vertices>{vertices}</vertices><triangles>{faces}</triangles></mesh></object><object id="2" type="model"><components><component objectid="1" transform="1 0 0 0 1 0 0 0 1 2 0 0"/></components></object></resources><build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 1 0 0"/></build></model>'''
        path=self.folder/'box.3mf'
        with zipfile.ZipFile(path,'w') as z:z.writestr('3D/3dmodel.model',xml)
        imported=read_3mf(path)
        self.assertTrue(np.allclose(imported.bounds[0],[76.2,0,0]))
        self.assertTrue(np.allclose(info(load_model(path))['dimensions'],[25.4,50.8,76.2]))

    def test_export_orientation_winding_and_origin(self):
        shape=md.Manifold.cube((10,20,30)).translate((100,200,300))
        write_stl(shape,self.folder/'print.stl',origin=True,order=[1,0,2])
        mesh=trimesh.load(self.folder/'print.stl',force='mesh')
        self.assertTrue(np.allclose(mesh.bounds[0],[0,0,0]));self.assertGreater(mesh.volume,0)
        self.assertTrue(np.allclose(mesh.extents,[20,10,30]))

    def test_result_manifest_roundtrip(self):
        result=self.calculate(md.Manifold.cube((300,100,80)))
        loaded=json.loads((self.folder/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(loaded['joints'],result['joints'])
        self.assertEqual(loaded['settings']['mode'],'separate')

    def test_axial_clearance_cannot_break_through_outer_wall(self):
        r=self.calculate(md.Manifold.cube((80,80,40)),cuts={'z':[20]},diameter=4,depth=19,tolerance=2,wall=.1)
        self.assertEqual(len(r['parts']),2)
        self.assertEqual(len(r['joints']),0)

    def test_print_orientation_uses_available_height(self):
        r=self.calculate(md.Manifold.cube((240,200,200)),mode='none')
        self.assertEqual(len(r['parts']),1)
        self.assertEqual(r['parts'][0]['printOrder'][2],0)


if __name__=='__main__':unittest.main(verbosity=2)
