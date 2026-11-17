from pathlib import Path
import sys
import tempfile
import unittest

import manifold3d as md
import numpy as np
import trimesh

from geometry import load_model, mesh_of, solid_of, write_stl
from preview import prepare_previews
from exporting import export_file, read_export
from indexed_mesh import indexed_path
from mesh_repair import ExtendedPlanarRepairAvailable
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_three_mf import mesh_object, model, package


def punctured_cube(size=20, opening=1):
    mesh=mesh_of(md.Manifold.cube((size,)*3))
    outer_points=[(0,0,size),(size,0,size),(size,size,size),(0,size,size)]
    outer=[int(np.flatnonzero(np.all(mesh.vertices==p,axis=1))[0]) for p in outer_points]
    lo,hi=(size-opening)/2,(size+opening)/2
    inner=np.array([(lo,lo,size),(hi,lo,size),(hi,hi,size),(lo,hi,size)])
    start=len(mesh.vertices)
    ring=[]
    for i in range(4):
        j=(i+1)%4
        ring.extend([(outer[i],outer[j],start+i),(outer[j],start+j,start+i)])
    sides=mesh.faces[~np.all(mesh.triangles[:,:,2]==size,axis=1)]
    return trimesh.Trimesh(np.vstack((mesh.vertices,inner)),np.vstack((sides,ring)),process=False)


def multipart_example(path, *, large=False, crossing=False):
    mesh=punctured_cube(100,16) if large else punctured_cube()
    vertices=''.join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x,y,z in mesh.vertices)
    triangles=''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in mesh.faces)
    object_xml=f'<object id="1"><mesh><vertices>{vertices}</vertices><triangles>{triangles}</triangles></mesh></object>'
    offset='48 48 98' if crossing else '120 0 0' if large else '30 0 0'
    items=('<item p:path="/3D/damaged.model" objectid="1"/>'
           f'<item p:path="/3D/intact.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 {offset}"/>')
    package(path,{'3D/assembly.model':model('',items),'3D/damaged.model':model(object_xml),
                  '3D/intact.model':model(mesh_object(1,(5,5,5)))})


def concave_puncture():
    cube=mesh_of(md.Manifold.cube((20,20,20)))
    outer=np.array([(0,0),(20,0),(20,20),(0,20)])
    inner=np.array([(9,9),(10.5,9),(10.5,10),(10,10),(10,10.5),(9,10.5)])[::-1]
    outline=[int(np.flatnonzero(np.all(cube.vertices==(*p,20),axis=1))[0]) for p in outer]
    index=np.r_[outline,np.arange(len(cube.vertices),len(cube.vertices)+len(inner))]
    rim=index[md.triangulate([outer,inner])]
    rest=cube.faces[~np.all(cube.triangles[:,:,2]==20,axis=1)]
    vertices=np.vstack((cube.vertices,np.column_stack((inner,np.full(len(inner),20)))))
    return trimesh.Trimesh(vertices,np.vstack((rest,rim)),process=False)


def touching_example(path):
    items=('<item p:path="/3D/cube.model" objectid="1"/>'
           '<item p:path="/3D/cube.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 10 10 0"/>')
    package(path,{'3D/assembly.model':model('',items),'3D/cube.model':model(mesh_object(1,(10,10,10)))})


class MeshRepairTests(unittest.TestCase):
    def test_extended_repair_requires_opt_in_preserves_file_and_reports_larger_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'large-opening.3mf'
            multipart_example(path,large=True)
            before=path.read_bytes()
            with self.assertRaisesRegex(ExtendedPlanarRepairAvailable,'3MF-Netz 1/2'):
                load_model(path,repair_report={})
            report={}
            repaired=load_model(path,repair_report=report,extended_repair=True)
            self.assertEqual(report,{'holesClosed':1,'largeHolesClosed':1})
            self.assertAlmostEqual(repaired.volume(),100**3+125)
            self.assertEqual(path.read_bytes(),before)

    def test_extended_repair_rejects_crossing_from_another_3mf_component(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'crossed-opening.3mf'
            multipart_example(path,large=True,crossing=True)
            with self.assertRaisesRegex(ValueError,'kreuzt die geplante Reparatur'):
                load_model(path,repair_report={},extended_repair=True)

    def test_repair_closes_small_concave_planar_hole(self):
        report={}
        solid=solid_of(concave_puncture(),repair_report=report)
        self.assertEqual(report,{'holesClosed':1})
        self.assertAlmostEqual(solid.volume(),8000)

    def test_repair_rejects_intersection_inside_concave_hole(self):
        crossing=mesh_of(md.Manifold.cube((.2,.2,2)).translate((9.3,10.3,19)))
        combined=trimesh.util.concatenate([concave_puncture(),crossing])
        with self.assertRaisesRegex(ValueError,'kreuzt die geplante Reparatur'):
            solid_of(combined,repair_report={})

    def test_small_flat_hole_repaired_and_saved_as_strict_solid(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'damaged.stl'
            punctured_cube().export(source)
            before=source.read_bytes()
            with self.assertRaisesRegex(ValueError,'offen'):
                load_model(source)
            report={}
            solid=load_model(source,repair_report=report)
            self.assertEqual(report,{'holesClosed':1})
            self.assertAlmostEqual(solid.volume(),8000)
            restored=Path(folder)/'restored.stl'
            write_stl(solid,restored)
            self.assertAlmostEqual(load_model(restored).volume(),8000)
            self.assertEqual(source.read_bytes(),before)

    def test_reorients_faces_without_inverting_a_cavity(self):
        shell=md.Manifold.cube((30,30,30))-md.Manifold.cube((10,10,10)).translate((10,10,10))
        mesh=mesh_of(shell)
        faces=mesh.faces.copy()
        faces[[0,-1]]=faces[[0,-1],::-1]
        mesh.faces=faces
        report={}
        solid=solid_of(mesh,repair_report=report)
        self.assertEqual(report,{'facesReoriented':2})
        self.assertAlmostEqual(solid.volume(),26000)

    def test_closes_microscopic_seam_without_inventing_faces(self):
        mesh=mesh_of(md.Manifold.cube((20,20,20)))
        faces=mesh.faces.copy()
        vertices=np.vstack((mesh.vertices,mesh.vertices[faces[0]]+[0,0,0.0000005]))
        faces[0]=np.arange(len(vertices)-3,len(vertices))
        candidate=trimesh.Trimesh(vertices,faces,process=False)
        report={}
        solid=solid_of(candidate,repair_report=report)
        self.assertEqual(report,{'seamsJoined':1})
        self.assertAlmostEqual(solid.volume(),8000,places=2)

    def test_large_missing_face_and_nonmanifold_edge_stay_invalid(self):
        cube=mesh_of(md.Manifold.cube((20,20,20)))
        faces=cube.faces[~np.all(cube.triangles[:,:,2]==20,axis=1)]
        missing=trimesh.Trimesh(cube.vertices,faces,process=False)
        with self.assertRaisesRegex(ValueError,'Randlinie zu groß'):
            solid_of(missing,repair_report={})
        a,b=cube.faces[0,:2]
        triangle=trimesh.Trimesh(np.vstack((cube.vertices,[-1,-1,-1])),np.vstack((cube.faces,[a,b,len(cube.vertices)])),process=False)
        with self.assertRaisesRegex(ValueError,'mehr als zwei Flächen'):
            solid_of(triangle,repair_report={})

    def test_rejects_a_cap_that_would_cross_another_surface(self):
        crossing=mesh_of(md.Manifold.cube((.2,.2,2)).translate((9.9,9.9,19)))
        combined=trimesh.util.concatenate([punctured_cube(),crossing])
        with self.assertRaisesRegex(ValueError,'kreuzt die geplante Reparatur'):
            solid_of(combined,repair_report={})

    def test_repairs_only_the_damaged_3mf_component(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'damaged.3mf'
            multipart_example(path)
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'3MF-Netz 1/2'):
                load_model(path)
            report={}
            shape=load_model(path,repair_report=report)
            self.assertEqual(report,{'holesClosed':1})
            self.assertEqual(len(shape.decompose()),2)
            self.assertAlmostEqual(shape.volume(),8125)
            self.assertEqual(path.read_bytes(),before)

    def test_preserves_topology_when_an_stl_weld_would_join_distinct_edges(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'contact.3mf'
            touching_example(source)
            shape=load_model(source)
            stl=root/'original.stl'
            write_stl(shape,stl,indexed=True)
            with self.assertRaisesRegex(ValueError,'nicht mannigfaltig'):
                load_model(stl)
            indexed=load_model(stl,use_indexed=True)
            self.assertEqual(len(indexed.decompose()),2)
            self.assertAlmostEqual(indexed.volume(),2000)
            preview=prepare_previews([{'key':'original','input':str(stl),'budget':120000}],root/'display')
            self.assertTrue(preview[0]['topologyPreserved'])
            self.assertEqual(preview[0]['triangles'],24)
            exported=root/'indexed.3mf'
            export_file(indexed,exported)
            self.assertAlmostEqual(read_export(exported,'3mf').volume(),2000)

    def test_corrupt_internal_index_file_cannot_replace_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            stl=Path(folder)/'original.stl'
            write_stl(md.Manifold.cube((10,10,10)),stl)
            indexed_path(stl).write_bytes(b'SPMESH01'+b'\xff'*8)
            with self.assertRaisesRegex(ValueError,'Netzdatei'):
                load_model(stl,use_indexed=True)
            self.assertAlmostEqual(load_model(stl).volume(),1000)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--example':
        multipart_example(Path(sys.argv[2]))
    elif len(sys.argv)==3 and sys.argv[1]=='--large-example':
        multipart_example(Path(sys.argv[2]),large=True)
    elif len(sys.argv)==3 and sys.argv[1]=='--contact-example':
        touching_example(Path(sys.argv[2]))
    else:
        unittest.main()
