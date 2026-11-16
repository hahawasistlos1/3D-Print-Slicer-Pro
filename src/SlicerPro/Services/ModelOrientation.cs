using System.Windows.Media.Media3D;
namespace SlicerPro.Services;

public static class ModelOrientation
{
 public static double[][] Matrix(double[] angles)
 {
  if(angles.Length!=3||angles.Any(a=>!double.IsFinite(a)||Math.Abs(a)>360))throw new ArgumentException("Winkel für X, Y und Z zwischen -360 und 360 Grad eingeben.");
  var x=angles[0]*Math.PI/180;var y=angles[1]*Math.PI/180;var z=angles[2]*Math.PI/180;
  var cx=Math.Cos(x);var cy=Math.Cos(y);var cz=Math.Cos(z);var sx=Math.Sin(x);var sy=Math.Sin(y);var sz=Math.Sin(z);
  double[][] matrix=[[cz*cy,cz*sy*sx-sz*cx,cz*sy*cx+sz*sx],[sz*cy,sz*sy*sx+cz*cx,sz*sy*cx-cz*sx],[-sy,cy*sx,cy*cx]];
  foreach(var row in matrix)for(var i=0;i<3;i++)if(Math.Abs(row[i])<1e-14)row[i]=0;
  return matrix;
 }
 public static double[] Transform(double[] point,double[][] matrix)=>matrix.Select(row=>row[0]*point[0]+row[1]*point[1]+row[2]*point[2]).ToArray();
 public static bool IsIdentity(double[] angles)
 {
  var matrix=Matrix(angles);return Enumerable.Range(0,3).All(i=>Enumerable.Range(0,3).All(j=>Math.Abs(matrix[i][j]-(i==j?1:0))<1e-12));
 }
 public static (MeshGeometry3D Mesh,MeshInfo Info) Preview(MeshGeometry3D source,double[] angles)
 {
  var matrix=Matrix(angles);var points=new List<double[]>(source.Positions.Count);double[] lo=[double.PositiveInfinity,double.PositiveInfinity,double.PositiveInfinity],hi=[double.NegativeInfinity,double.NegativeInfinity,double.NegativeInfinity];
  foreach(var point in source.Positions){var p=Transform([point.X,-point.Z,point.Y],matrix);points.Add(p);for(int i=0;i<3;i++){lo[i]=Math.Min(lo[i],p[i]);hi[i]=Math.Max(hi[i],p[i]);}}
  if(points.Count==0)throw new ArgumentException("Kein Anzeigenetz vorhanden.");
  var mesh=new MeshGeometry3D{TriangleIndices=source.TriangleIndices.Clone()};
  foreach(var p in points)mesh.Positions.Add(new Point3D(p[0]-lo[0],p[2]-lo[2],-(p[1]-lo[1])));
  mesh.Freeze();return (mesh,new MeshInfo{Dimensions=Enumerable.Range(0,3).Select(i=>hi[i]-lo[i]).ToArray(),Triangles=source.TriangleIndices.Count/3});
 }
}
