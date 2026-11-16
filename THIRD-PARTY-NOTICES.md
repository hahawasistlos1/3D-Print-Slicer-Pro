# Drittanbieter und Lizenzen

Die Anwendung benötigt keine kostenpflichtigen Bibliotheken. Die nachstehenden Komponenten werden unverändert als lokale Laufzeitpakete verteilt. Ihre Lizenztexte bleiben in den mitgelieferten Verzeichnissen erhalten. Die Lizenzangaben wurden anhand der offiziellen Projekte und der installierten Paketmetadaten geprüft.

| Komponente | Version | Lizenz / Quelle | Mitgelieferter Lizenztext |
|---|---|---|---|
| Manifold / manifold3d | 3.5.4 | Apache-2.0 · https://github.com/elalish/manifold | `runtime/Lib/site-packages/manifold3d-3.5.4.dist-info/licenses/LICENSE` |
| Trimesh | 4.11.1 | MIT · https://github.com/mikedh/trimesh | `runtime/Lib/site-packages/trimesh-4.11.1.dist-info/licenses/LICENSE.md` |
| NumPy | 2.4.2 | BSD-3-Clause mit zusätzlichen gebündelten Komponenten · https://numpy.org/ | `runtime/Lib/site-packages/numpy-2.4.2.dist-info/licenses/` |
| CPython | 3.14.5 x64 | PSF License und gebündelte Komponenten · https://www.python.org/ | `runtime/LICENSE.txt` |
| .NET / WPF / Windows Desktop | 10.x, vom SDK gepinnter Patch im Publish | MIT und Drittanbieterhinweise · https://github.com/dotnet/runtime und https://github.com/dotnet/wpf | `docs/licenses/microsoft.*` im Publish-Verzeichnis |

Die NumPy-Lizenzdatei enthält unter anderem die einschlägigen Hinweise für OpenBLAS/LAPACK und weitere im Wheel enthaltene Komponenten. Die Manifold-Wheel-Lizenzinformationen müssen bei einer Neuverteilung ebenso erhalten bleiben. Die Python-Distribution enthält zusätzliche Komponenten wie OpenSSL, libffi, SQLite und deren Hinweise in ihrer Lizenzsammlung.

Keine UI-Grafik wurde aus dem Referenzbild ausgeschnitten oder als statischer Hintergrund verwendet. Logo, App-Symbol, Hintergründe und Panels sind durch Code/Vectorpfade erstellt. Der Demo-Drache wird lokal prozedural aus Volumenkörpern und Polygonen erzeugt.

Die Anwendung selbst stellt keinerlei Netzwerkverbindung her. Dokumentationslinks dienen ausschließlich der Quellenangabe; sie werden für die Programmausführung nicht benötigt.
