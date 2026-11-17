using System.Buffers.Binary;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Media3D;
namespace SlicerPro.Controls;

public sealed class ModelViewport : Grid
{
 public const int MaxMeshTriangles=4_000_000;
 readonly Viewport3D viewport=new(); readonly PerspectiveCamera camera=new(){FieldOfView=38,NearPlaneDistance=.1,FarPlaneDistance=1e8};
 readonly Model3DGroup root=new(); readonly Model3DGroup objects=new(); readonly Model3DGroup floor=new();
 readonly Dictionary<GeometryModel3D,int> hitParts=[];
 readonly Canvas annotations=new(){IsHitTestVisible=false};
 readonly List<(Point3D position,TextBlock label)> markers=[];
 readonly TextBlock dimensions=new(){Foreground=new SolidColorBrush(Color.FromRgb(168,204,224)),FontSize=11,Margin=new Thickness(13),VerticalAlignment=VerticalAlignment.Bottom,IsHitTestVisible=false};
 Point last; bool dragging; double yaw=-27,pitch=17,distance=1100,framingAspect=1; Point3D center=new(0,150,0); double modelSize=400;
 public event Action<double,double,double,Point3D>? CameraChanged;
 public event Action<int>? PartSelected;
 public double OpacityLevel {get;set;}=1;
 public string MeshNote {get;set;}="";
 public ModelViewport()
 {
  Background=Brushes.Transparent; ClipToBounds=true;
  viewport.Camera=camera;Children.Add(viewport);Children.Add(annotations);Children.Add(dimensions);SizeChanged+=(_,_)=>{var aspect=Math.Max(1,ActualWidth/Math.Max(1,ActualHeight));distance*=aspect/framingAspect;framingAspect=aspect;UpdateCamera(false);};
  root.Children.Add(new AmbientLight(Color.FromRgb(85,100,115)));
  root.Children.Add(new DirectionalLight(Color.FromRgb(225,237,255),new Vector3D(-.5,-1,-.7)));
  root.Children.Add(new DirectionalLight(Color.FromRgb(64,134,172),new Vector3D(1,.4,.6)));
  root.Children.Add(floor);root.Children.Add(objects);viewport.Children.Add(new ModelVisual3D{Content=root});
  MouseDown+=Down;MouseMove+=Move;MouseUp+=Up;MouseWheel+=Wheel;
  UpdateCamera(false);
 }
 static Point3D World(double x,double y,double z)=>new(x,z,-y);
 static Material Mat(Color color,double opacity=1)
 {
  var brush=new SolidColorBrush(Color.FromArgb((byte)(255*opacity),color.R,color.G,color.B));brush.Freeze();
  var m=new MaterialGroup();m.Children.Add(new DiffuseMaterial(brush));m.Children.Add(new SpecularMaterial(new SolidColorBrush(Color.FromArgb(130,180,220,245)),35));m.Freeze();return m;
 }
 static readonly Color Grey=Color.FromRgb(150,169,190),Cyan=Color.FromRgb(35,206,243);
 public static Color? ParsePartColor(string? color)
 {
  if(color is not {Length:7}||color[0]!='#'||!uint.TryParse(color.AsSpan(1),System.Globalization.NumberStyles.HexNumber,System.Globalization.CultureInfo.InvariantCulture,out var rgb))
   return null;
  return Color.FromRgb((byte)(rgb>>16),(byte)(rgb>>8),(byte)rgb);
 }
 public static MeshGeometry3D LoadMesh(string file,CancellationToken cancellation=default)
 {
  if(!file.EndsWith(".mesh",StringComparison.OrdinalIgnoreCase))return LoadStl(file,cancellation);
  using var stream=File.OpenRead(file);
  Span<byte> header=stackalloc byte[16];
  stream.ReadExactly(header);
  var vertices=BinaryPrimitives.ReadUInt32LittleEndian(header[8..]);
  var faces=BinaryPrimitives.ReadUInt32LittleEndian(header[12..]);
  if(!header[..8].SequenceEqual("SPMESH01"u8)||faces==0||faces>MaxMeshTriangles||
     vertices==0||vertices>faces*3||stream.Length!=16L+24L*vertices+12L*faces)
   throw new InvalidDataException("Ungültige indizierte Vorschaugeometrie.");
  var points=new Point3DCollection((int)vertices);
  var triangles=new Int32Collection((int)faces*3);
  Span<byte> pointBytes=stackalloc byte[24];
  for(uint i=0;i<vertices;i++)
  {
   if(i%1024==0)cancellation.ThrowIfCancellationRequested();
   stream.ReadExactly(pointBytes);
   var point=World(BinaryPrimitives.ReadDoubleLittleEndian(pointBytes),
                   BinaryPrimitives.ReadDoubleLittleEndian(pointBytes[8..]),
                   BinaryPrimitives.ReadDoubleLittleEndian(pointBytes[16..]));
   if(!double.IsFinite(point.X)||!double.IsFinite(point.Y)||!double.IsFinite(point.Z))
    throw new InvalidDataException("Ungültige Koordinate in der indizierten Vorschau.");
   points.Add(point);
  }
  Span<byte> faceBytes=stackalloc byte[12];
  for(uint i=0;i<faces;i++)
  {
   if(i%1024==0)cancellation.ThrowIfCancellationRequested();
   stream.ReadExactly(faceBytes);
   for(int offset=0;offset<12;offset+=4)
   {
    var index=BinaryPrimitives.ReadUInt32LittleEndian(faceBytes[offset..]);
    if(index>=vertices)throw new InvalidDataException("Ungültiger Dreiecksindex in der indizierten Vorschau.");
    triangles.Add((int)index);
   }
  }
  var mesh=new MeshGeometry3D{Positions=points,TriangleIndices=triangles};
  mesh.Freeze();return mesh;
 }
 public static MeshGeometry3D LoadStl(string file,CancellationToken cancellation=default)
 {
  using var reader=new BinaryReader(File.OpenRead(file));reader.ReadBytes(80);var count=reader.ReadUInt32();
  if(count>MaxMeshTriangles||84L+50L*count!=reader.BaseStream.Length)throw new InvalidDataException("Ungültige interne STL-Geometrie.");
  int indices=checked((int)count*3);
  var points=new Point3DCollection(indices);
  var triangles=new Int32Collection(indices);
  Span<byte> triangle=stackalloc byte[50];
  for(uint i=0;i<count;i++)
  {
   if(i%1024==0)cancellation.ThrowIfCancellationRequested();
   reader.BaseStream.ReadExactly(triangle);
   for(int vertex=12;vertex<48;vertex+=12)
   {
    var point=World(BinaryPrimitives.ReadSingleLittleEndian(triangle[vertex..]),
                    BinaryPrimitives.ReadSingleLittleEndian(triangle[(vertex+4)..]),
                    BinaryPrimitives.ReadSingleLittleEndian(triangle[(vertex+8)..]));
    triangles.Add(points.Count);
    points.Add(point);
   }
  }
  var mesh=new MeshGeometry3D{Positions=points,TriangleIndices=triangles};
  mesh.Freeze();return mesh;
 }
 GeometryModel3D? planePreview,sourceModel;
 (Point3D Center,double Yaw,double Pitch)? interfaceFrame;
 public event Action<Point3D>? SurfacePicked;
 public void Clear(){objects.Children.Clear();planePreview=null;sourceModel=null;interfaceFrame=null;hitParts.Clear();floor.Children.Clear();floor.Transform=Transform3D.Identity;annotations.Children.Clear();markers.Clear();dimensions.Text="";}
 public void DisplayOriginal(MeshGeometry3D mesh,MeshInfo info)
 {
  Clear();sourceModel=Add(mesh,Mat(Grey),0);Frame(info);SetGrid(true);
 }
 public bool DisplayInterface(InterfaceRecord face,double[] normal)
 {
  Clear();
  if(face.Surface is not {Vertices.Length:>=3 and <=4000,Indices.Length:>=3 and <=24000} surface||
     surface.Indices.Length%3!=0||surface.Indices.Any(i=>i<0||i>=surface.Vertices.Length)||
     surface.Vertices.Any(p=>p is not {Length:3}||p.Any(v=>!double.IsFinite(v))))return false;
  var mesh=new MeshGeometry3D
  {
   Positions=new Point3DCollection(surface.Vertices.Select(p=>World(p[0],p[1],p[2]))),
   TriangleIndices=new Int32Collection(surface.Indices)
  };
  mesh.Freeze();
  var bounds=mesh.Bounds;
  modelSize=Math.Max(1,Math.Max(bounds.SizeX,Math.Max(bounds.SizeY,bounds.SizeZ)));
  var direction=new Vector3D(normal[0],normal[2],-normal[1]);
  if(!double.IsFinite(direction.Length)||direction.Length<1e-9)return false;
  direction.Normalize();
  interfaceFrame=(new Point3D(bounds.X+bounds.SizeX/2,bounds.Y+bounds.SizeY/2,bounds.Z+bounds.SizeZ/2),
    Math.Atan2(direction.X,direction.Z)*180/Math.PI,Math.Clamp(Math.Asin(Math.Clamp(direction.Y,-1,1))*180/Math.PI,-80,80));
  sourceModel=Add(mesh,Mat(Cyan),0);
  Reset();
  return true;
 }
 public void ShowInterfacePoints(IEnumerable<double[]> points)
 {
  annotations.Children.Clear();markers.Clear();
  int number=0;
  foreach(var point in points)
  {
   var label=new TextBlock{Text=(++number).ToString(),Foreground=Brushes.White,
     Background=new SolidColorBrush(Color.FromRgb(54,48,19)),Padding=new Thickness(5,1,5,1)};
   annotations.Children.Add(label);
   markers.Add((World(point[0],point[1],point[2]),label));
  }
  ProjectMarkers();
 }
 public void ShowPlane(MeshInfo info,ManualEdit? plane)
 {
  if(planePreview!=null){objects.Children.Remove(planePreview);planePreview=null;}
  if(plane==null)return;
  var normal=World(plane.Normal[0],plane.Normal[1],plane.Normal[2])-new Point3D();
  var origin=World(plane.Point[0],plane.Point[1],plane.Point[2]);
  var b=info.Bounds;
  var padding=info.Dimensions.Max()*.10;
  double Coordinate(int corner,int axis)=>((corner&(1<<axis))==0)?b[axis]-padding:b[axis+3]+padding;
  var corners=Enumerable.Range(0,8).Select(i=>World(Coordinate(i,0),Coordinate(i,1),Coordinate(i,2))).ToArray();
  var points=new List<Point3D>();
  for(int i=0;i<8;i++)
  for(int axis=0;axis<3;axis++)
  {
   int j=i|(1<<axis);
   if(i==j)continue;
   double a=Vector3D.DotProduct(corners[i]-origin,normal),d=Vector3D.DotProduct(corners[j]-origin,normal);
   if(!double.IsFinite(a)||!double.IsFinite(d))return;
   if(Math.Sign(a)==Math.Sign(d)||a==d)continue;
   var point=corners[i]+(corners[j]-corners[i])*(a/(a-d));
   if(!points.Any(p=>(p-point).Length<1e-7))points.Add(point);
  }
  if(points.Count<3)return;
  var center=new Point3D(points.Average(p=>p.X),points.Average(p=>p.Y),points.Average(p=>p.Z));
  var u=points[0]-center;
  var v=Vector3D.CrossProduct(normal,u);
  var mesh=new MeshGeometry3D();
  foreach(var point in points.OrderBy(p=>Math.Atan2(Vector3D.DotProduct(p-center,v),Vector3D.DotProduct(p-center,u))))mesh.Positions.Add(point);
  for(int i=1;i+1<points.Count;i++){mesh.TriangleIndices.Add(0);mesh.TriangleIndices.Add(i);mesh.TriangleIndices.Add(i+1);}
  mesh.Freeze();planePreview=Add(mesh,Mat(Cyan,.38),0);
 }
 public void DisplayParts(IEnumerable<(PartRecord part,MeshGeometry3D mesh)> meshes,SliceResult result,int selected=0,double explode=0,bool cuts=true,bool joints=true,bool single=false,HashSet<int>? hidden=null,int assemblyStep=int.MaxValue,double assemblyProgress=1,bool thinWalls=false,IReadOnlyDictionary<string,MeshGeometry3D>? connectorMeshes=null)
 {
  objects.Children.Clear();hitParts.Clear();annotations.Children.Clear();markers.Clear();
  floor.Transform=new TranslateTransform3D(0,-modelSize*explode*.6,0);
  var source=result.Original;var mid=new Point3D(source.Dimensions[0]/2,source.Dimensions[2]/2,-source.Dimensions[1]/2);
  var movingStep=result.Motion?.PathVerified==true&&assemblyStep>0&&assemblyStep<=result.Motion.AssemblySteps.Length?result.Motion.AssemblySteps[assemblyStep-1]:null;
  Vector3D InsertionOffset(int id)=>movingStep is {Base:false,FromOffset.Length:3}&&movingStep.Part==id?new Vector3D(movingStep.FromOffset[0],movingStep.FromOffset[2],-movingStep.FromOffset[1])*(1-assemblyProgress):new();
  foreach(var (part,mesh) in meshes)
  {
   if(hidden?.Contains(part.Id)==true||(single&&part.Id!=selected)||Array.IndexOf(result.AssemblyOrder,part.Id)>=assemblyStep)continue;
   var b=part.Bounds;var c=World((b[0]+b[3])/2,(b[1]+b[4])/2,(b[2]+b[5])/2);
   var delta=(c-mid)*explode+InsertionOffset(part.Id);
   var color=ParsePartColor(part.Color)??(part.Id==selected?Color.FromRgb(95,217,245):part.NeedsAssemblyCheck?Color.FromRgb(216,164,112):Grey);
   var m=Mat(color,OpacityLevel);
   var model=Add(mesh,m,part.Id);model.Transform=new TranslateTransform3D(delta);
   if(thinWalls&&part.PrintChecks is {} check)
    foreach(var sample in check.SamplePoints.Where(s=>s.Point.Length==3).Take(8))
    {
     var label=new TextBlock{Text=$"{sample.Thickness:N2}",Foreground=Brushes.Moccasin,Background=new SolidColorBrush(Color.FromArgb(225,72,41,15)),Padding=new Thickness(3,1,3,1),FontSize=10};
     annotations.Children.Add(label);
     markers.Add((World(sample.Point[0],sample.Point[1],sample.Point[2])+delta,label));
    }
   if(cuts&&part.CutFaces is not {Length:0})
   {
    var cap=new MeshGeometry3D();var body=new MeshGeometry3D();
    var planes=part.CutFaces??Enumerable.Range(0,3).SelectMany(axis=>result.Cuts[axis].Select(v=>new CutFaceRecord{Axis=axis,Offset=v})).ToArray();
    var equations=planes.Select(f=>(Normal:f.Normal is {Length:3} n
     ?new Vector3D(n[0],n[2],-n[1]):f.Axis switch{0=>new Vector3D(1,0,0),1=>new Vector3D(0,0,-1),_=>new Vector3D(0,1,0)},f.Offset)).ToArray();
    var indices=mesh.TriangleIndices;
    for(int i=0;i<indices.Count;i+=3)
    {
     var a=mesh.Positions[indices[i]];var d=mesh.Positions[indices[i+1]];var e=mesh.Positions[indices[i+2]];
     bool onCut=false;
     foreach(var (normal,offset) in equations)
     {
      if(Math.Abs(Vector3D.DotProduct((Vector3D)a,normal)-offset)>=.001||
         Math.Abs(Vector3D.DotProduct((Vector3D)d,normal)-offset)>=.001||
         Math.Abs(Vector3D.DotProduct((Vector3D)e,normal)-offset)>=.001)continue;
      onCut=true;break;
     }
     var target=onCut?cap:body;var n=target.Positions.Count;
     target.Positions.Add(a);target.Positions.Add(d);target.Positions.Add(e);target.TriangleIndices.Add(n);target.TriangleIndices.Add(n+1);target.TriangleIndices.Add(n+2);
    }
    body.Freeze();model.Geometry=body;cap.Freeze();var g=Add(cap,Mat(Color.FromRgb(20,153,188),OpacityLevel),part.Id);g.Transform=new TranslateTransform3D(delta);
    // Cyan contours are the actual cut-face edges. Only boundary edges are drawn.
    DrawCapEdges(cap,delta,Math.Max(.3,modelSize*.0015));
   }
  }
  if(joints)
   foreach(var j in result.Joints)
   {
    if(single&&j.A!=selected&&j.B!=selected)continue;
    if(hidden?.Contains(j.A)==true||hidden?.Contains(j.B)==true)continue;
    if(Array.IndexOf(result.AssemblyOrder,j.A)>=assemblyStep||(j.Mode!="separate"&&Array.IndexOf(result.AssemblyOrder,j.B)>=assemblyStep))continue;
    var direction=j.Normal is {Length:3} n?new Vector3D(n[0],n[2],-n[1]):j.Axis switch{0=>new Vector3D(1,0,0),1=>new Vector3D(0,0,-1),_=>new Vector3D(0,1,0)};
    var center=World(j.Center[0],j.Center[1],j.Center[2]);
    var offset=InsertionOffset(j.A);
    var marker=j.Kind switch
    {
     "round"=>Line(center-direction*j.Depth+offset,center+direction*j.Depth+offset,j.Diameter/2),
     "dovetail"=>DovetailMarker(j,offset),
     "clip" or "screw"=>null,
     _=>ConnectorBox(j,offset)
    };
    if(connectorMeshes?.TryGetValue(j.Id,out var actual)==true)
    {
     var holder=result.Parts.First(p=>p.Id==j.A).Bounds;
     var holderCenter=World((holder[0]+holder[3])/2,(holder[1]+holder[4])/2,(holder[2]+holder[5])/2);
     offset+=(holderCenter-mid)*explode;
     var visual=Add(actual,Mat(Cyan,.85),0);
     visual.Transform=new TranslateTransform3D(offset);
    }
    else if(marker!=null)Add(marker,Mat(Cyan,.85),0);
    var label=new TextBlock{Text="⊟",FontSize=18,FontWeight=FontWeights.Bold,Foreground=new SolidColorBrush(Cyan),Background=new SolidColorBrush(Color.FromArgb(140,3,21,30)),Padding=new Thickness(1,0,1,0)};
    annotations.Children.Add(label);markers.Add((World(j.Center[0],j.Center[1],j.Center[2])+offset,label));
   }
  dimensions.Text=selected>0?result.Parts.First(p=>p.Id==selected).Detail:$"{result.Parts.Length} Druckteile · {result.Joints.Length} Verbinder\n"+string.Join(" × ",source.Dimensions.Select(d=>d.ToString("N1")))+" mm";
  if(result.Motion?.PathVerified==true&&assemblyStep!=int.MaxValue&&assemblyStep>0&&assemblyStep<=result.Motion.AssemblySteps.Length)
  {
   var step=result.Motion.AssemblySteps[assemblyStep-1];
   dimensions.Text=step.Base?$"Montageschritt {assemblyStep}: Teil {step.Part:000} als Basis":$"Montageschritt {assemblyStep}: Teil {step.Part:000}\n{MotionRecord.DirectionLabel(step.InsertionDirection)} · {assemblyProgress:P0} montiert · {step.Distance*(1-assemblyProgress):N1} mm Restweg";
  }
  if(!string.IsNullOrEmpty(MeshNote))dimensions.Text+="\n"+MeshNote;
  ProjectMarkers();
 }
 void DrawCapEdges(MeshGeometry3D cap,Vector3D delta,double radius)
 {
  string Key(Point3D p)=>$"{p.X:F3},{p.Y:F3},{p.Z:F3}";
  var edges=new Dictionary<string,(Point3D a,Point3D b,int count)>();
  for(var i=0;i<cap.Positions.Count;i+=3)
   for(var j=0;j<3;j++)
   {
    var a=cap.Positions[i+j];var b=cap.Positions[i+(j+1)%3];var ka=Key(a);var kb=Key(b);var k=string.CompareOrdinal(ka,kb)<0?ka+"/"+kb:kb+"/"+ka;
    if(edges.TryGetValue(k,out var e))edges[k]=(a,b,e.count+1);else edges[k]=(a,b,1);
   }
  var combined=new MeshGeometry3D();
  foreach(var e in edges.Values.Where(e=>e.count==1))
  {
   var line=Line(e.a+delta,e.b+delta,radius);var offset=combined.Positions.Count;
   foreach(var p in line.Positions)combined.Positions.Add(p);foreach(var i in line.TriangleIndices)combined.TriangleIndices.Add(offset+i);
  }
  combined.Freeze();var glow=new MaterialGroup();glow.Children.Add(new DiffuseMaterial(new SolidColorBrush(Cyan)));glow.Children.Add(new EmissiveMaterial(new SolidColorBrush(Cyan)));glow.Freeze();Add(combined,glow,0);
 }
 GeometryModel3D Add(MeshGeometry3D mesh,Material material,int id)
 {
  var model=new GeometryModel3D(mesh,material){BackMaterial=material};objects.Children.Add(model);if(id>0)hitParts[model]=id;return model;
 }
 public void Frame(MeshInfo info)
 {
  var d=info.Dimensions;
  center=info.Bounds is {Length:6} b?World((b[0]+b[3])/2,(b[1]+b[4])/2,(b[2]+b[5])/2):World(d[0]/2,d[1]/2,d[2]/2);
  modelSize=d.Max();distance=modelSize*2.45*framingAspect;
  dimensions.Text=string.Join(" × ",d.Select(x=>x.ToString("N1")))+" mm\n"+info.Triangles.ToString("N0")+" Dreiecke"+(string.IsNullOrEmpty(MeshNote)?"":"\n"+MeshNote);
  UpdateCamera(true);
 }
 public void Reset()
 {
  if(interfaceFrame is {} face){center=face.Center;yaw=face.Yaw;pitch=face.Pitch;}
  else{yaw=-27;pitch=17;}
  distance=modelSize*2.45*framingAspect;UpdateCamera(true);
 }
 public void SetGrid(bool visible)
 {
  floor.Children.Clear();if(!visible)return;
  var extent=Math.Max(100,modelSize*1.5);var step=Math.Pow(10,Math.Floor(Math.Log10(extent/12)));if(extent/step>35)step*=2;
  var combined=new MeshGeometry3D();
  for(double p=-extent;p<=extent;p+=step)
  {
   foreach(var mesh in new[]{Line(new(p,-1,-extent),new(p,-1,extent),extent*.00045),Line(new(-extent,-1,p),new(extent,-1,p),extent*.00045)})
   {var offset=combined.Positions.Count;foreach(var v in mesh.Positions)combined.Positions.Add(v);foreach(var i in mesh.TriangleIndices)combined.TriangleIndices.Add(offset+i);}
  }
  combined.Freeze();var mat=Mat(Color.FromRgb(23,53,72));floor.Children.Add(new GeometryModel3D(combined,mat){BackMaterial=mat});
 }
 public void Sync(double y,double p,double d,Point3D c){yaw=y;pitch=p;distance=d;center=c;UpdateCamera(false);}
 void UpdateCamera(bool broadcast)
 {
  double y=yaw*Math.PI/180,p=pitch*Math.PI/180;
  var direction=new Vector3D(Math.Sin(y)*Math.Cos(p),Math.Sin(p),Math.Cos(y)*Math.Cos(p));
  camera.Position=center+direction*distance;camera.LookDirection=-direction*distance;camera.UpDirection=new(0,1,0);
  ProjectMarkers();
  if(broadcast)CameraChanged?.Invoke(yaw,pitch,distance,center);
 }
 void ProjectMarkers()
 {
  if(markers.Count==0)return;
  var axes=ProjectionAxes();
  foreach(var (position,label) in markers)
  {
   if(!TryProject(position,axes,out var point)){label.Visibility=Visibility.Collapsed;continue;}
   label.Visibility=Visibility.Visible;
   Canvas.SetLeft(label,point.X-8);Canvas.SetTop(label,point.Y-10);
  }
 }
 public bool TryProjectModelPoint(double[] point,out Point projected)
  =>TryProject(World(point[0],point[1],point[2]),ProjectionAxes(),out projected);
 (Vector3D Forward,Vector3D Right,Vector3D Up,double Focal) ProjectionAxes()
 {
  var forward=camera.LookDirection;forward.Normalize();
  var right=Vector3D.CrossProduct(forward,camera.UpDirection);right.Normalize();
  return (forward,right,Vector3D.CrossProduct(right,forward),ActualWidth/(2*Math.Tan(camera.FieldOfView*Math.PI/360)));
 }
 bool TryProject(Point3D position,(Vector3D Forward,Vector3D Right,Vector3D Up,double Focal) axes,out Point projected)
 {
  projected=new();
  if(ActualWidth<=0||ActualHeight<=0)return false;
  var relative=position-camera.Position;
  double depth=Vector3D.DotProduct(relative,axes.Forward);
  if(depth<=0)return false;
  projected=new(ActualWidth/2+axes.Focal*Vector3D.DotProduct(relative,axes.Right)/depth,
    ActualHeight/2-axes.Focal*Vector3D.DotProduct(relative,axes.Up)/depth);
  return projected.X>=0&&projected.Y>=0&&projected.X<=ActualWidth&&projected.Y<=ActualHeight;
 }
 void Down(object sender,MouseButtonEventArgs e)
 {
  if(e.ClickCount==2){dragging=true;Reset();return;}last=e.GetPosition(this);dragging=false;CaptureMouse();e.Handled=true;
 }
 void Move(object sender,MouseEventArgs e)
 {
  if(!IsMouseCaptured)return;var point=e.GetPosition(this);var delta=point-last;
  if(delta.Length<.5)return;dragging=true;
  if(e.RightButton==MouseButtonState.Pressed||Keyboard.Modifiers.HasFlag(ModifierKeys.Shift))
  {
   var right=Vector3D.CrossProduct(camera.LookDirection,camera.UpDirection);right.Normalize();center-=right*(delta.X*distance/Math.Max(300,ActualWidth));center+=new Vector3D(0,delta.Y*distance/Math.Max(300,ActualHeight),0);
  }
  else{yaw-=delta.X*.45;pitch=Math.Clamp(pitch+delta.Y*.35,-80,80);}
  last=point;UpdateCamera(true);
 }
 void Up(object sender,MouseButtonEventArgs e)
 {
  ReleaseMouseCapture();if(dragging)return;
  if(SurfacePicked!=null&&e.ChangedButton==MouseButton.Left&&(interfaceFrame!=null||Keyboard.Modifiers.HasFlag(ModifierKeys.Alt)))
  {
   VisualTreeHelper.HitTest(viewport,null,r=>
   {
    if(r is RayMeshGeometry3DHitTestResult hit&&hit.ModelHit==sourceModel){SurfacePicked(hit.PointHit);return HitTestResultBehavior.Stop;}
    return HitTestResultBehavior.Continue;
   },new PointHitTestParameters(e.GetPosition(viewport)));
   return;
  }
  VisualTreeHelper.HitTest(viewport,null,r=>{if(r is RayMeshGeometry3DHitTestResult hit&&hit.ModelHit is GeometryModel3D model&&hitParts.TryGetValue(model,out int id)){PartSelected?.Invoke(id);return HitTestResultBehavior.Stop;}return HitTestResultBehavior.Continue;},new PointHitTestParameters(e.GetPosition(viewport)));
 }
 void Wheel(object sender,MouseWheelEventArgs e){distance=Math.Clamp(distance*Math.Exp(-e.Delta*.001),modelSize*.15,modelSize*20);UpdateCamera(true);e.Handled=true;}
 static Point3D JointPoint(JointRecord joint,double[] local,Vector3D offset)
 {
  var basis=joint.Frame;
  double Coordinate(int axis)=>joint.Center[axis]+(basis is {Length:3}?Enumerable.Range(0,3).Sum(k=>local[k]*basis[k][axis]):local[axis]);
  return World(Coordinate(0),Coordinate(1),Coordinate(2))+offset;
 }
 static MeshGeometry3D DovetailMarker(JointRecord joint,Vector3D offset)
 {
  if(joint.TangentAxis is not int tangent||joint.Length is not double length)return new();
  var mesh=new MeshGeometry3D();
  int across=3-joint.Axis-tangent;
  double half=joint.Diameter/2,flare=half*1.5,d=joint.Depth;
  (double width,double depth)[] profile=[(-flare,-d),(flare,-d),(half,0),(flare,d),(-flare,d),(-half,0)];
  foreach(int side in new[]{-1,1})
   foreach(var (w,h) in profile)
   {
    double[] local=[0,0,0];local[across]=w;local[joint.Axis]=h;local[tangent]=side*length/2;
    mesh.Positions.Add(JointPoint(joint,local,offset));
   }
  foreach(int index in new[]{0,5,2,0,2,1,5,4,3,5,3,2,6,8,11,6,7,8,11,9,10,11,8,9})mesh.TriangleIndices.Add(index);
  for(int i=0;i<6;i++)
  {
   int next=(i+1)%6;
   foreach(int index in new[]{i,next,i+6,next,next+6,i+6})mesh.TriangleIndices.Add(index);
  }
  mesh.Freeze();
  return mesh;
 }
 static MeshGeometry3D ConnectorBox(JointRecord joint,Vector3D offset)
 {
  double[] size=[joint.Diameter,joint.Diameter,joint.Diameter];size[joint.Axis]=2*joint.Depth;
  if(joint.TangentAxis is int tangent&&tangent!=joint.Axis&&tangent>=0&&tangent<3&&joint.Length is double length)size[tangent]=length;
  var m=new MeshGeometry3D();
  for(int i=0;i<8;i++)
  {
   double[] local=[((i&1)==0?-.5:.5)*size[0],((i&2)==0?-.5:.5)*size[1],((i&4)==0?-.5:.5)*size[2]];
   m.Positions.Add(JointPoint(joint,local,offset));
  }
  foreach(var index in new[]{0,2,1,1,2,3,4,5,6,5,7,6,0,1,4,1,5,4,2,6,3,3,6,7,0,4,2,2,4,6,1,3,5,3,7,5})m.TriangleIndices.Add(index);
  m.Freeze();return m;
 }
 public static MeshGeometry3D Line(Point3D a,Point3D b,double radius)
 {
  var axis=b-a;if(axis.Length<1e-9)return new();axis.Normalize();var u=Vector3D.CrossProduct(axis,new(0,1,0));if(u.Length<.01)u=Vector3D.CrossProduct(axis,new(1,0,0));u.Normalize();var v=Vector3D.CrossProduct(axis,u);
  var m=new MeshGeometry3D();for(int i=0;i<6;i++){var radial=(u*Math.Cos(i*Math.PI/3)+v*Math.Sin(i*Math.PI/3))*radius;m.Positions.Add(a+radial);m.Positions.Add(b+radial);}
  for(int i=0;i<6;i++){int n=i*2,next=((i+1)%6)*2;foreach(var index in new[]{n,next,n+1,n+1,next,next+1})m.TriangleIndices.Add(index);}m.Freeze();return m;
 }
}
