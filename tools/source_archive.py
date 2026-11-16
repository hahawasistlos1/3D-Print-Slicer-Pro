"""Bundle all editable source files, excluding build outputs and runtimes."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
allowed={'.cs','.xaml','.csproj','.manifest','.ico','.png','.py','.ps1','.txt','.md','.sln','.props','.json'}
files=[]
for folder in ('src','engine','tests','tools','docs'):
    for file in (root/folder).rglob('*'):
        if file.is_file() and not {'bin','obj','__pycache__'}&set(file.relative_to(root).parts) and (file.suffix in allowed or file.name.startswith('LICENSE') or 'licenses' in file.relative_to(root).parts):
            files.append(file)
files.extend(root/name for name in ('README.md','THIRD-PARTY-NOTICES.md','3DPrintSlicerPro.sln','Directory.Build.props','global.json','.gitignore'))
with zipfile.ZipFile(root/'artifacts/3DPrintSlicerPro-Quellcode.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(set(files)):archive.write(file,file.relative_to(root).as_posix())
print(f'{len(set(files))} Quelldateien verpackt.')
