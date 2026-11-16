using System.IO;
using SlicerPro.Controls;
namespace SlicerPro.Services;

public sealed class PreviewRecord
{
 public string Key {get;set;}="";public string File {get;set;}="";
 public int SourceTriangles {get;set;} public int Triangles {get;set;} public int Budget {get;set;}
 public bool Reduced {get;set;} public bool BudgetReached {get;set;} public bool Watertight {get;set;} public bool TopologyPreserved {get;set;}
 public double Tolerance {get;set;} public double VolumeError {get;set;} public double BoundsError {get;set;}
 public string Note=>Reduced?$"Anzeige vereinfacht · {Triangles:N0}/{SourceTriangles:N0} Dreiecke":"Anzeige vollständig · "+Triangles.ToString("N0")+" Dreiecke";
 public string Detail=>Note+$"\nVereinfachungstoleranz: {Tolerance:G3} mm · Volumenabweichung: {VolumeError:P2}"+(BudgetReached?"":"\nAnzeigeziel überschritten; vollständige Flächen erhalten.");
}
public sealed record DisplayPreview(string Path,PreviewRecord Info);
public sealed record PreviewSet(Dictionary<string,DisplayPreview> Items)
{
 public DisplayPreview Original=>Items["original"];
 public string PartsNote=>Items.Where(p=>p.Key.StartsWith("part:")).Any(p=>p.Value.Info.Reduced)?"Anzeige: geschlossene vereinfachte Netze":"Anzeige: vollständige Netze";
 public string Detail=>string.Join("\n\n",Items.Select(p=>p.Key+": "+p.Value.Info.Detail));
 public string Summary=>$"Anzeige: {Items.Values.Sum(p=>(long)p.Info.Triangles):N0} von {Items.Values.Sum(p=>(long)p.Info.SourceTriangles):N0} Dreiecken. Größte Vereinfachungstoleranz: {Items.Values.Max(p=>p.Info.Tolerance):G3} mm."+(Items.Values.Any(p=>!p.Info.BudgetReached)?" Zielbudget nicht überall erreicht; Flächen bleiben vollständig.":"");
}
public sealed class PreviewService
{
 readonly Dictionary<string,DisplayPreview> cache=[];
 sealed class Manifest {public PreviewRecord[] Items {get;set;}=[];}
 sealed record Source(string Key,string Input,int Budget,string Fingerprint);
 static Source SourceFor(string key,string input,int budget)
 {
  var file=new FileInfo(input);
  var indexed=new FileInfo(Path.ChangeExtension(file.FullName,".mesh"));
  var topology=indexed.Exists?$"|{indexed.Length}|{indexed.LastWriteTimeUtc.Ticks}":"";
  return new(key,file.FullName,budget,file.FullName+"|"+file.Length+"|"+file.LastWriteTimeUtc.Ticks+topology+"|"+budget+"|closed-v3");
 }
 public async Task<PreviewSet> PrepareAsync(Workspace state,GeometryService geometry,bool exact=false,IProgress<(int,string)>? progress=null,CancellationToken token=default)
 {
  var sources=new List<Source>{SourceFor("original",System.IO.Path.Combine(state.ModelFolder,"original.stl"),120000)};
  if(state.Result is {} result)
  {
   sources.AddRange(result.Parts.Select(p=>SourceFor("part:"+p.Id,Path.Combine(state.ResultFolder!,p.File),Math.Max(600,180000/result.Parts.Length))));
   var detailed=result.Joints.Where(j=>j.Kind is "clip" or "screw").Select(j=>j.Id).ToHashSet();
   var connectors=result.Connectors.Where(c=>detailed.Contains(c.Id)).ToArray();
   if(connectors.Length>0)
    sources.AddRange(connectors.Select(c=>SourceFor("connector:"+c.Id,Path.Combine(state.ResultFolder!,c.File),Math.Max(1000,60000/connectors.Length))));
  }
  token.ThrowIfCancellationRequested();
  if(exact)
  {
   var complete=new Dictionary<string,DisplayPreview>();
   foreach(var source in sources)
   {
    var indexed=Path.ChangeExtension(source.Input,".mesh");
    var hasIndexed=File.Exists(indexed);
    var file=hasIndexed?indexed:source.Input;
    using var reader=new BinaryReader(File.OpenRead(file));
    reader.BaseStream.Position=hasIndexed?12:80;
    var count=checked((int)reader.ReadUInt32());
    complete.Add(source.Key,new(file,new(){SourceTriangles=count,Triangles=count,Budget=count,BudgetReached=true,Watertight=true,TopologyPreserved=true}));
   }
   return new(complete);
  }
  var missing=sources.Where(s=>!cache.TryGetValue(s.Fingerprint,out var found)||!System.IO.File.Exists(found.Path)).GroupBy(s=>s.Fingerprint).Select(g=>g.First()).ToArray();
  if(missing.Length>0)
  {
   var folder=GeometryService.NewFolder();
   await geometry.RunAsync(new{command="preview",output=folder,items=missing.Select(s=>new{key=s.Fingerprint,input=s.Input,budget=s.Budget}).ToArray()},folder,progress,token);
   token.ThrowIfCancellationRequested();var manifest=Json.Read<Manifest>(System.IO.Path.Combine(folder,"preview.json"));
   if(manifest.Items.Length!=missing.Length||manifest.Items.Select(i=>i.Key).Distinct().Count()!=missing.Length)throw new InvalidDataException("Unvollständige Vorschauzuordnung.");
   var prepared=new Dictionary<string,DisplayPreview>();
   foreach(var record in manifest.Items)
   {
    if(!missing.Any(s=>s.Fingerprint==record.Key)||System.IO.Path.GetFileName(record.File)!=record.File||!record.File.EndsWith(".mesh",StringComparison.OrdinalIgnoreCase)||!record.Watertight||!record.TopologyPreserved||record.Triangles<=0||record.Triangles>ModelViewport.MaxMeshTriangles)throw new InvalidDataException("Ungültige geschlossene Vorschaugeometrie.");
    var file=System.IO.Path.Combine(folder,record.File);if(!System.IO.File.Exists(file))throw new InvalidDataException("Vorschaudatei fehlt.");prepared.Add(record.Key,new(file,record));
   }
   foreach(var entry in prepared)cache[entry.Key]=entry.Value;
  }
  return new(sources.ToDictionary(s=>s.Key,s=>cache[s.Fingerprint]));
 }
}
