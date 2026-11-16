"""Format, orientation, cavity and atomic-file regression tests for exports."""
import itertools
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import manifold3d as md
import numpy as np
import trimesh
from exporting import export_file,read_export,CORE,REL,TYPES,START,MODEL_TYPE
from geometry import load_model,mesh_of,slice_model


class ExportTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(root.resolve())

    def tearDown(self):self.temp.cleanup()

    def test_all_formats_preserve_all_six_print_orientations(self):
        shape=md.Manifold.cube((13,27,41)).translate((-20,30,-50))
        for kind,order in itertools.product(('stl','obj','3mf'),itertools.permutations(range(3))):
            with self.subTest(kind=kind,order=order):
                path=self.folder/('part.'+kind);export_file(shape,path,order)
                actual=read_export(path,kind);box=np.array(actual.bounding_box())
                self.assertTrue(np.allclose(box[:3],0))
                self.assertTrue(np.allclose(box[3:],np.array([13,27,41])[list(order)]))
                self.assertAlmostEqual(actual.volume(),13*27*41,places=3)
                self.assertTrue(mesh_of(actual).is_watertight)
                self.assertTrue(mesh_of(actual).is_winding_consistent)

    def test_curved_geometry_roundtrips_without_replacing_by_a_box(self):
        shape=md.Manifold.cylinder(27.135,8.246,circular_segments=64)
        for kind in ('stl','obj','3mf'):
            with self.subTest(kind=kind):
                path=self.folder/('curve.'+kind);export_file(shape,path,[2,0,1])
                actual=load_model(path)
                self.assertLess(abs(actual.volume()/shape.volume()-1),1e-5)
                self.assertGreater(actual.num_tri(),100)

    def test_sealed_cavity_is_preserved_in_all_formats(self):
        shape=md.Manifold.cube((30,40,50))-md.Manifold.cube((10,20,30)).translate((10,10,10))
        for kind in ('stl','obj','3mf'):
            path=self.folder/('hollow.'+kind);export_file(shape,path,[1,0,2])
            actual=load_model(path)
            self.assertAlmostEqual(actual.volume(),54000,places=4)
            self.assertEqual(len(actual.decompose()),2)

    def test_3mf_is_a_self_contained_core_package_with_mm_unit(self):
        path=self.folder/'part.3mf';export_file(md.Manifold.cube((13,27,41)),path)
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()),{'[Content_Types].xml','_rels/.rels','3D/3dmodel.model'})
            rel=ET.fromstring(archive.read('_rels/.rels')).find('{'+REL+'}Relationship')
            self.assertEqual(rel.attrib['Type'],START)
            self.assertNotIn('TargetMode',rel.attrib)
            model=ET.fromstring(archive.read(rel.attrib['Target'].lstrip('/')))
            self.assertEqual(model.tag,'{'+CORE+'}model')
            self.assertEqual(model.attrib['unit'],'millimeter')
            self.assertNotIn('requiredextensions',model.attrib)
            defaults=ET.fromstring(archive.read('[Content_Types].xml')).findall('{'+TYPES+'}Default')
            self.assertIn(MODEL_TYPE,[d.attrib['ContentType'] for d in defaults])
            objects=model.findall('{'+CORE+'}resources/{'+CORE+'}object')
            build=model.findall('{'+CORE+'}build/{'+CORE+'}item')
            self.assertEqual(len(objects),1);self.assertEqual(build[0].attrib['objectid'],objects[0].attrib['id'])
            vertices=objects[0].findall('.//{'+CORE+'}vertex')
            faces=objects[0].findall('.//{'+CORE+'}triangle')
            self.assertEqual(len(vertices),8);self.assertEqual(len(faces),12)
            self.assertTrue(all(0<=int(i)<len(vertices) for face in faces for i in face.attrib.values()))

    def test_edge_contact_reports_stl_limit_and_exports_with_3mf_indices(self):
        cube=md.Manifold.cube((10,10,10))
        shape=md.Manifold.compose([cube,cube.translate((10,10,0))])
        path=self.folder/'contact.stl'
        with self.assertRaisesRegex(ValueError,'STL-Prüfung.*3MF'):
            export_file(shape,path)
        self.assertFalse(path.exists())
        indexed=path.with_suffix('.3mf')
        export_file(shape,indexed)
        actual=read_export(indexed,'3mf')
        self.assertEqual(len(actual.decompose()),2)
        self.assertEqual(actual.num_tri(),24)

    def test_stl_retries_failed_float32_conversion_and_checks_the_written_file(self):
        path=self.folder/'retry.stl'
        shape=md.Manifold.cube((13,27,41))
        calls=0

        def check(staged,kind):
            nonlocal calls
            calls+=1
            if calls==1:
                raise ValueError('Offene Kante nach Float32-Konvertierung')
            return read_export(staged,kind)

        with patch('exporting.read_export',side_effect=check):
            export_file(shape,path,[1,0,2])
        self.assertEqual(calls,2)
        saved=read_export(path,'stl')
        self.assertEqual(saved.bounding_box(),(0,0,0,27,13,41))
        self.assertAlmostEqual(saved.volume(),shape.volume())
        self.assertEqual(list(self.folder.iterdir()),[path])

    def test_stl_ascii_preserves_gap_lost_in_binary_and_can_be_reimported(self):
        cube=md.Manifold.cube((100,10,10))
        shape=md.Manifold.compose([cube,cube.translate((100.000001,0,0))])
        path=self.folder/'narrow-gap.stl'
        export_file(shape,path)
        with path.open('rb') as stream:
            self.assertTrue(stream.read(20).startswith(b'solid SlicerPro\n'))
        for restored in (read_export(path,'stl'),load_model(path,repair_report={})):
            self.assertEqual(len(restored.decompose()),2)
            self.assertEqual(restored.num_tri(),24)
            self.assertAlmostEqual(restored.volume(),shape.volume())
            self.assertEqual(restored.bounding_box(),shape.bounding_box())

    def test_obj_has_mm_annotation_and_no_material_or_external_reference(self):
        path=self.folder/'part.obj';export_file(md.Manifold.cube((13,27,41)),path)
        lines=path.read_text(encoding='utf-8').splitlines()
        self.assertIn('# units: millimeter',lines)
        self.assertFalse(any(line.startswith(('mtllib','usemtl')) for line in lines))
        faces=[line.split()[1:] for line in lines if line.startswith('f ')]
        self.assertEqual(len(faces),12)
        self.assertTrue(all(1<=int(i)<=8 for face in faces for i in face))

    def test_explicit_format_supports_atomic_single_export_temporary_names(self):
        for kind in ('stl','obj','3mf'):
            with self.subTest(kind=kind):
                path=self.folder/('part.'+kind+'.tmp-123')
                export_file(md.Manifold.cube((13,27,41)),path,[1,0,2],kind)
                self.assertAlmostEqual(read_export(path,kind).volume(),13*27*41,places=3)
                self.assertEqual(len(list(self.folder.glob(path.name+'.tmp-*'))),0)

    def test_invalid_format_keeps_existing_target(self):
        path=self.folder/'keep.foo';path.write_bytes(b'original')
        with self.assertRaises(ValueError):export_file(md.Manifold.cube((10,10,10)),path)
        self.assertEqual(path.read_bytes(),b'original')

    def test_failed_volume_validation_keeps_existing_target_and_cleans_stage(self):
        path=self.folder/'keep.obj';path.write_bytes(b'original')
        with patch('exporting.read_export',return_value=md.Manifold.cube((9,9,9))):
            with self.assertRaisesRegex(ValueError,'Volumen'):export_file(md.Manifold.cube((10,10,10)),path)
        self.assertEqual(path.read_bytes(),b'original')
        self.assertEqual(list(self.folder.iterdir()),[path])

    def test_failed_origin_validation_keeps_existing_target(self):
        path=self.folder/'keep.3mf';path.write_bytes(b'original')
        with patch('exporting.read_export',return_value=md.Manifold.cube((10,10,10)).translate((1,0,0))):
            with self.assertRaisesRegex(ValueError,'Ursprung'):export_file(md.Manifold.cube((10,10,10)),path)
        self.assertEqual(path.read_bytes(),b'original')
        self.assertEqual(list(self.folder.iterdir()),[path])

    def test_writer_failure_does_not_leave_a_partial_target(self):
        path=self.folder/'keep.obj';path.write_bytes(b'original')
        def fail(mesh,stage):
            stage.write_bytes(b'partial');raise OSError('disk write failed')
        with patch('exporting.write_obj',side_effect=fail),self.assertRaises(OSError):
            export_file(md.Manifold.cube((10,10,10)),path)
        self.assertEqual(path.read_bytes(),b'original')
        self.assertEqual(list(self.folder.iterdir()),[path])

    def test_invalid_or_empty_geometry_cannot_replace_target(self):
        for kind in ('stl','obj','3mf'):
            path=self.folder/('keep.'+kind);path.write_bytes(b'original')
            with self.assertRaises(ValueError):export_file(md.Manifold(),path)
            self.assertEqual(path.read_bytes(),b'original')

    def test_invalid_print_permutations_are_rejected(self):
        path=self.folder/'part.3mf'
        for order in ([0,0,2],[0,1],[0,1,3],[0,1,2,3],[False,1,2],[0.,1,2]):
            with self.subTest(order=order),self.assertRaises(ValueError):
                export_file(md.Manifold.cube((10,10,10)),path,order)
        self.assertFalse(path.exists())

    def test_export_does_not_mutate_source_vertices_or_faces(self):
        shape=md.Manifold.cube((13,27,41)).translate((-20,30,-50));before=shape.to_mesh64()
        for kind in ('stl','obj','3mf'):export_file(shape,self.folder/('part.'+kind),[1,0,2])
        after=shape.to_mesh64()
        self.assertTrue(np.array_equal(before.vert_properties,after.vert_properties))
        self.assertTrue(np.array_equal(before.tri_verts,after.tri_verts))

    def test_actual_grooves_and_separate_tongues_survive_obj_and_3mf(self):
        folder=self.folder/'sliced'
        result=slice_model(md.Manifold.cube((300,90,20)),{'kind':'tongue','diameter':4,'tongueLength':60,'depth':10,'wall':1,'count':1,'mode':'separate'},folder)
        self.assertTrue(result['motion']['pathVerified'])
        for item,kind in itertools.product(result['parts']+result['connectors'],('obj','3mf')):
            path=self.folder/(item['file']+'.'+kind)
            source=load_model(folder/item['file']);export_file(source,path,item['printOrder'])
            actual=load_model(path)
            self.assertLess(abs(actual.volume()/source.volume()-1),1e-5)
            self.assertTrue(np.allclose(np.array(actual.bounding_box())[3:],np.array(item['dimensions'])[item['printOrder']]))


if __name__=='__main__':unittest.main(verbosity=2)
