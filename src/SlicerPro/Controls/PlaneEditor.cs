using System.Globalization;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
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
  var view=new ModelViewport{MeshNote="Alt+Klick setzt den Drehpunkt auf die Modelloberfläche"};
  layout.Children.Add(view);
  view.DisplayOriginal(mesh,info);
  var overlay=new Canvas{ClipToBounds=true,Visibility=Visibility.Collapsed};
  layout.Children.Add(overlay);
  var pivot=new Border{Width=10,Height=10,CornerRadius=new(5),Background=Brushes.White,
   BorderBrush=Brushes.DarkCyan,BorderThickness=new(2),IsHitTestVisible=false};
  overlay.Children.Add(pivot);
  var handles=new StackPanel{Orientation=Orientation.Horizontal};
  overlay.Children.Add(handles);

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

  bool TryNumber(int index,out double number)
   =>double.TryParse(fields[index].Text.Replace(',','.'),NumberStyles.Float,CultureInfo.InvariantCulture,out number)&&double.IsFinite(number);

  ManualEdit? Read()
  {
   var values=new double[5];
   for(int i=0;i<values.Length;i++)
    if(!TryNumber(i,out values[i]))return null;
   if(Math.Abs(values[3])>360||Math.Abs(values[4])>90)return null;
   double direction=values[3]*Math.PI/180, tilt=values[4]*Math.PI/180;
   return new(){Point=values[..3],Normal=[Math.Cos(tilt)*Math.Cos(direction),Math.Cos(tilt)*Math.Sin(direction),Math.Sin(tilt)],
    Target=target??(list.SelectedItem as ManualEdit)?.Target};
  }
  double[]? pivotPoint=null;
  void ArrangeHandles()
  {
   if(pivotPoint==null)return;
   bool onScreen=view.TryProjectModelPoint(pivotPoint,out var at);
   pivot.Visibility=onScreen?Visibility.Visible:Visibility.Collapsed;
   Canvas.SetLeft(pivot,at.X-5);Canvas.SetTop(pivot,at.Y-5);
   double x=onScreen?at.X+13:12;
   double y=onScreen?at.Y+13:12;
   Canvas.SetLeft(handles,Math.Clamp(x,0,Math.Max(0,view.ActualWidth-226)));
   Canvas.SetTop(handles,Math.Clamp(y,0,Math.Max(0,view.ActualHeight-36)));
  }
  view.CameraChanged+=(_,_,_,_)=>ArrangeHandles();
  view.SizeChanged+=(_,_)=>ArrangeHandles();
  void WriteAngle(int index,double angle)
  {
   var value=index==3?Math.IEEERemainder(angle,360):Math.Clamp(angle,-90,90);
   fields[index].Text=value.ToString("0.###",CultureInfo.CurrentCulture);
  }
  Thumb RotationHandle(int index,string name,string label)
  {
   bool horizontal=index==3;
   // A separate thumb owns mouse capture while the camera stays in place.
   var grip=new Thumb{Width=106,Height=30,Margin=new(0,0,6,0),Focusable=true,
    Cursor=horizontal?Cursors.SizeWE:Cursors.SizeNS,
    ToolTip=horizontal?"Horizontal ziehen oder die Pfeiltasten verwenden":"Vertikal ziehen oder die Pfeiltasten verwenden"};
   AutomationProperties.SetName(grip,name);
   var border=new FrameworkElementFactory(typeof(Border));
   border.SetValue(Border.BackgroundProperty,new SolidColorBrush(Color.FromRgb(15,61,77)));
   border.SetValue(Border.BorderBrushProperty,Brushes.Cyan);
   border.SetValue(Border.BorderThicknessProperty,new Thickness(1));
   border.SetValue(Border.CornerRadiusProperty,new CornerRadius(5));
   var caption=new FrameworkElementFactory(typeof(TextBlock));
   caption.SetValue(TextBlock.TextProperty,label);
   caption.SetValue(TextBlock.ForegroundProperty,Brushes.White);
   caption.SetValue(FrameworkElement.HorizontalAlignmentProperty,HorizontalAlignment.Center);
   caption.SetValue(FrameworkElement.VerticalAlignmentProperty,VerticalAlignment.Center);
   border.AppendChild(caption);
   grip.Template=new ControlTemplate(typeof(Thumb)){VisualTree=border};
   Point start=new();
   double initial=0;
   grip.DragStarted+=(_,_)=>{start=Mouse.GetPosition(view);TryNumber(index,out initial);};
   grip.DragDelta+=(_,_)=>{
    var delta=Mouse.GetPosition(view)-start;
    WriteAngle(index,initial+.45*(horizontal?delta.X:-delta.Y));
   };
   grip.KeyDown+=(_,eventArgs)=>{
    var delta=eventArgs.Key switch
    {
     Key.Right when horizontal=>1,Key.Left when horizontal=>-1,
     Key.Up when !horizontal=>1,Key.Down when !horizontal=>-1,
     _=>0
    };
    if(delta==0||!TryNumber(index,out var angle))return;
    WriteAngle(index,angle+delta*(Keyboard.Modifiers.HasFlag(ModifierKeys.Shift)?10:1));
    eventArgs.Handled=true;
   };
   return grip;
  }
  handles.Children.Add(RotationHandle(3,"Richtung der Schnittebene drehen","↔ Richtung"));
  handles.Children.Add(RotationHandle(4,"Neigung der Schnittebene drehen","↕ Neigung"));
  void Preview()
  {
   bool merging=(list.SelectedItem as ManualEdit)?.Merge!=null;
   var plane=Read();
   view.ShowPlane(info,merging?null:plane);
   pivotPoint=merging?null:plane?.Point;
   overlay.Visibility=pivotPoint==null?Visibility.Collapsed:Visibility.Visible;
   ArrangeHandles();
   add.IsEnabled=plane!=null&&planes.Count<64;
   replace.IsEnabled=plane!=null&&list.SelectedIndex>=0&&!merging;
   remove.IsEnabled=list.SelectedIndex>=0;
   apply.IsEnabled=target==null||plane!=null&&planes.Count<64;
   note.Text=merging?"Diese Bearbeitung fügt Teile zusammen. Nachfolgende lokale Schnitte können davon abhängen."
    :plane==null?"Bitte gültige Koordinaten und Winkel eingeben. Neigung −90 bis 90°, Richtung −360 bis 360°."
    :target!=null?"An den Griffen ziehen. Die Ebene schneidet nur das gewählte Teil."
    :"An den Griffen ziehen. Mit „Ebene hinzufügen“ oder „Ändern“ in die Liste übernehmen.";
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
