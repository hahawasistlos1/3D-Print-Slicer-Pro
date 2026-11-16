using System.IO;
namespace SlicerPro.Services;

public sealed record ExportFormat(string Id,string Label,string Note) {public override string ToString()=>Label;}
public sealed record GeometryExportItem(string Input,string Output,int[]? Order,string? Format=null,string? Color=null);
public static class GeometryExport
{
 public static readonly ExportFormat[] Formats=[
  new("stl","STL · binär oder ASCII","Die App nutzt ASCII mit höherer Koordinatenpräzision, wenn die binäre Ausgabe die Netzprüfung nicht besteht. Die Koordinaten sind in Millimetern."),
  new("obj","OBJ · Dreiecksnetz","Geometrie ohne Materialien oder Texturen. Zahlen werden als Millimeter ausgegeben; beim Import im Zielprogramm Millimeter wählen."),
  new("3mf","3MF · indizierte Geometrie","Speichert die Dreiecksindizes und die Maßeinheit Millimeter. Empfohlen für komplexe Netze. Enthält keine Druckerprofile, Stützen oder G-Code.")];
 public static string PreferredFormat(string source)=>File.Exists(Path.ChangeExtension(source,".mesh"))?"3mf":"stl";
 public static string Filter=>string.Join("|",Formats.Select(f=>$"{f.Id.ToUpperInvariant()} (*.{f.Id})|*.{f.Id}"));
 public static string FormatFromPath(string file)
 {
  var kind=Path.GetExtension(file).TrimStart('.').ToLowerInvariant();
  if(!Formats.Any(f=>f.Id==kind))throw new ArgumentException("Bitte eine Datei mit der Endung .stl, .obj oder .3mf wählen.");
  return kind;
 }
 public static string FileName(string source,string format)=>Path.ChangeExtension(Path.GetFileName(source),format);
}
