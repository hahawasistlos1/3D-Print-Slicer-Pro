"""Closed display meshes, preserved holes and unchanged assembly/source data."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import manifold3d as md
import numpy as np
import indexed_mesh
from geometry import MAX_TRIANGLES,write_stl,mesh_of
from indexed_mesh import from_arrays,read_indexed
from preview import simplify_preview,prepare_previews,topology,MAX_VOLUME_ERROR


class PreviewTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(root.resolve())
    def tearDown(self):self.temp.cleanup()

    def assert_closed(self,shape):
        mesh=mesh_of(shape)
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)
        self.assertEqual(shape.status(),md.Error.NoError)

    def test_under_budget_keeps_entire_original_mesh(self):
        source=md.Manifold.cube((20,30,40))
        result,data=simplify_preview(source,120000)
        self.assertIs(result,source);self.assertEqual(data['triangles'],12)
        self.assertFalse(data['reduced']);self.assertTrue(data['budgetReached'])

    def test_dense_coplanar_box_is_retriangulated_not_sampled(self):
        source=md.Manifold.cube((20,30,40)).refine(40)
        result,data=simplify_preview(source,100)
        self.assertEqual(data['sourceTriangles'],19200);self.assertEqual(data['triangles'],12)
        self.assertAlmostEqual(result.volume(),source.volume(),places=8)
        self.assertTrue(np.allclose(result.bounding_box(),source.bounding_box()))
        self.assert_closed(result)

    def test_dense_sphere_becomes_closed_under_normal_display_budget(self):
        source=md.Manifold.sphere(50,512)
        result,data=simplify_preview(source,120000)
        self.assertEqual(source.num_tri(),131072)
        self.assertLessEqual(result.num_tri(),120000);self.assertTrue(data['reduced'])
        self.assertLessEqual(data['volumeError'],MAX_VOLUME_ERROR)
        self.assertLessEqual(data['tolerance'],.1);self.assert_closed(result)

    def test_through_hole_and_handle_are_preserved(self):
        source=md.Manifold.cube((80,80,30))-md.Manifold.cylinder(32,15,circular_segments=96).translate((40,40,-1))
        result,data=simplify_preview(source.refine(6),120)
        self.assertEqual(topology(result),[(1,1)])
        self.assertLess((result ^ md.Manifold.cylinder(30,5).translate((40,40,0))).volume(),1e-6)
        self.assert_closed(result)

    def test_sealed_negative_cavity_is_not_filled(self):
        source=md.Manifold.cube((100,100,100))-md.Manifold.sphere(25,256).translate((50,50,50))
        result,data=simplify_preview(source,1000)
        self.assertEqual(topology(result),[(-1,0),(1,0)])
        self.assertLess((result ^ md.Manifold.cube((4,4,4)).translate((48,48,48))).volume(),1e-6)
        self.assertLessEqual(data['volumeError'],MAX_VOLUME_ERROR);self.assert_closed(result)

    def test_material_island_inside_cavity_is_retained(self):
        source=(md.Manifold.cube((100,100,100))-md.Manifold.cube((80,80,80)).translate((10,10,10)))+md.Manifold.cube((10,10,10)).translate((45,45,45))
        result,data=simplify_preview(source.refine(12),100)
        self.assertEqual(topology(result),[(-1,0),(1,0),(1,0)])
        self.assertAlmostEqual((result ^ md.Manifold.cube((10,10,10)).translate((45,45,45))).volume(),1000,places=5)
        self.assert_closed(result)

    def test_disconnected_bodies_are_not_joined_or_removed(self):
        source=md.Manifold.sphere(20,96)+md.Manifold.sphere(10,96).translate((60,0,0))
        result,data=simplify_preview(source,100)
        self.assertEqual(topology(result),[(1,0),(1,0)]);self.assert_closed(result)

    def test_impossible_budget_keeps_complete_faces_and_reports_limit(self):
        source=md.Manifold.sphere(50,128)
        result,data=simplify_preview(source,12)
        self.assertGreater(result.num_tri(),12);self.assertFalse(data['budgetReached'])
        self.assertLessEqual(data['volumeError'],MAX_VOLUME_ERROR);self.assert_closed(result)

    def test_invalid_budgets_are_rejected(self):
        for budget in (0,11,-1,True,1.5,2_000_001):
            with self.subTest(budget=budget),self.assertRaises(ValueError):simplify_preview(md.Manifold.cube((10,10,10)),budget)

    def test_written_preview_preserves_world_coordinates_on_all_axes(self):
        source=md.Manifold.cube((20,30,40)).refine(10).translate((150,75,-20))
        path=self.folder/'source.stl';write_stl(source,path)
        records=prepare_previews([{'key':'part:2','input':str(path),'budget':100}],self.folder/'display')
        result=read_indexed(self.folder/'display'/records[0]['file'],MAX_TRIANGLES)
        self.assertTrue(np.allclose(result.bounding_box(),[150,75,-20,170,105,20]))
        self.assert_closed(result)

    def test_prepare_does_not_change_source_file_and_records_real_triangle_counts(self):
        path=self.folder/'source.stl';write_stl(md.Manifold.cube((20,30,40)).refine(10),path)
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        records=prepare_previews([{'key':'original','input':str(path),'budget':100}],self.folder/'display')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        manifest=json.loads((self.folder/'display/preview.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['items'],records)
        result=read_indexed(self.folder/'display'/records[0]['file'],MAX_TRIANGLES)
        self.assertEqual(result.num_tri(),records[0]['triangles']);self.assertTrue(records[0]['topologyPreserved'])

    def test_written_preview_keeps_cavity_smaller_than_float32_spacing(self):
        cavity=md.Manifold.cube((.00002,2,2)).translate((1000,10,10))
        source=md.Manifold.cube((1500,20,20))-cavity
        self.assertEqual(topology(source),[(-1,0),(1,0)])
        mesh=source.to_mesh64()
        rounded=from_arrays(np.asarray(mesh.vert_properties).astype(np.float32),mesh.tri_verts)
        self.assertNotEqual(topology(rounded),topology(source))
        path=self.folder/'source.stl'
        write_stl(source,path,indexed=True)
        records=prepare_previews([{'key':'original','input':str(path),'budget':120000}],self.folder/'display')
        restored=read_indexed(self.folder/'display'/records[0]['file'],MAX_TRIANGLES)
        self.assertEqual(topology(restored),topology(source))
        self.assertEqual(restored.num_tri(),source.num_tri())
        self.assertAlmostEqual(restored.volume(),source.volume())

    def test_preview_readback_does_not_rebuild_the_validated_mesh(self):
        path=self.folder/'source.stl'
        write_stl(md.Manifold.cube((20,30,40)),path)
        with patch('indexed_mesh.from_arrays',side_effect=AssertionError('Vorschau neu trianguliert')):
            records=prepare_previews([{'key':'original','input':str(path),'budget':100}],self.folder/'display')
        self.assertEqual(records[0]['triangles'],12)
        self.assertTrue(records[0]['topologyPreserved'])

    def test_changed_vertex_in_written_file_prevents_publication(self):
        path=self.folder/'source.stl'
        write_stl(md.Manifold.cube((20,30,40)),path)
        read_arrays=indexed_mesh._read_arrays

        def change_saved_coordinate(path,triangle_limit):
            with path.open('r+b') as stream:
                stream.seek(indexed_mesh.HEADER.size)
                stream.write(struct.pack('<d',.125))
            return read_arrays(path,triangle_limit)

        with patch('indexed_mesh._read_arrays',side_effect=change_saved_coordinate):
            with self.assertRaisesRegex(ValueError,'Eckpunkte oder Dreiecksindizes'):
                prepare_previews([{'key':'original','input':str(path),'budget':100}],self.folder/'display')
        self.assertFalse((self.folder/'display/preview.json').exists())

    def test_bad_simplification_falls_back_to_complete_source(self):
        source=md.Manifold.cube((20,30,40)).refine(10)
        with patch.object(md.Manifold,'simplify',return_value=md.Manifold.cube((1,1,1))):
            result,data=simplify_preview(source,100)
        self.assertIs(result,source);self.assertFalse(data['reduced'])
        self.assertFalse(data['budgetReached']);self.assert_closed(result)

    def test_empty_or_invalid_body_is_not_published_as_preview(self):
        with self.assertRaises(ValueError):simplify_preview(md.Manifold(),100)
        path=self.folder/'source.stl';write_stl(md.Manifold.cube((10,10,10)),path)
        with self.assertRaises(ValueError):prepare_previews([{'key':'x','input':str(path),'budget':100}]*2,self.folder/'display')
        self.assertFalse((self.folder/'display/preview.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
