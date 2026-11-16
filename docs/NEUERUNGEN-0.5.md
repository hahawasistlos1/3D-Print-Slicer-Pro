# Vorschau 0.5 · OBJ- und 3MF-Export

## Formate wählen

Unter „Export / Druck“ steht vor der Zielordnerwahl eine Auswahl für STL, OBJ oder 3MF. Alle Druckteile und separaten Verbinder werden im gewählten Format als einzelne Dateien ausgegeben. Der Einzelteil-Export über das Kontextmenü der Miniatur bietet dieselben Formate an.

3MF enthält ein Core-Meshobjekt und die Maßeinheit Millimeter. OBJ enthält Dreiecke, einen Millimeterkommentar und keine Material- oder Texturreferenzen. Bei OBJ/STL im Zielprogramm Millimeter einstellen. Es werden keine Druckerprofile, Farben, Stützen oder G-Code ausgegeben. Die 3MF-Paketstruktur richtet sich nach der [Core-Spezifikation des 3MF Consortiums](https://3mf.io/spec/core-v1-3-0/).

## Geometrie und Dateien schützen

Alle Formate erhalten echte Druckausrichtung und Minimum XYZ = 0. Eine ungerade Achsenpermutation korrigiert auch die Dreiecksorientierung. Geschlossene Hohlräume und die tatsächlichen Nuten und Federn bleiben erhalten. Nach dem Schreiben wird das Netz erneut importiert und auf Gültigkeit, Volumen und Druckmaße geprüft. Vorhandene Zieldateien werden erst danach ersetzt.

Der bisherige Einzelteil-Export konnte bei der Nachprüfung seiner `.tmp`-Datei scheitern. Das Format wird jetzt ausdrücklich mitgegeben. Auch das Normalisieren ohne Achsenwechsel funktioniert mit schreibgeschützten nativen Mesharrays.

Das Kontextmenü der Miniaturen verwendet nun zum dunklen Design passende Farben, damit seine Einträge lesbar sind.

Im Gesamtexport ordnet `Exportdateien.json` die ausgegebenen Namen und Druckachsen zu. Original und `.3dps`-Projekt enthalten weiterhin die unveränderte intern gespeicherte STL-Geometrie. Der Montageplan beschreibt die Montagepositionen unabhängig vom Ausgabeformat.

## Prüfung und Grenzen

80 Python-Tests einschließlich 14 neuer Exporttests; zusätzlich C#-Integration mit dem echten Worker und Reimport aller drei Formate. Die Exporttests umfassen alle sechs Achsenpermutationen, Hohlräume, echte Nut/Feder-Geometrie, 3MF-Struktur und Dateierhalt bei Schreib- oder Prüfungsfehlern.

Kein gemeinsames automatisches Druckbett-Packing und keine herstellerspezifischen Slicer-Projekte. Freie Schnittwinkel, weitere Verbindungstypen, Montagebewegungen mit Drehungen und globale Festigkeitsanalyse bleiben offen.
