import tempfile
import unittest
from pathlib import Path
import manifold3d as md
import numpy as np
from motion import Body,MotionChecker,analyze_assembly,allowed_directions


class MotionTests(unittest.TestCase):
    def test_reused_checker_does_not_cache_by_display_name(self):
        checker=MotionChecker()
        a=Body('a',md.Manifold.cube((10,10,10)))
        b=Body('b',md.Manifold.cube((10,10,10)).translate((20,0,0)))
        self.assertEqual(checker.check([a],[b],[-1,0,0],40)['status'],'clear')
        # Identical labels, different geometry and a real initial collision.
        b=Body('b',md.Manifold.cube((10,10,10)).translate((5,0,0)))
        self.assertEqual(checker.check([a],[b],[-1,0,0],40)['reason'],'initial-overlap')

    def test_reused_checker_refreshes_swept_mesh_for_same_label(self):
        checker=MotionChecker()
        channel=md.Manifold.cube((10,10,10))-md.Manifold.cube((12,4,4)).translate((-1,3,3))
        obstacle=Body('obstacle',md.Manifold.cube((1,2,2)).translate((20,4,4)))
        self.assertEqual(checker.check([Body('body',channel)],[obstacle],[1,0,0],40)['status'],'clear')
        self.assertEqual(checker.check([Body('body',md.Manifold.cube((10,10,10)))],[obstacle],[1,0,0],40)['status'],'collision')

    def test_clear_path_is_proven_continuously(self):
        a=Body('a',md.Manifold.cube((10,10,10)))
        b=Body('b',md.Manifold.cube((10,10,10)).translate((20,0,0)))
        self.assertEqual(MotionChecker().check([a],[b],[-1,0,0],40)['status'],'clear')

    def test_thin_obstacle_between_sample_positions_is_detected(self):
        a=Body('a',md.Manifold.cube((1,1,1)))
        b=Body('b',md.Manifold.cube((.03,4,4)).translate((13.371,-1,-1)))
        result=MotionChecker().check([a],[b],[1,0,0],50)
        self.assertEqual(result['status'],'collision')

    def test_concave_sweep_keeps_open_channel(self):
        # Convex-hull broad phase overlaps the obstacle; the exact triangle
        # sweep must still prove that an open U channel slides past it.
        u=md.Manifold.cube((10,10,10))-md.Manifold.cube((12,4,4)).translate((-1,3,3))
        obstacle=md.Manifold.cube((1,2,2)).translate((20,4,4))
        result=MotionChecker().check([Body('u',u)],[Body('pin',obstacle)],[1,0,0],40)
        self.assertEqual(result['status'],'clear')

    def test_blind_hole_withdrawal_is_clear_but_wrong_direction_hits_pin(self):
        pin=md.Manifold.cylinder(12,1,center=True).rotate((0,90,0)).translate((10,5,5))
        socket=md.Manifold.cylinder(12.4,1.2,center=True).rotate((0,90,0)).translate((10,5,5))
        block=md.Manifold.cube((10,10,10)).translate((10,0,0))-socket
        self.assertEqual(MotionChecker().check([Body('b',block)],[Body('p',pin)],[1,0,0],30)['status'],'clear')
        self.assertEqual(MotionChecker().check([Body('b',block)],[Body('p',pin)],[-1,0,0],30)['status'],'collision')

    def test_initial_overlap_is_not_a_valid_path(self):
        a=md.Manifold.cube((10,10,10))
        result=MotionChecker().check([Body('a',a)],[Body('b',a.translate((5,0,0)))],[-1,0,0],30)
        self.assertEqual(result['reason'],'initial-overlap')

    def test_budget_exhaustion_never_becomes_success(self):
        a=md.Manifold.cube((10,10,10));b=a.translate((20,0,0))
        self.assertEqual(MotionChecker(max_tests=0).check([Body('a',a)],[Body('b',b)],[1,0,0],40)['status'],'unknown')

    def test_multiple_joint_axes_are_reported_as_unresolved(self):
        joints=[{'a':1,'b':2,'axis':0,'mode':'integrated'},{'a':1,'b':3,'axis':1,'mode':'integrated'}]
        self.assertEqual(allowed_directions(1,joints,{1,2,3}),[])

    def test_two_parts_produce_reversible_assembly_order(self):
        parts=[{'solid':md.Manifold.cube((10,10,10))},{'solid':md.Manifold.cube((10,10,10)).translate((10,0,0))}]
        result=analyze_assembly(parts,[{'id':'V001','a':1,'b':2,'axis':0,'mode':'integrated'}],[])
        self.assertTrue(result['pathVerified'])
        self.assertEqual(len(result['disassemblySteps']),1)
        self.assertEqual(len(result['assemblySteps']),2)

    def test_pin_preinsertion_and_carrying_are_included(self):
        pin=md.Manifold.cylinder(12,1,center=True).rotate((0,90,0)).translate((10,5,5))
        socket=md.Manifold.cylinder(12.4,1.2,center=True).rotate((0,90,0)).translate((10,5,5))
        parts=[{'solid':md.Manifold.cube((10,10,10))-socket},
               {'solid':md.Manifold.cube((10,10,10)).translate((10,0,0))-socket}]
        joints=[{'id':'V001','a':1,'b':2,'axis':0,'mode':'separate'}]
        result=analyze_assembly(parts,joints,[('V001',pin)])
        self.assertTrue(result['pathVerified'])
        self.assertEqual(len(result['preinsertSteps']),1)
        self.assertEqual(result['preinsertSteps'][0]['insertionDirection'],[-1,0,0])
        self.assertEqual(result['disassemblySteps'][0]['carriedConnectors'],['V001'])

    def test_sealed_cavity_does_not_offer_a_false_escape(self):
        shell=md.Manifold.cube((30,30,30))-md.Manifold.cube((20,20,20)).translate((5,5,5))
        island=md.Manifold.cube((4,4,4)).translate((13,13,13))
        result=analyze_assembly([{'solid':shell},{'solid':island}],[],[])
        self.assertFalse(result['pathVerified'])
        self.assertEqual(result['remainingParts'],[1,2])
        self.assertTrue(any(f['status']=='collision' for f in result['lastFailures']))

    def test_all_axis_directions_match_independent_dense_checks(self):
        rng=np.random.default_rng(20261106)
        moving=md.Manifold.cube((8,8,8))-md.Manifold.cube((10,3,3)).translate((-1,2.5,2.5))
        checked=0
        for axis in range(3):
            for sign in (-1,1):
                direction=np.zeros(3);direction[axis]=sign
                for _ in range(3):
                    center=rng.uniform(-12,20,3)
                    obstacle=md.Manifold.cube((2,2,2)).translate(center)
                    result=MotionChecker().check([Body('m',moving)],[Body('o',obstacle)],direction,25)
                    if result['status']=='clear':
                        checked+=1
                        for fraction in np.linspace(0,1,81):
                            self.assertLessEqual((moving.translate(direction*25*fraction)^obstacle).volume(),1e-6)
        self.assertGreater(checked,0)

    def test_face_budget_is_reported_as_unknown(self):
        u=md.Manifold.cube((10,10,10))-md.Manifold.cube((12,4,4)).translate((-1,3,3))
        obstacle=md.Manifold.cube((1,2,2)).translate((20,4,4))
        checker=MotionChecker(max_faces=0)
        self.assertEqual(checker.check([Body('u',u)],[Body('p',obstacle)],[1,0,0],40)['status'],'unknown')
        self.assertTrue(checker.exhausted)

    def test_auto_sizing_creates_real_smaller_dowel_without_reducing_wall(self):
        from geometry import slice_model,load_model,info
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            shape=md.Manifold.cube((300,11,11))
            fixed=slice_model(shape,{'count':1,'pathCheck':False},Path(folder)/'fixed')
            automatic=slice_model(shape,{'count':1,'autoSize':True,'pathCheck':False},Path(folder)/'auto')
            self.assertEqual(len(fixed['joints']),0)
            self.assertEqual(len(automatic['joints']),1)
            joint=automatic['joints'][0]
            self.assertTrue(joint['autoSized']);self.assertLess(joint['diameter'],10)
            self.assertGreaterEqual(joint['diameter'],3);self.assertEqual(automatic['settings']['wall'],2)
            pin=load_model(Path(folder)/'auto'/automatic['connectors'][0]['file'])
            self.assertAlmostEqual(min(info(pin)['dimensions']),joint['diameter'],places=4)

    def test_auto_sizing_respects_minimum_and_disabled_path_check(self):
        from geometry import slice_model
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            result=slice_model(md.Manifold.cube((300,7,7)),{'autoSize':True,'minDiameter':3,'pathCheck':False},folder)
            self.assertEqual(result['joints'],[])
            self.assertFalse(result['motion']['checked']);self.assertFalse(result['assembly']['pathVerified'])

    def test_small_overlaps_cannot_accumulate_into_false_success(self):
        moving=[Body(f'p{i}',md.Manifold.cube((.001,.001,.001)).translate((0,i*.002,0))) for i in range(20)]
        obstacle=Body('obstacle',md.Manifold.cube((.1,.05,.001)).translate((.05,0,0)))
        result=MotionChecker().check(moving,[obstacle],[1,0,0],.1)
        self.assertNotEqual(result['status'],'clear')

    def test_explicit_two_mm_minimum_can_connect_thin_demo_parts(self):
        from geometry import slice_model,demo_dragon
        root=Path(__file__).resolve().parents[1]/'artifacts/test-temp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            result=slice_model(demo_dragon(),{'strategy':'adaptive','autoSize':True,'minDiameter':2,'pathCheck':False},folder)
            self.assertTrue(result['assembly']['connected'])
            self.assertTrue(all(j['diameter']>=2 and j['depth']>=3 for j in result['joints']))
            self.assertTrue(any(j['autoSized'] for j in result['joints']))


if __name__=='__main__':unittest.main(verbosity=2)
