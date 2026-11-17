using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace SlicerPro.Controls;

public static class ConnectorPositionsEditor
{
 public static ConnectorPlacement[]? Choose(Window owner,SliceResult result,ConnectorPlacement[] current)
 {
  var window=Dialogs.Window(owner,"Verbinderpositionen",900,640);
  window.MinWidth=620;window.MinHeight=420;
  var layout=new DockPanel{Margin=new(18)};
  var top=new StackPanel();
  DockPanel.SetDock(top,Dock.Top);layout.Children.Add(top);
  top.Children.Add(new TextBlock{Text="Schnittstelle",Margin=new(0,0,0,5)});
  var faces=result.Interfaces.Where(f=>result.Parts.Any(p=>p.Id==f.A&&p.Key!=null)&&result.Parts.Any(p=>p.Id==f.B&&p.Key!=null)).ToArray();
  var choice=new ComboBox{ItemsSource=faces.Select(f=>$"{f.Id} · Teil {f.A:000} ↔ {f.B:000} · {f.Area:N1} mm²{(f.ColorBoundary?" · Farbgrenze":"")}").ToArray()};
  top.Children.Add(choice);
  var instructions=new TextBlock{TextWrapping=TextWrapping.Wrap,Margin=new(0,12,0,8)};
  top.Children.Add(instructions);
  var note=new TextBlock{TextWrapping=TextWrapping.Wrap,Foreground=Brushes.LightSteelBlue,Margin=new(0,8,0,0)};
  var footer=new StackPanel();
  DockPanel.SetDock(footer,Dock.Bottom);layout.Children.Add(footer);footer.Children.Add(note);
  var actions=new WrapPanel{HorizontalAlignment=HorizontalAlignment.Right,Margin=new(0,10,0,0)};
  var cancel=new Button{Content="Abbrechen",IsCancel=true,Margin=new(0,0,8,0)};
  var reset=new Button{Content="Alle auf Automatik",Margin=new(0,0,8,0),IsEnabled=current.Length>0};
  var apply=new Button{Content="Neu berechnen",IsEnabled=faces.Length>0};
  actions.Children.Add(cancel);actions.Children.Add(reset);actions.Children.Add(apply);footer.Children.Add(actions);
  var body=new Grid();
  body.ColumnDefinitions.Add(new(){Width=new(1.5,GridUnitType.Star)});
  body.ColumnDefinitions.Add(new(){Width=new(1,GridUnitType.Star)});
  var preview=new ModelViewport{Background=new SolidColorBrush(Color.FromRgb(7,20,31))};
  body.Children.Add(preview);
  var coordinates=new DockPanel{Margin=new(12,0,0,0)};
  var clear=new Button{Content="Punkte dieser Fläche leeren",Margin=new(0,8,0,0),IsEnabled=faces.Length>0};
  DockPanel.SetDock(clear,Dock.Bottom);coordinates.Children.Add(clear);
  var values=new TextBox{AcceptsReturn=true,VerticalScrollBarVisibility=ScrollBarVisibility.Auto,VerticalContentAlignment=VerticalAlignment.Top};
  coordinates.Children.Add(values);
  Grid.SetColumn(coordinates,1);body.Children.Add(coordinates);layout.Children.Add(body);
  ConnectorPlacement[]? answer=null;
  Dictionary<int,string> drafts=[];
  bool switching=false;

  (double[] normal,int fixedAxis,int[] free) Axes(InterfaceRecord face)
  {
   var normal=face.Normal is {Length:3} n?n:Enumerable.Range(0,3).Select(i=>i==face.Axis?1d:0d).ToArray();
   int fixedAxis=Enumerable.Range(0,3).MaxBy(i=>Math.Abs(normal[i]));
   return (normal,fixedAxis,Enumerable.Range(0,3).Where(i=>i!=fixedAxis).ToArray());
  }
  string FormatPoint(double[] center,int[] free)=>string.Join("; ",free.Select(i=>center[i].ToString("0.######",CultureInfo.CurrentCulture)));

  string[] Lines(string value)=>value.Split('\n',StringSplitOptions.TrimEntries|StringSplitOptions.RemoveEmptyEntries);

  bool TryCenter(string line,InterfaceRecord face,out double[] center)
  {
   var (normal,fixedAxis,free)=Axes(face);
   var fields=line.Split(';',StringSplitOptions.TrimEntries);
   center=new double[3];
   if(fields.Length!=2||!Read(fields[0],out center[free[0]])||!Read(fields[1],out center[free[1]]))return false;
   center[fixedAxis]=(face.Offset-center[free[0]]*normal[free[0]]-center[free[1]]*normal[free[1]])/normal[fixedAxis];
   return double.IsFinite(center[fixedAxis]);
  }

  void ShowPoints()
  {
   var face=faces[choice.SelectedIndex];
   var centers=new List<double[]>();
   foreach(var line in Lines(values.Text).Take(8))
    if(TryCenter(line,face,out var center))centers.Add(center);
   preview.ShowInterfacePoints(centers);
  }

  choice.SelectionChanged+=(_,_) =>
  {
   if(choice.SelectedIndex<0)return;
   var face=faces[choice.SelectedIndex];
   var (normal,fixedAxis,free)=Axes(face);
   var visual=preview.DisplayInterface(face,normal);
   preview.Visibility=visual?Visibility.Visible:Visibility.Collapsed;
   Grid.SetColumn(coordinates,visual?1:0);
   Grid.SetColumnSpan(coordinates,visual?1:2);
   coordinates.Margin=visual?new Thickness(12,0,0,0):new Thickness();
   var picking=visual?"Auf die Fläche klicken, um einen Mittelpunkt hinzuzufügen. Strg+Klick ersetzt die aktuelle Zeile. "
    :"Für diese Schnittstelle steht die Koordinateneingabe zur Verfügung. Bei älteren Ergebnissen neu berechnen, um die Fläche anzuzeigen. ";
   instructions.Text=picking+$"Koordinaten je Zeile als {"XYZ"[free[0]]}; {"XYZ"[free[1]]} in mm. {"XYZ"[fixedAxis]} folgt aus der Ebene. Leere Liste = Automatik.";
   var previous=current.Where(p=>p.InterfaceId==face.Id&&p.ColorBoundary==face.ColorBoundary).Select(p=>p.Center).ToArray();
   var centers=previous.Length>0?previous:result.Joints.Where(j=>face.Connectors.Contains(j.Id)).Select(j=>j.Center).ToArray();
   switching=true;
   values.Text=drafts.GetValueOrDefault(choice.SelectedIndex)??string.Join(Environment.NewLine,centers.Where(c=>c is {Length:3}).Select(c=>FormatPoint(c,free)));
   switching=false;
   values.CaretIndex=0;
   ShowPoints();
   note.Text=drafts.ContainsKey(choice.SelectedIndex)?"Positionen geändert.":previous.Length>0?"Manuelle Positionen gespeichert.":"Vorbelegt mit den zuletzt berechneten Positionen.";
  };
  values.TextChanged+=(_,_)=>{
   if(switching||choice.SelectedIndex<0)return;
   drafts[choice.SelectedIndex]=values.Text;
   note.Text="Positionen geändert. Die Berechnung prüft Wandreserve und Kollisionen.";
   ShowPoints();
  };
  clear.Click+=(_,_)=>{values.Clear();drafts[choice.SelectedIndex]="";};
  preview.SurfacePicked+=point=>
  {
   if(choice.SelectedIndex<0)return;
   double[] model=[point.X,-point.Z,point.Y];
   var (_,_,free)=Axes(faces[choice.SelectedIndex]);
   var line=FormatPoint(model,free);
   if(Keyboard.Modifiers.HasFlag(ModifierKeys.Control)&&values.LineCount>0&&values.Text.Length>0)
   {
    int row=values.GetLineIndexFromCharacterIndex(values.CaretIndex);
    if(row<0)return;
    int start=values.GetCharacterIndexFromLineIndex(row);
    int length=values.GetLineLength(row);
    if(start<0||length<0||start>values.Text.Length-length)return;
    var trimmed=values.Text.AsSpan(start,length).TrimEnd("\r\n".AsSpan()).Length;
    values.Text=values.Text.Remove(start,trimmed).Insert(start,line);
    values.CaretIndex=start;
   }
   else
   {
    if(Lines(values.Text).Length>=8){note.Text="Bis zu acht Positionen. Eine Zeile löschen oder mit Strg+Klick ersetzen.";return;}
    values.Text=string.Join(Environment.NewLine,Lines(values.Text).Append(line));
    values.CaretIndex=values.Text.Length;
   }
  };
  apply.Click+=(_,_) =>
  {
   var edited=drafts.Keys.Select(i=>(faces[i].Id,faces[i].ColorBoundary)).ToHashSet();
   var replacements=current.Where(p=>!edited.Contains((p.InterfaceId,p.ColorBoundary))).ToList();
   foreach(var (index,content) in drafts)
   {
    var face=faces[index];
    var lines=Lines(content);
    if(lines.Length>8)
    {
     choice.SelectedIndex=index;note.Text="Bitte höchstens acht Positionen eingeben.";return;
    }
    foreach(var line in lines)
    {
     if(!TryCenter(line,face,out var center))
     {
      choice.SelectedIndex=index;note.Text="Bitte pro Zeile zwei gültige Zahlen mit Semikolon trennen.";return;
     }
     replacements.Add(new(){InterfaceId=face.Id,AKey=result.Parts.Single(p=>p.Id==face.A).Key!,
      BKey=result.Parts.Single(p=>p.Id==face.B).Key!,Center=center,ColorBoundary=face.ColorBoundary});
    }
   }
   answer=replacements.ToArray();
   window.DialogResult=true;
  };
  reset.Click+=(_,_)=>{answer=[];window.DialogResult=true;};
  choice.SelectedIndex=faces.Length==0?-1:0;
  if(faces.Length==0)
  {
   instructions.Text="Dieses Ergebnis enthält keine bearbeitbare Schnittstelle. Modell zuerst teilen oder alte Teilung neu berechnen.";
   body.Visibility=Visibility.Collapsed;
  }
  window.Content=layout;
  return window.ShowDialog()==true?answer:null;
 }
 static bool Read(string value,out double number)
  =>double.TryParse(value.Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture,out number)&&double.IsFinite(number);
}
