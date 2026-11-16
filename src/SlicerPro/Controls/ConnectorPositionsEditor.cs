using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace SlicerPro.Controls;

public static class ConnectorPositionsEditor
{
 public static ConnectorPlacement[]? Choose(Window owner,SliceResult result,ConnectorPlacement[] current)
 {
  var window=Dialogs.Window(owner,"Verbinderpositionen",650,550);
  var layout=new DockPanel{Margin=new(18)};
  var top=new StackPanel();
  DockPanel.SetDock(top,Dock.Top);layout.Children.Add(top);
  top.Children.Add(new TextBlock{Text="Schnittstelle",Margin=new(0,0,0,5)});
  var faces=result.Interfaces.Where(f=>result.Parts.Any(p=>p.Id==f.A&&p.Key!=null)&&result.Parts.Any(p=>p.Id==f.B&&p.Key!=null)).ToArray();
  var choice=new ComboBox{ItemsSource=faces.Select(f=>$"{f.Id} · Teil {f.A:000} ↔ {f.B:000} · {f.Area:N1} mm²").ToArray()};
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
  var values=new TextBox{AcceptsReturn=true,VerticalScrollBarVisibility=ScrollBarVisibility.Auto,VerticalContentAlignment=VerticalAlignment.Top};
  layout.Children.Add(values);
  ConnectorPlacement[]? answer=null;

  (double[] normal,int fixedAxis,int[] free) Axes(InterfaceRecord face)
  {
   var normal=face.Normal is {Length:3} n?n:Enumerable.Range(0,3).Select(i=>i==face.Axis?1d:0d).ToArray();
   int fixedAxis=Enumerable.Range(0,3).MaxBy(i=>Math.Abs(normal[i]));
   return (normal,fixedAxis,Enumerable.Range(0,3).Where(i=>i!=fixedAxis).ToArray());
  }
  choice.SelectionChanged+=(_,_) =>
  {
   if(choice.SelectedIndex<0)return;
   var face=faces[choice.SelectedIndex];
   var (_,fixedAxis,free)=Axes(face);
   instructions.Text=$"Je Zeile einen Mittelpunkt als {"XYZ"[free[0]]}; {"XYZ"[free[1]]} in mm eingeben. {"XYZ"[fixedAxis]} folgt aus der Schnittebene. Leere Liste aktiviert die automatische Platzierung für diese Schnittstelle.";
   var previous=current.Where(p=>p.InterfaceId==face.Id).Select(p=>p.Center).ToArray();
   var centers=previous.Length>0?previous:result.Joints.Where(j=>face.Connectors.Contains(j.Id)).Select(j=>j.Center).ToArray();
   values.Text=string.Join(Environment.NewLine,centers.Select(c=>string.Join("; ",free.Select(i=>c[i].ToString("G",CultureInfo.CurrentCulture)))));
   note.Text=previous.Length>0?"Manuelle Positionen gespeichert.":"Vorbelegt mit den zuletzt berechneten Positionen.";
  };
  apply.Click+=(_,_) =>
  {
   var face=faces[choice.SelectedIndex];
   var (normal,fixedAxis,free)=Axes(face);
   var replacements=new List<ConnectorPlacement>();
   var lines=values.Text.Split('\n',StringSplitOptions.TrimEntries|StringSplitOptions.RemoveEmptyEntries);
   if(lines.Length>8){note.Text="Bitte höchstens acht Positionen eingeben.";return;}
   foreach(var line in lines)
   {
    var fields=line.Split(';',StringSplitOptions.TrimEntries);
    var center=new double[3];
    if(fields.Length!=2||!Read(fields[0],out center[free[0]])||!Read(fields[1],out center[free[1]]))
    {
     note.Text="Bitte pro Zeile zwei gültige Zahlen mit Semikolon trennen.";return;
    }
    center[fixedAxis]=(face.Offset-center[free[0]]*normal[free[0]]-center[free[1]]*normal[free[1]])/normal[fixedAxis];
    if(!double.IsFinite(center[fixedAxis])){note.Text="Position liegt außerhalb des unterstützten Zahlenbereichs.";return;}
    replacements.Add(new(){InterfaceId=face.Id,AKey=result.Parts.Single(p=>p.Id==face.A).Key!,
     BKey=result.Parts.Single(p=>p.Id==face.B).Key!,Center=center});
   }
   answer=current.Where(p=>p.InterfaceId!=face.Id).Concat(replacements).ToArray();
   window.DialogResult=true;
  };
  reset.Click+=(_,_)=>{answer=[];window.DialogResult=true;};
  choice.SelectedIndex=faces.Length==0?-1:0;
  if(faces.Length==0)instructions.Text="Dieses Ergebnis enthält keine bearbeitbare Schnittstelle. Modell zuerst teilen oder alte Teilung neu berechnen.";
  window.Content=layout;
  return window.ShowDialog()==true?answer:null;
 }
 static bool Read(string value,out double number)
  =>double.TryParse(value.Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture,out number)&&double.IsFinite(number);
}
