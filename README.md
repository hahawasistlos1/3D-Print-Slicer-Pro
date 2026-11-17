# 3D Print Slicer Pro · Vorschau 0.11.6

Lokale Windows-Desktopanwendung in C#/.NET 10 und WPF, mit einem separaten, mitgelieferten Geometrieprozess auf Basis von Manifold. Das Projekt enthält reale Schnitte, Verschlussflächen, integrierte/separate Verbinder, Bohrungen und exportierbare STL-Dateien. Die Oberfläche orientiert sich an der bereitgestellten dunkelblauen/cyanfarbenen Referenz.

**Dies ist eine Vorschau.** Version 0.11.6 bewertet mögliche Schnitte zusätzlich mit räumlichen Verbinderproben. Weitere Details findest du im [Entwicklungsstand](docs/ENTWICKLUNGSSTAND.md).

## Starten

- **Portable:** `artifacts/3DPrintSlicerPro-Portable.zip` vollständig in einen Ordner entpacken und `3D Print Slicer Pro.exe` starten. Alternativ die bereits entpackte EXE unter `artifacts/Portable-0.11.6/` verwenden. Den gesamten Ordner zusammenlassen.
- **Installation:** `artifacts/3DPrintSlicerPro-Setup.exe` starten. Installiert für den aktuellen Benutzer, erstellt Desktop-/Startmenüverknüpfungen und einen Deinstallationseintrag. Keine separat installierte .NET- oder Python-Laufzeit nötig. Das Setup ist nicht digital signiert.
- **Entwickeln:** `3DPrintSlicerPro.sln` in Visual Studio 2026 mit .NET-Desktopentwicklung öffnen. Startprojekt: `SlicerPro`.

Windows 10/11 x64. Für die Anwendung ist keine Internetverbindung, Anmeldung, Cloud oder kostenpflichtige Bibliothek erforderlich. Nur die erstmalige Vorbereitung einer Entwicklungsumgebung benötigt Downloads.

## Bedienung

1. STL, OBJ oder 3MF laden. STL/OBJ-Zahlen werden als Millimeter interpretiert. 3MF-Einheiten werden umgerechnet. Die App löst Modellreferenzen der 3MF Production Extension innerhalb desselben Archivs auf und verarbeitet bis zu vier Millionen Dreiecke, auch nach dem Zusammenfügen.
2. Druckerprofil oder X/Y/Z und Sicherheitsabstand je Seite einstellen.
3. Runddübel, rechteckige Zapfen, gerade Nut/Feder oder seitlichen Schwalbenschwanz sowie integriert, separat, kombiniert oder ohne Verbinder wählen.
4. Die adaptive Strategie oder ein Raster wählen und **Modell schneiden & Verbinder setzen** drücken. Der Fortschritt erscheint unten, **Abbrechen** beendet den isolierten Rechenprozess.
5. Prüfbericht lesen, Teile ansehen und **Export / Druck** wählen.

Die Anwendung öffnet beim Start einen **prozeduralen Demo-Drachen mit echter Geometrie**. Dieser ist nicht das Drachenmodell aus dem Referenzbild. Aus dem einzelnen Referenzbild lässt sich dessen Original-3D-Geometrie nicht übernehmen. Es werden keine festen Beispielresultate als Berechnung ausgegeben.

Orange markierte Teile und Schnittstellen im Prüfbericht benötigen eine Montageprüfung. Eine erfolgreiche Netz-/Druckraumprüfung bedeutet nicht, dass alle Teile verbunden sind. Nach Änderungen der Eingaben muss vor dem STL-Export neu berechnet werden.

**Montagewege prüfen** ist standardmäßig aktiv. Die geradlinige Prüfung folgt XYZ oder der tatsächlichen Einschubrichtung mit vorbestückten separaten Verbindern. Unter Vorschau lassen sich nachgewiesene Einsteckwege stufenlos darstellen. Die Größenautomatik verkleinert Breite, Durchmesser und Einstecktiefe bei Bedarf bis zu den eingestellten Mindestmaßen. Wandreserve und Spiel bleiben erhalten.

Bei Außenschrauben prüft die App den Gewindeeingriff an einzelnen Stellungen mit höchstens 45 Grad Drehwinkel dazwischen. Die übrigen Teile und Verbinder bleiben für die Prüfung in Endlage. Der Prüfbericht und der PDF-Montageplan zeigen Kollisionen und unvollständige Prüfungen an. Zwischenpositionen, unterschiedliche Einschraubreihenfolgen und das Verhalten gedruckter Teile erfordern weitere Prüfung.

Bei **Nut und Feder** sind Breite, Länge entlang der Schnittfläche und Einstecktiefe je Seite unabhängig einstellbar. Die Federlänge bleibt bei Größenautomatik fest. Geprüft werden beide Achsenrichtungen in der Fläche. Die Nut erhält das eingestellte Spiel als Gesamtzugabe in Breite und Länge sowie axiale Zugabe. Es sind gerade, begrenzte rechteckige Segmente mit geschlossenen Nutenden, keine umlaufenden Konturverbindungen. Fehlende sichere Positionen werden im Prüfbericht gemeldet.

Mit **⤾ Modell frei ausrichten** neben den manuellen Schnittoptionen lässt sich das vollständige Modell drehen: Winkel von −360 bis 360 Grad eingeben, **Vorschau aktualisieren**, dann **Ausrichtung anwenden**. Die zusätzliche Drehung erfolgt in den aktuellen Modellachsen, zuerst X, dann Y, dann Z. Anschließend liegt das Modellminimum wieder bei XYZ = 0. Druckteile und manuelle Schnitte werden zurückgesetzt; danach neu schneiden. Rückgängig/Wiederholen stellt die vorherigen berechneten Zustände während der Sitzung wieder her. Die Schnittfamilien bleiben entlang der aktuellen XYZ-Achsen; dadurch können sie schräg zur vorherigen Modelllage verlaufen. Für unabhängige Ebenen öffne **Manuelle Schnitte / Skalieren → Freie Schnittebenen bearbeiten**. Lokale Neuteilung und Zusammenfügen findest du im Kontextmenü einer Teileminiatur.

In **Freie Schnittebenen** drehst du die Ebene mit **Richtung** nach links oder rechts und mit **Neigung** nach oben oder unten. **Alt+Klick** auf das Modell setzt den Drehpunkt. Die Winkel lassen sich auch direkt eintippen oder am fokussierten Griff mit den Pfeiltasten ändern. **Ebene hinzufügen** oder **Ändern** übernimmt die Vorschau in die Liste. **Neu berechnen** führt den Schnitt aus.

Die adaptive Schnittplanung bevorzugt bei Runddübeln, rechteckigen Steckverbindern und Nut und Feder Schnitte mit Platz für mindestens eine räumliche Verbinderprobe. Diese prüft die eingestellte Wandreserve über die gesamte Einstecktiefe. Der Prüfbericht zeigt die Anzahl der Proben und der gewählten Schnitte mit erfolgreicher Probe. Die endgültige Platzierung prüft danach die tatsächlichen Teile, die Verbinder und den Druckraum.

Mit **Schnitt-Einstellungen → Nach Farbe trennen** werden geschlossene Farbgruppen einer 3MF-Datei zu einzelnen Druckteilen. Die Strategie übernimmt 3MF-Basismaterialien, Farbgruppen und eindeutige Filamentzuweisungen pro Körper aus Bambu Studio oder OrcaSlicer. Auch standardkonforme Dreiecksfarben lassen sich trennen, wenn genau zwei Farben durch eine geschlossene Grenze in einer Ebene eindeutig auf zwei Seiten liegen. Freie Bemalung, proprietäre Bemalungsdaten, Texturen und Farbverläufe benötigen separat definierte Volumenkörper.

Zu große Farbteile werden für den Druckraum weiter unterteilt. Mit **Verbinder zwischen Farbgruppen** sucht die App zusätzlich gemeinsame ebene Kontaktflächen, auch schräge, und prüft die Verbindergeometrie mit der eingestellten Wandreserve. **Ohne Verbinder schneiden** schaltet alle Verbinder ab. Teilevorschau und 3MF-Einzelexport übernehmen die Farbwerte. Die Suche nach Farbkontakten begrenzt den Aufwand bei sehr dichten Netzen und zeigt in diesem Fall eine Meldung.

Unter **Einstellungen → Ausführliche Dünnwandprüfung** werden bis zu 200.000 Dreiecksmittelpunkte in Druckteilen und separaten Verbindern geprüft. Das Ergebnis bleibt eine Messung an Stichproben. Die Schwelle in Millimetern bestimmt, welche Messungen als Dünnwand-Hinweise erscheinen.

Wenn beim Laden eine größere Öffnung in einer vorhandenen ebenen Fläche gefunden wird, bietet die App die **erweiterte Netzreparatur** für diesen Import an. Sie prüft Randlinien mit bis zu 96 Kanten und einem Durchmesser von höchstens 40 mm beziehungsweise 35 % der größten Ausdehnung des betroffenen Netzes. Es gilt jeweils der kleinere Wert. Die App verwirft Reparaturflächen, die vorhandene Geometrie kreuzen, und speichert den Befund im Projekt. Die Quelldatei bleibt unverändert.

Nach dem ersten Schnitt **Verbinderpositionen bearbeiten …** öffnen und eine Schnittstelle wählen. In der 3D-Ansicht der Kontaktfläche fügt ein Klick einen Mittelpunkt hinzu. Eine Koordinatenzeile wählen und mit **Strg+Klick** ersetzen. Die Punkte sind nummeriert. Mit **Punkte dieser Fläche leeren** und **Neu berechnen** kehrt diese Schnittstelle zur Automatik zurück. Die Koordinateneingabe funktioniert auch bei älteren Ergebnissen und bei sehr komplexen Flächen ohne 3D-Vorschau.

Die Vorschau lässt sich mit der linken Maustaste drehen, dem Mausrad zoomen und der rechten Maustaste oder Umschalt+Ziehen verschieben. Die Kameras sind synchronisiert. Doppelklick setzt die Kamera zurück. Teile anklicken; Rechtsklick auf ein Vorschaubild bietet Ein-/Ausblenden und Einzelexport. Die Punkte-Schaltfläche öffnet Transparenz, Explosionsabstand und Montageschritte.

Große Anzeigenetze werden separat vereinfacht, ohne einzelne Dreiecke auszulassen. Geschlossene Flächen, Hohlraumschalen, Durchbrüche, Volumen und Montageposition werden geprüft. Die Anzeige nennt die tatsächlichen Dreieckszahlen; Details stehen unter Vorschau. Dort lässt sich auch **Vollständige Originalnetze anzeigen** aktivieren. Wird ein Anzeigeziel innerhalb der Qualitätsgrenzen nicht erreicht, bleibt das komplette Netz erhalten und kann langsamer sein. Die vollständige Fertigungsgeometrie bleibt für Schnitt, Projekt und Export erhalten. Vorschauen werden für unveränderte Quellen während der Sitzung wiederverwendet.

`Strg+O`: Modell laden. `Strg+S`: Projekt speichern. `Strg+Z`/`Strg+Y`: vorherige berechnete Projektzustände. Drag-and-drop unterstützt Modelle und `.3dps`-Projekte.

Projekte enthalten die aktuelle ungeteilte, gegebenenfalls skalierte oder ausgerichtete Geometrie, Resultate und Parameter als ZIP-basiertes `.3dps`-Format. Die importierte Ausgangsdatei wird nicht überschrieben. Exportierte Teile liegen in Druckausrichtung mit Minimum XYZ = 0 vor. Der Montageplan verwendet die Montagekoordinaten des aktuell berechneten Modells.

Unter **Export / Druck** lässt sich STL, OBJ oder 3MF für alle Druckteile und separaten Verbinder wählen. Jedes Teil erhält eine eigene Datei. Beim Einzelteil-Export über das Kontextmenü der Miniatur stehen dieselben Formate zur Wahl. 3MF speichert ausdrücklich Millimeter; bei STL/OBJ im Zielprogramm Millimeter wählen. Es werden Geometriedateien ohne Druckerprofile, Stützen oder G-Code ausgegeben. `Exportdateien.json` im Gesamtexport ordnet die Dateien und ihre Druckausrichtungen zu. Original und Projekt enthalten weiterhin die intern verwendete STL-Geometrie.

## Bauen und prüfen

```powershell
# Nur falls runtime/ noch fehlt; benötigt 64-Bit-Python mit pip und Internet:
.\tools\bootstrap.ps1

# Kompilieren und Geometrie-/Integrationstests:
.\tools\build.ps1

# Zusätzlich portable ZIP und eigenständiges Offline-Setup erzeugen:
.\tools\build.ps1 -Package
```

Erforderlich: .NET 10 SDK. Das eingecheckte `global.json` verwendet 10.0.403 mit Feature-Rollforward. Die Laufzeitpakete werden beim ersten Publish von NuGet bezogen; danach ist ein Build mit gefülltem Cache offline möglich. Laufzeitversionen werden vom SDK gewählt.

Die Geometrietests benötigen kein pytest und verwenden die lokale Laufzeit:

```powershell
.\runtime\python.exe tests\test_geometry.py
.\runtime\python.exe tests\test_planning.py
.\runtime\python.exe tests\test_motion.py
.\runtime\python.exe tests\test_tongue.py
.\runtime\python.exe tests\test_export.py
.\runtime\python.exe tests\test_preview.py
.\runtime\python.exe tests\test_orientation.py
dotnet run --project tests\SlicerPro.Integration -c Release -- (Get-Location).Path
```

Integrationstests setzen `artifacts/demo.stl` voraus, das `tools/build.ps1` automatisch erzeugt. Vor einem erneuten Build die laufende Entwicklungs-EXE schließen. Prüfprotokolle und Beispiele stehen unter `artifacts/`.

## Dateien und Einstellungen

`%LOCALAPPDATA%/3DPrintSlicerPro/` enthält lokale Einstellungen, Rechensitzungen und `errors.log`. Sitzungen bleiben zur Wiederherstellung und für Rückgängig erhalten; eine automatische Speicherbereinigung ist noch nicht implementiert. Zur isolierten Entwicklung kann `SLICERPRO_DATA_DIR` auf einen Testordner gesetzt werden. Nutzerprojekte werden am gewählten Speicherort abgelegt und bei der Deinstallation beibehalten.

Architektur: [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md). Dateiformat: [docs/DATEIFORMAT.md](docs/DATEIFORMAT.md). Freie Bibliotheken und Lizenztexte: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
