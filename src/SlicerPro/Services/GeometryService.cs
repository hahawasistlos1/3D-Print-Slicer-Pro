using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
namespace SlicerPro.Services;

public sealed class GeometryService
{
 public static string NewFolder()
 {
  var folder=Path.Combine(App.DataRoot,"Sessions",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);return folder;
 }
 public static string LocateRuntime()
 {
  var here=new DirectoryInfo(AppContext.BaseDirectory);
  while(here!=null) {var file=Path.Combine(here.FullName,"runtime","python.exe");if(File.Exists(file)) return file;here=here.Parent;}
  throw new FileNotFoundException("Die lokale Geometrie-Laufzeit fehlt. Bitte die vollständige Portable-Version entpacken oder das Setup ausführen.");
 }
 public async Task RunAsync(object request,string work,IProgress<(int,string)>? progress,CancellationToken cancellation)
 {
  var python=LocateRuntime();
  var worker=Path.Combine(AppContext.BaseDirectory,"engine","worker.py");
  if(!File.Exists(worker)) throw new FileNotFoundException("Geometrie-Worker fehlt.");
  Directory.CreateDirectory(work);var job=Path.Combine(work,"job.json");Json.Write(job,request);
  var start=new ProcessStartInfo(python){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8,WorkingDirectory=work};
  start.ArgumentList.Add("-B");start.ArgumentList.Add(worker);start.ArgumentList.Add(job);
  start.Environment["PYTHONIOENCODING"]="utf-8";start.Environment["PYTHONUTF8"]="1";
  start.Environment["OMP_NUM_THREADS"]="2";start.Environment["OPENBLAS_NUM_THREADS"]="1";
  using var process=Process.Start(start)??throw new IOException("Geometrieprozess konnte nicht gestartet werden.");
  using var stop=cancellation.Register(()=>{try {process.Kill(true);}catch{}});
  var stderr=process.StandardError.ReadToEndAsync();string? failure=null;
  while(await process.StandardOutput.ReadLineAsync() is {} line)
  {
   using var data=JsonDocument.Parse(line);
   if(data.RootElement.TryGetProperty("error",out var e)) failure=e.GetString();
   if(data.RootElement.TryGetProperty("progress",out var p)) progress?.Report((p.GetInt32(),data.RootElement.GetProperty("message").GetString()??""));
  }
  await process.WaitForExitAsync(CancellationToken.None);var details=await stderr;
  cancellation.ThrowIfCancellationRequested();
  if(process.ExitCode!=0)
  {
   var exception=new InvalidOperationException(failure??"Die Geometrieberechnung ist fehlgeschlagen.");
   App.Log(new Exception(details,exception));throw exception;
  }
 }
}
