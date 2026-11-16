"""Rigid full-model reorientation and downstream slicing regressions."""
import hashlib
import tempfile
import unittest
from pathlib import Path
import numpy as np
import manifold3d as md
from orientation import rotation_matrix,rotate_model,write_rotated_model
from geometry import MAX_TRIANGLES,write_stl,load_model,mesh_of,slice_model
from preview import topology,prepare_previews
from indexed_mesh import read_indexed
from exporting import export_file


class OrientationTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(root.resolve())
    def tearDown(self):self.temp.cleanup()

    def test_rotation_matrices_are_rigid_and_orientation_preserving(self):
        for angles in ([0,0,0],[90,0,0],[17,-29,43],[-360,180,270],[.001,-.002,.003]):
            with self.subTest(angles=angles):
                r=rotation_matrix(angles)
                self.assertTrue(np.allclose(r.T@r,np.eye(3),atol=1e-12));self.assertAlmostEqual(np.linalg.det(r),1,places=12)

    def test_quarter_turns_swap_expected_dimensions_on_each_axis(self):
        source=md.Manifold.cube((20,30,50))
        for angles,dims in (([90,0,0],[20,50,30]),([0,90,0],[50,30,20]),([0,0,90],[30,20,50])):
            with self.subTest(angles=angles):
                result=rotate_model(source,angles)
                self.assertTrue(np.allclose(result.bounding_box(),[0,0,0]+dims))
                self.assertAlmostEqual(result.volume(),30000,places=6)

    def test_positive_z_rotation_moves_asymmetric_geometry_in_right_handed_direction(self):
        source=md.Manifold.cube((20,30,50))+md.Manifold.cube((8,5,10)).translate((18,0,0))
        vertices=np.asarray(source.to_mesh64().vert_properties)[:,:3]
        expected=np.column_stack((-vertices[:,1],vertices[:,0],vertices[:,2]));expected-=expected.min(axis=0)
        result=rotate_model(source,[0,0,90]);actual=np.asarray(result.to_mesh64().vert_properties)[:,:3]
        self.assertEqual(set(map(tuple,np.round(actual,8))),set(map(tuple,np.round(expected,8))))

    def test_negative_rotation_matches_inverse_direction(self):
        source=md.Manifold.cube((20,30,50))
        vertices=np.asarray(source.to_mesh64().vert_properties)[:,:3]
        expected=np.column_stack((vertices[:,1],-vertices[:,0],vertices[:,2]));expected-=expected.min(axis=0)
        actual=np.asarray(rotate_model(source,[0,0,-90]).to_mesh64().vert_properties)[:,:3]
        self.assertEqual(set(map(tuple,np.round(actual,8))),set(map(tuple,np.round(expected,8))))

    def test_45_degree_bounds_follow_diagonal_geometry(self):
        result=rotate_model(md.Manifold.cube((20,30,50)),[0,0,45])
        self.assertTrue(np.allclose(result.bounding_box(),[0,0,0,50/np.sqrt(2),50/np.sqrt(2),50]))

    def test_combined_rotations_apply_x_then_y_then_z(self):
        result=rotate_model(md.Manifold.cube((20,30,50)),[90,90,0])
        self.assertTrue(np.allclose(result.bounding_box(),[0,0,0,30,50,20]))

    def test_zero_and_full_turns_preserve_original_geometry(self):
        source=md.Manifold.cube((20,30,50))
        for angles in ([0,0,0],[360,0,0],[0,-360,360]):
            result=rotate_model(source,angles)
            self.assertAlmostEqual((source-result).volume(),0,places=6);self.assertAlmostEqual((result-source).volume(),0,places=6)

    def test_sealed_cavity_remains_empty_after_arbitrary_rotation(self):
        source=md.Manifold.cube((100,100,100))-md.Manifold.cube((60,60,60)).translate((20,20,20))
        result=rotate_model(source,[17,-29,43]);box=np.asarray(result.bounding_box());center=(box[:3]+box[3:])/2
        self.assertEqual(topology(result),[(-1,0),(1,0)])
        self.assertLess((result ^ md.Manifold.cube((2,2,2),center=True).translate(center)).volume(),1e-6)
        self.assertTrue(mesh_of(result).is_watertight)

    def test_disconnected_material_bodies_are_retained(self):
        source=md.Manifold.cube((20,30,50))+md.Manifold.sphere(5,32).translate((50,40,35))
        result=rotate_model(source,[17,-29,43])
        self.assertEqual(topology(result),[(1,0),(1,0)]);self.assertAlmostEqual(result.volume(),source.volume(),places=6)

    def test_written_rotation_preserves_source_and_records_exact_new_dimensions(self):
        path=self.folder/'source.stl';write_stl(md.Manifold.cube((20,30,50)),path)
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        data,orientation=write_rotated_model(path,self.folder/'rotated',[0,0,90])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        self.assertTrue(np.allclose(data['dimensions'],[30,20,50]));self.assertEqual(orientation['order'],'XYZ')
        self.assertEqual(orientation['angles'],[0,0,90]);self.assertTrue(data['watertight'] and data['normalsConsistent'])
        self.assertTrue(np.allclose(load_model(self.folder/'rotated/original.stl',normalize=False).bounding_box(),[0,0,0,30,20,50]))

    def test_invalid_angles_or_empty_geometry_are_rejected(self):
        for angles in (None,[],[0,0],[0,0,0,0],[361,0,0],[0,float('nan'),0],[0,0,float('inf')],['bad',0,0],[[0],[0],[0]]):
            with self.subTest(angles=angles),self.assertRaises(ValueError):rotation_matrix(angles)
        with self.assertRaises(ValueError):rotate_model(md.Manifold(),[0,0,0])

    def test_rotated_model_can_be_sliced_and_exported_with_valid_caps(self):
        source=md.Manifold.cube((300,100,80));rotated=rotate_model(source,[0,0,30])
        result=slice_model(rotated,{'mode':'none','strategy':'adaptive'},self.folder/'parts')
        self.assertTrue(result['valid']);self.assertGreater(len(result['parts']),1)
        self.assertAlmostEqual(result['cutVolume'],source.volume(),places=4)
        for part in result['parts']:
            shape=load_model(self.folder/'parts'/part['file'])
            self.assertTrue(mesh_of(shape).is_watertight)
            export_file(shape,self.folder/(part['file']+'.3mf'),order=part['printOrder'])

    def test_display_preview_keeps_newly_rotated_model_coordinates(self):
        path=self.folder/'source.stl';write_stl(md.Manifold.cube((20,30,50)),path)
        data,_=write_rotated_model(path,self.folder/'rotated',[17,-29,43])
        records=prepare_previews([{'key':'original','input':str(self.folder/'rotated/original.stl'),'budget':120000}],self.folder/'display')
        shape=read_indexed(self.folder/'display'/records[0]['file'],MAX_TRIANGLES)
        self.assertTrue(np.allclose(shape.bounding_box(),data['bounds']));self.assertFalse(records[0]['reduced'])


if __name__=='__main__':unittest.main(verbosity=2)
