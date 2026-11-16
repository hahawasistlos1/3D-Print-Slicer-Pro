using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using SlicerPro.Services;
using System.Globalization;
using System.Windows.Media.Media3D;
namespace SlicerPro.Controls;

public static class Dialogs
{
 public static Window Window(Window owner,string title,double width=530,double height=510)
 =>new(){Owner=owner,Title=title,Width=width,Height=height,MinWidth=400,MinHeight=220,WindowStartupLocation=WindowStartupLocation.CenterOwner,ShowInTaskbar=false,Background=new SolidColorBrush(Color.FromRgb(9,23,33)),Foreground=Brushes.White};
 public static string? Input(Window owner,string title,string label,string value)
 {
  var window=Window(owner,title,450,220);window.ResizeMode=ResizeMode.NoResize;
  var stack=new StackPanel{Margin=new(20)};stack.Children.Add(new TextBlock{Text=label,TextWrapping=TextWrapping.Wrap});
  var box=new TextBox{Text=value,Margin=new(0,12,0,15)};stack.Children.Add(box);
  var ok=new Button{Content="Übernehmen",HorizontalAlignment=HorizontalAlignment.Right,IsDefault=true};
  ok.Click+=(_,_)=>window.DialogResult=true;stack.Children.Add(ok);window.Content=stack;
  window.Loaded+=(_,_)=>{box.Focus();box.SelectAll();};return window.ShowDialog()==true?box.Text:null;
 }
 public static string? ExportFormat(Window owner,string preferredFormat)
 {
  var window=Window(owner,"Export / Druck",550,420);window.ResizeMode=ResizeMode.NoResize;
  var stack=new StackPanel{Margin=new(22)};
  stack.Children.Add(new TextBlock{Text="Format für Druckteile und Verbinder",FontSize=19,Margin=new(0,0,0,15)});
  var selected=preferredFormat;var choices=new StackPanel();stack.Children.Add(choices);
  var note=new TextBlock{Text=GeometryExport.Formats.Single(f=>f.Id==preferredFormat).Note,TextWrapping=TextWrapping.Wrap,MinHeight=65,Margin=new(0,12,0,8),Foreground=Brushes.LightSteelBlue};
  foreach(var format in GeometryExport.Formats){var radio=new RadioButton{Content=format.Label,GroupName="ExportFormat",IsChecked=format.Id==selected,Foreground=Brushes.White,FontSize=14,Margin=new(0,4,0,4)};radio.Checked+=(_,_)=>{selected=format.Id;note.Text=format.Note;};choices.Children.Add(radio);}stack.Children.Add(note);
  stack.Children.Add(new TextBlock{Text="Alle Teile werden einzeln in Druckausrichtung und mit Ursprung auf dem Druckbett ausgegeben. Montageplan, Prüfhinweise und Projekt sind enthalten.",TextWrapping=TextWrapping.Wrap,Margin=new(0,0,0,16)});
  var row=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right};
  var cancel=new Button{Content="Abbrechen",IsCancel=true,Margin=new(0,0,8,0)};row.Children.Add(cancel);
  var next=new Button{Content="Zielordner wählen",IsDefault=true};next.Click+=(_,_)=>window.DialogResult=true;row.Children.Add(next);stack.Children.Add(row);window.Content=stack;
  return window.ShowDialog()==true?selected:null;
 }
 public static double[]? ChooseOrientation(Window owner,MeshGeometry3D source)
 {
  var window=Window(owner,"Modell ausrichten",820,690);
  var grid=new Grid{Margin=new(20)};grid.RowDefinitions.Add(new(){Height=GridLength.Auto});grid.RowDefinitions.Add(new(){Height=new(1,GridUnitType.Star)});grid.RowDefinitions.Add(new(){Height=GridLength.Auto});grid.RowDefinitions.Add(new(){Height=GridLength.Auto});grid.RowDefinitions.Add(new(){Height=GridLength.Auto});
  var header=new TextBlock{Text="Modell vor dem Schneiden drehen · X → Y → Z",FontSize=19,Margin=new(0,0,0,10)};grid.Children.Add(header);
  var view=new ModelViewport{MinHeight=230,MeshNote="Ausrichtungsvorschau · Anzeigegeometrie"};Grid.SetRow(view,1);grid.Children.Add(view);
  var controls=new Grid{Margin=new(0,12,0,8)};for(int i=0;i<3;i++)controls.ColumnDefinitions.Add(new());
  var fields=new TextBox[3];for(int i=0;i<3;i++){var stack=new StackPanel{Margin=new(i==0?0:10,0,0,0)};stack.Children.Add(new TextBlock{Text="XYZ"[i]+"-Winkel in Grad",Margin=new(0,0,0,5)});fields[i]=new(){Text="0"};stack.Children.Add(fields[i]);Grid.SetColumn(stack,i);controls.Children.Add(stack);}Grid.SetRow(controls,2);grid.Children.Add(controls);
  var note=new TextBlock{Text="Winkel ändern und Vorschau aktualisieren. Exakte Maße werden beim Anwenden aus dem vollständigen Modell berechnet. Druckteile und manuelle Schnitte werden zurückgesetzt; Rückgängig ist möglich.",TextWrapping=TextWrapping.Wrap,Foreground=Brushes.LightSteelBlue,Margin=new(0,0,0,12)};Grid.SetRow(note,3);grid.Children.Add(note);
  var row=new WrapPanel{HorizontalAlignment=HorizontalAlignment.Right};var cancel=new Button{Content="Abbrechen",IsCancel=true,Margin=new(0,0,8,0)};var update=new Button{Content="Vorschau aktualisieren",Margin=new(0,0,8,0)};var apply=new Button{Content="Ausrichtung anwenden",IsEnabled=false};row.Children.Add(cancel);row.Children.Add(update);row.Children.Add(apply);Grid.SetRow(row,4);grid.Children.Add(row);
  double[]? chosen=null;
  foreach(var field in fields)field.TextChanged+=(_,_)=>{chosen=null;apply.IsEnabled=false;note.Text="Winkel geändert · Vorschau aktualisieren, dann Ausrichtung anwenden. Das setzt Druckteile und manuelle Schnitte zurück.";};
  update.Click+=(_,_)=>{try{var angles=fields.Select(f=>double.Parse(f.Text.Trim().Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture)).ToArray();var preview=ModelOrientation.Preview(source,angles);view.DisplayOriginal(preview.Mesh,preview.Info);chosen=angles;apply.IsEnabled=!ModelOrientation.IsIdentity(angles);note.Text="Vorschau: "+string.Join(" × ",preview.Info.Dimensions.Select(d=>d.ToString("N2")))+" mm (Anzeigegeometrie). Exakte Maße folgen beim Anwenden. Druckteile und manuelle Schnitte werden zurückgesetzt.";}catch(Exception e)when(e is ArgumentException or FormatException or OverflowException){chosen=null;apply.IsEnabled=false;note.Text="Bitte gültige Winkel von -360 bis 360 Grad eingeben.";}};
  apply.Click+=(_,_)=>window.DialogResult=true;window.Content=grid;
  var initial=ModelOrientation.Preview(source,[0,0,0]);view.DisplayOriginal(initial.Mesh,initial.Info);
  return window.ShowDialog()==true?chosen:null;
 }
 public static void Report(Window owner,string title,string text,params (string label,Action action)[] actions)
 {
  var window=Window(owner,title,800,630);var grid=new Grid{Margin=new(18)};grid.RowDefinitions.Add(new(){Height=new(1,GridUnitType.Star)});grid.RowDefinitions.Add(new(){Height=GridLength.Auto});
  var box=new TextBox{Text=text,IsReadOnly=true,AcceptsReturn=true,TextWrapping=TextWrapping.Wrap,VerticalScrollBarVisibility=ScrollBarVisibility.Auto,FontSize=13,Padding=new(12)};grid.Children.Add(box);
  var row=new WrapPanel{HorizontalAlignment=HorizontalAlignment.Right,Margin=new(0,14,0,0)};Grid.SetRow(row,1);grid.Children.Add(row);
  foreach(var (label,action) in actions){var button=new Button{Content=label,Margin=new(5,0,0,0)};button.Click+=(_,_)=>action();row.Children.Add(button);}
  var close=new Button{Content="Schließen",Margin=new(5,0,0,0),IsCancel=true};row.Children.Add(close);window.Content=grid;window.ShowDialog();
 }
}
