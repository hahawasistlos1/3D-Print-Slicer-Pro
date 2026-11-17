param([switch]$Package,[switch]$SkipTests)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$env:DOTNET_CLI_TELEMETRY_OPTOUT='1'
$env:MSBuildEnableWorkloadResolver='false'
$env:DOTNET_CLI_HOME=Join-Path $taskRoot 'artifacts\dotnet-home'
function Invoke-Dotnet {
 & dotnet @args
 if($LASTEXITCODE -ne 0){throw "dotnet ist fehlgeschlagen: $args"}
}
if(-not(Test-Path 'runtime\python.exe')){throw 'Lokale Laufzeit fehlt. Zuerst tools\bootstrap.ps1 ausführen.'}
& .\runtime\python.exe tools\make_icon.py
if($LASTEXITCODE -ne 0){throw 'App-Symbol konnte nicht erzeugt werden.'}
Invoke-Dotnet build 3DPrintSlicerPro.sln -c Release --ignore-failed-sources '-m:1'
if(-not $SkipTests){
 & .\runtime\python.exe tests\test_geometry.py 2>&1 | Tee-Object -FilePath artifacts\geometry-tests.log
 if($LASTEXITCODE -ne 0){throw 'Geometrietests fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_planning.py 2>&1 | Tee-Object -FilePath artifacts\planning-tests.log
 if($LASTEXITCODE -ne 0){throw 'Tests der adaptiven Schnittplanung fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_motion.py 2>&1 | Tee-Object -FilePath artifacts\motion-tests.log
 if($LASTEXITCODE -ne 0){throw 'Montageweg- oder Größenautomatiktests fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_tongue.py 2>&1 | Tee-Object -FilePath artifacts\tongue-tests.log
 if($LASTEXITCODE -ne 0){throw 'Nut-und-Feder-Tests fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_export.py 2>&1 | Tee-Object -FilePath artifacts\export-tests.log
 if($LASTEXITCODE -ne 0){throw 'STL-/OBJ-/3MF-Exporttests fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_preview.py 2>&1 | Tee-Object -FilePath artifacts\preview-tests.log
 if($LASTEXITCODE -ne 0){throw 'Tests der geschlossenen Vorschau fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_orientation.py 2>&1 | Tee-Object -FilePath artifacts\orientation-tests.log
 if($LASTEXITCODE -ne 0){throw 'Tests der Modellausrichtung fehlgeschlagen.'}
 & .\runtime\python.exe tests\test_manual_planes.py 2>&1 | Tee-Object -FilePath artifacts\manual-edit-tests.log
 if($LASTEXITCODE -ne 0){throw 'Tests der manuellen Geometriebearbeitung fehlgeschlagen.'}
 & .\runtime\python.exe -B tests\test_connector_updates.py 2>&1 | Tee-Object -FilePath artifacts\connector-update-tests.log
 if($LASTEXITCODE -ne 0){throw 'Tests der neuen Verbinder und Druckhinweise fehlgeschlagen.'}
 & .\runtime\python.exe -B tests\test_special_connectors.py 2>&1 | Tee-Object -FilePath artifacts\special-connector-tests.log
 if($LASTEXITCODE -ne 0){throw 'Steckclip- und Gewindetests fehlgeschlagen.'}
 & .\runtime\python.exe -B tests\test_three_mf.py 2>&1 | Tee-Object -FilePath artifacts\3mf-import-tests.log
 if($LASTEXITCODE -ne 0){throw 'Mehrteilige 3MF-Importtests fehlgeschlagen.'}
 & .\runtime\python.exe -B tests\test_mesh_repair.py 2>&1 | Tee-Object -FilePath artifacts\mesh-repair-tests.log
 if($LASTEXITCODE -ne 0){throw 'Tests der Netzreparatur fehlgeschlagen.'}
 & .\runtime\python.exe -B tests\test_mesh_repair.py --example artifacts\mesh-repair-test.3mf
 if($LASTEXITCODE -ne 0){throw 'Reparatur-Testarchiv konnte nicht erzeugt werden.'}
 & .\runtime\python.exe -B tests\test_mesh_repair.py --large-example artifacts\mesh-repair-large-test.3mf
 if($LASTEXITCODE -ne 0){throw 'Testarchiv für die erweiterte Reparatur konnte nicht erzeugt werden.'}
 & .\runtime\python.exe -B tests\test_mesh_repair.py --contact-example artifacts\mesh-index-test.3mf
 if($LASTEXITCODE -ne 0){throw 'Testarchiv für indizierte Netze konnte nicht erzeugt werden.'}
 & .\runtime\python.exe -B tests\test_three_mf.py --example artifacts\multipart-3mf-test.3mf
 if($LASTEXITCODE -ne 0){throw '3MF-Testarchiv konnte nicht erzeugt werden.'}
 & .\runtime\python.exe -B tests\test_three_mf.py --color-example artifacts\farben-test.3mf
 if($LASTEXITCODE -ne 0){throw '3MF-Testarchiv für Farbtrennung konnte nicht erzeugt werden.'}
 & .\runtime\python.exe -c "from geometry import demo_dragon,write_stl,md; write_stl(demo_dragon(),'artifacts/demo.stl'); write_stl(md.Manifold.cube((300,100,80)),'artifacts/box.stl')"
 & .\runtime\python.exe -c "from geometry import md,write_stl; write_stl(md.Manifold.sphere(50,512),'artifacts/preview-dense.stl')"
 if($LASTEXITCODE -ne 0){throw 'Dichtes Vorschaumodell konnte nicht erzeugt werden.'}
 Invoke-Dotnet run --project tests\SlicerPro.Integration -c Release -- $taskRoot
}
if($Package){
 $packageVersion=([xml](Get-Content -LiteralPath Directory.Build.props -Raw)).Project.PropertyGroup.Version
 $portable=Join-Path $taskRoot ("artifacts\Portable-"+$packageVersion)
 # RuntimeFrameworkVersion can be overridden; default uses the installed SDK patch.
 Invoke-Dotnet publish src\SlicerPro -c Release -r win-x64 --self-contained true -o $portable --ignore-failed-sources
 Copy-Item -LiteralPath runtime -Destination $portable -Recurse -Force
 Copy-Item -LiteralPath docs -Destination $portable -Recurse -Force
 Copy-Item -LiteralPath README.md,THIRD-PARTY-NOTICES.md -Destination $portable -Force
 $runtimeConfig=Get-Content -LiteralPath (Join-Path $portable '3D Print Slicer Pro.runtimeconfig.json') -Raw | ConvertFrom-Json
 $runtimeVersion=$runtimeConfig.runtimeOptions.includedFrameworks[0].version
 $assets=Get-Content -LiteralPath src\SlicerPro\obj\project.assets.json -Raw | ConvertFrom-Json
 $packageRoot=$assets.packageFolders.PSObject.Properties.Name | Select-Object -First 1
 $licenses=Join-Path $portable 'docs\licenses'
 New-Item -ItemType Directory -Path $licenses -Force | Out-Null
 foreach($runtimePackageName in @('microsoft.netcore.app.runtime.win-x64','microsoft.windowsdesktop.app.runtime.win-x64')){
  $packageFolder=Join-Path $packageRoot "$runtimePackageName\$runtimeVersion"
  Get-ChildItem -LiteralPath $packageFolder -File | Where-Object { $_.Name -like '*LICENSE*' -or $_.Name -like '*NOTICE*' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $licenses ($runtimePackageName+'-'+$_.Name)) -Force }
 }
 # Refresh archive without extracting/removing any user-owned directory.
 $payload=Join-Path $taskRoot 'artifacts\payload.zip'
 if(Test-Path -LiteralPath $payload){Remove-Item -LiteralPath $payload}
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 [IO.Compression.ZipFile]::CreateFromDirectory($portable,$payload,[IO.Compression.CompressionLevel]::Optimal,$false)
 Copy-Item -LiteralPath $payload -Destination artifacts\3DPrintSlicerPro-Portable.zip -Force
 Invoke-Dotnet publish src\SlicerPro.Setup -c Release -o artifacts\Setup --ignore-failed-sources
 Copy-Item -LiteralPath 'artifacts\Setup\3DPrintSlicerPro-Setup.exe' -Destination artifacts\3DPrintSlicerPro-Setup.exe -Force
 & .\runtime\python.exe tools\source_archive.py
 if($LASTEXITCODE -ne 0){throw 'Quellcodearchiv fehlgeschlagen.'}
 Get-FileHash -Algorithm SHA256 -LiteralPath artifacts\3DPrintSlicerPro-Portable.zip,artifacts\3DPrintSlicerPro-Setup.exe,artifacts\3DPrintSlicerPro-Quellcode.zip | ForEach-Object { $_.Hash+'  '+[IO.Path]::GetFileName($_.Path) } | Set-Content -LiteralPath artifacts\SHA256.txt
}
