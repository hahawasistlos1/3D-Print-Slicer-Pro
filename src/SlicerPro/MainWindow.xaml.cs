using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Media3D;
using Microsoft.Win32;
using SlicerPro.Controls;
using SlicerPro.Services;
namespace SlicerPro;

public partial class MainWindow : Window
{
 readonly GeometryService geometry=new(); Workspace? current;
 readonly PreviewService previewService=new();PreviewSet? displayPreviews;MeshGeometry3D? originalMesh;bool exactPreview;
 readonly Stack<Workspace> undo=[],redo=[]; readonly Dictionary<int,MeshGeometry3D> partMeshes=[];
 Dictionary<string,MeshGeometry3D> connectorMeshes=[];
 readonly List<PrinterProfile> profiles=[]; readonly HashSet<int> hidden=[];
 CancellationTokenSource? cancellation; bool busy,dirty,gridVisible=true,cutsVisible=true,connectorsVisible=true,single,ready,loadingSettings,thinWallsVisible;
 double explode,opacity=1,insertionProgress=1; int selected,assemblyStep=int.MaxValue; SliceSettings settings=new();string? projectPath;
 public MainWindow()
 {
  InitializeComponent();
  VersionText.Text=$"LOKAL  ●  VORSCHAU {typeof(MainWindow).Assembly.GetName().Version!.ToString(3)}";
  Width=Math.Min(1620,SystemParameters.WorkArea.Width-16);Height=Math.Min(940,SystemParameters.WorkArea.Height-16);
  OriginalView.CameraChanged+=(y,p,d,c)=>PartsView.Sync(y,p,d,c);PartsView.CameraChanged+=(y,p,d,c)=>OriginalView.Sync(y,p,d,c);
  PartsView.PartSelected+=id=>{selected=id;RefreshParts();HighlightThumbnails();};
  LoadPreferences();ViewMode.SelectedIndex=0;ready=true;
  foreach(var box in new[]{BedX,BedY,BedZ,MarginBox,TargetBox,DiameterBox,DepthBox,ToleranceBox,TongueLengthBox,RectHeightBox,ClipStrainBox,ThreadLengthBox,ThreadPitchBox})box.TextChanged+=ParametersChanged;
  foreach(var box in new[]{StrategyBox,KindBox,ModeBox,CountBox})box.SelectionChanged+=ParametersChanged;
  OptimizeBox.Checked+=ParametersChanged;OptimizeBox.Unchecked+=ParametersChanged;
  PathCheckBox.Checked+=ParametersChanged;PathCheckBox.Unchecked+=ParametersChanged;AutoSizeBox.Checked+=ParametersChanged;AutoSizeBox.Unchecked+=ParametersChanged;
  AcrossColorsBox.Checked+=ParametersChanged;AcrossColorsBox.Unchecked+=ParametersChanged;
  ModeBox.SelectionChanged+=StrategyChanged;
  StrategyChanged(this,null!);
  Loaded+=async (_,_)=>
  {
   var args=Environment.GetCommandLineArgs();
   if(args.Length>1&&File.Exists(args[1])){await OpenFile(args[1]);return;}
   if(args.Contains("--empty"))return;
   await LoadDemo();
  };
 }
 void LoadPreferences()
 {
  profiles.AddRange([new(){Name="Standard · 220 × 220 × 250",X=220,Y=220,Z=250},new(){Name="Großformat · 300 × 300 × 300",X=300,Y=300,Z=300},new(){Name="Kompakt · 180 × 180 × 180",X=180,Y=180,Z=180}]);
  try
  {
   var path=Path.Combine(App.DataRoot,"preferences.json");if(File.Exists(path)){var p=Json.Read<Preferences>(path);settings=p.Settings;profiles.AddRange(p.Profiles);}
  }catch(Exception e){App.Log(e);StatusText.Text="Einstellungen konnten nicht gelesen werden; Standardwerte geladen.";}
  PrinterBox.ItemsSource=profiles;ApplySettings(settings);
 }
 void SavePreferences()
 {
  var defaults=settings.Clone();defaults.Cuts.Clear();defaults.Edits=[];defaults.Placements=[];if(defaults.Strategy=="color")defaults.Strategy="adaptive";
  Directory.CreateDirectory(App.DataRoot);Json.Write(Path.Combine(App.DataRoot,"preferences.json"),new Preferences{Settings=defaults,Profiles=profiles.Skip(3).ToArray()});
 }
 sealed class Preferences {public SliceSettings Settings {get;set;}=new();public PrinterProfile[] Profiles {get;set;}=[];}
 static double Number(TextBox box,string label)
 {
  if(!double.TryParse(box.Text.Trim().Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture,out double value)||!double.IsFinite(value))throw new ArgumentException($"Bitte einen gültigen Zahlenwert für „{label}“ eingeben.");return value;
 }
 static string TagOf(ComboBox box)=>((ComboBoxItem)box.SelectedItem).Tag.ToString()!;
 SliceSettings ReadSettings()
 {
  var s=settings.Clone();s.BedX=Number(BedX,"Druckraum X");s.BedY=Number(BedY,"Druckraum Y");s.BedZ=Number(BedZ,"Druckraum Z");
  s.Margin=Number(MarginBox,"Sicherheitsabstand");s.Target=Number(TargetBox,"Teilgröße");s.Diameter=Number(DiameterBox,"Durchmesser / Breite");s.TongueLength=Number(TongueLengthBox,"Federlänge");s.RectHeight=Number(RectHeightBox,"Zapfenhöhe");s.Depth=Number(DepthBox,"Einstecktiefe");s.Tolerance=Number(ToleranceBox,"Toleranz");s.ClipStrainPercent=Number(ClipStrainBox,"Armdehnungsgrenze");s.ThreadLength=Number(ThreadLengthBox,"Gewindelänge");s.ThreadPitch=Number(ThreadPitchBox,"Gewindesteigung");
  s.ConnectAcrossColors=AcrossColorsBox.IsChecked==true;
  s.Count=int.Parse(((ComboBoxItem)CountBox.SelectedItem).Content.ToString()!,CultureInfo.InvariantCulture);s.Strategy=TagOf(StrategyBox);s.Kind=TagOf(KindBox);s.Mode=TagOf(ModeBox);s.Optimize=OptimizeBox.IsChecked==true;s.AutoSize=AutoSizeBox.IsChecked==true;s.PathCheck=PathCheckBox.IsChecked==true;return s;
 }
 void ApplySettings(SliceSettings s)
 {
  loadingSettings=true;settings=s.Clone();
  BedX.Text=s.BedX.ToString("G",CultureInfo.CurrentCulture);BedY.Text=s.BedY.ToString("G",CultureInfo.CurrentCulture);BedZ.Text=s.BedZ.ToString("G",CultureInfo.CurrentCulture);
  MarginBox.Text=s.Margin.ToString("G");TargetBox.Text=s.Target.ToString("G");DiameterBox.Text=s.Diameter.ToString("G");DepthBox.Text=s.Depth.ToString("G");ToleranceBox.Text=s.Tolerance.ToString("G");TongueLengthBox.Text=s.TongueLength.ToString("G");RectHeightBox.Text=s.RectHeight.ToString("G");ClipStrainBox.Text=s.ClipStrainPercent.ToString("G");ThreadLengthBox.Text=s.ThreadLength.ToString("G");ThreadPitchBox.Text=s.ThreadPitch.ToString("G");
  void Choose(ComboBox box,string tag){foreach(ComboBoxItem item in box.Items)if(item.Tag?.ToString()==tag){box.SelectedItem=item;return;}}
  Choose(StrategyBox,s.Strategy);Choose(KindBox,s.Kind);Choose(ModeBox,s.Mode);
  foreach(ComboBoxItem item in CountBox.Items)if(item.Content.ToString()==s.Count.ToString())CountBox.SelectedItem=item;
  OptimizeBox.IsChecked=s.Optimize;
  AutoSizeBox.IsChecked=s.AutoSize;PathCheckBox.IsChecked=s.PathCheck;
  AcrossColorsBox.IsChecked=s.ConnectAcrossColors;
  PrinterBox.SelectedItem=profiles.FirstOrDefault(p=>Math.Abs(p.X-s.BedX)<1e-6&&Math.Abs(p.Y-s.BedY)<1e-6&&Math.Abs(p.Z-s.BedZ)<1e-6);
  loadingSettings=false;
  if(ready&&current?.Result is {} result){SetResultStatus(result);if(!ParametersMatchResult()){ResultStatus.Text="⚠ Ergebnis nicht aktuell · neu berechnen";ResultStatus.Foreground=Brushes.Orange;}}
 }
 bool ParametersMatchResult()
 {
  if(current?.Result is not {} result)return true;
  if(result.Planning==null||result.Motion==null)return false;
  try{return JsonSerializer.Serialize(ReadSettings(),Json.Options)==JsonSerializer.Serialize(result.Settings,Json.Options);}catch{return false;}
 }
 void ParametersChanged(object sender,RoutedEventArgs e)
 {
  if(!ready||loadingSettings||busy)return;
  if(current!=null)dirty=true;
  if(current?.Result is {} result)
  {
   if(ParametersMatchResult())SetResultStatus(result);
   else {ResultStatus.Text="⚠ Parameter geändert · neu berechnen";ResultStatus.Foreground=Brushes.Orange;StatusText.Text="Vorhandene Geometrie bleibt erhalten. Änderungen erst mit erneutem Schneiden anwenden.";}
  }
 }
 void StrategyChanged(object sender,SelectionChangedEventArgs e)
 {
  if(TargetBox!=null&&StrategyBox.SelectedItem is ComboBoxItem item)TargetBox.IsEnabled=item.Tag?.ToString()=="custom";
  var color=StrategyBox?.SelectedItem is ComboBoxItem {Tag:"color"};
  if(AcrossColorsBox!=null)
  {
   AcrossColorsBox.Visibility=color?Visibility.Visible:Visibility.Collapsed;
   AcrossColorsBox.IsEnabled=ModeBox?.SelectedItem is not ComboBoxItem {Tag:"none"};
  }
  if(SliceLabel!=null)
   SliceLabel.Text=color?"Nach Farbe trennen":"Modell schneiden\n& Verbinder setzen\n(Automatisch)";
 }
 void SetResultStatus(SliceResult result)
 {
  bool assemblyWarning=result.Assembly?.Connected==false||result.Interfaces.Any(f=>f.Placed<f.Requested)||result.Motion?.PathVerified!=true;
  bool thin=result.Parts.Any(p=>p.PrintChecks?.ThinSamples>0)||result.Connectors.Any(p=>p.PrintChecks?.ThinSamples>0);
  bool warning=assemblyWarning||thin;
  ResultStatus.Text=!result.Valid?"⚠ Fehlerhafte Teile · Export gesperrt":thin?"⚠ Netz / Druckraum geprüft · Dünnwand-Hinweise":assemblyWarning?"⚠ Netz / Druckraum geprüft · Montage prüfen":"✓ Netz / Druckraum und gerade Montagewege geprüft";
  ResultStatus.Foreground=new SolidColorBrush(!result.Valid?Color.FromRgb(255,125,90):warning?Color.FromRgb(255,189,89):Color.FromRgb(100,234,190));
  ResultStatus.ToolTip=(result.Assembly?.Summary??"Für ältere Projekte bitte neu berechnen.")+"\n"+(result.Motion?.Summary??"Montagewege nicht geprüft")+(thin?"\nDünnwand-Hinweise und Koordinaten im Prüfbericht":"");
 }
 void Remember(){if(current!=null){undo.Push(current with{Settings=current.Settings.Clone()});redo.Clear();}UpdateHistory();}
 void UpdateHistory(){UndoButton.IsEnabled=!busy&&undo.Count>0;RedoButton.IsEnabled=!busy&&redo.Count>0;}
 async Task<bool> Work(Func<CancellationToken,IProgress<(int,string)>,Task> action)
 {
  if(busy)return false;busy=true;cancellation=new();
  SliceButton.IsEnabled=false;CancelButton.Visibility=Visibility.Visible;CutPanel.IsEnabled=false;ConnectorPanel.IsEnabled=false;PrinterBox.IsEnabled=false;UpdateHistory();
  var progress=new Progress<(int,string)>(p=>{Progress.Value=p.Item1;StatusText.Text=p.Item2;});
  try {await action(cancellation.Token,progress);return true;}
  catch(OperationCanceledException){StatusText.Text="Abgebrochen · bisheriges Ergebnis bleibt erhalten";return false;}
  catch(Exception e){App.Log(e);StatusText.Text="Fehler · "+e.Message;MessageBox.Show(this,e.Message,"Vorgang fehlgeschlagen",MessageBoxButton.OK,MessageBoxImage.Warning);return false;}
  finally{busy=false;cancellation.Dispose();cancellation=null;SliceButton.IsEnabled=true;CutPanel.IsEnabled=true;ConnectorPanel.IsEnabled=true;PrinterBox.IsEnabled=true;CancelButton.Visibility=Visibility.Collapsed;Progress.Value=0;UpdateHistory();}
 }
 async Task LoadDemo()
 {
  await Work(async (token,p)=>
  {
   var folder=GeometryService.NewFolder();await geometry.RunAsync(new{command="demo",output=folder,name="Demo-Drache (prozedural)"},folder,p,token);
   var next=ReadSettings();next.Cuts.Clear();next.Edits=[];next.Placements=[];
   if(next.Strategy=="color")next.Strategy="adaptive";
   await RenderWorkspace(new(folder,null,Json.Read<ModelRecord>(Path.Combine(folder,"model.json")),null,next),true);ApplySettings(next);projectPath=null;dirty=false;
   StatusText.Text="Prozedurales Demo-Modell · echte Geometrie · bereit zum Schneiden";
  });
 }
 async Task OpenFile(string file)
 {
  if(busy||!CanReplace())return;
  if(Path.GetExtension(file).Equals(".3dps",StringComparison.OrdinalIgnoreCase))
  {
   await Work(async (_,_)=>{var state=await Task.Run(()=>ProjectService.Open(file));await RenderWorkspace(state,true);ApplySettings(state.Settings);projectPath=file;dirty=false;StatusText.Text="Projekt geöffnet · "+Path.GetFileName(file);});
  }
  else await Work(async (token,p)=>
  {
   var folder=GeometryService.NewFolder();
   try
   {
    await geometry.RunAsync(new{command="import",input=file,output=folder},folder,p,token);
   }
   catch(ExtendedPlanarRepairException error)
   {
    var answer=MessageBox.Show(this,error.Message+"\n\nDie erweiterte Reparatur versucht, ebene Öffnungen mit einer Fläche zu schließen. Nutze sie, wenn die Öffnung im Modell unbeabsichtigt ist.\n\nErweiterte Netzreparatur versuchen?",
     "Erweiterte Netzreparatur",MessageBoxButton.YesNo,MessageBoxImage.Question,MessageBoxResult.No);
    if(answer!=MessageBoxResult.Yes)
    {
     StatusText.Text="Import abgebrochen · bisheriges Modell bleibt erhalten";
     return;
    }
    await geometry.RunAsync(new{command="import",input=file,output=folder,extendedPlanarRepair=true},folder,p,token);
   }
   var next=ReadSettings();next.Cuts.Clear();next.Edits=[];next.Placements=[];
   var model=Json.Read<ModelRecord>(Path.Combine(folder,"model.json"));
   if(next.Strategy=="color"&&model.ColorSeparation is not {Groups.Length:>0})next.Strategy="adaptive";
   await RenderWorkspace(new(folder,null,model,null,next),true);ApplySettings(next);projectPath=null;dirty=true;
   StatusText.Text=model.Repair?.Summary??("Modell geladen · "+(model.ColorSeparation is {Groups.Length:>0} colors?colors.Summary:"Millimeter")+" · "+model.Name);
  });
 }
 bool CanReplace()
 {
  if(!dirty||current==null)return true;
  var answer=MessageBox.Show(this,"Änderungen am aktuellen Projekt speichern?","Projekt wechseln",MessageBoxButton.YesNoCancel,MessageBoxImage.Question);
  return answer==MessageBoxResult.No||(answer==MessageBoxResult.Yes&&SaveProject());
 }
 async Task RenderWorkspace(Workspace? candidate=null,bool remember=false)
 {
  var state=candidate??current;
  if(state==null){OriginalView.Clear();PartsView.Clear();EmptyLabel.Visibility=Visibility.Visible;return;}
  StatusText.Text="3D-Vorschau aufbauen …";
  var token=cancellation?.Token??CancellationToken.None;
  var display=await previewService.PrepareAsync(state,geometry,exactPreview,new Progress<(int,string)>(p=>{Progress.Value=p.Item1;StatusText.Text=p.Item2;}),token);
  var mesh=await Task.Run(()=>ModelViewport.LoadMesh(display.Original.Path,token),token);
  var preparedParts=state.Result is {} pending?await Task.Run(()=>pending.Parts.ToDictionary(p=>p.Id,p=>ModelViewport.LoadMesh(display.Items["part:"+p.Id].Path,token)),token):new Dictionary<int,MeshGeometry3D>();
  var preparedConnectors=await Task.Run(()=>display.Items.Where(p=>p.Key.StartsWith("connector:",StringComparison.Ordinal))
   .ToDictionary(p=>p.Key["connector:".Length..],p=>ModelViewport.LoadMesh(p.Value.Path,token)),token);
  token.ThrowIfCancellationRequested();
  // Commit only after all background preparation succeeds; no await below.
  if(remember)Remember();current=state;displayPreviews=display;originalMesh=mesh;connectorMeshes=preparedConnectors;
  OriginalView.MeshNote=display.Original.Info.Note;PartsView.MeshNote=display.Original.Info.Note;
  OriginalView.DisplayOriginal(mesh,state.Model.Original);PartsView.DisplayOriginal(mesh,state.Model.Original);partMeshes.Clear();Thumbnails.Children.Clear();selected=0;hidden.Clear();single=false;assemblyStep=int.MaxValue;
  var i=state.Model.Original;
  LengthText.Text=$"Länge:      {i.Dimensions[0]:N2} mm";WidthText.Text=$"Breite:      {i.Dimensions[1]:N2} mm";HeightText.Text=$"Höhe:       {i.Dimensions[2]:N2} mm";
  TotalText.Text=string.Join(" × ",i.Dimensions.Select(x=>x.ToString("N1")))+" mm";
  MeshText.Text=$"{i.Triangles:N0} Dreiecke · {i.Volume/1000:N1} cm³\nGeschlossen · {i.Components} Komponente(n)";
  if(state.Model.Repair!=null)MeshText.Text+=" · repariert";
  MeshText.ToolTip=display.Original.Info.Detail+(state.Model.Orientation is {} orientation?"\n"+orientation.Label:"")
   +(state.Model.ColorSeparation?.Summary is {} colors?"\n"+colors:"")
   +(state.Model.Repair is {} repair?"\n"+repair.Summary:"");
  EmptyLabel.Visibility=Visibility.Collapsed;Title="3D Print Slicer Pro · "+state.Model.Name;
  if(state.Result is {} result)
  {
   foreach(var p in preparedParts)partMeshes.Add(p.Key,p.Value);
   BuildThumbnails();RefreshParts();
   SetResultStatus(result);
   ResultSummary.Text=$"▤  Druckteile:  {result.Parts.Length}\n♧  Verbinder:  {result.Joints.Length} ({result.Connectors.Length} separat)\n◇  {(result.Planning?.Label??"Gespeichertes Ergebnis")}";
   ResultSummary.ToolTip=$"Druckraum: {result.Settings.BedX:G} × {result.Settings.BedY:G} × {result.Settings.BedZ:G} mm\n{result.Assembly?.Summary}";
   if(!ParametersMatchResult()){ResultStatus.Text="⚠ Ergebnis nicht aktuell · neu berechnen";ResultStatus.Foreground=Brushes.Orange;}
  }
  else {ResultTitle.Text="Schnittvorschau · noch nicht berechnet";PartsHeading.Text="Teile-Vorschau (0 Teile)";ResultStatus.Text="Modell geladen · noch nicht geteilt";ResultSummary.Text=state.Model.Name+"\nDrucker und Verbinder wählen, dann schneiden.";SelectionLabel.Text="Noch keine Druckteile berechnet";}
  OriginalView.SetGrid(gridVisible);PartsView.SetGrid(gridVisible);
  StatusText.Text=exactPreview?"Vollständige Originalnetze bereit":display.Summary;
 }
 void RefreshParts()
 {
  if(current?.Result is not {} r)return;
  PartsView.MeshNote=displayPreviews?.PartsNote??"";
  PartsView.OpacityLevel=opacity;
  PartsView.DisplayParts(r.Parts.Select(p=>(p,partMeshes[p.Id])),r,selected,explode,cutsVisible,connectorsVisible,single,hidden,assemblyStep,insertionProgress,thinWallsVisible,connectorMeshes);
  PartsHeading.Text=$"Teile-Vorschau ({r.Parts.Length} Teile)";
  ResultTitle.Text=single?$"Einzelteil {selected:000}":assemblyStep!=int.MaxValue?$"Montage · Schritt {assemblyStep}/{r.Parts.Length}":explode>0?"Explosionsansicht (Druckteile)":"Automatisch geteilt (Druckteile)";
  SelectionLabel.Text=selected>0?r.Parts.First(p=>p.Id==selected).Name+" · "+r.Parts.First(p=>p.Id==selected).SizeLabel:"Maus: drehen · Rad: zoomen · rechts: verschieben";
 }
 void BuildThumbnails()
 {
  Thumbnails.Children.Clear();if(current?.Result is not {} r)return;
  foreach(var part in r.Parts)
  {
   var button=new Button{Width=87,Margin=new(0,0,5,0),Padding=new(2),ToolTip=part.Detail,Tag=part.Id};
   var stack=new StackPanel();var thumb=new Viewport3D{Width=79,Height=88,IsHitTestVisible=false};
   var mesh=partMeshes[part.Id];var b=mesh.Bounds;var center=new Point3D(b.X+b.SizeX/2,b.Y+b.SizeY/2,b.Z+b.SizeZ/2);var size=Math.Max(Math.Max(b.SizeX,b.SizeY),b.SizeZ);
   var dir=new Vector3D(-.7,.5,1);dir.Normalize();thumb.Camera=new PerspectiveCamera(center+dir*size*2.5,-dir*size*2.5,new(0,1,0),35);
   var group=new Model3DGroup();group.Children.Add(new AmbientLight(Color.FromRgb(100,115,130)));group.Children.Add(new DirectionalLight(Colors.White,new(1,-1,-1)));
   var mat=new DiffuseMaterial(new SolidColorBrush(ModelViewport.ParsePartColor(part.Color)??Color.FromRgb(155,179,201)));group.Children.Add(new GeometryModel3D(mesh,mat){BackMaterial=mat});thumb.Children.Add(new ModelVisual3D{Content=group}); 
   stack.Children.Add(thumb);stack.Children.Add(new TextBlock{Text=$"Teil {part.Id:000}"+(part.NeedsAssemblyCheck?" ⚠":""),FontSize=10,HorizontalAlignment=HorizontalAlignment.Center,Foreground=!part.Printable?Brushes.OrangeRed:part.NeedsAssemblyCheck?Brushes.Orange:Brushes.LightCyan});button.Content=stack;
   button.Click+=(_,_)=>{selected=part.Id;RefreshParts();HighlightThumbnails();};
   var menu=new ContextMenu();var hide=new MenuItem{Header="Teil ein-/ausblenden"};hide.Click+=(_,_)=>{if(!hidden.Add(part.Id))hidden.Remove(part.Id);RefreshParts();};
   var export=new MenuItem{Header="Dieses Teil exportieren (STL / OBJ / 3MF)"};export.Click+=async (_,_)=>await ExportPart(part);
   var split=new MenuItem{Header="Dieses Teil neu teilen …",IsEnabled=part.Key!=null,ToolTip=part.Key==null?"Projekt einmal neu berechnen, um lokale Schnitte zu aktivieren.":null};
   split.Click+=async (_,_)=>await EditPlanes(part);
   var merge=new MenuItem{Header="Mit weiteren Teilen zusammenfügen …",IsEnabled=part.Key!=null&&part.Neighbors.Length>0};
   merge.Click+=async (_,_)=>await MergeParts(part);
   menu.Items.Add(hide);menu.Items.Add(split);menu.Items.Add(merge);menu.Items.Add(export);button.ContextMenu=menu;Thumbnails.Children.Add(button);
  }
 }
 void HighlightThumbnails(){foreach(Button b in Thumbnails.Children)b.BorderBrush=(int)b.Tag==selected?(Brush)FindResource("Cyan"):new SolidColorBrush(Color.FromRgb(74,104,122));}
 async Task EditPlanes(PartRecord? part=null)
 {
  if(busy)return;
  if(current==null||originalMesh==null){MessageBox.Show(this,"Bitte zuerst ein 3D-Modell laden.","Freie Schnittebenen");return;}
  if(part!=null&&(!ParametersMatchResult()||part.Key==null))
  {
   MessageBox.Show(this,"Bitte die aktuelle Teilung zuerst neu berechnen.","Einzelteil neu teilen");return;
  }
  SliceSettings proposed;
  try{proposed=ReadSettings();}catch(ArgumentException ex){MessageBox.Show(this,ex.Message,"Eingabe prüfen");return;}
  var mesh=part==null?originalMesh:partMeshes[part.Id];
  var info=part==null?current.Model.Original:new MeshInfo{Bounds=part.Bounds,Dimensions=part.Dimensions,Triangles=mesh.TriangleIndices.Count/3};
  var planes=PlaneEditor.Choose(this,mesh,info,proposed.Edits,part?.Key);
  if(planes==null)return;
  proposed.Edits=planes;
  await SliceAsync(proposed);
 }
 async Task MergeParts(PartRecord anchor)
 {
  if(busy||current?.Result is not {} result||anchor.Key==null)return;
  if(!ParametersMatchResult()){MessageBox.Show(this,"Bitte die aktuelle Teilung zuerst neu berechnen.","Teile zusammenfügen");return;}
  var proposed=ReadSettings();
  if(proposed.Edits.Length>=64){MessageBox.Show(this,"Bis zu 64 manuelle Bearbeitungen sind möglich.","Teile zusammenfügen");return;}
  var window=Dialogs.Window(this,"Teile zusammenfügen",520,560);
  var content=new DockPanel{Margin=new(18)};
  var note=new TextBlock{Text=$"Teil {anchor.Id:000} ist ausgewählt. Wähle die weiteren Teile. Die fertige Geometrie muss zusammenhängen und in den Druckraum passen.",TextWrapping=TextWrapping.Wrap,Margin=new(0,0,0,12)};
  DockPanel.SetDock(note,Dock.Top);content.Children.Add(note);
  var actions=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Margin=new(0,12,0,0)};
  var apply=new Button{Content="Zusammenfügen",IsEnabled=false};
  actions.Children.Add(new Button{Content="Abbrechen",IsCancel=true,Margin=new(0,0,8,0)});actions.Children.Add(apply);
  DockPanel.SetDock(actions,Dock.Bottom);content.Children.Add(actions);
  var choices=new ListBox{SelectionMode=SelectionMode.Multiple};
  foreach(var part in result.Parts.Where(p=>p.Id!=anchor.Id&&p.Key!=null))
   choices.Items.Add(new ListBoxItem{Content=$"Teil {part.Id:000} · {part.SizeLabel}",Tag=part.Key});
  choices.SelectionChanged+=(_,_)=>apply.IsEnabled=choices.SelectedItems.Count>0;
  apply.Click+=(_,_)=>window.DialogResult=true;
  content.Children.Add(choices);window.Content=content;
  if(window.ShowDialog()!=true)return;
  var keys=choices.SelectedItems.Cast<ListBoxItem>().Select(item=>(string)item.Tag).Prepend(anchor.Key).ToArray();
  proposed.Edits=[..proposed.Edits,new ManualEdit{Merge=keys}];
  await SliceAsync(proposed);
 }
 async void ConnectorPositionsClick(object sender,RoutedEventArgs e)
 {
  if(busy)return;
  if(current?.Result is not {} result){MessageBox.Show(this,"Bitte das Modell zuerst teilen.","Verbinderpositionen");return;}
  SliceSettings proposed;
  try{proposed=ReadSettings();}catch(ArgumentException ex){MessageBox.Show(this,ex.Message,"Eingabe prüfen");return;}
  if(proposed.Mode=="none"){MessageBox.Show(this,"Bitte zuerst eine Verbinder-Variante auswählen.","Verbinderpositionen");return;}
  var positions=ConnectorPositionsEditor.Choose(this,result,proposed.Placements);
  if(positions==null)return;
  proposed.Placements=positions;
  await SliceAsync(proposed);
 }
 async Task SliceAsync(SliceSettings? proposed=null)
 {
  if(current==null){MessageBox.Show(this,"Bitte zuerst ein 3D-Modell laden.","Modell fehlt");return;}
  SliceSettings s;try{s=proposed??ReadSettings();}catch(Exception e){MessageBox.Show(this,e.Message,"Eingabe prüfen");return;}
  var state=current;
  if(s.Strategy=="color"&&state.Model.ColorSeparation is not {Groups.Length:>0})
  {
   MessageBox.Show(this,state.Model.ColorSeparation?.Issue??"Für die Farbtrennung ein 3MF mit getrennten, farblich zugewiesenen Volumenkörpern laden.","Nach Farbe trennen");return;
  }
  await Work(async (token,p)=>
  {
   var folder=GeometryService.NewFolder();await geometry.RunAsync(new{command="slice",input=Path.Combine(state.ModelFolder,"original.stl"),output=folder,settings=s},folder,p,token);
   var result=Json.Read<SliceResult>(Path.Combine(folder,"result.json"));await RenderWorkspace(state with{ResultFolder=folder,Result=result,Settings=s.Clone()},true);ApplySettings(s);dirty=true;
   SavePreferences();StatusText.Text=$"{result.Parts.Length} Teile · {result.Joints.Length} Verbinder · {result.Warnings.Length} Prüfhinweise";
  });
 }
 async Task ComparePlans()
 {
  if(busy)return;
  if(current==null){MessageBox.Show(this,"Bitte zuerst ein 3D-Modell laden.","Alternative Schnittpläne");return;}
  SliceSettings input;
  try{input=ReadSettings();}catch(ArgumentException ex){MessageBox.Show(this,ex.Message,"Eingabe prüfen");return;}
  var source=current;
  (string id,string label)[] methods=[("adaptive","Adaptiv"),("equal","Gleichmäßige Teilgrößen"),("few","Maximale Rasterschritte"),("custom","Benutzerdefiniertes Teilmaß")];
  var candidates=new List<(string Label,Workspace State)>();
  var failures=new List<string>();
  bool finished=await Work(async(token,progress)=>
  {
   for(int i=0;i<methods.Length;i++)
   {
    token.ThrowIfCancellationRequested();
    var (id,label)=methods[i];int index=i;
    var proposed=input.Clone();proposed.Strategy=id;
    var folder=GeometryService.NewFolder();
    var stage=new Progress<(int value,string message)>(status=>
     progress.Report(((100*index+status.value)/methods.Length,$"{label} ({index+1}/{methods.Length}) · {status.message}")));
    try
    {
     await geometry.RunAsync(new{command="slice",input=Path.Combine(source.ModelFolder,"original.stl"),output=folder,settings=proposed},folder,stage,token);
     var result=Json.Read<SliceResult>(Path.Combine(folder,"result.json"));
     candidates.Add((label,source with{ResultFolder=folder,Result=result,Settings=proposed}));
    }
    catch(InvalidOperationException ex){failures.Add($"{label} — {ex.Message}");}
   }
  });
  if(!finished)return;
  var ranked=candidates.OrderByDescending(c=>c.State.Result!.Valid)
   .ThenByDescending(c=>c.State.Result!.Assembly?.Connected)
   .ThenByDescending(c=>c.State.Result!.Motion?.PathVerified)
   .ThenBy(c=>c.State.Result!.Assembly?.UnconnectedInterfaces)
   .ThenBy(c=>c.State.Result!.Parts.Length)
   .ToArray();
  var dialog=Dialogs.Window(this,"Berechnete Schnittpläne",730,560);
  var content=new DockPanel{Margin=new(18)};
  var header=new TextBlock{Text="Sortiert nach Druckraum und Netz, Verbindungsgraph, Montageprüfung und Teilezahl. Wähle einen berechneten Plan zum Übernehmen.",TextWrapping=TextWrapping.Wrap,Margin=new(0,0,0,10)};
  DockPanel.SetDock(header,Dock.Top);content.Children.Add(header);
  var footer=new StackPanel();
  foreach(string failure in failures)footer.Children.Add(new TextBlock{Text=failure,TextWrapping=TextWrapping.Wrap,Foreground=Brushes.LightSalmon,Margin=new(0,4,0,0)});
  var row=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Margin=new(0,10,0,0)};
  var apply=new Button{Content="Plan übernehmen",IsEnabled=ranked.Length>0};
  row.Children.Add(new Button{Content="Schließen",IsCancel=true,Margin=new(0,0,8,0)});row.Children.Add(apply);footer.Children.Add(row);
  DockPanel.SetDock(footer,Dock.Bottom);content.Children.Add(footer);
  var choices=new ListBox();
  foreach(var candidate in ranked)
  {
   var result=candidate.State.Result!;
   var block=new TextBlock{TextWrapping=TextWrapping.Wrap,Margin=new(6),Text=$"{candidate.Label} · {result.Parts.Length} Teile · {result.Joints.Length} Verbinder\n"+
    $"{(result.Valid?"Netze und Druckraum geprüft":"Mindestens ein fehlerhaftes Teil")} · {result.Assembly?.Summary}\n{result.Motion?.Summary}"};
   choices.Items.Add(new ListBoxItem{Content=block});
  }
  choices.SelectedIndex=ranked.Length>0?0:-1;
  apply.Click+=(_,_)=>dialog.DialogResult=true;
  content.Children.Add(choices);dialog.Content=content;
  StatusText.Text=$"{ranked.Length} Schnittpläne berechnet";
  if(dialog.ShowDialog()!=true||choices.SelectedIndex<0)return;
  var chosen=ranked[choices.SelectedIndex];
  await Work(async(_,_)=>{await RenderWorkspace(chosen.State,true);ApplySettings(chosen.State.Settings);dirty=true;StatusText.Text=$"Schnittplan übernommen · {chosen.Label}";});
 }
 bool SaveProject()
 {
  if(busy||current==null)return false;
  var dialog=new SaveFileDialog{Filter="Slicer-Projekt (*.3dps)|*.3dps",FileName=projectPath??SafeName(current.Model.Name)+".3dps"};
  if(dialog.ShowDialog(this)!=true)return false;
  try{settings=ReadSettings();current=current with{Settings=settings.Clone()};ProjectService.Save(current,dialog.FileName);projectPath=dialog.FileName;dirty=false;SavePreferences();StatusText.Text="Projekt gespeichert · Original, Teile und Parameter enthalten";return true;}catch(Exception e){App.Log(e);MessageBox.Show(this,e.Message,"Speichern fehlgeschlagen");return false;}
 }
 static string SafeName(string name)=>string.Concat(name.Select(c=>Path.GetInvalidFileNameChars().Contains(c)?'_':c));
 async Task ExportAll()
 {
  if(busy)return;if(current?.Result is not {} r){MessageBox.Show(this,"Bitte zuerst das Modell schneiden.","Noch keine Druckteile");return;}
  if(!r.Valid){MessageBox.Show(this,"Mindestens ein Teil ist fehlerhaft. Der Export ist gesperrt. Bitte Prüfbericht öffnen.","Geometriefehler");return;}
  if(!ParametersMatchResult()){MessageBox.Show(this,"Die Eingaben wurden seit der Berechnung geändert. Bitte vor dem Export erneut schneiden.","Ergebnis nicht aktuell");return;}
  var format=Dialogs.ExportFormat(this,GeometryExport.PreferredFormat(Path.Combine(current.ModelFolder,"original.stl")));if(format==null)return;
  var dialog=new OpenFolderDialog{Title=$"Ordner für den vollständigen {format.ToUpperInvariant()}-Export wählen"};if(dialog.ShowDialog(this)!=true)return;
  var state=current;var destination=Path.Combine(dialog.FolderName,SafeName(state.Model.Name)+"_"+DateTime.Now.ToString("yyyyMMdd_HHmmss_fff"));
  await Work(async (token,p)=>
  {
   var incomplete=destination+".unvollstaendig";
   foreach(var sub in new[]{"Original","Druckteile","Verbinder","Montageanleitung","Projektdatei"})Directory.CreateDirectory(Path.Combine(incomplete,sub));
   var items=r.Parts.Select(part=>new GeometryExportItem(Path.Combine(state.ResultFolder!,part.File),Path.Combine(incomplete,"Druckteile",GeometryExport.FileName(part.File,format)),part.PrintOrder,format,part.Color)).Concat(r.Connectors.Select(c=>new GeometryExportItem(Path.Combine(state.ResultFolder!,c.File),Path.Combine(incomplete,"Verbinder",GeometryExport.FileName(c.File,format)),c.PrintOrder,format))).ToArray();
   await geometry.RunAsync(new{command="export",output=GeometryService.NewFolder(),items},GeometryService.NewFolder(),p,token);
   token.ThrowIfCancellationRequested();File.Copy(Path.Combine(state.ModelFolder,"original.stl"),Path.Combine(incomplete,"Original","Original.stl"));
   AssemblyService.WritePdf(state,Path.Combine(incomplete,"Montageanleitung","Montageplan.pdf"));
   Json.Write(Path.Combine(incomplete,"Montageanleitung","Zuordnung.json"),r);
   Json.Write(Path.Combine(incomplete,"Exportdateien.json"),new{format,unit="millimeter",files=items.Select(item=>new{source=Path.GetFileName(item.Input),color=item.Color,file=Path.GetRelativePath(incomplete,item.Output).Replace('\\','/'),printOrder=item.Order,origin=new[]{0,0,0}})});
   File.WriteAllText(Path.Combine(incomplete,"Montageanleitung","Pruefhinweise.txt"),string.Join(Environment.NewLine,r.Warnings));
   ProjectService.Save(state,Path.Combine(incomplete,"Projektdatei",SafeName(state.Model.Name)+".3dps"));
   Directory.Move(incomplete,destination);StatusText.Text=format.ToUpperInvariant()+"-Export abgeschlossen · "+destination;
   MessageBox.Show(this,$"{r.Parts.Length} Druckteile und {r.Connectors.Length} separate Verbinder als {format.ToUpperInvariant()} exportiert.\n\n{destination}\n\nMontageplan und Prüfhinweise sind enthalten.","Export abgeschlossen");
  });
 }
 async Task ExportPart(PartRecord part)
 {
  if(busy||current?.ResultFolder==null)return;if(!part.Printable){MessageBox.Show(this,"Dieses Teil enthält Geometriefehler.");return;}
  if(!ParametersMatchResult()){MessageBox.Show(this,"Bitte die geänderten Parameter vor dem Export neu berechnen.","Ergebnis nicht aktuell");return;}
  var source=Path.Combine(current.ResultFolder,part.File);
  var preferred=GeometryExport.PreferredFormat(source);
  var dialog=new SaveFileDialog{Filter=GeometryExport.Filter,FilterIndex=Array.FindIndex(GeometryExport.Formats,f=>f.Id==preferred)+1,FileName=Path.GetFileNameWithoutExtension(part.File),AddExtension=true};
  dialog.FileOk+=(_,e)=>{try{GeometryExport.FormatFromPath(dialog.FileName);}catch(ArgumentException ex){e.Cancel=true;MessageBox.Show(this,ex.Message,"Exportformat wählen");}};
  if(dialog.ShowDialog(this)!=true)return;var format=GeometryExport.FormatFromPath(dialog.FileName);
  await Work(async(token,p)=>{var temp=dialog.FileName+".tmp-"+Guid.NewGuid().ToString("N");try{await geometry.RunAsync(new{command="export",output=GeometryService.NewFolder(),items=new[]{new GeometryExportItem(source,temp,part.PrintOrder,format,part.Color)}},GeometryService.NewFolder(),p,token);token.ThrowIfCancellationRequested();File.Move(temp,dialog.FileName,true);StatusText.Text=part.Name+" als "+format.ToUpperInvariant()+" exportiert · mm · Druckausrichtung";}finally{if(File.Exists(temp))File.Delete(temp);}});
 }
 void SavePdf()
 {
  if(current?.Result==null)return;var dialog=new SaveFileDialog{Filter="PDF (*.pdf)|*.pdf",FileName="Montageplan.pdf"};if(dialog.ShowDialog(this)==true){try{AssemblyService.WritePdf(current,dialog.FileName);StatusText.Text="Montageplan gespeichert";}catch(Exception e){App.Log(e);MessageBox.Show(this,e.Message);}}
 }
 string ReportText()
 {
  if(current?.Result is not {} r)return "Noch keine Druckteile berechnet.\n\nImport → Drucker wählen → Verbinder wählen → Automatisch schneiden → Exportieren.\n\nAdaptive Planung untersucht lokale achsenparallele Schnitte anhand echter Querschnitte. Passende Bereiche bleiben ganz. Gleichmäßiges Raster und manuelle Ebenen bleiben verfügbar.\n\nRunddübel, rechteckige Zapfen, Nut/Feder, Schwalbenschwanz, Steckclips und Außenschrauben sind verfügbar. Steckclips und Außenschrauben erfordern eine Passprobe.";
  var b=new StringBuilder($"{current.Model.Name}\n\nGEOMETRIE\n{r.Parts.Length} Teile · {r.Joints.Length} Verbindungen · {r.Connectors.Length} separate Verbinder\nGeschlossene Netze und Druckraum: {(r.Valid?"bestanden":"FEHLER")}\nMaterial: {r.Settings.Material} · Spiel / Gesamtzugabe: {r.Settings.Tolerance:N2} mm\nWandreserve an Verbindern: {r.Settings.Wall:N1} mm\n\nPRÜFHINWEISE\n");
  if(current.Model.Orientation is {} orientation)b.AppendLine(orientation.Label);
  if(current.Model.Repair is {} repair)b.AppendLine(repair.Summary);
  foreach(var warning in r.Warnings)b.AppendLine("• "+warning);
  b.AppendLine($"\nSCHNITTPLAN\n{r.Planning?.Label??"Älteres Projekt"} · {r.Planning?.EvaluatedPlanes??0} untersuchte Querschnitte\n{r.Assembly?.Summary??"Verbindungsgraph nicht ausgewertet"}\n{r.Assembly?.UnconnectedInterfaces??0} Schnittstellen ohne Verbinder");
  if(r.Planning is {ConnectorProbeChecks:>0} planning)
   b.AppendLine($"Schnittplanung · {planning.ConnectorProbeChecks} Verbinderproben · {planning.ConnectorProbeCuts} gewählte Schnitte mit Platz für eine Probe");
  b.AppendLine("\nENTWICKLUNGSSTAND\nDie Montageprüfung untersucht geradlinige Wege von Teilen mit vorbestückten separaten Verbindern. Bei Außenschrauben prüft sie Stichproben des Gewindeeingriffs in der Endlage der übrigen Körper. Verformung, Reibung und Festigkeit erfordern eine Passprobe.\n\nTEILE");
  foreach(var part in r.Parts)
  {
   b.AppendLine(part.Name+": "+part.SizeLabel+" · "+part.Connectors.Length+" Verbinder"+(part.Printable?"":" · "+string.Join(", ",part.Errors)));
   if(part.PrintChecks is {} check)
   {
    b.AppendLine("  "+check.Summary);
    foreach(var hit in check.SamplePoints)b.AppendLine($"  {hit.Thickness:N3} mm · XYZ ({string.Join(" / ",hit.Point.Select(v=>v.ToString("N2")))}) mm");
   }
  }
  foreach(var connector in r.Connectors.Where(c=>c.PrintChecks!=null))b.AppendLine($"{connector.Id}: {connector.PrintChecks!.Summary}");
  b.AppendLine("\nMONTAGEZUORDNUNG");
  foreach(var j in r.Joints)
  {
   b.AppendLine($"{j.Id}: Teil {j.A:000} ↔ Teil {j.B:000} · {(j.Mode=="separate"?"separat":"integriert an Teil "+j.A.ToString("000"))} · {j.KindLabel} · {j.SizeLabel} · {j.TravelLabel}{(j.ManualPosition?" · manuell platziert":"")}{(j.AutoSized?" · automatisch verkleinert":"")}");
   if(j.Kind=="screw")b.AppendLine("  "+(j.ScrewInsertion?.Summary??"Gewindeeingriff: ungeprüft"));
  }
  if(r.Motion is {} motion)
  {
   b.AppendLine("\nMONTAGEWEGE\n"+motion.Summary);
   if(motion.BudgetReached)b.AppendLine("Rechenbudget erreicht; verbleibende Wege sind ungeprüft.");
   if(motion.UnresolvedPins.Length>0)b.AppendLine("Vorbestückung separater Verbinder nicht nachgewiesen: "+string.Join(", ",motion.UnresolvedPins));
   foreach(var limitation in motion.Limitations)b.AppendLine("• "+limitation);
   if(motion.PathVerified)
   {
    b.AppendLine("\nSeparate Verbinder vorbestücken (jeweils am einzelnen Hostteil):");
    foreach(var pin in motion.PreinsertSteps)b.AppendLine($"{pin.Connector} in Teil {pin.Host:000}: {MotionRecord.DirectionLabel(pin.InsertionDirection)}, Weg {pin.Distance:N1} mm");
    b.AppendLine("\nNachgewiesene Teilfolge:");
    foreach(var step in motion.AssemblySteps)b.AppendLine(step.Base?$"Teil {step.Part:000} als Basis":$"Teil {step.Part:000}: Einstecken {MotionRecord.DirectionLabel(step.InsertionDirection)}, Weg {step.Distance:N1} mm");
   }
   else foreach(var fail in motion.LastFailures.Take(40))b.AppendLine($"Teil {fail.Part:000}, {MotionRecord.DirectionLabel(fail.Direction)}: {fail.Description}{(fail.Obstacle.Length>0?" ("+fail.Obstacle+")":"")}");
  }
  b.AppendLine("\nSCHNITTSTELLEN");foreach(var f in r.Interfaces)b.AppendLine($"{f.Id}: Teil {f.A:000} ↔ {f.B:000} · {f.Area:N1} mm² · {f.Placed}/{f.Requested} Verbinder");
  return b.ToString();
 }
 async void LoadClick(object sender,RoutedEventArgs e){if(busy)return;var d=new OpenFileDialog{Filter="3D-Modelle|*.stl;*.obj;*.3mf|Alle Dateien|*.*"};if(d.ShowDialog(this)==true)await OpenFile(d.FileName);}
 async void OpenProjectClick(object sender,RoutedEventArgs e){if(busy)return;var d=new OpenFileDialog{Filter="Slicer-Projekt (*.3dps)|*.3dps"};if(d.ShowDialog(this)==true)await OpenFile(d.FileName);}
 void SaveClick(object sender,RoutedEventArgs e)=>SaveProject();
 async void SliceClick(object sender,RoutedEventArgs e)=>await SliceAsync();
 async void ExportClick(object sender,RoutedEventArgs e){SetNav(ExportNav);await ExportAll();}
 void CancelClick(object sender,RoutedEventArgs e)=>cancellation?.Cancel();
 void NewClick(object sender,RoutedEventArgs e)
 {
  if(busy||!CanReplace())return;Remember();current=null;settings.Cuts.Clear();settings.Edits=[];settings.Placements=[];originalMesh=null;displayPreviews=null;projectPath=null;dirty=false;OriginalView.Clear();PartsView.Clear();Thumbnails.Children.Clear();partMeshes.Clear();connectorMeshes.Clear();EmptyLabel.Visibility=Visibility.Visible;
  LengthText.Text="Länge:      —";WidthText.Text="Breite:      —";HeightText.Text="Höhe:       —";TotalText.Text="Kein Modell geladen";MeshText.Text="STL, OBJ und 3MF · offline";ResultStatus.Text="Bereit zum Laden";ResultSummary.Text="";PartsHeading.Text="Teile-Vorschau (0 Teile)";SelectionLabel.Text="Noch keine Druckteile berechnet";Title="3D Print Slicer Pro";StatusText.Text="Neues Projekt";
 }
 void ProjectClick(object sender,RoutedEventArgs e){SetNav(ProjectNav);Dialogs.Report(this,"Projekt", $"3D Print Slicer Pro · Vorschauversion {typeof(MainWindow).Assembly.GetName().Version!.ToString(3)}\n\nModelle intelligent teilen · vollständig lokal\n\nAlle Berechnungen erfolgen auf echter 3D-Geometrie. Das prozedurale Demo-Modell ist ein eigens erzeugter Drache und entspricht nicht dem Drachen aus dem Referenzbild.\n\nBedienung: linke Maustaste drehen, Mausrad zoomen, rechte Maustaste verschieben. Beide Ansichten drehen synchron.\n\nSTL und OBJ haben keine verbindliche Maßeinheit: Zahlen werden als Millimeter gelesen. 3MF-Einheiten werden umgerechnet.\n\nErweiterte Funktionen und Prüfgrenzen stehen im Prüfbericht und in docs/ENTWICKLUNGSSTAND.md.",("Demo-Drache laden",async()=>{if(!busy&&CanReplace())await LoadDemo();}));}
 void SetNav(Button active)
 {
  foreach(var b in new[]{ProjectNav,CutNav,ConnectorNav,PreviewNav,ExportNav,SettingsNav})
  {b.BorderThickness=b==active?new(1):new(0);b.BorderBrush=(Brush)FindResource("Cyan");b.Background=b==active?new SolidColorBrush(Color.FromRgb(7,65,88)):Brushes.Transparent;}
 }
 void CutNavClick(object sender,RoutedEventArgs e){SetNav(CutNav);StrategyBox.Focus();}
 void ConnectorNavClick(object sender,RoutedEventArgs e){SetNav(ConnectorNav);KindBox.Focus();}
 void PreviewNavClick(object sender,RoutedEventArgs e){SetNav(PreviewNav);ViewOptionsClick(sender,e);}
 void ReportClick(object sender,RoutedEventArgs e)=>Dialogs.Report(this,"Prüfbericht und Montagezuordnung",ReportText(),("Montage-PDF speichern",SavePdf));
 void ResetViewClick(object sender,RoutedEventArgs e){OriginalView.Reset();PartsView.Reset();}
 void GridClick(object sender,RoutedEventArgs e){gridVisible=!gridVisible;OriginalView.SetGrid(gridVisible);PartsView.SetGrid(gridVisible);}
 void ExplodeClick(object sender,RoutedEventArgs e){explode=explode>0?0:.35;RefreshParts();}
 void FocusPartClick(object sender,RoutedEventArgs e){if(current?.Result==null)return;if(selected==0)selected=current.Result.Parts[0].Id;single=!single;assemblyStep=int.MaxValue;insertionProgress=1;RefreshParts();HighlightThumbnails();}
 void ViewModeChanged(object sender,SelectionChangedEventArgs e)
 {
  if(!ready||current?.Result==null)return;single=false;explode=0;assemblyStep=int.MaxValue;
  if(ViewMode.SelectedIndex==2)explode=.35;
  if(ViewMode.SelectedIndex==3){assemblyStep=1;explode=0;}
  if(ViewMode.SelectedIndex==4){single=true;if(selected==0)selected=current.Result.Parts[0].Id;}
  if(ViewMode.SelectedIndex==5&&originalMesh!=null){PartsView.MeshNote=OriginalView.MeshNote;PartsView.DisplayOriginal(originalMesh,current.Model.Original);ResultTitle.Text="Originalmodell";return;}
  RefreshParts();
 }
 void ViewOptionsClick(object sender,RoutedEventArgs e)
 {
  if(busy)return;
  var window=Dialogs.Window(this,"3D-Vorschau",490,650);var stack=new StackPanel{Margin=new(22)};
  stack.Children.Add(new TextBlock{Text="Darstellung und schrittweise Montage",FontSize=18,Margin=new(0,0,0,15)});
  var exact=new CheckBox{Content="Vollständige Originalnetze anzeigen",IsChecked=exactPreview,ToolTip="Kann bei großen Modellen mehr Arbeitsspeicher und Zeit benötigen. Schnittberechnung und Export verwenden immer vollständige Geometrie."};
  exact.Click+=async(_,_)=>{var value=exact.IsChecked==true;var previous=exactPreview;window.Close();if(!await Work(async(_,_)=>{exactPreview=value;await RenderWorkspace();}))exactPreview=previous;};stack.Children.Add(exact);
  stack.Children.Add(new TextBlock{Text=displayPreviews?.Summary??"Noch kein Modell geladen.",TextWrapping=TextWrapping.Wrap,FontSize=11,Foreground=Brushes.LightSteelBlue,Margin=new(0,0,0,10)});
  var thin=new CheckBox{Content="Dünnwand-Stichproben anzeigen (mm)",IsChecked=thinWallsVisible};
  thin.Click+=(_,_)=>{thinWallsVisible=thin.IsChecked==true;RefreshParts();};stack.Children.Add(thin);
  var cut=new CheckBox{Content="Schnittflächen und cyanblaue Konturen",IsChecked=cutsVisible};cut.Click+=(_,_)=>{cutsVisible=cut.IsChecked==true;RefreshParts();};stack.Children.Add(cut);
  var con=new CheckBox{Content="Tatsächliche Verbinderpositionen anzeigen",IsChecked=connectorsVisible};con.Click+=(_,_)=>{connectorsVisible=con.IsChecked==true;RefreshParts();};stack.Children.Add(con);
  stack.Children.Add(new TextBlock{Text="Deckkraft",Margin=new(0,12,0,5)});var transparency=new Slider{Minimum=.15,Maximum=1,Value=opacity};transparency.ValueChanged+=(_,_)=>{opacity=transparency.Value;RefreshParts();};stack.Children.Add(transparency);
  stack.Children.Add(new TextBlock{Text="Explosionsabstand",Margin=new(0,12,0,5)});var explosion=new Slider{Minimum=0,Maximum=1,Value=explode};explosion.ValueChanged+=(_,_)=>{explode=explosion.Value;RefreshParts();};stack.Children.Add(explosion);
  stack.Children.Add(new TextBlock{Text=current?.Result?.Motion?.PathVerified==true?"Montageschritt (geradlinig nachgewiesen)":"Teilfolge (kein vollständiger Montageweg nachgewiesen)",TextWrapping=TextWrapping.Wrap,Margin=new(0,12,0,5)});var step=new Slider{Minimum=1,Maximum=Math.Max(1,current?.Result?.Parts.Length??1),TickFrequency=1,IsSnapToTickEnabled=true,Value=assemblyStep==int.MaxValue?(current?.Result?.Parts.Length??1):assemblyStep};step.ValueChanged+=(_,_)=>{assemblyStep=(int)step.Value;explode=0;RefreshParts();};stack.Children.Add(step);
  stack.Children.Add(new TextBlock{Text="Einsteckposition: außen → montiert",Margin=new(0,12,0,5)});var insertion=new Slider{Minimum=0,Maximum=1,Value=insertionProgress,IsEnabled=current?.Result?.Motion?.PathVerified==true};insertion.ValueChanged+=(_,_)=>{insertionProgress=insertion.Value;assemblyStep=(int)step.Value;explode=0;RefreshParts();};stack.Children.Add(insertion);
  var all=new Button{Content="Alle Teile wieder einblenden",Margin=new(0,15,0,0)};all.Click+=(_,_)=>{hidden.Clear();assemblyStep=int.MaxValue;single=false;RefreshParts();};stack.Children.Add(all);window.Content=new ScrollViewer{Content=stack,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};window.ShowDialog();
 }
 void RoundClick(object sender,RoutedEventArgs e)=>KindBox.SelectedIndex=0;
 void RectClick(object sender,RoutedEventArgs e)=>KindBox.SelectedIndex=1;
 void TongueClick(object sender,RoutedEventArgs e)=>KindBox.SelectedIndex=2;
 void DovetailClick(object sender,RoutedEventArgs e)=>KindBox.SelectedIndex=3;
 void ClipClick(object sender,RoutedEventArgs e)=>KindBox.SelectedIndex=4;
 void ScrewClick(object sender,RoutedEventArgs e)=>KindBox.SelectedIndex=5;
 void KindChanged(object sender,SelectionChangedEventArgs e)
 {
  if(ScrewChoice==null||ThreadFields==null||ClipFields==null||ModeBox==null||DepthLabel==null)return;
  int index=KindBox.SelectedIndex;
  Button[] choices=[RoundChoice,RectChoice,TongueChoice,DovetailChoice,ClipChoice,ScrewChoice];
  for(int i=0;i<choices.Length;i++)choices[i].Style=(Style)FindResource(i==index?"GlowButton":typeof(Button));
  RailLengthLabel.Text=index==3?"Länge in Einschubrichtung:":"Federlänge in der Fläche:";
  TongueFields.Visibility=index is 2 or 3?Visibility.Visible:Visibility.Collapsed;
  RectFields.Visibility=index==1?Visibility.Visible:Visibility.Collapsed;
  ClipFields.Visibility=index==4?Visibility.Visible:Visibility.Collapsed;
  ThreadFields.Visibility=index==5?Visibility.Visible:Visibility.Collapsed;
  DepthLabel.Visibility=DepthBox.Visibility=index==5?Visibility.Collapsed:Visibility.Visible;
  WidthLabel.Text=index switch{1=>"Zapfenbreite:",2=>"Federbreite:",3=>"Breite am Nutmund:",4=>"Clipbreite:",5=>"Gewindedurchmesser:",_=>"Durchmesser:"};
  IntegratedMode.IsEnabled=MixedMode.IsEnabled=index!=5;
  if(index==5&&ModeBox.SelectedIndex is 0 or 2)ModeBox.SelectedIndex=1;
 }
 void PrinterChanged(object sender,SelectionChangedEventArgs e){if(loadingSettings||PrinterBox.SelectedItem is not PrinterProfile p)return;BedX.Text=p.X.ToString("G");BedY.Text=p.Y.ToString("G");BedZ.Text=p.Z.ToString("G");}
 void SavePrinterClick(object sender,RoutedEventArgs e)
 {
  if(busy)return;try{var s=ReadSettings();if(Math.Min(s.BedX,Math.Min(s.BedY,s.BedZ))<=0)throw new ArgumentException("Druckmaße müssen positiv sein.");var name=Dialogs.Input(this,"Druckerprofil speichern","Name des Druckers:","Mein Drucker");if(string.IsNullOrWhiteSpace(name))return;profiles.Add(new(){Name=name.Trim(),X=s.BedX,Y=s.BedY,Z=s.BedZ});PrinterBox.Items.Refresh();PrinterBox.SelectedIndex=profiles.Count-1;settings=s;SavePreferences();}catch(Exception ex){MessageBox.Show(this,ex.Message);}
 }
 void SettingsClick(object sender,RoutedEventArgs e)
 {
  if(busy)return;SetNav(SettingsNav);var window=Dialogs.Window(this,"Material und Einstellungen",540,590);var stack=new StackPanel{Margin=new(22)};
  stack.Children.Add(new TextBlock{Text="Materialprofil",Margin=new(0,0,0,6)});var material=new ComboBox{ItemsSource=new[]{"PLA","PETG","ABS","ASA","TPU","Resin"},SelectedItem=settings.Material};stack.Children.Add(material);
  stack.Children.Add(new TextBlock{Text="Wandreserve um Verbinder in mm",Margin=new(0,14,0,6)});var wall=new TextBox{Text=settings.Wall.ToString("G")};stack.Children.Add(wall);
  stack.Children.Add(new TextBlock{Text="Mindestdurchmesser / Mindestbreite bei Größenautomatik (mm)",Margin=new(0,12,0,6)});var minDiameter=new TextBox{Text=settings.MinDiameter.ToString("G")};stack.Children.Add(minDiameter);
  stack.Children.Add(new TextBlock{Text="Mindesteinstecktiefe je Seite bei Größenautomatik (mm)",Margin=new(0,12,0,6)});var minDepth=new TextBox{Text=settings.MinDepth.ToString("G")};stack.Children.Add(minDepth);
  stack.Children.Add(new TextBlock{Text="Dünnwand-Stichprobe unter (mm, 0 = aus)",Margin=new(0,12,0,6)});var thinWall=new TextBox{Text=settings.ThinWallThreshold.ToString("G")};stack.Children.Add(thinWall);
  var detailedWall=new CheckBox{Content="Ausführliche Dünnwandprüfung",IsChecked=settings.DetailedWallCheck,Margin=new(0,8,0,0),
   ToolTip="Misst an den Dreiecksmittelpunkten, bis zu 200.000 Stichproben pro Berechnung. Bei großen Modellen dauert das länger."};
  stack.Children.Add(detailedWall);
  stack.Children.Add(new TextBlock{Text="Materialabhängige Startwerte für das Durchmesserspiel sind nur Vorschläge. Eine Passprobe ist erforderlich. Flexible oder spröde Materialien benötigen eine eigene Belastungsprüfung.",TextWrapping=TextWrapping.Wrap,Foreground=Brushes.LightSteelBlue,Margin=new(0,15,0,15)});
  var suggest=new Button{Content="Toleranzvorschlag für Material übernehmen"};suggest.Click+=(_,_)=>ToleranceBox.Text=(material.SelectedItem?.ToString() switch{"PETG"=>.3,"ABS"=>.3,"ASA"=>.3,"TPU"=>.4,"Resin"=>.15,_=>.2}).ToString("G");stack.Children.Add(suggest);
  var save=new Button{Content="Einstellungen speichern",Margin=new(0,14,0,0),IsDefault=true};
  save.Click+=(_,_)=>{
   try
   {
    var w=Number(wall,"Wandreserve");var d=Number(minDiameter,"Mindestdurchmesser");var depth=Number(minDepth,"Mindesteinstecktiefe");
    if(Math.Min(w,Math.Min(d,depth))<=0)throw new ArgumentException("Wandreserve und Mindestmaße müssen positiv sein.");
    var values=ReadSettings();
    values.ThinWallThreshold=Number(thinWall,"Dünnwandschwelle");
    values.DetailedWallCheck=detailedWall.IsChecked==true;
    if(values.ThinWallThreshold is <0 or >50)throw new ArgumentException("Dünnwandschwelle muss zwischen 0 und 50 mm liegen.");
    if(values.AutoSize&&(d>values.Diameter||depth>values.Depth))throw new ArgumentException("Mindestmaße dürfen die gewählten Obergrenzen nicht überschreiten.");
    settings=values;settings.Material=material.SelectedItem?.ToString()??"PLA";settings.Wall=w;settings.MinDiameter=d;settings.MinDepth=depth;
    SavePreferences();ParametersChanged(this,new RoutedEventArgs());window.Close();
   }
   catch(Exception ex){MessageBox.Show(window,ex.Message);}
  };
  stack.Children.Add(save);window.Content=new ScrollViewer{Content=stack,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};window.ShowDialog();
 }
 void AdvancedClick(object sender,RoutedEventArgs e)
 {
  if(busy)return;var window=Dialogs.Window(this,"Manuelle Schnitte und Skalierung",590,610);var stack=new StackPanel{Margin=new(22)};
  var free=new Button{Content="Freie Schnittebenen bearbeiten …",Margin=new(0,0,0,12)};
  free.Click+=async(_,_)=>{window.Close();await EditPlanes();};stack.Children.Add(free);
  var compare=new Button{Content="Alternative Schnittpläne berechnen …",Margin=new(0,0,0,12)};
  compare.Click+=async(_,_)=>{window.Close();await ComparePlans();};stack.Children.Add(compare);
  stack.Children.Add(new TextBlock{Text="Schnittpositionen ab Modellursprung in mm, durch Semikolon trennen. Leer = automatisch. Adaptiv: Vorgaben zuerst schneiden, danach zu große Körper weiterteilen. Raster: jede vorgegebene Teilgröße muss bereits passen.",TextWrapping=TextWrapping.Wrap,Margin=new(0,0,0,12)});
  var fields=new Dictionary<string,TextBox>();
  foreach(var axis in new[]{"x","y","z"}){stack.Children.Add(new TextBlock{Text="Achse "+axis.ToUpperInvariant(),Margin=new(0,6,0,4)});var box=new TextBox{Text=settings.Cuts.TryGetValue(axis,out var values)?string.Join("; ",values.Select(v=>v.ToString("G"))):""};fields[axis]=box;stack.Children.Add(box);}
  var apply=new Button{Content="Schnitte übernehmen",Margin=new(0,16,0,10)};
  apply.Click+=(_,_)=>{try{var cuts=new Dictionary<string,double[]>();foreach(var (axis,box) in fields)if(!string.IsNullOrWhiteSpace(box.Text))cuts[axis]=box.Text.Split(';',StringSplitOptions.TrimEntries|StringSplitOptions.RemoveEmptyEntries).Select(s=>double.Parse(s.Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture)).ToArray();if(cuts.Values.SelectMany(v=>v).Any(v=>!double.IsFinite(v)))throw new ArgumentException();settings.Cuts=cuts;ParametersChanged(this,new RoutedEventArgs());window.Close();StatusText.Text="Manuelle Schnittparameter übernommen · zum Anwenden neu schneiden";}catch{MessageBox.Show(window,"Bitte gültige Zahlen eingeben, z. B. 150; 300.");}};stack.Children.Add(apply);
  var scale=new Button{Content="Gesamtes Modell proportional skalieren …"};scale.Click+=async(_,_)=>
  {
   if(current==null)return;var input=Dialogs.Input(window,"Modell skalieren","Faktor (z. B. 0,5 für halbe Größe):","1");if(input==null)return;
   if(!double.TryParse(input.Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture,out double factor)||factor<=0||!double.IsFinite(factor)){MessageBox.Show(window,"Positiven Skalierungsfaktor eingeben.");return;}
   window.Close();var state=current;
   await Work(async(token,p)=>{var folder=GeometryService.NewFolder();await geometry.RunAsync(new{command="scale",input=Path.Combine(state.ModelFolder,"original.stl"),output=folder,scale=factor,name=state.Model.Name},folder,p,token);var next=ReadSettings();next.Cuts.Clear();next.Edits=[];next.Placements=[];await RenderWorkspace(new(folder,null,Json.Read<ModelRecord>(Path.Combine(folder,"model.json")),null,next),true);ApplySettings(next);dirty=true;StatusText.Text="Modell skaliert · Ergebnis muss neu berechnet werden";});
  };stack.Children.Add(scale);window.Content=stack;window.ShowDialog();
 }
 async void OrientClick(object sender,RoutedEventArgs e)
 {
  if(busy)return;if(current==null||originalMesh==null){MessageBox.Show(this,"Bitte zuerst ein Modell laden.","Modell ausrichten");return;}
  var angles=Dialogs.ChooseOrientation(this,originalMesh);if(angles==null)return;
  var state=current;SliceSettings next;try{next=ReadSettings();}catch(Exception ex){MessageBox.Show(this,ex.Message,"Eingabe prüfen");return;}
  next.Cuts.Clear();next.Edits=[];next.Placements=[];
  await Work(async(token,p)=>
  {
   var folder=GeometryService.NewFolder();
   await geometry.RunAsync(new{command="rotate",input=Path.Combine(state.ModelFolder,"original.stl"),output=folder,angles,name=state.Model.Name},folder,p,token);
   var model=Json.Read<ModelRecord>(Path.Combine(folder,"model.json"));
   await RenderWorkspace(new(folder,null,model,null,next),true);ApplySettings(next);dirty=true;
   StatusText.Text="Modell ausgerichtet · X/Y/Z: "+string.Join(" / ",angles.Select(a=>a.ToString("G")))+"° · zum Teilen neu schneiden";
  });
 }
 async void UndoClick(object sender,RoutedEventArgs e){if(busy||undo.Count==0)return;var previous=current;var target=undo.Peek();await Work(async(_,_)=>{await RenderWorkspace(target);undo.Pop();if(previous!=null)redo.Push(previous);ApplySettings(target.Settings);dirty=true;StatusText.Text="Rückgängig · vorheriger Projektzustand";});}
 async void RedoClick(object sender,RoutedEventArgs e){if(busy||redo.Count==0)return;var previous=current;var target=redo.Peek();await Work(async(_,_)=>{await RenderWorkspace(target);redo.Pop();if(previous!=null)undo.Push(previous);ApplySettings(target.Settings);dirty=true;StatusText.Text="Wiederhergestellt";});}
 void OpenModelCommand(object sender,ExecutedRoutedEventArgs e)=>LoadClick(sender,e);
 void SaveCommand(object sender,ExecutedRoutedEventArgs e)=>SaveProject();
 void UndoCommand(object sender,ExecutedRoutedEventArgs e)=>UndoClick(sender,e);
 void RedoCommand(object sender,ExecutedRoutedEventArgs e)=>RedoClick(sender,e);
 async void FileDropped(object sender,DragEventArgs e){if(e.Data.GetData(DataFormats.FileDrop) is string[] {Length:>0} files)await OpenFile(files[0]);}
 void WindowClosing(object? sender,CancelEventArgs e)
 {
  if(busy){e.Cancel=true;StatusText.Text="Bitte den laufenden Vorgang zuerst abbrechen.";return;}
  if(!CanReplace()){e.Cancel=true;return;}try{settings=ReadSettings();SavePreferences();}catch(Exception ex){App.Log(ex);}
 }
}
