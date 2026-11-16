using System.Globalization;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Media3D;

namespace SlicerPro.Controls;

public static class PlaneEditor
{
 public static ManualEdit[]? Choose(Window owner,MeshGeometry3D mesh,MeshInfo info,ManualEdit[] current,string? target=null)
 {
  var window=Dialogs.Window(owner,target==null?"Freie Schnittebenen":"Einzelteil neu teilen",930,690);
  window.MinHeight=560;
  var layout=new Grid{Margin=new(16)};
  layout.ColumnDefinitions.Add(new(){Width=new(1,GridUnitType.Star)});
  layout.ColumnDefinitions.Add(new(){Width=new(290)});
  layout.RowDefinitions.Add(new(){Height=new(1,GridUnitType.Star)});
  layout.RowDefinitions.Add(new(){Height=GridLength.Auto});
  var view=new ModelViewport{MeshNote="Ebenenvorschau · Alt + Klick setzt einen Punkt auf der Oberfläche"};
  layout.Children.Add(view);
  view.DisplayOriginal(mesh,info);

  var controls=new StackPanel{Margin=new(14,0,0,0)};
  var scroll=new ScrollViewer{Content=controls,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};
  Grid.SetColumn(scroll,1);layout.Children.Add(scroll);
  var planes=current.ToList();
  var list=new ListBox{MaxHeight=120,MinHeight=68,DisplayMemberPath=nameof(ManualEdit.Label)};
  controls.Children.Add(new TextBlock{Text=target==null?"Bearbeitungen in Reihenfolge":"Ebene für das gewählte Teil",Margin=new(0,0,0,6)});
  if(target==null)controls.Children.Add(list);
  var fields=new TextBox[5];
  string[] labels=["Punkt X (mm)","Punkt Y (mm)","Punkt Z (mm)","Richtung in XY (°)","Neigung über XY (°)"];
  for(int i=0;i<fields.Length;i++)
  {
   var label=new TextBlock{Text=labels[i],Margin=new(0,7,0,3)};
   fields[i]=new();
   AutomationProperties.SetName(fields[i],labels[i]);
   controls.Children.Add(label);controls.Children.Add(fields[i]);
  }
  var note=new TextBlock{TextWrapping=TextWrapping.Wrap,Foreground=Brushes.LightSteelBlue,Margin=new(0,8,0,0)};
  var change=new WrapPanel{Margin=new(0,10,0,0)};
  var add=new Button{Content="Ebene hinzufügen",Margin=new(0,0,6,5)};
  var replace=new Button{Content="Ändern",Margin=new(0,0,6,5)};
  var remove=new Button{Content="Entfernen",Margin=new(0,0,0,5)};
  if(target==null){change.Children.Add(add);change.Children.Add(replace);change.Children.Add(remove);controls.Children.Add(change);}
  controls.Children.Add(note);

  var actions=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Margin=new(0,10,0,0)};
  var cancel=new Button{Content="Abbrechen",IsCancel=true,Margin=new(0,0,8,0)};
  var apply=new Button{Content="Neu berechnen"};
  actions.Children.Add(cancel);actions.Children.Add(apply);Grid.SetRow(actions,1);Grid.SetColumnSpan(actions,2);layout.Children.Add(actions);

  ManualEdit? Read()
  {
   var values=new double[5];
   for(int i=0;i<values.Length;i++)
    if(!double.TryParse(fields[i].Text.Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture,out values[i])||!double.IsFinite(values[i]))
     return null;
   if(Math.Abs(values[3])>360||Math.Abs(values[4])>90)return null;
   double direction=values[3]*Math.PI/180, tilt=values[4]*Math.PI/180;
   return new(){Point=values[..3],Normal=[Math.Cos(tilt)*Math.Cos(direction),Math.Cos(tilt)*Math.Sin(direction),Math.Sin(tilt)],
    Target=target??(list.SelectedItem as ManualEdit)?.Target};
  }
  void Preview()
  {
   bool merging=(list.SelectedItem as ManualEdit)?.Merge!=null;
   var plane=Read();
   view.ShowPlane(info,merging?null:plane);
   add.IsEnabled=plane!=null&&planes.Count<64;
   replace.IsEnabled=plane!=null&&list.SelectedIndex>=0&&!merging;
   remove.IsEnabled=list.SelectedIndex>=0;
   apply.IsEnabled=target==null||plane!=null&&planes.Count<64;
   note.Text=merging?"Diese Bearbeitung fügt Teile zusammen. Nachfolgende lokale Schnitte können davon abhängen."
    :plane==null?"Bitte gültige Koordinaten und Winkel eingeben. Neigung −90 bis 90°, Richtung −360 bis 360°."
    :target!=null?"Die Ebene schneidet nur das gewählte Teil."
    :"Mit „Ebene hinzufügen“ oder „Ändern“ in die Liste übernehmen. Die Vorschau zeigt die Ebene im Modellrahmen.";
  }
  void Fill(double[] point,double[] normal)
  {
   var values=point.Concat([Math.Atan2(normal[1],normal[0])*180/Math.PI,Math.Asin(Math.Clamp(normal[2],-1,1))*180/Math.PI]).ToArray();
   for(int i=0;i<fields.Length;i++)fields[i].Text=values[i].ToString("G",CultureInfo.CurrentCulture);
  }
  void Refresh(int index)
  {
   list.ItemsSource=planes.ToArray();list.SelectedIndex=index;Preview();
  }
  list.SelectionChanged+=(_,_)=>{if(list.SelectedItem is ManualEdit{Merge:null} plane)Fill(plane.Point,plane.Normal);Preview();};
  foreach(var field in fields)field.TextChanged+=(_,_)=>Preview();
  view.SurfacePicked+=point=>
  {
   double[] model=[point.X,-point.Z,point.Y];
   for(int i=0;i<3;i++)fields[i].Text=model[i].ToString("0.###",CultureInfo.CurrentCulture);
  };
  add.Click+=(_,_)=>{if(Read() is {} plane){plane.Target=null;planes.Add(plane);Refresh(planes.Count-1);}};
  replace.Click+=(_,_)=>{if(list.SelectedIndex is >=0 and var index&&Read() is {} plane){planes[index]=plane;Refresh(index);}};
  remove.Click+=(_,_)=>{var index=list.SelectedIndex;if(index>=0){planes.RemoveAt(index);Refresh(Math.Min(index,planes.Count-1));}};
  apply.Click+=(_,_)=>{if(target!=null&&Read() is {} plane)planes.Add(plane);window.DialogResult=true;};
  Fill(Enumerable.Range(0,3).Select(i=>(info.Bounds[i]+info.Bounds[i+3])/2).ToArray(),[1,1,0]);
  Refresh(target==null&&planes.Count>0?0:-1);
  window.Content=layout;
  return window.ShowDialog()==true?planes.ToArray():null;
 }
}
