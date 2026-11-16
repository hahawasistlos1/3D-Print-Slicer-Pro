using System.IO;
using System.Text.Json;
namespace SlicerPro;

public sealed class SliceSettings
{
 public double BedX {get;set;}=220; public double BedY {get;set;}=220; public double BedZ {get;set;}=250;
 public double Margin {get;set;}=.2; public double Target {get;set;}=220; public bool Optimize {get;set;}=true;
 public string Strategy {get;set;}="adaptive"; public string Kind {get;set;}="round"; public string Mode {get;set;}="separate";
 public double Diameter {get;set;}=10; public double Depth {get;set;}=15; public double Tolerance {get;set;}=.2; public double Wall {get;set;}=2;
 public double TongueLength {get;set;}=40;
 public double RectHeight {get;set;}
 public double ThinWallThreshold {get;set;}=1;
 public double ClipStrainPercent {get;set;}=3;
 public double ThreadPitch {get;set;}=2;
 public double ThreadLength {get;set;}=12;
 public int Count {get;set;}=2; public string Material {get;set;}="PLA";
 public bool AutoSize {get;set;} public double MinDiameter {get;set;}=3;public double MinDepth {get;set;}=3;public bool PathCheck {get;set;}=true;
 public Dictionary<string,double[]> Cuts {get;set;}=[];
 public ManualEdit[] Edits {get;set;}=[];
 public ConnectorPlacement[] Placements {get;set;}=[];
 public SliceSettings Clone()=>JsonSerializer.Deserialize<SliceSettings>(JsonSerializer.Serialize(this,Json.Options),Json.Options)!;
}
public sealed class ConnectorPlacement
{
 public string InterfaceId {get;set;}="";
 public string AKey {get;set;}="";
 public string BKey {get;set;}="";
 public double[] Center {get;set;}=[];
}
public sealed class ManualEdit
{
 public double[] Point {get;set;}=[];
 public double[] Normal {get;set;}=[];
 public string? Target {get;set;}
 public string[]? Merge {get;set;}
 public string Label=>Merge is {} keys?$"{keys.Length} Teile zusammenfügen"
  :$"({string.Join(" / ",Point.Select(v=>v.ToString("N1")))}) mm · "+MotionRecord.DirectionLabel(Normal)+(Target==null?" · alle Teile":" · lokales Teil");
}
public sealed class MeshInfo
{
 public double[] Dimensions {get;set;}=[0,0,0]; public double[] Bounds {get;set;}=[0,0,0,0,0,0];
 public double Volume {get;set;} public int Triangles {get;set;} public bool Watertight {get;set;} public bool NormalsConsistent {get;set;} public int Components {get;set;}
}
public sealed class ModelRecord { public string Name {get;set;}="Modell"; public MeshInfo Original {get;set;}=new(); public OrientationRecord? Orientation {get;set;} public MeshRepairRecord? Repair {get;set;} public ColorSeparationRecord? ColorSeparation {get;set;} }
public sealed class ColorSeparationRecord
{
 public string?[] Groups {get;set;}=[];
 public string? Issue {get;set;}
 public string? Summary=>Groups.Length>0?$"{Groups.Length} trennbare Farbgruppen":Issue;
}
public sealed class MeshRepairRecord
{
 public int HolesClosed {get;set;}
 public int FacesReoriented {get;set;}
 public int SeamsJoined {get;set;}
 public string Summary=>"Importreparatur · "+string.Join(" · ",new[]{
  HolesClosed>0?$"{HolesClosed} kleine Öffnung(en) geschlossen":null,
  FacesReoriented>0?$"{FacesReoriented} Flächen ausgerichtet":null,
  SeamsJoined>0?$"Numerische Nähte an {SeamsJoined} Netz(en) geschlossen":null
 }.OfType<string>());
}
public sealed class OrientationRecord {public double[] Angles {get;set;}=[];public string Order {get;set;}="XYZ";public double[][] Matrix {get;set;}=[];public double[] PreviousDimensions {get;set;}=[];public double VolumeError {get;set;}public string Label=>"Letzte zusätzliche Drehung X/Y/Z: "+string.Join(" / ",Angles.Select(a=>a.ToString("G")))+"°";}
public sealed class PartRecord
{
 public string? Key {get;set;}
 public string? Color {get;set;}
 public int Id {get;set;} public string Name {get;set;}=""; public string File {get;set;}=""; public double[] Dimensions {get;set;}=[];
 public double[] Bounds {get;set;}=[]; public bool Printable {get;set;} public string[] Errors {get;set;}=[];
 public int[] Cell {get;set;}=[]; public int[] Neighbors {get;set;}=[]; public string[] Connectors {get;set;}=[]; public int[]? PrintOrder {get;set;}
 public int[]? ConnectedNeighbors {get;set;} public CutFaceRecord[]? CutFaces {get;set;}
 public int? RequestedConnectors {get;set;}
 public PrintCheckRecord? PrintChecks {get;set;}
 public bool NeedsAssemblyCheck=>RequestedConnectors is {} requested?requested>Connectors.Length:Neighbors.Length>0&&(ConnectedNeighbors?.Length<Neighbors.Length||Connectors.Length==0);
 public string SizeLabel=>string.Join(" × ",Dimensions.Select(x=>x.ToString("N1")))+" mm";
 public string Detail=>(Color is {} color?$"Farbe {color}\n":"")+$"{SizeLabel}\n{Connectors.Length} Verbinder · Nachbarn: {string.Join(", ",Neighbors.Select(x=>x.ToString("000")))}\n"+(Printable?"Netz geschlossen · passt in Druckraum":"Fehler: "+string.Join(", ",Errors))+(NeedsAssemblyCheck?"\n⚠ Schnittstellen ohne Verbinder prüfen":"")+(PrintChecks?.ThinSamples>0?"\n⚠ Dünnwand-Hinweis im Prüfbericht":"");
}
public sealed class PrintCheckRecord
{
 public double WallThreshold {get;set;}
 public int TestedRays {get;set;}
 public int ValidRays {get;set;}
 public int ThinSamples {get;set;}
 public double? MinimumSample {get;set;}
 public WallSampleRecord[] SamplePoints {get;set;}=[];
 public double? OverhangArea {get;set;}
 public double OverhangAngle {get;set;}
 public string Summary=>
  (WallThreshold<=0?"Dünnwand-Stichprobe aus":ThinSamples>0?$"{ThinSamples} Dünnwand-Hinweise, kleinste Probe {MinimumSample:N3} mm"
   :$"Keine Dünnwand-Hinweise unter {WallThreshold:G} mm in {ValidRays}/{TestedRays} gültigen Stichproben")
  +(OverhangArea is double area?$" · Überhangfläche bei 45°: {area:N1} mm²":"");
}
public sealed class WallSampleRecord {public double Thickness {get;set;} public double[] Point {get;set;}=[];}
public sealed class CutFaceRecord
{
 public int Axis {get;set;}
 public double Offset {get;set;}
 public double[]? Normal {get;set;}
 public int? Plane {get;set;}
}
public sealed class PlanningRecord
{
 public string Algorithm {get;set;}="grid-axis-v1";public int EvaluatedPlanes {get;set;} public bool BudgetReached {get;set;}
 public string Label=>Algorithm.StartsWith("color")?"Nach Farbe getrennt":Algorithm.StartsWith("adaptive")?"Adaptiv · lokale Schnitte":"Achsenparalleles Raster";
 // Preserve the geometric planning record when exporting a saved project.
 [System.Text.Json.Serialization.JsonExtensionData] public Dictionary<string,JsonElement>? Extra {get;set;}
}
public sealed class AssemblyRecord
{
 public bool? Connected {get;set;} public int[][] Groups {get;set;}=[];public int UnconnectedInterfaces {get;set;} public bool PathVerified {get;set;}
 public string Summary=>Connected==null?"Verbindung nicht geprüft (ohne Verbinder)":Connected==true?"Alle Teile im Verbindungsgraph verbunden":$"{Groups.Length} lose Baugruppen";
}
public sealed class InterfaceRecord
{
 public double[]? Normal {get;set;}
 public int? Plane {get;set;}
 public string Id {get;set;}="";public int A {get;set;} public int B {get;set;} public int Axis {get;set;} public double Offset {get;set;} public double Area {get;set;} public int Placed {get;set;} public int Requested {get;set;}public string[] Connectors {get;set;}=[];
}
public sealed class ConnectorRecord { public string Id {get;set;}=""; public string File {get;set;}=""; public int[]? PrintOrder {get;set;} public PrintCheckRecord? PrintChecks {get;set;} }
public sealed class JointRecord
{
 public string Id {get;set;}=""; public int A {get;set;} public int B {get;set;} public int Axis {get;set;} public double[] Center {get;set;}=[];
 public string Mode {get;set;}=""; public string Kind {get;set;}=""; public double Diameter {get;set;} public double Depth {get;set;} public double Tolerance {get;set;}
 public bool AutoSized {get;set;}
 public bool ManualPosition {get;set;}
 public double[]? Normal {get;set;}
 public double[][]? Frame {get;set;}
 public double[]? RemovalDirection {get;set;}
 public double[]? PinWithdrawal {get;set;}
 public double? Length {get;set;} public int? TangentAxis {get;set;}
 public double? Pitch {get;set;}
 public double? ThreadLength {get;set;}
 public double? GripLength {get;set;}
 public double? HeadDiameter {get;set;}
 public double? ClipStrainPercent {get;set;}
 public double? ClipDeflection {get;set;}
 public string KindLabel=>Kind switch{"tongue"=>"Nut/Feder","rect"=>"Steckverbinder","dovetail"=>"Schwalbenschwanz","clip"=>"Steckclip","screw"=>"Außenschraube",_=>"Runddübel"};
 public string TravelLabel=>Kind=="screw"?$"Von außen durch Teil {A:000} in Teil {B:000} eindrehen"
  :Kind=="clip"?"Gerade ansetzen · Rastarme elastisch eindrücken"
  :RemovalDirection is {Length:3} removal
  ? "Einschub Teil "+B.ToString("000")+" relativ zu "+A.ToString("000")+" "+MotionRecord.DirectionLabel(removal.Select(v=>-v).ToArray())
  :Normal is {} normal?MotionRecord.DirectionLabel(normal):"XYZ"[Axis].ToString();
 public string SizeLabel=>Kind=="screw"?$"Ø {Diameter:N2} mm · Gewinde {ThreadLength:N2} mm · Steigung {Pitch:N2} mm · Griffstrecke {GripLength:N2} mm"
  :Kind=="clip"?$"{Diameter:N2} × {Length:N2} × {2*Depth:N2} mm · berechnete Armdehnung {ClipStrainPercent:N2} %"
  :Kind is "tongue" or "dovetail"?$"{Diameter:N2} × {Length:N2} × {2*Depth:N2} mm (B × L × T)"
  :Kind=="rect"?$"{Diameter:N2} × {(Length??Diameter):N2} × {2*Depth:N2} mm (B × H × T)"
  :$"{Diameter:N2} × {2*Depth:N2} mm";
}
public sealed class MotionRecord
{
 public bool Checked {get;set;} public string Status {get;set;}="not-checked";public bool PathVerified {get;set;} public bool BudgetReached {get;set;}
 public string? Reason {get;set;}
 public int BooleanTests {get;set;} public int SweptFaces {get;set;} public double VolumeTolerance {get;set;}
 public string Method {get;set;}="";public string Scope {get;set;}="";public int[] RemainingParts {get;set;}=[];public string[] UnresolvedPins {get;set;}=[];
 public string[][] InitialCollisions {get;set;}=[];public string[] Limitations {get;set;}=[];
 public PinInsertionRecord[] PreinsertSteps {get;set;}=[];public RemovalRecord[] DisassemblySteps {get;set;}=[];public AssemblyStepRecord[] AssemblySteps {get;set;}=[];public MotionFailureRecord[] LastFailures {get;set;}=[];
 public string Summary=>Reason=="flexible-or-rotational-joints"?"Rast- oder Drehmontage per Passprobe prüfen"
  :!Checked?"Montagewege nicht geprüft":PathVerified?"Geradlinige Montagefolge nachgewiesen":"Montagefolge nicht vollständig nachgewiesen";
 [System.Text.Json.Serialization.JsonExtensionData]public Dictionary<string,JsonElement>? Extra {get;set;}
 public static string DirectionLabel(double[] direction)
 {
  if(direction.Length!=3)return "—";
  var indices=Enumerable.Range(0,3).Where(i=>Math.Abs(direction[i])>1e-8).ToArray();
  return indices.Length==1?(direction[indices[0]]>0?"+":"-")+"XYZ"[indices[0]]
   :"XYZ ("+string.Join(" / ",direction.Select(v=>v.ToString("N3")))+")";
 }
}
public sealed class PinInsertionRecord {public string Connector {get;set;}="";public int Host {get;set;}public double Distance {get;set;}public double[] FromOffset {get;set;}=[];public double[] InsertionDirection {get;set;}=[];}
public sealed class RemovalRecord {public int Part {get;set;}public double[] Direction {get;set;}=[];public double Distance {get;set;}public string[] CarriedConnectors {get;set;}=[];public string Proof {get;set;}="";}
public sealed class AssemblyStepRecord {public int Part {get;set;}public bool Base {get;set;}public double[] FromOffset {get;set;}=[];public double[] InsertionDirection {get;set;}=[];public double Distance {get;set;}public string[] CarriedConnectors {get;set;}=[];}
public sealed class MotionFailureRecord
{
 public int Part {get;set;}public double[] Direction {get;set;}=[];public string Status {get;set;}="";public string Reason {get;set;}="";public string Body {get;set;}="";public string Obstacle {get;set;}="";
 public string Description=>Reason switch{"continuous-sweep-overlap"=>"Kollision im Bewegungsraum","initial-overlap"=>"Überschneidung in der Montageposition","multiple-insertion-directions"=>"Mehrere Einsteckrichtungen gleichzeitig","budget-exhausted"=>"Rechenbudget erreicht","numerical-overlap-limit"=>"Numerische Restüberschneidungen nicht sicher auszuschließen",_=>"Bewegungsweg geometrisch nicht nachgewiesen"};
}
public sealed class SliceResult
{
 public int Version {get;set;} public PartRecord[] Parts {get;set;}=[]; public ConnectorRecord[] Connectors {get;set;}=[]; public JointRecord[] Joints {get;set;}=[];
 public double[][] Cuts {get;set;}=[]; public string[] Warnings {get;set;}=[]; public bool Valid {get;set;}
 public int[] AssemblyOrder {get;set;}=[]; public SliceSettings Settings {get;set;}=new(); public MeshInfo Original {get;set;}=new();
 public PlanningRecord? Planning {get;set;} public AssemblyRecord? Assembly {get;set;} public InterfaceRecord[] Interfaces {get;set;}=[];
 public MotionRecord? Motion {get;set;}
}
public sealed record Workspace(string ModelFolder, string? ResultFolder, ModelRecord Model, SliceResult? Result, SliceSettings Settings);
public static class Json
{
 public static readonly JsonSerializerOptions Options=new() {PropertyNamingPolicy=JsonNamingPolicy.CamelCase,PropertyNameCaseInsensitive=true,WriteIndented=true};
 public static T Read<T>(string file)=>JsonSerializer.Deserialize<T>(System.IO.File.ReadAllText(file),Options)??throw new InvalidDataException("Leere Projektdatei.");
 public static void Write(string file,object obj)=>System.IO.File.WriteAllText(file,JsonSerializer.Serialize(obj,Options));
}
public sealed class PrinterProfile {public string Name {get;set;}=""; public double X {get;set;} public double Y {get;set;} public double Z {get;set;} public override string ToString()=>Name;}
