using System.IO;
using System.IO.Compression;
namespace SlicerPro.Services;

public static class ProjectService
{
 public static void Save(Workspace state,string file)
 {
  var staging=file+".tmp-"+Guid.NewGuid().ToString("N");
  try
  {
   using(var zip=ZipFile.Open(staging,ZipArchiveMode.Create))
   {
    void Add(string path,string name)=>zip.CreateEntryFromFile(path,name,CompressionLevel.Fastest);
    Add(Path.Combine(state.ModelFolder,"original.stl"),"model/original.stl");
    var indexed=Path.Combine(state.ModelFolder,"original.mesh");
    if(File.Exists(indexed))Add(indexed,"model/original.mesh");
    Add(Path.Combine(state.ModelFolder,"model.json"),"model/model.json");
    var colorCount=state.Model.ColorSeparation?.Groups.Length??0;
    for(var i=0;i<colorCount;i++)
    {
     var name=$"color_{i:D3}.mesh";
     Add(Path.Combine(state.ModelFolder,name),"model/"+name);
    }
    using(var writer=new StreamWriter(zip.CreateEntry("project.json").Open()))writer.Write(System.Text.Json.JsonSerializer.Serialize(new {version=1,settings=state.Settings},Json.Options));
    if(state.ResultFolder!=null)
     foreach(var p in Directory.EnumerateFiles(state.ResultFolder).Where(f=>Path.GetExtension(f) is ".stl" or ".mesh" or ".json").Where(f=>Path.GetFileName(f)!="job.json")) Add(p,"result/"+Path.GetFileName(p));
   }
   File.Move(staging,file,true);
  } finally {if(File.Exists(staging))File.Delete(staging);}
 }
 public static Workspace Open(string file)
 {
  var folder=GeometryService.NewFolder();
  using var zip=ZipFile.OpenRead(file);
  if(zip.Entries.Sum(e=>e.Length)>2_000_000_000L||zip.Entries.Count>3000)throw new InvalidDataException("Projekt zu groß.");
  var root=Path.GetFullPath(folder)+Path.DirectorySeparatorChar;
  foreach(var entry in zip.Entries)
  {
   var target=Path.GetFullPath(Path.Combine(folder,entry.FullName));
   if(!target.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Ungültiger Pfad im Projektarchiv.");
   if(entry.FullName.EndsWith('/')){Directory.CreateDirectory(target);continue;}
   Directory.CreateDirectory(Path.GetDirectoryName(target)!);entry.ExtractToFile(target);
  }
  var project=Json.Read<ProjectHeader>(Path.Combine(folder,"project.json"));
  if(project.Version!=1)throw new InvalidDataException("Diese Projektversion wird nicht unterstützt.");
  var model=Json.Read<ModelRecord>(Path.Combine(folder,"model","model.json"));
  if(model.ColorSeparation is {} colors&&(colors.Groups.Length>64||
    Enumerable.Range(0,colors.Groups.Length).Any(i=>!File.Exists(Path.Combine(folder,"model",$"color_{i:D3}.mesh")))))
   throw new InvalidDataException("Farbgruppen im Projekt sind unvollständig oder ungültig.");
  var resultPath=Path.Combine(folder,"result","result.json");var result=File.Exists(resultPath)?Json.Read<SliceResult>(resultPath):null;
  // Only names inside result/ may be referenced by a manifest.
  if(result!=null)
  {
   foreach(var name in result.Parts.Select(p=>p.File).Concat(result.Connectors.Select(p=>p.File)))
    if(Path.GetFileName(name)!=name||!name.EndsWith(".stl",StringComparison.OrdinalIgnoreCase)||!File.Exists(Path.Combine(folder,"result",name)))throw new InvalidDataException("Ungültige Geometriereferenz im Projekt.");
  }
  return new(Path.Combine(folder,"model"),result==null?null:Path.Combine(folder,"result"),model,result,project.Settings);
 }
 private sealed class ProjectHeader {public int Version {get;set;} public SliceSettings Settings {get;set;}=new();}
}
