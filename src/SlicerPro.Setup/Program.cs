using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Text.Json;
using Microsoft.Win32;
namespace SlicerPro.Setup;

static class Program
{
 const string AppId="3DPrintSlicerPro";
 const string RegistryPath=@"Software\Microsoft\Windows\CurrentVersion\Uninstall\3DPrintSlicerPro";
 const string ManifestName=".slicerpro-install.json";
 [STAThread]
 static int Main(string[] args)
 {
  ApplicationConfiguration.Initialize();
  try
  {
   if(args.Length==2&&args[0]=="--verify-extract")
   {Install(Path.GetFullPath(args[1]),false);return 0;}
   if(args.Length==3&&args[0]=="--cleanup")
   {
    try{Process.GetProcessById(int.Parse(args[2])).WaitForExit(15000);}catch(ArgumentException){}
    Uninstall(Path.GetFullPath(args[1]));return 0;
   }
   if(args.Contains("--uninstall"))
   {
    var folder=AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
    ReadManifest(folder);
    if(MessageBox.Show("3D Print Slicer Pro deinstallieren?\n\nEigene Projekte und Einstellungen bleiben erhalten.","Deinstallation",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return 0;
    if(IsAppRunning(folder))throw new InvalidOperationException("Bitte 3D Print Slicer Pro zuerst schließen.");
    var temp=Path.Combine(Path.GetTempPath(),"SlicerPro-Uninstall-"+Guid.NewGuid().ToString("N")+".exe");File.Copy(Environment.ProcessPath!,temp);
    var start=new ProcessStartInfo(temp){UseShellExecute=false};start.ArgumentList.Add("--cleanup");start.ArgumentList.Add(folder);start.ArgumentList.Add(Environment.ProcessId.ToString());Process.Start(start);return 0;
   }
   Application.Run(new InstallerForm());return 0;
  }
  catch(Exception e){if(args.FirstOrDefault()=="--verify-extract"){File.WriteAllText(args[1]+".error.txt",e.ToString());return 1;}MessageBox.Show(e.Message,"Setup fehlgeschlagen",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}
 }
 static bool IsAppRunning(string folder)=>Process.GetProcessesByName("3D Print Slicer Pro").Any(p=>{try{return p.MainModule?.FileName?.StartsWith(folder+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)==true;}catch{return true;}});
 static string SafePath(string folder,string relative)
 {
  var root=Path.GetFullPath(folder).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;var file=Path.GetFullPath(Path.Combine(root,relative));
  if(!file.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Ungültiger Paketpfad.");return file;
 }
 static Manifest ReadManifest(string folder)
 {
  var manifest=JsonSerializer.Deserialize<Manifest>(File.ReadAllText(Path.Combine(folder,ManifestName)))??throw new InvalidDataException("Installationsnachweis fehlt.");
  if((manifest.AppId!=AppId&&manifest.AppId!="3DPrintSlicerPro-0.1")||!string.Equals(manifest.InstallPath,Path.GetFullPath(folder),StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Dieser Ordner ist keine passende Slicer-Pro-Installation.");
  foreach(var file in manifest.Files)SafePath(folder,file);return manifest;
 }
 public static void Install(string folder,bool register)
 {
  folder=Path.GetFullPath(folder);
  if(Path.GetPathRoot(folder)==folder||folder.Length<10)throw new InvalidOperationException("Bitte einen eigenen Programmordner wählen.");
  if(IsAppRunning(folder))throw new InvalidOperationException("Bitte die laufende Anwendung vor der Installation schließen.");
  if(Directory.Exists(folder)&&Directory.EnumerateFileSystemEntries(folder).Any())ReadManifest(folder);
  Directory.CreateDirectory(folder);
  using var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")??throw new FileNotFoundException("Installationspaket fehlt. Bitte tools/build.ps1 -Package ausführen.");
  using var zip=new ZipArchive(stream,ZipArchiveMode.Read);var files=new List<string>();
  foreach(var entry in zip.Entries)
  {
   var path=SafePath(folder,entry.FullName);
   if(entry.FullName.EndsWith('/')){Directory.CreateDirectory(path);continue;}
   Directory.CreateDirectory(Path.GetDirectoryName(path)!);entry.ExtractToFile(path,true);files.Add(entry.FullName);
  }
  if(register)
  {
   File.Copy(Environment.ProcessPath!,Path.Combine(folder,"Uninstall.exe"),true);files.Add("Uninstall.exe");
   CreateShortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"3D Print Slicer Pro.lnk"),folder);
   var menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"3D Print Slicer Pro");Directory.CreateDirectory(menu);
   CreateShortcut(Path.Combine(menu,"3D Print Slicer Pro.lnk"),folder);
   using var key=Registry.CurrentUser.CreateSubKey(RegistryPath);key.SetValue("DisplayName","3D Print Slicer Pro (Vorschau)");key.SetValue("DisplayVersion","0.11.0");key.SetValue("Publisher","3D Print Slicer Pro");key.SetValue("InstallLocation",folder);key.SetValue("DisplayIcon",Path.Combine(folder,"3D Print Slicer Pro.exe"));key.SetValue("UninstallString","\""+Path.Combine(folder,"Uninstall.exe")+"\" --uninstall");key.SetValue("NoModify",1);key.SetValue("NoRepair",1);
  }
  File.WriteAllText(Path.Combine(folder,ManifestName),JsonSerializer.Serialize(new Manifest{AppId=AppId,InstallPath=folder,Files=files.ToArray(),Registered=register}));
 }
 static void CreateShortcut(string file,string folder)
 {
  var type=Type.GetTypeFromProgID("WScript.Shell")??throw new InvalidOperationException("Windows-Verknüpfungen sind nicht verfügbar.");
  dynamic shell=Activator.CreateInstance(type)!;dynamic shortcut=shell.CreateShortcut(file);shortcut.TargetPath=Path.Combine(folder,"3D Print Slicer Pro.exe");shortcut.WorkingDirectory=folder;shortcut.Description="3D-Modelle lokal teilen und mit Verbindern exportieren";shortcut.Save();
 }
 static void Uninstall(string folder)
 {
  var manifest=ReadManifest(folder);
  if(IsAppRunning(folder))throw new InvalidOperationException("Anwendung läuft noch. Bitte schließen und erneut deinstallieren.");
  // Delete only package-owned paths from the validated installation manifest.
  foreach(var relative in manifest.Files){var file=SafePath(folder,relative);if(File.Exists(file))File.Delete(file);}
  if(manifest.Registered)
  {
   var desktop=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"3D Print Slicer Pro.lnk");if(File.Exists(desktop))File.Delete(desktop);
   var menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"3D Print Slicer Pro");var shortcut=Path.Combine(menu,"3D Print Slicer Pro.lnk");if(File.Exists(shortcut))File.Delete(shortcut);if(Directory.Exists(menu)&&!Directory.EnumerateFileSystemEntries(menu).Any())Directory.Delete(menu);
   Registry.CurrentUser.DeleteSubKeyTree(RegistryPath,false);
  }
  File.Delete(Path.Combine(folder,ManifestName));
  foreach(var dir in Directory.EnumerateDirectories(folder,"*",SearchOption.AllDirectories).OrderByDescending(p=>p.Length))if(!Directory.EnumerateFileSystemEntries(dir).Any())Directory.Delete(dir);
  if(!Directory.EnumerateFileSystemEntries(folder).Any())Directory.Delete(folder);
  MessageBox.Show("3D Print Slicer Pro wurde deinstalliert. Eigene Projekte und Einstellungen wurden beibehalten.","Deinstallation abgeschlossen");
 }
 sealed class Manifest {public string AppId {get;set;}="";public string InstallPath {get;set;}="";public string[] Files {get;set;}=[];public bool Registered {get;set;}}
}

sealed class InstallerForm:Form
{
 readonly TextBox destination=new();readonly Button install=new();readonly Label status=new();readonly CheckBox start=new();
 bool installed;
 public InstallerForm()
 {
  Text="3D Print Slicer Pro · Offline-Setup";ClientSize=new(650,380);StartPosition=FormStartPosition.CenterScreen;BackColor=Color.FromArgb(7,20,30);ForeColor=Color.White;Font=new("Segoe UI",10);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
  var title=new Label{Text="3D Print Slicer Pro",Font=new("Segoe UI",26,FontStyle.Bold),ForeColor=Color.FromArgb(80,220,255),AutoSize=true,Location=new(28,25)};Controls.Add(title);
  Controls.Add(new Label{Text="Vorschauversion 0.11.0 · Windows 10/11 (64 Bit)\nAlle Laufzeiten enthalten. Keine Internetverbindung erforderlich.",AutoSize=true,Location=new(30,90)});
  Controls.Add(new Label{Text="Installationsordner",AutoSize=true,Location=new(30,155)});
  destination.Text=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","3DPrintSlicerPro");destination.SetBounds(30,180,495,30);Controls.Add(destination);
  var browse=new Button{Text="…",Location=new(540,179),Size=new(70,31)};browse.Click+=(_,_)=>{using var dialog=new FolderBrowserDialog{Description="Eigenen Programmordner wählen",UseDescriptionForTitle=true};if(dialog.ShowDialog(this)==DialogResult.OK)destination.Text=Path.Combine(dialog.SelectedPath,"3DPrintSlicerPro");};Controls.Add(browse);
  start.Text="Anwendung nach der Installation starten";start.Checked=true;start.SetBounds(30,226,550,28);Controls.Add(start);
  status.Text="Installation nur für diesen Benutzer · ohne Administratorrechte";status.SetBounds(30,267,590,38);Controls.Add(status);
  install.Text="Installieren";install.SetBounds(430,320,180,38);install.BackColor=Color.FromArgb(0,98,132);install.ForeColor=Color.White;install.FlatStyle=FlatStyle.Flat;Controls.Add(install);
  install.Click+=async(_,_)=>
  {
   if(installed){Close();return;}
   install.Enabled=false;destination.Enabled=false;browse.Enabled=false;status.Text="Dateien werden lokal entpackt …";var folder=destination.Text;
   try{await Task.Run(()=>Program.Install(folder,true));installed=true;status.Text="Installation abgeschlossen.";if(start.Checked)Process.Start(new ProcessStartInfo(Path.Combine(folder,"3D Print Slicer Pro.exe")){UseShellExecute=true,WorkingDirectory=folder});install.Text="Schließen";install.Enabled=true;}
   catch(Exception ex){MessageBox.Show(this,ex.Message,"Installation fehlgeschlagen",MessageBoxButtons.OK,MessageBoxIcon.Error);status.Text="Installation fehlgeschlagen. Bitte Zielordner prüfen.";install.Enabled=true;destination.Enabled=true;browse.Enabled=true;}
  };
 }
}
