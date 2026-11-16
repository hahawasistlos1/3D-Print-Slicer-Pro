# Architektur

## Benutzeroberfläche und Anzeige

`src/SlicerPro/MainWindow.xaml` implementiert die Referenzanordnung mit echten WPF-Steuerelementen. `Controls/ModelViewport.cs` verwendet native `Viewport3D`-Geometrie ohne Browser und Webzugriff. Das Referenzbild ist kein Bestandteil der Laufzeitdarstellung. Materialien, Gitternetz und Konturen werden als native Meshes erzeugt. Verbinderzeichen sind auf die tatsächlichen 3D-Positionen projizierte Annotationen.

Die erste Version verwendet Code-behind als Orchestrator und getrennte Services/Modelle. Vor größeren UI-Erweiterungen empfiehlt sich eine Extraktion in einzelne ViewModels; ein vollständiges MVVM-Framework ist keine Laufzeitabhängigkeit.

Seit 0.6 erzeugt `engine/preview.py` separate geschlossene Anzeigenetze über `Manifold.simplify`. Bis zu sechs Toleranzen werden vom vollständigen Ausgangskörper aus untersucht. Das Maximum ist das kleinere Maß aus 0,25 mm und 0,1 % der größten Körperausdehnung. Kandidaten müssen Status, geschlossene konsistente Netze, Vorzeichen/Genus aller Schalen, höchstens 0,5 % Volumenänderung und passende Bounds erhalten. Die tatsächliche geschriebene Float32-STL wird erneut geprüft. Das Dreiecksziel ist weich: Es werden keine Flächen entfernt, um es zu erzwingen.

`Services/PreviewService.cs` hält einen Sitzungscache nach Quellpfad, Länge, Änderungszeit und Anzeigeziel. Original und Teile werden im separaten Worker vorbereitet; Teilkoordinaten bleiben erhalten. Die Cachedateien liegen in eigenen Sitzungsordnern, werden weder zur Fertigung verwendet noch ins Projekt aufgenommen. `ModelViewport.LoadStl` liest sämtliche Dreiecke seines Eingabenetzes. Der Originalnetzmodus umgeht die Vereinfachung; beide Varianten sind vom Schnitt-/Exportmodell getrennt.

Seit 0.3 verwendet die Montagevorschau die gespeicherten nachgewiesenen Teilfolgen, Richtungen und Verschiebevektoren. Der Einsteckpositions-Regler verschiebt die tatsächliche Teilgeometrie und ihre mitgeführten Dübel auf diesem Weg; ungeprüfte Abläufe erhalten diesen Regler nicht.

## Import, Analyse und Geometrie

`engine/geometry.py` trennt Import (`load_model`, `read_3mf`), Netzprüfung (`solid_of`, `info`), Rasterplanung (`plan`), Geometrieschnitte (`slice_model`), Verbindergenerierung (`connector`), Platzierungs-/Kollisionsprüfungen und Export (`write_stl`). `engine/planning.py` ergänzt adaptive lokale Schnittbäume, Querschnittsbewertung, echte gemeinsame Schnittflächen und Kandidaten aus erodierten Polygonen. `engine/components.py` fasst äußere Schalen mit ihren eingeschlossenen Hohlraumschalen zu zusammenhängenden Materialkörpern zusammen.

Manifold liefert native robuste Volumenoperationen. Trimesh liest/schreibt STL und OBJ und analysiert die Netze. Core-3MF wird mit ZIP/XML der Standardbibliothek eingelesen. NumPy verwaltet Geometriearrays. Nur diese Bibliotheken und CPython sind enthalten; keine Netzwerkdienste oder Benutzerkonten.

Der adaptive Planer untersucht pro übergroßem Körper lokale Querschnitte und führt die besten Vorschläge als echte Schnitte aus. Bereits passende Materialkörper bleiben erhalten. Die Suchbewertung ist auf 1024 Querschnitte begrenzt. Der Rasterplaner bleibt als alternative Strategie verfügbar. Beide berücksichtigen bis zu sechs Druckraumachsenanordnungen. Für integrierte Verbindungen wird Einstecktiefe im Basismaß reserviert. Jeder finale Körper wird erneut auf den nutzbaren Druckraum geprüft. Die Druckausrichtung des Exports wird tatsächlich auf alle Eckpunkte und die Dreiecksorientierung angewendet.

Verbinderzentren werden auf überlappenden Nachbarflächen gesucht. Eine vergrößerte 3D-Prüfhülle muss vollständig in beiden Ausgangsteilen liegen. Sie berücksichtigt Durchmesserspiel, Wandreserve und zusätzliche Tiefe. Vorherige Verbinderhüllen dürfen sich nicht überschneiden. Booleans erzeugen anschließend die echten Taschen bzw. den verankerten Zapfen. Getrennte oder zu große Teile werden nicht als gültig freigegeben.

Seit 0.4 erzeugt `connector` gerade rechteckige Nut/Feder-Segmente. `connector_candidates` untersucht beide tangentialen Achsen. Verschobene Schnittpolygone begrenzen zunächst mögliche Rechteckzentren; diese notwendige Eckbedingung reicht bei konkaven Flächen nicht aus. Deshalb erfolgt anschließend dieselbe vollständige Volumenprüfung der vergrößerten Hülle. Die Länge bleibt auch bei Größenautomatik fest, Breite und Tiefe werden abgestuft.

## Hintergrundverarbeitung und Fehler

`engine/orientation.py` bildet eine starre Drehmatrix Rz · Ry · Rx und wendet sie auf das vollständige Modell an. Das neue Minimum wird anschließend auf Null verschoben. Volumen, geschlossene Netze, Schalentopologie und die tatsächlich geschriebene STL werden geprüft. `Services/ModelOrientation.cs` verwendet dieselbe Winkelkonvention für die separate Anzeigenetzvorschau. Eine neue Sitzung ersetzt den vorherigen Modellordner nicht. Vorhandene Druckteile und manuelle Schnitte gehören zur alten Lage und werden bei Übernahme zurückgesetzt.

`RenderWorkspace` bereitet Original- und sämtliche Teilnetze zunächst lokal im Hintergrund vor. Erst danach werden Projektzustand, Anzeigenetze und Historie gemeinsam auf dem UI-Thread übernommen. Bei Abbruch vor dieser Übernahme bleiben vorherige Geometrie, Anzeige und Undo-/Redo-Stapel bestehen. Auch Rückgängig/Wiederholen entnimmt einen Zustand erst nach erfolgreicher Vorbereitung aus dem jeweiligen Stapel.

`Services/GeometryService.cs` startet `runtime/python.exe` ohne Shell. `engine/worker.py` verarbeitet jeweils eine JSON-Auftragsdatei und liefert zeilenweise JSON-Fortschritt. Fehler führen zu einem Prozessfehler und einer verständlichen Meldung; Tracebacks werden lokal protokolliert. Abbrechen beendet den Prozessbaum. Ein altes Ergebnis bleibt bis zum erfolgreichen Ende der neuen Berechnung erhalten.

Jobs schreiben in neue Sitzungsverzeichnisse. Ein abgebrochener Export bleibt ausdrücklich mit `.unvollstaendig` im Namen erkennbar. Der Exportordner erhält den endgültigen Namen erst nach Fertigstellung aller Geometriedateien und Metadaten.

## Durchgehende Bewegungsprüfung

`engine/motion.py` versucht eine geradlinige Einzelteil-Demontage. Aktive Verbinder liefern ihre jeweilige Einsteckrichtung, auch schräg zu XYZ. Separate Dübel werden als starre, vorbestückte Bestandteile ihres unteren Hostteils A mitgeführt. Zunächst wird ihre Vorbestückungsfolge am jeweiligen Hostteil geprüft. Die Teil-Demontage wird anschließend für die Montage umgekehrt.

Die konvexe Hülle von Start-/Endkörper ist eine konservative Freiprüfung. Nur ihre Kollisionsfreiheit kann einen Weg freigeben; eine Hüllenüberschneidung verlangt eine genauere Prüfung. Dafür werden führende Dreiecke mit dem Verschiebevektor zu Dreiecksprismen extrudiert und gegen stationäre Körper geschnitten. Anfangsüberschneidungen, ungültige Prismen, numerisch nicht sicher ausschließbare Restvolumina und Budgetüberschreitungen können keine Erfolgsfreigabe erzeugen. Kleine Restvolumina werden je Hindernis über Körper und Prismen begrenzt aufsummiert.

Die Prüfung verwendet Einzelteiltranslationen entlang der Verbinderrichtung oder entlang XYZ bei ungebundenen Teilen. Sie löst keine Bewegungen mit Drehung, Flexibilität oder gleichzeitig bewegten Teilgruppen. Eine unbekannte gerade Folge wird deshalb nicht als Beweis allgemeiner Unmontierbarkeit ausgegeben.

## Projekte, Montage und Einstellungen

`engine/exporting.py` schreibt STL, OBJ oder Core-3MF. `mesh_for_export` wendet eine geprüfte Achsenpermutation an, korrigiert bei ungerader Permutation die Windung und verschiebt das Minimum auf Null. Die Ausgabe wird zunächst in eine eindeutig benannte temporäre Datei geschrieben. Ein erneuter Import muss ein geschlossenes, konsistent orientiertes Netz mit erhaltenem Volumen und richtigen Druckmaßen ergeben; erst dann wird die Zieldatei atomar ersetzt. Für einen abweichend benannten temporären Pfad kann das Format ausdrücklich im Auftrag stehen. `Services/GeometryExport.cs` und der Exportdialog bieten die drei Formate auch für Einzelteile an.

3MF wird mit ZIP/XML der Standardbibliothek als ein Core-Meshobjekt je Datei geschrieben; es benötigt keine optionale Erweiterung. Die Geometrie wird gestreamt, ohne einen zusätzlichen vollständigen XML-Baum für die Ausgabe anzulegen. OBJ verwendet 1-basierte Dreiecksindizes, Millimeterkommentar und keine Materialreferenzen. Die interne Projektgeometrie bleibt STL. Der Gesamtexport enthält zusätzlich `Exportdateien.json` für die Zuordnung von Quelldatei, Ausgabe und Druckachsen.

`Services/ProjectService.cs` schreibt ein vollständiges Projekt zunächst als temporäres ZIP und ersetzt die Zieldatei erst nach erfolgreichem Abschluss. Beim Öffnen werden Größen- und Pfadgrenzen geprüft. Ergebnisdateien müssen direkt innerhalb des Resultatordners liegen.

`Services/AssemblyService.cs` erzeugt einen mehrseitigen PDF-Montageplan ohne zusätzliche Bibliothek. Zuordnungen enthalten Verbinder-ID, beide Teilenummern, Achse, Maße, Toleranz und Variante. Wenn der eingeschränkte Bewegungsnachweis gelingt, wird dessen umgekehrte Demontagefolge verwendet. Andernfalls bleibt die Sortierung nach Z, Y, X lediglich ein geometrischer Vorschlag.

Einstellungen und Druckerprofile liegen unter `%LOCALAPPDATA%/3DPrintSlicerPro/preferences.json`. In einer Testsitzung kann `SLICERPRO_DATA_DIR` gesetzt werden. Original- und Exportdateien des Benutzers werden nicht durch Rechenjobs verändert.

## Distribution

`tools/bootstrap.ps1` lädt CPython und festgelegte freie Python-Wheels. `tools/build.ps1 -Package` prüft das Projekt und erzeugt einen eigenständigen `win-x64`-Publish inklusive .NET und Python sowie ein ZIP-Paket. Das Setup-Projekt bettet dieses ZIP direkt in eine eigenständige EXE ein.

Der Installer installiert nur für den aktuellen Benutzer. Deinstallation entfernt ausschließlich die im geprüften Installationsmanifest enthaltenen Programmdateien und die zugehörigen Verknüpfungen/Registrierung. Projektdateien und lokale Benutzereinstellungen liegen außerhalb dieses Manifests. Die ausführbare Deinstallation kopiert sich zum Entfernen der installierten EXE in einen temporären Ordner.

## Manuelle Geometriebearbeitung ab 0.8

engine/manual_planes.py verarbeitet die geordnete Liste der Bearbeitungen nach der Basisplanung und vor der Verbinderplatzierung. Schrägen Ebenen ist eine lokale orthonormale Basis zugeordnet. Reale planare Kontaktregionen werden in dieser Basis bewertet; Verbinder und Aussparungen werden in Modellkoordinaten zurücktransformiert. Beim Zusammenfügen werden die Körper ohne Steckgeometrie vereinigt und die tatsächlichen verbleibenden Schnittkappen für die Kontaktprüfung verwendet. Volumen, Zusammenhang und Druckraum werden geprüft. Die App übernimmt Änderungen erst nach erfolgreicher Berechnung und Vorbereitung der Anzeigenetze.


## Seitlicher Einschub und Druckhinweise ab 0.9

engine/dovetail.py extrudiert das hinterschnittene Profil in der lokalen Schnittebene. Der Werkzeugkörper reicht bis hinter die Außenkante. Teilgetrennte Wandreserveproben umfassen den vorgesehenen Materialbereich bis zur Öffnung. Die Bewegungsprüfung erhält den tangentialen Weg des Teils und den separaten Auszugsvektor des Schlüssels. Manuelle Positionen werden vor der Automatik verarbeitet und bleiben an Schnittstelle und Teileschlüsseln gebunden. engine/print_checks.py misst beschränkt normal zur Oberfläche und summiert steile nach unten gerichtete Flächen in Druckausrichtung.
