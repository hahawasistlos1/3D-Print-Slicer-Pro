"""Regression tests for local planning and topology-aware connector search."""
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import manifold3d as md
from geometry import slice_model, info, load_model, validate_settings, demo_dragon, fit_order, write_stl
from planning import adaptive_partition, section_body, common_interface


class PlanningTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(root.resolve())

    def tearDown(self):self.temp.cleanup()

    def run_slice(self,shape,**settings):
        return slice_model(shape,{'strategy':'adaptive','mode':'separate',**settings},self.folder)

    def test_shifted_exact_capacity_multiple_retains_a_valid_plane(self):
        solid = md.Manifold.cube((499.2, 134, 69)).translate((850.5369384765625, 0, 0))
        result = self.run_slice(solid, mode='none')
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['parts']), 2)
        self.assertAlmostEqual(result['cutVolume'], solid.volume())

    def test_adaptive_volume_closed_parts_and_print_volume(self):
        shape=md.Manifold.cube((510,290,350))
        result=self.run_slice(shape)
        self.assertTrue(result['valid'])
        self.assertAlmostEqual(result['cutVolume']/shape.volume(),1,places=8)
        self.assertEqual(result['planning']['algorithm'],'adaptive-axis-v1')
        for part in result['parts']:
            self.assertIsNotNone(fit_order(load_model(self.folder/part['file']),[219.6,219.6,249.6]))
            self.assertTrue(part['cutFaces'])

    def test_local_cuts_have_branch_bounds_and_leave_fitting_parts(self):
        shape=md.Manifold.cube((410,80,50))+md.Manifold.cube((80,410,50))
        adaptive=self.run_slice(shape,mode='none')
        grid=slice_model(shape,{'mode':'none'},self.folder/'grid')
        self.assertLessEqual(len(adaptive['parts']),len(grid['parts']))
        self.assertTrue(any(c['bounds'][3]<410-1e-5 for c in adaptive['planning']['localCuts']))
        right=next(p for p in adaptive['parts'] if p['bounds'][0]>100)
        self.assertEqual([f['axis'] for f in right['cutFaces']],[0])
        self.assertTrue(adaptive['valid'])

    def test_scoring_avoids_neck_too_thin_for_dowel(self):
        a=md.Manifold.cube((130,80,80))
        b=md.Manifold.cube((130,80,80)).translate((170,0,0))
        neck=md.Manifold.cube((50,5,5)).translate((125,37.5,37.5))
        result=self.run_slice(a+b+neck,diameter=6,depth=8,wall=1)
        offsets=[c['offset'] for c in result['planning']['localCuts'] if c['axis']==0]
        self.assertTrue(offsets)
        self.assertTrue(all(not 130<v<170 for v in offsets))
        self.assertGreater(len(result['joints']),0)

    def test_hollow_cross_section_finds_actual_wall_positions(self):
        shape=md.Manifold.cube((300,100,80))-md.Manifold.cube((280,80,60)).translate((10,10,10))
        result=self.run_slice(shape,diameter=4,depth=6,wall=1)
        self.assertGreaterEqual(len(result['joints']),2)
        self.assertTrue(result['assembly']['connected'])
        self.assertTrue(all(p['components']==1 for p in result['parts']))

    def test_manual_plane_is_preserved_before_local_planning(self):
        shape=md.Manifold.cube((500,100,80))
        result=self.run_slice(shape,mode='none',cuts={'x':[120]})
        self.assertIn(120,result['cuts'][0])
        self.assertTrue(any(c.get('manual') for c in result['planning']['localCuts']))
        self.assertTrue(result['valid'])

    def test_disconnected_source_not_assumed_connected(self):
        shape=md.Manifold.cube((20,20,20))+md.Manifold.cube((20,20,20)).translate((30,0,0))
        result=self.run_slice(shape)
        self.assertEqual(len(result['parts']),2)
        self.assertFalse(result['assembly']['connected'])
        self.assertEqual(len(result['assembly']['groups']),2)

    def test_no_connector_mode_does_not_claim_assembly_test(self):
        result=self.run_slice(md.Manifold.cube((300,50,50)),mode='none')
        self.assertIsNone(result['assembly']['connected'])
        self.assertFalse(result['assembly']['pathVerified'])

    def test_actual_contacts_detect_t_junction(self):
        shape=md.Manifold.cube((350,250,80))
        result=self.run_slice(shape,diameter=4,depth=6,wall=1)
        # All detected contact pairs must be symmetric, including adjacent
        # branches with different local cut coordinates (a T junction).
        pairs={(i['a'],i['b']) for i in result['interfaces']}
        self.assertGreater(len(pairs),1)
        for a,b in pairs:
            self.assertIn(b,result['parts'][a-1]['neighbors'])
            self.assertIn(a,result['parts'][b-1]['neighbors'])
        self.assertTrue(result['assembly']['connected'])

    def test_touching_bounding_boxes_do_not_invent_interface(self):
        # Separated triangular prisms have touching X bounding boxes but
        # their actual faces are disjoint in Y.
        left=md.Manifold.cube((150,30,30))
        right=md.Manifold.cube((150,30,30)).translate((150,40,0))
        result=self.run_slice(left+right,mode='none',cuts={'x':[150]})
        self.assertEqual(result['interfaces'],[])

    def test_cyclic_sections_have_consistent_area_on_all_axes(self):
        shape=md.Manifold.cube((10,20,30))
        for axis,expected in enumerate((600,300,200)):
            self.assertAlmostEqual(section_body(shape,axis).slice((10,20,30)[axis]/2).area(),expected)

    def test_empty_manifold_never_fits_or_exports(self):
        self.assertIsNone(fit_order(md.Manifold(),[220,220,250]))
        with self.assertRaises(ValueError):write_stl(md.Manifold(),self.folder/'empty.stl')

    def test_sealed_cavity_stays_empty_without_any_cut(self):
        shape=md.Manifold.cube((100,100,100))-md.Manifold.cube((80,80,80)).translate((10,10,10))
        result=self.run_slice(shape,mode='none')
        self.assertEqual(len(result['parts']),1)
        self.assertEqual(result['parts'][0]['components'],1)
        self.assertAlmostEqual(result['cutVolume'],shape.volume(),places=5)
        self.assertAlmostEqual(load_model(self.folder/'Teil_001.stl').volume(),shape.volume(),places=3)

    def test_grid_cut_away_from_cavity_preserves_negative_shell(self):
        shape=md.Manifold.cube((300,100,80))-md.Manifold.cube((50,50,50)).translate((20,25,15))
        result=self.run_slice(shape,mode='none',strategy='equal')
        self.assertAlmostEqual(result['cutVolume'],shape.volume(),places=5)
        self.assertEqual(len(result['parts']),2)

    def test_material_island_inside_cavity_is_a_separate_part(self):
        shape=md.Manifold.cube((100,100,100))-md.Manifold.cube((80,80,80)).translate((10,10,10))
        shape+=md.Manifold.cube((10,10,10)).translate((30,30,30))
        result=self.run_slice(shape,mode='none')
        self.assertEqual(len(result['parts']),2)
        self.assertAlmostEqual(result['cutVolume'],shape.volume(),places=5)

    def test_demo_improves_part_count_without_hiding_unjoined_parts(self):
        shape=demo_dragon();result=self.run_slice(shape)
        self.assertLess(len(result['parts']),31)
        self.assertGreater(len(result['joints']),0)
        # Independently traverse the actual joint endpoints; never accept
        # contacts alone or empty connector geometry as evidence of connection.
        unseen=set(p['id'] for p in result['parts']);groups=[]
        while unseen:
            todo=[min(unseen)];unseen.remove(todo[0]);group=set()
            while todo:
                node=todo.pop();group.add(node)
                for joint in result['joints']:
                    other=joint['b'] if joint['a']==node else joint['a'] if joint['b']==node else None
                    if other in unseen:unseen.remove(other);todo.append(other)
            groups.append(group)
        self.assertEqual(result['assembly']['connected'],len(groups)==1)
        self.assertEqual({frozenset(g) for g in result['assembly']['groups']},{frozenset(g) for g in groups})
        if len(groups)>1:self.assertTrue(any('lose Baugruppen' in w for w in result['warnings']))

    def test_huge_grid_is_rejected_before_allocating_cut_lists(self):
        with self.assertRaisesRegex(ValueError,'Rasterzellen'):
            self.run_slice(md.Manifold.cube((1e9,10,10)),strategy='equal',mode='none')

    def test_huge_adaptive_span_is_rejected_before_search(self):
        with self.assertRaisesRegex(ValueError,'Modellspanne'):
            self.run_slice(md.Manifold.cube((1e9,10,10)),mode='none')

    def test_scoring_budget_fallback_is_reported_and_remains_real(self):
        with patch('planning.MAX_EVALUATIONS',0):
            result=self.run_slice(md.Manifold.cube((300,100,80)),mode='none')
        self.assertTrue(result['planning']['budgetReached'])
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['parts']),2)
        self.assertTrue(any('Bewertungsbudget' in w for w in result['warnings']))


if __name__=='__main__':unittest.main(verbosity=2)
