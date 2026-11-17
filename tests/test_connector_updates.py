import tempfile
import unittest
from pathlib import Path

import manifold3d as md
import numpy as np

from geometry import load_model, slice_model
from motion import Body, MotionChecker
from print_checks import print_checks


class ConnectorUpdateTests(unittest.TestCase):
    def slice(self, shape=None, **settings):
        shape=md.Manifold.cube((300,100,80)) if shape is None else shape
        with tempfile.TemporaryDirectory() as tmp:
            result=slice_model(shape,{'strategy':'equal','count':1,'depth':10,**settings},tmp)
            parts=[Body(str(p['id']),load_model(Path(tmp)/p['file'],normalize=False)) for p in result['parts']]
            pins=[Body(p['id'],load_model(Path(tmp)/p['file'],normalize=False)) for p in result['connectors']]
        return result, parts, pins

    def test_side_loaded_key_in_all_modes(self):
        for mode,count in (('integrated',0),('separate',2),('mixed',1)):
            with self.subTest(mode=mode):
                r,parts,pins=self.slice(kind='dovetail',mode=mode,count=2)
                self.assertTrue(r['valid'] and r['motion']['pathVerified'])
                self.assertEqual(len(r['joints']),2)
                self.assertEqual(len(pins),count)
                self.assertEqual(r['joints'][0]['removalDirection'],[0,-1,0])
                self.assertAlmostEqual((parts[0].solid^parts[1].solid).volume(),0)
                for pin in pins:
                    self.assertGreater(pin.solid.volume(),10*20*40)
                    self.assertLess(pin.solid.volume(),15*20*40)

    def test_undercut_blocks_perpendicular_withdrawal(self):
        r,parts,pins=self.slice(kind='dovetail')
        joint=r['joints'][0]
        self.assertEqual(MotionChecker().check(pins,[parts[0]],joint['pinWithdrawal'],100)['status'],'clear')
        self.assertEqual(MotionChecker().check(pins,[parts[0]],[1,0,0],30)['status'],'collision')

    def test_oblique_seam_along_vertical_flat_entry(self):
        body=md.Manifold.cube((100,100,90))
        edit={'point':[50,50,45],'normal':[1,1,0]}
        r,_,_=self.slice(body,kind='dovetail',strategy='adaptive',edits=[edit])
        self.assertTrue(r['motion']['pathVerified'])
        joint=r['joints'][0]
        np.testing.assert_allclose(np.abs(joint['pinWithdrawal']),[0,0,1],atol=1e-9)
        self.assertAlmostEqual(np.dot(joint['normal'],joint['pinWithdrawal']),0.)

    def test_thin_panel_does_not_get_side_groove(self):
        r,_,_=self.slice(md.Manifold.cube((300,100,4)),kind='dovetail')
        self.assertEqual(r['joints'],[])
        self.assertTrue(any('Wandreserve' in w for w in r['warnings']))

    def test_manual_centers_replace_auto_count_and_preserve_geometry_checks(self):
        initial,_,_=self.slice()
        a,b=initial['parts']
        positions=[{'interfaceId':'S001','aKey':a['key'],'bKey':b['key'],'center':[150,y,42]} for y in (25,75)]
        r,parts,pins=self.slice(placements=positions)
        self.assertEqual(r['interfaces'][0]['requested'],2)
        np.testing.assert_allclose([j['center'] for j in r['joints']],[p['center'] for p in positions],rtol=0,atol=1e-9)
        self.assertTrue(all(j['manualPosition'] for j in r['joints']))
        self.assertEqual(len(pins),2)
        self.assertTrue(all((pin.solid^part.solid).volume()<1e-6 for pin in pins for part in parts))
        self.assertTrue(r['motion']['pathVerified'])

    def test_invalid_manual_positions_fail_instead_of_moving(self):
        initial,_,_=self.slice()
        a,b=initial['parts']
        placement={'interfaceId':'S001','aKey':a['key'],'bKey':b['key'],'center':[150,50,40]}
        for change in ({'center':[151,50,40]},{'center':[150,1,1]},{'aKey':'stale'},{'interfaceId':'S002'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.slice(placements=[{**placement,**change}])
        with self.assertRaisesRegex(ValueError,'kollidieren'):
            self.slice(placements=[placement,placement])

    def test_close_manual_round_dowels_preserve_both_wall_envelopes(self):
        initial,_,_=self.slice()
        a,b=initial['parts']
        placement={'interfaceId':'S001','aKey':a['key'],'bKey':b['key'],'center':[150,40,40]}
        # At diameter 3, tolerance .2 and wall 2, the two radii sum to 7.2 mm.
        second={**placement,'center':[150,47.8,40]}
        r,parts,pins=self.slice(diameter=3,placements=[placement,second])
        self.assertEqual(len(pins),2)
        self.assertTrue(r['motion']['pathVerified'])
        self.assertTrue(all((pin.solid^part.solid).volume()<1e-6 for pin in pins for part in parts))
        with self.assertRaisesRegex(ValueError,'kollidieren'):
            self.slice(diameter=3,placements=[placement,{**second,'center':[150,47.6,40]}])

    def test_manually_placed_key_on_an_oblique_interface(self):
        body=md.Manifold.cube((100,100,90))
        settings={'kind':'dovetail','strategy':'adaptive','edits':[{'point':[50,50,45],'normal':[1,1,0]}]}
        initial,_,_=self.slice(body,**settings)
        a,b=initial['parts']
        placement={'interfaceId':'S001','aKey':a['key'],'bKey':b['key'],'center':[45,55,45]}
        r,_,_=self.slice(body,placements=[placement],**settings)
        np.testing.assert_allclose(r['joints'][0]['center'],placement['center'],atol=1e-6)
        self.assertTrue(r['motion']['pathVerified'])

    def test_interface_preview_keeps_hole_in_cut_surface(self):
        shape=md.Manifold.cube((300,100,80))-md.Manifold.cube((300,70,50)).translate((0,15,15))
        r,_,_=self.slice(shape,diameter=4,depth=4)
        interface=r['interfaces'][0]
        surface=interface['surface']
        vertices=np.array(surface['vertices'])
        triangles=vertices[np.array(surface['indices']).reshape(-1,3)]
        self.assertTrue(np.all(vertices[:,0]==interface['offset']))
        area=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1).sum()/2
        self.assertAlmostEqual(area,100*80-70*50)
        centroids=triangles.mean(axis=1)
        self.assertFalse(np.any((centroids[:,1]>15)&(centroids[:,1]<85)&(centroids[:,2]>15)&(centroids[:,2]<65)))

    def test_thin_wall_and_cavity_ceiling(self):
        shell=md.Manifold.cube((8,10,4))-md.Manifold.cube((6,8,2)).translate((1,1,1))
        report=print_checks(shell,[0,1,2],1.5,192)
        self.assertEqual(report['minimumSample'],1)
        self.assertGreater(report['validRays'],0)
        self.assertGreater(report['thinSamples'],0)
        self.assertEqual(report['overhangArea'],48)
        self.assertEqual(len(report['samplePoints']),8)

    def test_bed_face_excluded_and_wall_sampling_bounded(self):
        block=md.Manifold.cube((8,10,.6))
        report=print_checks(block,[0,1,2],1,12)
        self.assertEqual(report['minimumSample'],.6)
        self.assertEqual(report['overhangArea'],0)
        self.assertEqual(print_checks(block,[0,1,2],1,3)['testedRays'],3)
        self.assertEqual(print_checks(block,[0,1,2],0,3)['testedRays'],0)

    def test_wall_report_in_result_and_parts_remain_exportable(self):
        r,_,_=self.slice(md.Manifold.cube((100,80,.7)),mode='none')
        self.assertTrue(r['valid'])
        self.assertAlmostEqual(r['parts'][0]['printChecks']['minimumSample'],.7)
        self.assertTrue(any('Dünnwand-Hinweis' in w for w in r['warnings']))

    def test_detailed_wall_check_covers_a_dense_part(self):
        shape=md.Manifold.cylinder(5,15,circular_segments=80)
        basic,_,_=self.slice(shape,mode='none')
        detailed,_,_=self.slice(shape,mode='none',detailedWallCheck=True)
        self.assertEqual(basic['parts'][0]['printChecks']['testedRays'],192)
        self.assertEqual(detailed['parts'][0]['printChecks']['testedRays'],shape.num_tri())


if __name__=='__main__':
    unittest.main()
