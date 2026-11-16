# Tatsächlicher Entwicklungsstand · 0.11.0

## Funktionsfähig

| Bereich | Implementierung |
|---|---|
| Desktop | C#/.NET 10, WPF, deutsche Oberfläche, Referenzanordnung mit dunklen Panels und cyanfarbenen Akzenten |
| Import | Binäres/ASCII-STL, OBJ ohne Materialien, Core-3MF und archivinterne Modellreferenzen der Production Extension, mit Einheiten und Transformationen |
| Geometrie | Geschlossene Volumenkörper mit nativen Manifold-Operationen; echte Schnittkappen; zusammenhanglose Komponenten werden zu eigenen Teilen |
| Schnittplan | Adaptive lokale Teilung mit Querschnitts-/Fragmentbewertung; zusätzlich gleichmäßiges Raster, Raster mit maximalem Schritt, benutzerdefiniertes Zielmaß; sechs Achsenanordnungen des Druckraums |
| Manuelle Schnitte | Achsenparallele Ebenen durch Semikolonlisten; hinzufügen, verschieben, entfernen durch Bearbeitung der Listen und Neuberechnen |
| Skalierung | Proportionaler Faktor auf das ganze Modell mit echter Geometrieänderung |
| Modellausrichtung | Zusätzliche X-/Y-/Z-Drehwinkel von −360 bis 360 Grad, eigene 3D-Vorschau, Anwendung auf vollständige Geometrie; Ursprung normalisiert; vorhandene Druckteile/manuelle Schnitte zurückgesetzt; Rückgängig/Wiederholen |
| Verbinder | Runddübel, quadratische Steckzapfen und gerade Nut/Feder-Segmente mit unabhängiger Breite/Länge; Bohrungen/Taschen mit Spiel und axialer Zugabe |
| Varianten | Integriert am unteren Nachbarteil, separat, kombiniert; alternativ ohne Verbinder |
| Größenautomatik | Optional absteigende Durchmesser/Breiten und Einstecktiefen bis zu expliziten Mindestmaßen; feste Federlänge, konstante Wandreserve und Toleranz; tatsächliche Maße je Verbinder |
| Platzierung | Suche in tatsächlichen Schnittpolygonen einschließlich getrennter und ringförmiger Flächen; rechteckige Kandidaten in beiden Flächenrichtungen bei Nut/Feder; vollständige 3D-Enthaltenseinsprüfung für Einstecktiefe und Wandreserve, Abstand und Kollision mit vorherigen Verbinderhüllen |
| Prüfungen | Eingang geschlossen/mannigfaltig und konsistente Normalen; Volumenerhaltung beim Schnitt; Komponenten; Ausgaben geschlossen; Verbinder bleiben am Teil; Druckraum einschließlich Zapfen; lokale Überschneidung der verbundenen Teile |
| Vorschau | Echte WPF-Meshes, gekoppelte Kameras, Drehen, Zoom, Verschieben, Zentrieren, Gitter, cyanfarbene Schnittkonturen, Verbinderpositionen als Markierungen |
| Große Anzeigenetze | Separate geschlossene Vereinfachung mit Prüfung von Schalen/Genus, Volumen und Lage; vollständiger Originalnetzmodus; Sitzungscache; kein Dreiecksauslassen im Renderer |
| Teile | Nummerierung, Miniaturen, Maße, Nachbarn, Anzahl Verbinder, Auswahl, Ausblenden, Explosions-/Einzelansicht, Deckkraft |
| Montage | Tatsächliche Kontakte getrennt von verbundenen Nachbarn, Verbindungsgraph und lose Baugruppen, Schnittstellenbericht, IDs, Vorschlag unten-nach-oben, schrittweise Teileanzeige, mehrseitiger PDF-Plan und JSON-Zuordnung |
| Montagewege | Durchgehende geradlinige XYZ-Prüfung einzelner Teile und vorbestückter Dübel; umgekehrte Demontagefolge, explizite unbekannte Fälle, stufenlose Einsteckvorschau für vollständig geprüfte Abläufe |
| Projekte | Atomar gespeicherte ZIP-basierte `.3dps`, Originalmodell, Netze, Einstellungen, Schnitte, Verbinder, Zuordnung; Wiederöffnen ohne Originaldatei |
| Historie | Rückgängig/Wiederholen der berechneten Projektzustände während der aktuellen Sitzung; keine persistente vollständige Bearbeitungshistorie |
| Export | STL, OBJ und Core-3MF einzeln oder im Gesamtexport; eine Datei je Teil; echte Druckausrichtung und Ursprung; Nachprüfung von geschlossenem Netz, Volumen und Maßen vor Ersetzen der Zieldatei; Dateizuordnung, Original, PDF, Hinweise und Projekt im Exportordner |
| Profile | Lokale beliebig ergänzbare Druckerprofile; Materialauswahl mit ausdrücklich unverbindlichen Toleranzvorschlägen |
| Verarbeitung | Isolierter Hintergrundprozess, JSON-Fortschritt, echter Prozessabbruch, Ergebnisse werden erst nach erfolgreichem Job übernommen |
| Distribution | Eigenständige Offline-Portable-Version und eigener .NET-Installer mit Benutzerinstallation, Verknüpfungen und Deinstallationslogik |

## Nicht fertig / nicht freigegeben

- Die Oberfläche ist eine eigenständige Nachbildung der Referenzanordnung, **nicht pixelgetreu**. Symbole, einige Proportionen, Fensterrahmen und Miniaturdarstellung weichen ab. Das Bild wird nicht als UI-Hintergrund verwendet.
- Der Demo-Drache wurde aus Volumenkörpern und Flügelkonturen konstruiert. Die Originalgeometrie des Drachen auf der Bildvorlage ist nicht vorhanden.
- Steckclips und Außenschrauben erzeugen passende Geometrie. Praktische Rast- und Drehmontage bleiben offen. Außenschrauben werden separat gedruckt. Nut/Feder unterstützt gerade rechteckige Segmente mit geschlossenen Nutenden, keine umlaufende Kontur, offenen Schienen oder Hinterschneidungen.
- Rechteckige Verbinder unterstützen unabhängige Breite und Höhe. Verbinderpositionen lassen sich pro Schnittstelle setzen. Frei vorgegebene Lasten fehlen.
- Die adaptive Schnittplanung bewertet lokale achsenparallele Vorschläge anhand tatsächlicher Querschnitte und Fragmente. Anatomie, Lastpfade, Überhänge, Schnittflächenqualität und wenig Verschnitt werden nicht global optimiert. Weder adaptive Planung noch „wenige Rasterzellen“ garantieren die minimal mögliche Zahl zusammenhängender Druckteile.
- Das vollständige Modell kann vor dem Schneiden frei ausgerichtet werden. Die automatische Teilung folgt den aktuellen XYZ-Achsen. Freie Zusatzebenen, lokale Neuteilung und Zusammenfügen stehen als manuelle Bearbeitungen zur Verfügung. Der Planvergleich rechnet vier Strategien mit denselben Einstellungen durch. Ein direkter 3D-Drehgriff für Ebenen fehlt.
- Die Dünnwand-Stichprobe arbeitet mit begrenzten Messstrahlen je Körper. Die Überhangfläche ist ein geometrischer Winkelindikator. Eine lückenlose Wandstärken- und Selbstüberschneidungsprüfung, Festigkeitsanalyse sowie allgemeine Montagepfade mit Drehungen oder Gruppenbewegungen fehlen.
- Ein Verbinder kann geometrisch passen, während andere Teile das Einschieben blockieren. Version 0.3 prüft durchgehende gerade Wege entlang XYZ und seit 0.8 entlang der Verbinderrichtung einschließlich Dübelvorbestückung. Nur vollständig geprüfte Abläufe erhalten eine solche Freigabe. Bei offenen Fällen bleibt die Folge ein geometrischer Vorschlag. Unterschiedliche Einsteckachsen können außerhalb der unterstützten Strategie liegen.
- Dünne oder hohle Stellen können keine sichere Verbinderposition liefern. Solche Stellen werden ausgelassen und im Prüfbericht gemeldet. Eine druckraumtaugliche Ausgabe ist deshalb noch keine vollständig montierbare Baugruppe.
- Beim Import können kleine konvexe Öffnungen in ebenen Flächen, eindeutige mikroskopische Nahtspalten und widerspruchsfrei ausrichtbare Flächennormalen repariert werden. Größere oder geometrisch mehrdeutige Defekte werden mit konkretem Befund gemeldet. Schnitt, Vorschau und Export verwenden weiterhin die strikte Prüfung. 3MF-Importe bewahren die indizierte Geometrie für Verarbeitung und Projektdatei, auch bei reinen Kantenkontakten zwischen Volumenkörpern.
- Der 3MF-Import verarbeitet Geometrie einschließlich Modellreferenzen im Archiv. Materialien, Texturen, Stützstrukturen, geschützte Alternativmodelle und herstellerspezifische Slicer-Einstellungen bleiben außen vor.
- STL, OBJ und Core-3MF geben Geometrie aus. Kein G-Code, keine Druckerprofile, Texturen, Farben oder Stützen im Export und keine direkte Slicer-Übergabe. Gesamtexport erstellt einzelne Dateien; kein automatisch gepacktes gemeinsames Druckbett. OBJ/STL haben keine verbindliche Maßeinheit; die Zahlen sind Millimeter.
- Keine eingeprägten Teilenummern, bildbasierte PDF-Montageillustrationen, editierbaren Exportkennzeichen oder persistente Undo-Historie.
- Keine feste RAM-Grenze und keine vollständige CPU-Budgetierung. NumPy/OpenBLAS-Threads werden begrenzt; native Manifold-Parallelität ist nicht vollständig konfigurierbar.
- Die Anzeigevereinfachung prüft geschlossene Netze, positive/negative Schalen und deren Henkelzahl, höchstens 0,5 % Volumenänderung und begrenzte Oberflächenverschiebung. Das ist keine globale Selbstüberschneidungs- oder Wandstärkenanalyse. Sehr feine Details können in der vereinfachten Anzeige abweichen. Die vollständige Anzeige ist umschaltbar. Dreiecksziele sind weich; Qualitätsgrenzen werden nicht zum Einhalten des Budgets gelockert. Große Originalnetze können weiterhin viel RAM und Zeit benötigen.
- Keine automatische Sitzungsbereinigung. Große Projekte und viele Neuberechnungen benötigen entsprechend viel Plattenspeicher.
- Importgrenze: 500 MB / 4 Millionen Dreiecke. Rastergrenze: 512 Zellen/Teile. 3MF-XML maximal 300 MB; Projektarchive maximal 2 GB entpackt.
- Kein Signaturzertifikat, kein Updatekanal und noch keine Prüfung auf einem separaten sauberen Windows-10-System. Messwerte für den Intel N95 werden als separates Prüfprotokoll ausgeliefert.

## Prüfstand

Die 158 automatisierten Python-Tests prüfen Geometrie, lokale Planung, Hohlräume, Materialinseln, Größenautomatik, Montagewege, Export und Anzeige. Die zwölf Nut/Feder-Tests erfassen unter anderem alle Schnittachsen und Flächenrichtungen, schmale Platten, interne Löcher, Spiel, Volumen, integrierte/separate Varianten und feste Länge bei Größenautomatik. Bewegungstests erfassen dünne Hindernisse zwischen Stichprobenpositionen, konkave Kanäle, versiegelte Hohlräume ohne Ausweg, alle XYZ-Richtungen, numerische Restvolumina, Budgetgrenzen und wiederverwendete Anzeigenamen mit neuer Geometrie. Siebzehn Exporttests prüfen alle sechs Druckausrichtungen in drei Formaten, Hohlräume, reale Nuten/Federn, 3MF-Paketstruktur, Nachprüfung und Dateierhalt bei Fehlern. Sechzehn Vorschautests prüfen geschlossene Vereinfachung, Durchbrüche, versiegelte Hohlräume, Materialinseln, Montageposition und unveränderte Quellen. Dreizehn Ausrichtungstests prüfen bekannte/negative/kombinierte Winkel, Volumen, Hohlräume, Ursprung und anschließenden Schnitt/Export. Die C#-Integration prüft zusätzlich die Übereinstimmung von Vorschau und vollständiger Drehgeometrie sowie den Projekt-Roundtrip der Winkel.

Zusätzlich wurde die WPF-Anwendung gestartet, das Demo-Modell angezeigt und der automatische Schnitt per tatsächlicher Oberfläche ausgeführt. Die Resultatzahlen stammen aus dieser Berechnung. Es handelt sich um Softwaretests, nicht um physisch gedruckte Passproben oder einen Belastungsnachweis.

## Nächste Prioritäten

1. Adaptive Planung um alternative Schnittbäume und Montagekriterien erweitern; dünne Teilbereiche und lose Baugruppen stärker vermeiden. Reale Schnittpolygone werden bereits für die Platzierung verwendet.
2. Globale Wandstärken-/Selbstüberschneidungsprüfung und Montagewege mit Drehungen sowie bewegten Teilgruppen ergänzen.
3. Direkte Drehgriffe für freie Ebenen und visuelles Platzieren von Verbindern ergänzen.
4. Verformungs- und Drehmontage von Steckclips und Außenschrauben prüfen.
5. Rendering, Speicherbudget, echte Mesh-Vereinfachung, N95-Messungen und Langzeittests ausbauen.
6. Signierung, Setup-/Deinstallation auf sauberen Windows-10/11-VMs und Updateverfahren abschließen.

Version 0.9 ergänzt zehn Regressionstests für Schwalbenschwanzvarianten, seitlichen Einschub, geschlossene Hinterschneidung, schräge Flächen, manuelle Platzierung und Druckhinweise. Die C#-Integration prüft Geometrieprozess, Projekt-Roundtrip und PDF-Zuordnung der neuen Daten.
