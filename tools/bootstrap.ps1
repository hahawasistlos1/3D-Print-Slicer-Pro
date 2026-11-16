param([string]$Python='python')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
New-Item -ItemType Directory -Path runtime,artifacts -Force | Out-Null
$archive=Join-Path $taskRoot 'artifacts\python-embed.zip'
Invoke-WebRequest 'https://www.python.org/ftp/python/3.14.5/python-3.14.5-embed-amd64.zip' -OutFile $archive
Expand-Archive -LiteralPath $archive -DestinationPath runtime -Force
@'
python314.zip
.
Lib/site-packages
../engine
import site
'@ | Set-Content -LiteralPath runtime\python314._pth -Encoding utf8
& $Python -m pip install --target runtime\Lib\site-packages --upgrade --only-binary=:all: -r engine\requirements.txt
if($LASTEXITCODE -ne 0){throw 'Installation der freien Geometriebibliotheken fehlgeschlagen.'}
Write-Host 'Offline-Laufzeit vorbereitet. Nun tools\build.ps1 -Package ausführen.'
