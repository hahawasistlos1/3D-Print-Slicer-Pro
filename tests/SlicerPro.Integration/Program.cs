using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using SlicerPro;
using SlicerPro.Services;
using SlicerPro.Controls;

var root=Path.GetFullPath(args[0]);var work=Path.Combine(root,"artifacts","integration");Directory.CreateDirectory(work);
Environment.SetEnvironmentVariable("SLICERPRO_DATA_DIR",work);
var service=new GeometryService();var model=GeometryService.NewFolder();
await service.RunAsync(new{command="import",input=Path.Combine(root,"artifacts","demo.stl"),output=model},model,null,CancellationToken.None);
var settings=new SliceSettings{BedX=300,BedY=300,BedZ=300,Diameter=6,Depth=8,Wall=1,Mode="mixed"};
var resultFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="slice",input=Path.Combine(model,"original.stl"),output=resultFolder,settings},resultFolder,null,CancellationToken.None);
var result=Json.Read<SliceResult>(Path.Combine(resultFolder,"result.json"));
var original=Json.Read<ModelRecord>(Path.Combine(model,"model.json"));
var state=new Workspace(model,resultFolder,original,result,settings);
void Check(bool success,string label){if(!success)throw new Exception(label);Console.WriteLine("PASS "+label);}
Check(result.Valid&&result.Parts.Length>1,"Worker: echte Teile und Netzprüfung");
var project=Path.Combine(work,"Roundtrip.3dps");ProjectService.Save(state,project);var reopened=ProjectService.Open(project);
Check(reopened.Result?.Joints.Length==result.Joints.Length,"Projekt: Verbinderzuordnung erhalten");
Check(reopened.Settings.Mode==settings.Mode&&reopened.Settings.Wall==settings.Wall,"Projekt: Parameter erhalten");
Check(reopened.Result?.Planning?.Algorithm=="adaptive-axis-v1","Projekt: adaptive Strategie erhalten");
Check(reopened.Result?.Interfaces.Length==result.Interfaces.Length&&result.Interfaces.Length>0,"Projekt: tatsächliche Schnittstellen erhalten");
Check(reopened.Result?.Assembly?.Groups.Length==result.Assembly?.Groups.Length,"Projekt: geprüfter Verbindungsgraph erhalten");
Check(reopened.Result!.Parts.All(p=>p.CutFaces!=null&&p.ConnectedNeighbors!=null),"Projekt: lokale Schnittflächen und Verbindungsnachbarn erhalten");
Check(reopened.Result.Planning!.Extra?.ContainsKey("localCuts")==true,"Projekt: lokale Planungsgeometrie erhalten");
Check(reopened.Result.Motion?.Checked==true,"Projekt: Montagewegprüfung ausgeführt und erhalten");
Check(reopened.Result.Motion!.Status==result.Motion?.Status&&reopened.Result.Motion.DisassemblySteps.Length==result.Motion.DisassemblySteps.Length,"Projekt: Bewegungsnachweise unverändert");
string Hash(string f)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(f)));
Check(Hash(Path.Combine(model,"original.stl"))==Hash(Path.Combine(reopened.ModelFolder,"original.stl")),"Projekt: Originalgeometrie unverändert");
foreach(var part in result.Parts)Check(Hash(Path.Combine(resultFolder,part.File))==Hash(Path.Combine(reopened.ResultFolder!,part.File)),"Projekt: "+part.Name+" unverändert");
var pdf=Path.Combine(work,"Montageplan.pdf");AssemblyService.WritePdf(reopened,pdf);var pdfBytes=File.ReadAllBytes(pdf);
Check(System.Text.Encoding.ASCII.GetString(pdfBytes[..8]).StartsWith("%PDF-1.4"),"Montageplan: PDF-Datei erzeugt");
var output=Path.Combine(work,"Export.stl");var first=result.Parts[0];var job=GeometryService.NewFolder();
await service.RunAsync(new{command="export",output=job,items=new[]{new{input=Path.Combine(resultFolder,first.File),output,order=first.PrintOrder}}},job,null,CancellationToken.None);
Check(File.Exists(output)&&new FileInfo(output).Length>84,"Worker: STL-Export in Druckausrichtung");
var malicious=Path.Combine(work,"Traversal.3dps");if(File.Exists(malicious))File.Delete(malicious);using(var zip=ZipFile.Open(malicious,ZipArchiveMode.Create)){using var writer=new StreamWriter(zip.CreateEntry("../outside.txt").Open());writer.Write("test");}
try{ProjectService.Open(malicious);throw new Exception("Pfadschutz fehlt");}catch(InvalidDataException){Console.WriteLine("PASS Projektarchiv: Pfadschutz");}
using(var cancel=new CancellationTokenSource()){cancel.Cancel();try{await service.RunAsync(new{command="demo",output=GeometryService.NewFolder()},GeometryService.NewFolder(),null,cancel.Token);throw new Exception("Abbruch fehlt");}catch(OperationCanceledException){Console.WriteLine("PASS Worker: Abbruch ohne Erfolgsmeldung");}}
var boxFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="import",input=Path.Combine(root,"artifacts","box.stl"),output=boxFolder,name="Passprobe-Quader"},boxFolder,null,CancellationToken.None);
var boxResultFolder=GeometryService.NewFolder();var boxSettings=new SliceSettings{Strategy="equal",Mode="separate"};
await service.RunAsync(new{command="slice",input=Path.Combine(boxFolder,"original.stl"),output=boxResultFolder,settings=boxSettings},boxResultFolder,null,CancellationToken.None);
var boxResult=Json.Read<SliceResult>(Path.Combine(boxResultFolder,"result.json"));
Check(boxResult.Motion?.PathVerified==true&&boxResult.Assembly?.PathVerified==true,"Montagewege: vollständige gerade Quaderfolge nachgewiesen");
Check(boxResult.Motion!.PreinsertSteps.Length==2&&boxResult.Motion.AssemblySteps.Length==2,"Montagewege: Dübelvorbestückung und Teilefolge enthalten");
Check(boxResult.Motion.AssemblySteps[1].InsertionDirection.SequenceEqual(new double[]{1,0,0}),"Montagewege: tatsächliche Einsteckrichtung erhalten");
var boxState=new Workspace(boxFolder,boxResultFolder,Json.Read<ModelRecord>(Path.Combine(boxFolder,"model.json")),boxResult,boxSettings);
var boxProject=Path.Combine(work,"Montage-Geprueft.3dps");ProjectService.Save(boxState,boxProject);
Check(ProjectService.Open(boxProject).Result?.Motion?.AssemblySteps[1].Distance==boxResult.Motion.AssemblySteps[1].Distance,"Projekt: nachgewiesener Einsteckweg bleibt erhalten");
AssemblyService.WritePdf(boxState,Path.Combine(work,"Montageplan-Geprueft.pdf"));
Check(new PartRecord{Neighbors=[2],ConnectedNeighbors=[],RequestedConnectors=0}.NeedsAssemblyCheck==false,"Anzeige: absichtlich ohne Verbinder erhält keine falsche Teilewarnung");
var tongueFolder=GeometryService.NewFolder();var tongueSettings=new SliceSettings{Strategy="equal",Kind="tongue",Diameter=6,TongueLength=60,Depth=12,Wall=2};
await service.RunAsync(new{command="slice",input=Path.Combine(boxFolder,"original.stl"),output=tongueFolder,settings=tongueSettings},tongueFolder,null,CancellationToken.None);
var tongueResult=Json.Read<SliceResult>(Path.Combine(tongueFolder,"result.json"));
Check(tongueResult.Valid&&tongueResult.Joints.Length==2&&tongueResult.Motion?.PathVerified==true,"Nut/Feder: echter Worker erzeugt zwei Federn und prüft Montagewege");
Check(tongueResult.Joints.All(j=>j.Kind=="tongue"&&j.Length==60&&j.TangentAxis is int tangent&&tangent!=j.Axis),"Nut/Feder: Länge und Flächenrichtung des tatsächlichen Verbinders");
var tongueState=new Workspace(boxFolder,tongueFolder,Json.Read<ModelRecord>(Path.Combine(boxFolder,"model.json")),tongueResult,tongueSettings);
var tongueProject=Path.Combine(work,"Nut-Feder-Geprueft.3dps");ProjectService.Save(tongueState,tongueProject);
var tongueOpened=ProjectService.Open(tongueProject);
Check(tongueOpened.Settings.TongueLength==60&&tongueOpened.Result!.Joints.All(j=>j.Length==60&&j.TangentAxis==tongueResult.Joints[0].TangentAxis),"Nut/Feder: Geometrieparameter bleiben im Projekt erhalten");
foreach(var pin in tongueResult.Connectors)Check(Hash(Path.Combine(tongueFolder,pin.File))==Hash(Path.Combine(tongueOpened.ResultFolder!,pin.File)),"Nut/Feder: lose Feder bleibt im Projekt Hash-identisch");
AssemblyService.WritePdf(tongueState,Path.Combine(work,"Montageplan-Nut-Feder.pdf"));
var tongueExport=Path.Combine(work,"Feder-Passprobe.stl");var tongueJob=GeometryService.NewFolder();var loose=tongueResult.Connectors[0];
await service.RunAsync(new{command="export",output=tongueJob,items=new[]{new{input=Path.Combine(tongueFolder,loose.File),output=tongueExport,order=loose.PrintOrder}}},tongueJob,null,CancellationToken.None);
Check(File.Exists(tongueExport)&&new FileInfo(tongueExport).Length>84,"Nut/Feder: separate Feder als echte STL exportiert");
foreach(var format in GeometryExport.Formats)
{
 var formatFolder=Path.Combine(work,"Export-0.5",format.Id);Directory.CreateDirectory(formatFolder);
 var exportItems=tongueResult.Parts.Select(p=>new GeometryExportItem(Path.Combine(tongueFolder,p.File),Path.Combine(formatFolder,GeometryExport.FileName(p.File,format.Id)),p.PrintOrder,format.Id))
  .Concat(tongueResult.Connectors.Select(c=>new GeometryExportItem(Path.Combine(tongueFolder,c.File),Path.Combine(formatFolder,GeometryExport.FileName(c.File,format.Id)),c.PrintOrder,format.Id))).ToArray();
 var firstOutput=exportItems[0].Output;exportItems[0]=exportItems[0] with {Output=firstOutput+".tmp"};
 var exportJob=GeometryService.NewFolder();
 await service.RunAsync(new{command="export",output=exportJob,items=exportItems},exportJob,null,CancellationToken.None);
 Check(File.Exists(exportItems[0].Output),format.Id.ToUpperInvariant()+": Einzelteil-Export mit temporärer Dateiendung funktioniert");
 File.Move(exportItems[0].Output,firstOutput,true);
 Check(Directory.GetFiles(formatFolder,"*."+format.Id).Length==4,format.Id.ToUpperInvariant()+": zwei Druckteile und zwei Federn exportiert");
 var reimport=GeometryService.NewFolder();
 await service.RunAsync(new{command="import",input=firstOutput,output=reimport},reimport,null,CancellationToken.None);
 var reimported=Json.Read<ModelRecord>(Path.Combine(reimport,"model.json"));var firstTonguePart=tongueResult.Parts[0];
 var expectedDimensions=firstTonguePart.PrintOrder!.Select(axis=>firstTonguePart.Dimensions[axis]);
 Check(reimported.Original.Watertight&&reimported.Original.NormalsConsistent&&reimported.Original.Volume>0&&reimported.Original.Dimensions.Zip(expectedDimensions).All(pair=>Math.Abs(pair.First-pair.Second)<1e-3),format.Id.ToUpperInvariant()+": Reimport mit geschlossenem Netz und echten Druckmaßen");
}
Check(Hash(Path.Combine(tongueFolder,tongueResult.Parts[0].File))==Hash(Path.Combine(tongueOpened.ResultFolder!,tongueResult.Parts[0].File)),"Exportformate: gespeicherte Montagegeometrie unverändert");
var denseFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="import",input=Path.Combine(root,"artifacts","preview-dense.stl"),output=denseFolder,name="Dichte Kugel · 131072 Dreiecke"},denseFolder,null,CancellationToken.None);
var denseModel=Json.Read<ModelRecord>(Path.Combine(denseFolder,"model.json"));var denseState=new Workspace(denseFolder,null,denseModel,null,new());
var denseSource=Path.Combine(denseFolder,"original.stl");var denseHash=Hash(denseSource);
var previewService=new PreviewService();var display=await previewService.PrepareAsync(denseState,service);
Check(display.Original.Info.Reduced&&display.Original.Info.Watertight&&display.Original.Info.TopologyPreserved&&display.Original.Info.Triangles<=120000,"Vorschau: dichtes Original erhält geschlossenes vereinfachtes Anzeigenetz");
var exactMesh=ModelViewport.LoadStl(denseSource);
Check(exactMesh.TriangleIndices.Count==denseModel.Original.Triangles*3,"WPF: auch oberhalb 120000 Dreiecken werden alle Flächen geladen");
var displayMesh=ModelViewport.LoadMesh(display.Original.Path);
Check(displayMesh.TriangleIndices.Count==display.Original.Info.Triangles*3,"WPF: vereinfachte Geometrie wird vollständig geladen");
Check(Hash(denseSource)==denseHash,"Vorschau: Originaldatei Hash-identisch erhalten");
var cached=await previewService.PrepareAsync(denseState,service);
Check(cached.Original.Path==display.Original.Path,"Vorschau: unveränderte Geometrie verwendet den Sitzungscache");
var full=await previewService.PrepareAsync(denseState,service,exact:true);
Check(full.Original.Path==denseSource&&!full.Original.Info.Reduced,"Vorschau: Originalnetzmodus verwendet die vollständige Quelldatei");
var previewParts=await previewService.PrepareAsync(tongueState,service);
Check(previewParts.Items.Count==3&&previewParts.Items.ContainsKey("part:2"),"Vorschau: Original und beide Druckteile eindeutig zugeordnet");
var part2Mesh=ModelViewport.LoadMesh(previewParts.Items["part:2"].Path);
Check(Math.Abs(part2Mesh.Bounds.X-150)<1e-3,"Vorschau: zweites Teil behält seine Montageposition bei X=150 mm");
var denseProject=Path.Combine(work,"Dichte-Kugel-Vorschau.3dps");ProjectService.Save(denseState,denseProject);
using(var denseArchive=ZipFile.OpenRead(denseProject))Check(!denseArchive.Entries.Any(e=>e.Name.StartsWith("Anzeige_")),"Projekt: Anzeigegeometrie wird nicht als Fertigungsgeometrie gespeichert");
var exportDense=Path.Combine(work,"Dichte-Kugel-Export.stl");var exportDenseJob=GeometryService.NewFolder();
await service.RunAsync(new{command="export",output=exportDenseJob,items=new[]{new GeometryExportItem(denseSource,exportDense,[0,1,2],"stl")}},exportDenseJob,null,CancellationToken.None);
Check(ModelViewport.LoadStl(exportDense).TriangleIndices.Count==denseModel.Original.Triangles*3,"Export: vollständige Geometrie bleibt trotz vereinfachter Anzeige erhalten");
File.SetLastWriteTimeUtc(denseSource,File.GetLastWriteTimeUtc(denseSource).AddSeconds(2));
var renewed=await previewService.PrepareAsync(denseState,service);
Check(renewed.Original.Path!=display.Original.Path,"Vorschau: geänderte Quelldateikennung erneuert den Cache");
using(var cancelledPreview=new CancellationTokenSource()){cancelledPreview.Cancel();try{await previewService.PrepareAsync(denseState,service,token:cancelledPreview.Token);throw new Exception("Vorschau-Abbruch fehlt");}catch(OperationCanceledException){Console.WriteLine("PASS Vorschau: Abbruch wird berücksichtigt");}}
var orientationSource=Path.Combine(boxFolder,"original.stl");var orientationHash=Hash(orientationSource);var orientationMesh=ModelViewport.LoadStl(orientationSource);
foreach(var angles in new[]{new double[]{0,0,30},new double[]{90,90,0},new double[]{17,-29,43}})
{
 var orientedFolder=GeometryService.NewFolder();
 await service.RunAsync(new{command="rotate",input=orientationSource,output=orientedFolder,angles,name="Ausgerichteter Quader"},orientedFolder,null,CancellationToken.None);
 var oriented=Json.Read<ModelRecord>(Path.Combine(orientedFolder,"model.json"));var viewPreview=ModelOrientation.Preview(orientationMesh,angles);
 Check(oriented.Original.Watertight&&oriented.Original.NormalsConsistent&&Math.Abs(oriented.Original.Volume/2400000-1)<1e-5,"Ausrichtung: echter Worker erhält geschlossenes Netz und Volumen");
 Check(oriented.Original.Dimensions.Zip(viewPreview.Info.Dimensions).All(p=>Math.Abs(p.First-p.Second)<1e-3),"Ausrichtung: C#-Vorschau und vollständige Geometrie haben passende Maße");
 Check(oriented.Orientation?.Angles.SequenceEqual(angles)==true&&oriented.Orientation.Order=="XYZ","Ausrichtung: Winkelfolge in Modellmetadaten erhalten");
 var orientedSettings=new SliceSettings();orientedSettings.Cuts.Clear();var orientedState=new Workspace(orientedFolder,null,oriented,null,orientedSettings);
 var orientedProject=Path.Combine(work,"Ausgerichteter-Quader.3dps");ProjectService.Save(orientedState,orientedProject);var orientedOpened=ProjectService.Open(orientedProject);
 Check(orientedOpened.Model.Orientation!.Angles.SequenceEqual(angles)&&Hash(Path.Combine(orientedOpened.ModelFolder,"original.stl"))==Hash(Path.Combine(orientedFolder,"original.stl")),"Ausrichtung: Projekt-Roundtrip erhält Winkel und gedrehte Geometrie");
}
Check(Hash(orientationSource)==orientationHash,"Ausrichtung: vorheriges Modell bleibt Hash-identisch erhalten");
var quarterPreview=ModelOrientation.Preview(orientationMesh,[0,0,90]);
Check(quarterPreview.Info.Dimensions.Zip(new double[]{100,300,80}).All(p=>Math.Abs(p.First-p.Second)<1e-8),"Ausrichtung: 90 Grad um Z vertauscht X und Y in der Vorschau");
Check(ModelOrientation.IsIdentity([0,0,360])&&!ModelOrientation.IsIdentity([0,0,30]),"Ausrichtung: wirkungslose volle Drehung wird erkannt");
var manualFolder=GeometryService.NewFolder();
var manualSettings=new SliceSettings{BedX=450,BedY=450,BedZ=450,Count=1,
 Edits=[new ManualEdit{Point=[150,50,40],Normal=[1,1,0]}]};
await service.RunAsync(new{command="slice",input=orientationSource,output=manualFolder,settings=manualSettings},manualFolder,null,CancellationToken.None);
var manualResult=Json.Read<SliceResult>(Path.Combine(manualFolder,"result.json"));
Check(manualResult.Valid&&manualResult.Parts.Length==2&&manualResult.Joints.Single().Normal is {Length:3}&&manualResult.Motion?.PathVerified==true,
 "Freie Ebene: zwei echte Teile, schräger Verbinder und geprüfter Montageweg");
Check(manualResult.Parts.All(p=>p.Key!=null&&p.CutFaces!.Any(f=>f.Plane==1&&f.Normal is {Length:3})),"Freie Ebene: Teilezuordnung und Kappenebene übertragen");
var manualState=boxState with{ResultFolder=manualFolder,Result=manualResult,Settings=manualSettings};
var manualProject=Path.Combine(work,"Freie-Schnittebene.3dps");
ProjectService.Save(manualState,manualProject);
var manualOpened=ProjectService.Open(manualProject);
Check(manualOpened.Settings.Edits.Single().Normal.SequenceEqual(new double[]{1,1,0})&&manualOpened.Result!.Motion!.AssemblySteps[1].InsertionDirection.Count(v=>Math.Abs(v)>.1)==2,
 "Freie Ebene: Projekt speichert manuelle Eingabe und schrägen Montageweg");
AssemblyService.WritePdf(manualOpened,Path.Combine(work,"Montageplan-Freie-Ebene.pdf"));
var mergeSettings=manualOpened.Settings.Clone();
mergeSettings.Edits=[..mergeSettings.Edits,new ManualEdit{Merge=manualOpened.Result!.Parts.Select(p=>p.Key!).ToArray()}];
var mergedFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="slice",input=orientationSource,output=mergedFolder,settings=mergeSettings},mergedFolder,null,CancellationToken.None);
var merged=Json.Read<SliceResult>(Path.Combine(mergedFolder,"result.json"));
Check(merged.Valid&&merged.Parts.Length==1&&merged.Joints.Length==0&&merged.Interfaces.Length==0,"Zusammenfügen: echte Vereinigung ohne alte Steckgeometrie");
var railFolder=GeometryService.NewFolder();
var railSettings=new SliceSettings{Strategy="equal",Kind="dovetail",Mode="separate",Count=1,Depth=10};
await service.RunAsync(new{command="slice",input=orientationSource,output=railFolder,settings=railSettings},railFolder,null,CancellationToken.None);
var railResult=Json.Read<SliceResult>(Path.Combine(railFolder,"result.json"));
var railJoint=railResult.Joints.Single();
Check(railResult.Valid&&railResult.Connectors.Length==1&&railResult.Motion?.PathVerified==true&&railJoint.RemovalDirection is {Length:3}&&railJoint.PinWithdrawal is {Length:3},"Schwalbenschwanz: echter Schlüssel und geprüfter Seiteneinschub");
var railFace=railResult.Interfaces.Single();
railSettings.Placements=[new ConnectorPlacement{InterfaceId=railFace.Id,AKey=railResult.Parts[0].Key!,BKey=railResult.Parts[1].Key!,Center=[railFace.Offset,48,45]}];
var fixedFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="slice",input=orientationSource,output=fixedFolder,settings=railSettings},fixedFolder,null,CancellationToken.None);
var fixedResult=Json.Read<SliceResult>(Path.Combine(fixedFolder,"result.json"));
Check(fixedResult.Joints.Single().ManualPosition&&Math.Abs(fixedResult.Joints[0].Center[2]-45)<1e-8&&fixedResult.Motion?.PathVerified==true,"Schwalbenschwanz: manuelle Position nach Geometrie- und Montageprüfung übernommen");
var railProject=Path.Combine(work,"Schwalbenschwanz.3dps");
ProjectService.Save(boxState with{ResultFolder=fixedFolder,Result=fixedResult,Settings=railSettings},railProject);
var railOpened=ProjectService.Open(railProject);
Check(railOpened.Settings.Placements.Length==1&&railOpened.Result?.Joints.Single().ManualPosition==true
 &&railOpened.Result.Parts.All(p=>p.PrintChecks is {TestedRays:>0,OverhangArea:not null}),"Projekt: manuelle Position, Schwalbenschwanz und Druckhinweise bleiben gespeichert");
AssemblyService.WritePdf(railOpened,Path.Combine(work,"Montageplan-Schwalbenschwanz.pdf"));
foreach(var kind in new[]{"clip","screw"})
{
 var folder=GeometryService.NewFolder();
 var specialSettings=new SliceSettings{Strategy="equal",Kind=kind,Mode="separate",Count=1};
 await service.RunAsync(new{command="slice",input=orientationSource,output=folder,settings=specialSettings},folder,null,CancellationToken.None);
 var specialResult=Json.Read<SliceResult>(Path.Combine(folder,"result.json"));
 var joint=specialResult.Joints.Single();
 Check(specialResult.Valid&&specialResult.Connectors.Length==1&&specialResult.Motion?.Reason=="flexible-or-rotational-joints"
  &&specialResult.Motion.PathVerified==false,kind+": echte lose Geometrie mit offenem Montagenachweis");
 Check(kind=="clip"?joint.ClipStrainPercent is >0 and <=3:joint.Pitch==2&&joint.ThreadLength==12,
  kind+": berechnete Parameter übertragen");
 var specialState=boxState with{ResultFolder=folder,Result=specialResult,Settings=specialSettings};
 var specialProject=Path.Combine(work,kind=="clip"?"Steckclip.3dps":"Aussenschraube.3dps");
 ProjectService.Save(specialState,specialProject);
 var opened=ProjectService.Open(specialProject);
 var displaySpecial=await previewService.PrepareAsync(opened,service);
 var displayed=displaySpecial.Items["connector:"+joint.Id];
 Check(opened.Settings.Kind==kind&&displayed.Info.Watertight&&ModelViewport.LoadMesh(displayed.Path).TriangleIndices.Count>0,
  kind+": Projekt-Roundtrip und echtes geschlossenes Anzeigenetz");
}
var multipartFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="import",input=Path.Combine(root,"artifacts","multipart-3mf-test.3mf"),output=multipartFolder},
 multipartFolder,null,CancellationToken.None);
var multipart=Json.Read<ModelRecord>(Path.Combine(multipartFolder,"model.json"));
Check(multipart.Original.Watertight&&multipart.Original.Components==2&&multipart.Original.Dimensions.SequenceEqual(new double[]{120,40,30}),
 "3MF-Import: externe Objekte aus dem Archiv mit eigenen IDs und Maßen geladen");
var multipartOutput=GeometryService.NewFolder();
await service.RunAsync(new{command="slice",input=Path.Combine(multipartFolder,"original.stl"),output=multipartOutput,settings=new SliceSettings{Mode="none"}},
 multipartOutput,null,CancellationToken.None);
var multipartResult=Json.Read<SliceResult>(Path.Combine(multipartOutput,"result.json"));
Check(multipartResult.Valid&&multipartResult.Parts.Length==2,"3MF-Import: übernommene Volumenkörper bleiben im Schnittablauf erhalten");
var repairFolder=GeometryService.NewFolder();
var repairSource=Path.Combine(root,"artifacts","mesh-repair-test.3mf");
var repairSourceHash=Hash(repairSource);
await service.RunAsync(new{command="import",input=repairSource,output=repairFolder},
 repairFolder,null,CancellationToken.None);
var repaired=Json.Read<ModelRecord>(Path.Combine(repairFolder,"model.json"));
Check(repaired.Repair?.HolesClosed==1&&repaired.Original.Watertight&&repaired.Original.Components==2&&
 Math.Abs(repaired.Original.Volume-8125)<1e-6&&Hash(repairSource)==repairSourceHash,
 "3MF-Netzreparatur: eine kleine Öffnung geschlossen, Quelldatei erhalten");
var repairProject=Path.Combine(work,"Netzreparatur.3dps");
ProjectService.Save(new Workspace(repairFolder,null,repaired,null,new SliceSettings()),repairProject);
Check(ProjectService.Open(repairProject).Model.Repair?.HolesClosed==1,"3MF-Netzreparatur: Prüfvermerk im Projekt gespeichert");
var contactFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="import",input=Path.Combine(root,"artifacts","mesh-index-test.3mf"),output=contactFolder},
 contactFolder,null,CancellationToken.None);
var contactModel=Json.Read<ModelRecord>(Path.Combine(contactFolder,"model.json"));
var contactState=new Workspace(contactFolder,null,contactModel,null,new SliceSettings{Mode="none"});
var contactProject=Path.Combine(work,"Getrennte-Netzkanten.3dps");
ProjectService.Save(contactState,contactProject);
var contactOpened=ProjectService.Open(contactProject);
var contactDisplay=await previewService.PrepareAsync(contactOpened,service);
Check(contactModel.Repair==null&&contactDisplay.Original.Info.TopologyPreserved&&contactModel.Original.Components==2,
 "3MF-Kantenkontakt: Netzindizes bleiben nach Projekt-Roundtrip bis zur Vorschau erhalten");
var contactMesh=ModelViewport.LoadMesh(contactDisplay.Original.Path);
var contactExact=await previewService.PrepareAsync(contactOpened,service,exact:true);
Check(contactMesh.Positions.Count==16&&contactMesh.TriangleIndices.Count==72&&contactExact.Original.Path.EndsWith(".mesh")&&
 ModelViewport.LoadMesh(contactExact.Original.Path).TriangleIndices.SequenceEqual(contactMesh.TriangleIndices),
 "3MF-Kantenkontakt: WPF liest indizierte Vorschau und vollständiges Netz");
var contactOutput=GeometryService.NewFolder();
await service.RunAsync(new{command="slice",input=Path.Combine(contactOpened.ModelFolder,"original.stl"),output=contactOutput,settings=contactOpened.Settings},
 contactOutput,null,CancellationToken.None);
var contactResult=Json.Read<SliceResult>(Path.Combine(contactOutput,"result.json"));
Check(contactResult.Valid&&contactResult.Parts.Length==2&&File.Exists(Path.Combine(contactOutput,"Teil_001.mesh")),
 "3MF-Kantenkontakt: beide Körper ohne STL-Neuverschweißung weiterverarbeitet");
var colorFolder=GeometryService.NewFolder();
await service.RunAsync(new{command="import",input=Path.Combine(root,"artifacts","farben-test.3mf"),output=colorFolder},
 colorFolder,null,CancellationToken.None);
var colorModel=Json.Read<ModelRecord>(Path.Combine(colorFolder,"model.json"));
var colorSettings=new SliceSettings{Strategy="color",Mode="none"};
var colorOutput=GeometryService.NewFolder();
await service.RunAsync(new{command="slice",input=Path.Combine(colorFolder,"original.stl"),output=colorOutput,settings=colorSettings},
 colorOutput,null,CancellationToken.None);
var colorResult=Json.Read<SliceResult>(Path.Combine(colorOutput,"result.json"));
Check(colorResult.Valid&&colorResult.Parts.Select(p=>p.Color).SequenceEqual(new[]{"#2266EE","#EE2244"})&&
 colorModel.ColorSeparation?.Groups.SequenceEqual(new[]{"#2266EE","#EE2244"})==true,
 "Farbtrennung: berührende Volumenkörper getrennt und mit Farbe ausgegeben");
var colorProject=Path.Combine(work,"Farbgruppen.3dps");
ProjectService.Save(new Workspace(colorFolder,colorOutput,colorModel,colorResult,colorSettings),colorProject);
var colorOpened=ProjectService.Open(colorProject);
var colorPreview=await previewService.PrepareAsync(colorOpened,service);
Check(File.Exists(Path.Combine(colorOpened.ModelFolder,"color_001.mesh"))&&colorOpened.Settings.Strategy=="color"&&
 colorOpened.Result?.Parts[1].Color=="#EE2244"&&colorPreview.Items.Count==3&&
 ModelViewport.ParsePartColor(colorOpened.Result?.Parts[1].Color)?.R==238,
 "Farbtrennung: Projekt-Roundtrip und Anzeige mit identischer Farbzuordnung");
Console.WriteLine("Integration erfolgreich.");
