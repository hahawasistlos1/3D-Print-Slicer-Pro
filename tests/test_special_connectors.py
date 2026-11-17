from pathlib import Path
import tempfile
import unittest

import manifold3d as md
import numpy as np

from geometry import load_model, slice_model
from exporting import export_file, read_export
from special_connectors import sample_screw_insertion, thread_profile


class SpecialConnectorsTests(unittest.TestCase):
    def cut(self, folder, **settings):
        shape = md.Manifold.cube((300,100,80))
        return slice_model(shape, {'strategy':'equal','count':1,**settings}, folder)

    def test_clip_modes_use_closed_parts_and_keep_motion_open(self):
        for mode, loose in (('integrated',0),('separate',2),('mixed',1)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                result=self.cut(folder,kind='clip',mode=mode,count=2)
                self.assertTrue(result['valid'])
                self.assertEqual(len(result['joints']),2)
                self.assertEqual(len(result['connectors']),loose)
                self.assertFalse(result['motion']['pathVerified'])
                self.assertEqual(result['motion']['reason'],'flexible-or-rotational-joints')
                self.assertTrue(all(0<j['clipStrainPercent']<=3 for j in result['joints']))
                for record in result['parts']+result['connectors']:
                    self.assertGreater(load_model(Path(folder)/record['file'],normalize=False).volume(),0)

    def test_clip_limit_and_retention(self):
        with tempfile.TemporaryDirectory() as folder:
            r=self.cut(folder,kind='clip',clipStrainPercent=.1)
            self.assertEqual(len(r['joints']),0)
            r=self.cut(folder,kind='clip')
            a,b=(load_model(Path(folder)/p['file'],normalize=False) for p in r['parts'])
            pin=load_model(Path(folder)/r['connectors'][0]['file'],normalize=False)
            self.assertLess((pin^a).volume()+(pin^b).volume(),1e-5)
            self.assertGreater((pin.translate((1,0,0))^a).volume(),.05)

    def test_helical_profile_repeats_and_rotates_between_levels(self):
        thread=thread_profile(5,2,0,12,.8)
        slices=[thread.slice(height) for height in (3,4,5)]
        self.assertLess((slices[0]-slices[2]).area()+(slices[2]-slices[0]).area(),1e-6)
        self.assertGreater((slices[0]-slices[1]).area(),1)

    def test_screw_uses_real_tapped_socket_and_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            r=self.cut(folder,kind='screw',threadPitch=2.5,threadLength=15)
            self.assertTrue(r['valid'])
            j=r['joints'][0]
            self.assertEqual((j['pitch'],j['threadLength']),(2.5,15))
            self.assertAlmostEqual(j['gripLength'],150)
            self.assertFalse(r['motion']['pathVerified'])
            self.assertEqual(j['screwInsertion']['status'],'samples-clear')
            self.assertEqual(j['screwInsertion']['testedPoses'],49)
            p=r['connectors'][0]
            screw=load_model(Path(folder)/p['file'],normalize=False)
            receiver=load_model(Path(folder)/r['parts'][1]['file'],normalize=False)
            self.assertLess((screw^receiver).volume(),1e-4)
            self.assertGreater((screw.translate((-1.25,0,0))^receiver).volume(),.1)
            output=Path(folder)/'Schraube.3mf'
            export_file(screw,output,order=p['printOrder'])
            self.assertAlmostEqual(read_export(output,'3mf').volume()/screw.volume(),1,places=5)

    def test_screw_sample_detects_obstruction_between_clear_endpoints(self):
        pin=md.Manifold.cylinder(.5,1)
        blocker=md.Manifold.cube((1,1,.1),center=True).translate((0,0,-.75))
        joint={'pitch':1,'threadLength':2,'center':[0,0,0],'axis':2}
        self.assertEqual((pin^blocker).volume(),0)
        self.assertEqual((pin.translate((0,0,-2))^blocker).volume(),0)
        report=sample_screw_insertion(pin,[('Hindernis',blocker)],joint,20)
        self.assertEqual(report['status'],'collision')
        self.assertEqual(report['obstacle'],'Hindernis')
        self.assertTrue(0<report['remainingTravel']<2)
        incomplete=sample_screw_insertion(pin,[('Hindernis',blocker)],joint,1)
        self.assertEqual((incomplete['status'],incomplete['testedPoses']),('budget',1))

    def test_disabling_assembly_checks_skips_the_screw_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            result=self.cut(folder,kind='screw',pathCheck=False)
            self.assertNotIn('screwInsertion',result['joints'][0])

    def test_screw_rejects_blind_entry_and_oversized_screw(self):
        shape=md.Manifold.cube((300,100,80))
        with tempfile.TemporaryDirectory() as folder:
            r=slice_model(shape,{'strategy':'equal','kind':'screw','bedX':200,'bedY':35,'bedZ':35,
                                 'diameter':16,'wall':12,'count':1},folder)
            self.assertEqual(len(r['joints']),0)
            for settings in ({'mode':'integrated'},{'threadPitch':20},{'threadLength':1}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    self.cut(folder,kind='screw',**settings)


if __name__=='__main__':
    unittest.main()
