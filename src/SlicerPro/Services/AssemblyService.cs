using System.IO;
using System.Text;
namespace SlicerPro.Services;

public static class AssemblyService
{
 // Minimal multipage PDF writer, WinAnsi/Helvetica, no third-party service.
 public static void WritePdf(Workspace state,string path)
 {
  Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
  var enc=Encoding.GetEncoding(1252);
  var r=state.Result??throw new InvalidOperationException("Bitte zuerst schneiden.");
  var lines=new List<string>{"3D Print Slicer Pro - Montageplan",state.Model.Name,DateTime.Now.ToString("dd.MM.yyyy HH:mm"),"",$"{r.Parts.Length} Teile / {r.Joints.Length} Verbindungen",$"Material: {r.Settings.Material} / Spiel / Gesamtzugabe: {r.Settings.Tolerance:N2} mm",r.Planning?.Label??"Schnittplan aus älterem Projekt",r.Assembly?.Summary??"Verbindungsgraph nicht ausgewertet",$"Schnittstellen ohne Verbinder: {r.Assembly?.UnconnectedInterfaces??0}",r.Motion?.Summary??"Montagewege nicht geprüft","Nur geradlinige Bewegungen entlang XYZ oder der Verbinderrichtung mit vorbestückten separaten Verbindern.","Keine Reibungs-, Verformungs- oder Festigkeitsprüfung.","",r.Motion?.PathVerified==true?"Nachgewiesene geradlinige Teilfolge:":"Geometrischer Vorschlag (Montagewege nicht vollständig nachgewiesen):",string.Join(", ",r.AssemblyOrder.Select(i=>$"{i:000}")),"", "Zuordnung der Verbinder:"};
  foreach(var j in r.Joints)lines.Add($"{j.Id}: Teil {j.A:000} <-> Teil {j.B:000}, {j.TravelLabel} / {(j.Mode=="separate"?"separat":"an Teil "+j.A.ToString("000")+" integriert")}, {j.KindLabel}: {j.SizeLabel}{(j.AutoSized?" (automatisch verkleinert)":"")}");
  if(r.Assembly is {} assembly&&assembly.Groups.Length>1){lines.Add("");lines.Add("Lose Baugruppen:");for(int i=0;i<assembly.Groups.Length;i++)lines.Add($"Gruppe {i+1}: "+string.Join(", ",assembly.Groups[i].Select(p=>$"Teil {p:000}")));}
  if(r.Settings.Strategy=="color")
  {
   lines.Add("");lines.Add("Farbzuordnung:");
   foreach(var part in r.Parts)lines.Add($"Teil {part.Id:000}: {part.Color??"Ohne Farbzuweisung"}");
  }
  lines.Add("");lines.Add("Schnittstellen:");foreach(var f in r.Interfaces)lines.Add($"{f.Id}: Teil {f.A:000} <-> Teil {f.B:000}, {f.Area:N1} mm², {f.Placed}/{f.Requested} Verbinder");
  if(r.Motion is {} motion)
  {
   lines.Add("");lines.Add("Montagewege: "+motion.Summary);
   if(motion.BudgetReached)lines.Add("Rechenbudget erreicht: Verbleibende Wege sind ungeprüft.");
   if(motion.UnresolvedPins.Length>0)lines.Add("Vorbestückung separater Verbinder nicht nachgewiesen: "+string.Join(", ",motion.UnresolvedPins));
   if(motion.PathVerified)
   {
    lines.Add("Separate Verbinder am einzelnen Hostteil vorbestücken (festhalten oder fixieren):");
    foreach(var pin in motion.PreinsertSteps)lines.Add($"{pin.Connector} in Teil {pin.Host:000}: {MotionRecord.DirectionLabel(pin.InsertionDirection)}, Weg {pin.Distance:N1} mm");
    lines.Add("Teile in dieser Reihenfolge einfügen:");
    foreach(var step in motion.AssemblySteps)lines.Add(step.Base?$"Teil {step.Part:000} als Basis":$"Teil {step.Part:000}: Einstecken {MotionRecord.DirectionLabel(step.InsertionDirection)}, Weg {step.Distance:N1} mm");
   }
   else foreach(var fail in motion.LastFailures.Take(25))lines.Add($"Teil {fail.Part:000}, {MotionRecord.DirectionLabel(fail.Direction)}: {fail.Description}");
  }
  lines.Add("");lines.Add("Prüfhinweise:");lines.AddRange(r.Warnings.Select(w=>w.Replace("↔","<->")));
  lines.Add("");lines.Add("Druckteile und separate Verbinder sind in Druckausrichtung, auf dem Nullpunkt und in Millimetern.");
  lines.Add("Keine Garantie der Tragfähigkeit. Zuerst Passprobe drucken.");
  if(state.Model.Orientation is {} orientation)lines.Insert(4,orientation.Label);
  var wrapped=new List<string>();foreach(var line in lines){var rest=line;while(rest.Length>95){var at=rest.LastIndexOf(' ',95);if(at<1)at=95;wrapped.Add(rest[..at]);rest=rest[at..].TrimStart();}wrapped.Add(rest);}
  var pages=wrapped.Chunk(47).ToArray();
  var objects=new List<byte[]>();
  void Add(string s)=>objects.Add(enc.GetBytes(s));
  Add("<< /Type /Catalog /Pages 2 0 R >>");
  Add($"<< /Type /Pages /Count {pages.Length} /Kids [ {string.Join(" ",Enumerable.Range(0,pages.Length).Select(i=>$"{4+2*i} 0 R"))} ] >>");
  Add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  for(var i=0;i<pages.Length;i++)
  {
   Add($"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {5+2*i} 0 R >>");
   string Escape(string s)=>s.Replace("\\","\\\\").Replace("(","\\(").Replace(")","\\)");
   var content="BT /F1 11 Tf 44 795 Td 15 TL\n"+string.Join("\n",pages[i].Select(l=>$"({Escape(l)}) Tj T*"))+ $"\nET\nBT /F1 9 Tf 44 24 Td (Seite {i+1} / {pages.Length}) Tj ET";
   var bytes=enc.GetBytes(content);Add($"<< /Length {bytes.Length} >>\nstream\n{content}\nendstream");
  }
  using var stream=File.Create(path);void Write(string s){var bytes=enc.GetBytes(s);stream.Write(bytes);}
  Write("%PDF-1.4\n");var offsets=new List<long>{0};
  for(var i=0;i<objects.Count;i++){offsets.Add(stream.Position);Write($"{i+1} 0 obj\n");stream.Write(objects[i]);Write("\nendobj\n");}
  var xref=stream.Position;Write($"xref\n0 {offsets.Count}\n0000000000 65535 f \n");foreach(var offset in offsets.Skip(1))Write($"{offset:0000000000} 00000 n \n");
  Write($"trailer\n<< /Size {offsets.Count} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n");
 }
}
