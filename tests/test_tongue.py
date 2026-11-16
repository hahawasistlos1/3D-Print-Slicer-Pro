"""Real straight tongue/groove placement, clearance and assembly regressions."""
import json
import tempfile
import unittest
from pathlib import Path
import manifold3d as md
import numpy as np
from geometry import slice_model, connector, load_model, write_stl, mesh_of, validate_settings


class TongueTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(root.resolve())

    def tearDown(self):self.temp.cleanup()

    def calculate(self,shape=None,**settings):
        return slice_model(md.Manifold.cube((300,90,20)) if shape is None else shape,
            {'kind':'tongue','mode':'separate','strategy':'equal','diameter':4,'tongueLength':60,
             'depth':10,'wall':1,'count':1,**settings},self.folder)

    def test_long_feder_fits_thin_panel_without_enclosing_circle(self):
        r=self.calculate(md.Manifold.cube((300,90,12)))
        self.assertEqual(len(r['joints']),1)
        j=r['joints'][0]
        self.assertEqual((j['axis'],j['tangentAxis'],j['length']),(0,1,60))
        self.assertTrue(r['valid'] and r['motion']['pathVerified'])
        self.assertEqual(len(r['motion']['preinsertSteps']),1)

    def test_all_cut_axes_and_both_tangent_orientations(self):
        for axis in range(3):
            for tangent in range(3):
                if tangent==axis:continue
                with self.subTest(axis=axis,tangent=tangent):
                    dims=[12,12,12];dims[axis]=300;dims[tangent]=90
                    r=self.calculate(md.Manifold.cube(dims))
                    self.assertEqual(len(r['joints']),1)
                    j=r['joints'][0]
                    self.assertEqual((j['axis'],j['tangentAxis']),(axis,tangent))
                    self.assertTrue(r['motion']['pathVerified'])

    def test_separate_spline_volume_and_closed_stl_roundtrip(self):
        r=self.calculate()
        j=r['joints'][0]
        pin=load_model(self.folder/r['connectors'][0]['file'])
        self.assertAlmostEqual(pin.volume(),4*60*20,places=3)
        self.assertTrue(mesh_of(pin).is_watertight)
        self.assertEqual(sorted(np.round(np.array(pin.bounding_box())[3:]-np.array(pin.bounding_box())[:3],4)),[4,20,60])
        self.assertEqual(json.loads((self.folder/'result.json').read_text(encoding='utf-8'))['joints'][0],j)

    def test_socket_clearance_in_both_tangents_and_axial_direction(self):
        r=self.calculate(tolerance=.4)
        removed=300*90*20-sum(p['volume'] for p in r['parts'])
        self.assertAlmostEqual(removed,4.4*60.4*20.8,places=4)
        j=r['joints'][0]
        pin=connector(j['axis'],j['center'],2,10,'tongue',60,j['tangentAxis'])
        import trimesh
        for part in r['parts']:
            # Read directly, preserving assembly coordinates (load_model normalises).
            from geometry import solid_of
            body=solid_of(trimesh.load(self.folder/part['file'],force='mesh'))
            self.assertLess((body ^ pin).volume(),1e-5)

    def test_integrated_tongue_is_attached_and_assembly_is_proven(self):
        r=self.calculate(mode='integrated')
        self.assertEqual(len(r['connectors']),0)
        self.assertEqual(len(r['joints']),1)
        self.assertTrue(r['motion']['pathVerified'])
        self.assertTrue(all(p['components']==1 and p['watertight'] for p in r['parts']))
        self.assertAlmostEqual(sum(p['volume'] for p in r['parts']),300*90*20+4*60*10-4.2*60.2*10.2,places=4)

    def test_mixed_generates_both_actual_variants(self):
        r=self.calculate(md.Manifold.cube((500,90,20)),mode='mixed',cuts={'x':[170,340]})
        self.assertEqual([j['mode'] for j in r['joints']],['integrated','separate'])
        self.assertEqual(len(r['connectors']),1)
        self.assertTrue(r['motion']['pathVerified'])

    def test_long_footprint_cannot_bridge_an_internal_hole(self):
        shape=md.Manifold.cube((300,80,20))-md.Manifold.cube((300,16,8)).translate((0,32,6))
        r=self.calculate(shape,tongueLength=60)
        self.assertEqual(len(r['joints']),0)
        self.assertFalse(r['assembly']['connected'])
        short=self.calculate(shape,tongueLength=10)
        self.assertEqual(len(short['joints']),1)

    def test_too_long_reports_missing_connector_without_faking_shape(self):
        r=self.calculate(tongueLength=200)
        self.assertEqual(r['joints'],[])
        self.assertEqual(r['connectors'],[])
        self.assertTrue(any('0/1' in w for w in r['warnings']))
        self.assertAlmostEqual(sum(p['volume'] for p in r['parts']),300*90*20)

    def test_auto_size_changes_width_and_depth_but_preserves_length(self):
        r=self.calculate(md.Manifold.cube((300,90,8)),diameter=10,autoSize=True,minDiameter=2,minDepth=3)
        self.assertEqual(len(r['joints']),1)
        j=r['joints'][0]
        self.assertTrue(j['autoSized'])
        self.assertGreaterEqual(j['diameter'],2)
        self.assertLess(j['diameter'],10)
        self.assertEqual(j['length'],60)
        self.assertTrue(r['motion']['pathVerified'])

    def test_invalid_lengths_are_rejected(self):
        for length in [0,-1,float('nan'),float('inf'),3]:
            with self.subTest(length=length),self.assertRaises(ValueError):
                validate_settings({'kind':'tongue','diameter':4,'tongueLength':length})

    def test_too_deep_does_not_break_outer_wall(self):
        r=self.calculate(md.Manifold.cube((40,90,20)),cuts={'x':[20]},depth=19,tolerance=.4)
        self.assertEqual(r['joints'],[])

    def test_unprintable_loose_feder_is_not_committed(self):
        # All six bed permutations are insufficient for this loose spline.
        r=self.calculate(md.Manifold.cube((300,450,20)),tongueLength=300)
        self.assertEqual(r['joints'],[])


if __name__=='__main__':unittest.main(verbosity=2)
