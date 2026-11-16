import tempfile
import unittest
from pathlib import Path

import manifold3d as md
import numpy as np

from geometry import load_model, slice_model
from motion import Body, MotionChecker


def plane(point, normal, target=None):
    return {'point': point, 'normal': normal, 'target': target}


class ManualEditTests(unittest.TestCase):
    def run_cut(self, edits, *, body=None, **settings):
        body = md.Manifold.cube((100, 80, 60)) if body is None else body
        with tempfile.TemporaryDirectory() as tmp:
            result = slice_model(body, {'strategy': 'adaptive', 'count': 1, 'edits': edits, **settings}, tmp)
            shapes = [load_model(Path(tmp)/part['file'], normalize=False) for part in result['parts']]
            return result, shapes

    def test_real_oblique_caps_and_volume_conservation(self):
        result, shapes = self.run_cut([plane([50,40,30], [1,1,0])], mode='none')
        self.assertTrue(result['valid'])
        self.assertEqual(len(shapes), 2)
        self.assertAlmostEqual(sum(shape.volume() for shape in shapes), 480000, places=4)
        self.assertAlmostEqual((shapes[0]^shapes[1]).volume(), 0, places=6)
        np.testing.assert_allclose(result['interfaces'][0]['normal'], [2**-.5,2**-.5,0])
        self.assertAlmostEqual(result['interfaces'][0]['area'], 80*60*2**.5, places=3)

    def test_round_separate_uses_real_slanted_mounting_and_preinsertion(self):
        result, _ = self.run_cut([plane([50,40,30], [1,1,0])])
        self.assertEqual(len(result['connectors']), 1)
        self.assertEqual(len(result['joints']), 1)
        self.assertTrue(result['motion']['pathVerified'])
        np.testing.assert_allclose(np.abs(result['motion']['assemblySteps'][1]['insertionDirection']), [2**-.5,2**-.5,0])
        np.testing.assert_allclose(result['motion']['preinsertSteps'][0]['insertionDirection'], [-2**-.5,-2**-.5,0])

    def test_rect_and_tongue_integration_and_cavity(self):
        for kind in ('rect', 'tongue'):
            with self.subTest(kind=kind):
                body = md.Manifold.cube((100,80,60))-md.Manifold.cube((20,18,16)).translate((40,30,22))
                result, shapes = self.run_cut([plane([50,40,30], [1,1,0])], body=body, mode='integrated', kind=kind)
                self.assertTrue(result['valid'])
                self.assertEqual(len(result['joints']), 1)
                self.assertEqual(result['connectors'], [])
                self.assertLess((shapes[0]^shapes[1]).volume()/body.volume(), 1e-8)

    def test_rectangular_pin_has_independent_dimensions(self):
        result, _ = self.run_cut([plane([50,40,30], [1,0,0])], kind='rect', diameter=7, rectHeight=19, depth=8)
        joint = result['joints'][0]
        self.assertEqual((joint['diameter'], joint['length'], joint['depth']), (7,19,8))
        self.assertEqual(sorted(result['connectors'][0]['dimensions']), [7,16,19])
        self.assertTrue(result['motion']['pathVerified'])

    def test_scoped_cut_does_not_split_neighbor(self):
        initial = [plane([50,40,30], [1,0,0])]
        first, _ = self.run_cut(initial, mode='none')
        target, untouched = [part['key'] for part in first['parts']]
        result, _ = self.run_cut(initial+[plane([50,40,30], [0,1,0], target)], mode='none')
        self.assertEqual(len(result['parts']), 3)
        self.assertIn(untouched, [part['key'] for part in result['parts']])
        self.assertEqual(len(result['interfaces']), 3)

    def test_union_then_local_resplit_has_no_stale_seam(self):
        edits = [plane([50,40,30], [1,1,0])]
        first, _ = self.run_cut(edits, mode='none')
        edits += [{'merge':[part['key'] for part in first['parts']]}]
        joined, shapes = self.run_cut(edits, mode='none')
        self.assertEqual(len(shapes), 1)
        self.assertEqual(joined['interfaces'], [])
        self.assertAlmostEqual(shapes[0].volume(), 480000)
        split, _ = self.run_cut(edits+[plane([50,40,30], [0,1,1], joined['parts'][0]['key'])], mode='none')
        self.assertEqual(len(split['parts']), 2)
        self.assertEqual([interface['plane'] for interface in split['interfaces']], [3])

    def test_merge_preserves_other_cap_contacts(self):
        first_plane = plane([50,40,30], [1,0,0])
        first, _ = self.run_cut([first_plane], mode='none')
        target = first['parts'][0]['key']
        edits = [first_plane, plane([50,40,30], [0,1,0], target)]
        split, _ = self.run_cut(edits, mode='none')
        edit = {'merge':[part['key'] for part in split['parts'] if part['key'].startswith(target+'/')]}
        merged, _ = self.run_cut(edits+[edit])
        self.assertEqual(len(merged['interfaces']), 1)
        self.assertEqual(len(merged['joints']), 1)
        self.assertTrue(merged['motion']['pathVerified'])

    def test_oversize_union_and_stale_target_are_rejected(self):
        settings = {'mode':'none', 'bedX':60, 'bedY':90, 'bedZ':70, 'optimize':False}
        initial, _ = self.run_cut([], **settings)
        with self.assertRaisesRegex(ValueError, 'überschreitet'):
            self.run_cut([{'merge':[p['key'] for p in initial['parts']]}], **settings)
        with self.assertRaisesRegex(ValueError, 'Zielteil'):
            self.run_cut([plane([50,40,30],[1,0,0], 'stale')], **settings)

    def test_non_intersecting_and_invalid_planes_rejected(self):
        for point, normal in (([300,40,30], [1,1,0]), ([50,40,30], [0,0,0]), ([50,40,30], [1,1]), ([float('nan'),0,0], [1,0,0])):
            with self.subTest(point=point, normal=normal), self.assertRaises(ValueError):
                self.run_cut([plane(point, normal)])

    def test_diagonal_sweep_detects_mid_path_obstacle(self):
        moving = Body('moving', md.Manifold.cube((2,2,2)))
        obstacle = Body('obstacle', md.Manifold.cube((1,1,1)).translate((7,7,.5)))
        self.assertEqual(MotionChecker().check([moving], [obstacle], [2**-.5,2**-.5,0], 20)['status'], 'collision')


if __name__ == '__main__':
    unittest.main()
