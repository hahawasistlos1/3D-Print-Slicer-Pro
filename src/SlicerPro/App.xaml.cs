using System.IO;
using System.Windows;
namespace SlicerPro;
public partial class App : Application
{
 public App() { DispatcherUnhandledException += (_, e) => { Log(e.Exception); MessageBox.Show(e.Exception.Message, "3D Print Slicer Pro · Fehler", MessageBoxButton.OK, MessageBoxImage.Error); e.Handled = true; }; }
 public static string DataRoot => Environment.GetEnvironmentVariable("SLICERPRO_DATA_DIR") is {Length:>0} custom ? Path.GetFullPath(custom) : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "3DPrintSlicerPro");
 public static void Log(Exception e) { try { Directory.CreateDirectory(DataRoot); File.AppendAllText(Path.Combine(DataRoot,"errors.log"),$"{DateTime.Now:O} {e}\n"); } catch { } }
}
