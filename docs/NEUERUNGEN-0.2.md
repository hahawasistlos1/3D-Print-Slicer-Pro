# Neuerungen 0.2

## Adaptive lokale Schnittplanung

Die neue Strategie **Adaptiv · Modellform berücksichtigen** arbeitet mit einzelnen verbundenen Materialkörpern und einem lokalen Schnittbaum. Bereits in den Druckraum passende Bereiche werden nicht weiter geschnitten. Größere Bereiche erhalten lokale achsenparallele Schnitte.

Der Planer bewertet bis zu 1024 Querschnitte anhand zusammenhängender Flächen, durch Erosion erkannter schmaler Bereiche, möglicher Verbinderquerschnitte, entstehender Fragmente und einer Abschätzung der nötigen Druckteile. Er untersucht die besten Vorschläge mit echten Manifold-Schnitten. Bei ausgeschöpftem Bewertungsbudget werden weitere Schnitte weiterhin geometrisch berechnet, aber ohne zusätzliche Querschnittbewertung. Der Prüfbericht meldet diesen Fall.

Manuelle Ebenen werden zuerst angewandt, die verbleibenden Körper anschließend adaptiv weitergeteilt. Rasterstrategien bleiben verfügbar. Freie Schnittwinkel, ein globales Optimum und eine Festigkeitsgarantie sind weiterhin nicht implementiert.

Beim prozeduralen Demo-Drachen mit 220 × 220 × 250 mm Druckraum erzeugt die neue Planung 16 statt der bisherigen 31 Teile. Das ist ein Regressionsergebnis für dieses Modell, keine allgemeine Zusage. Bei großen Dübeln bleiben dünne Flügelsegmente teilweise ohne passende Verbindung und werden ausdrücklich gemeldet.

## Tatsächliche Flächen und Verbinder

Nachbarn werden anhand sich tatsächlich überlappender Schnittflächen bestimmt, nicht mehr nur anhand benachbarter Rasterzellen. Das unterstützt auch T-förmige Anschlüsse zwischen unterschiedlich aufgeteilten Bereichen.

Verbinderpositionen werden innerhalb der um Wandreserve und Verbinderquerschnitt verkleinerten Schnittpolygone gesucht. Mehrere getrennte Flächen und ringförmige Hohlkörperquerschnitte werden einzeln berücksichtigt. Jeder Vorschlag durchläuft weiterhin eine vollständige 3D-Enthaltenseinsprüfung über die Einstecktiefe. Leere oder ungültige Prüfkörper werden abgefangen; sie können keinen Verbinder und keinen Erfolg erzeugen.

Berührende Nachbarn und über Verbinder angeschlossene Nachbarn werden getrennt erfasst. Der Prüfbericht zeigt je Schnittstelle die tatsächliche Fläche sowie erzeugte/angeforderte Verbinder und die verbleibenden losen Baugruppen. Die Vorschau markiert Teile mit unverbundenen Schnittstellen orange. Ein zusammenhängender Verbindungsgraph beweist weiterhin keine durchführbare Einschubbewegung oder Belastbarkeit.

## Erhaltung geschlossener Hohlräume

Die native Zerlegung trennt Oberflächenschalen. Bei einem versiegelten Hohlraum entsteht dabei eine negative innere Schale. Diese wird jetzt ihrem einschließenden äußeren Körper zugeordnet und zusammen mit ihm weiterverarbeitet. Die Reparatur gilt für adaptive und Rasterteilung. Die Summe der Materialvolumina wird nach der Zuordnung und nach den Schnitten geprüft. Eine Materialinsel innerhalb eines Hohlraums bleibt ein eigenes Teil.

## Oberfläche und Projektdateien

- Die adaptive Strategie ist der Standard für neue Einstellungen. Bereits gespeicherte Strategien werden beibehalten.
- Nur Schnittflächen des jeweiligen Teils erhalten eine cyanfarbene Markierung. Rasterprojekte aus 0.1 bleiben lesbar.
- Die kompakteren linken Panels lassen mehr Platz für die Druckerabmessungen auf kleineren Bildschirmen.
- Gespeicherte Druckerprofile werden bei passenden Abmessungen angezeigt.
- Nach Eingabeänderungen wird das vorhandene Ergebnis als nicht aktuell markiert. Ein STL-Export verlangt dann eine erneute Berechnung.
- Der Montageplan enthält Strategie, Verbindungsgraph, lose Baugruppen und Schnittstellenübersicht.
- `.3dps` bleibt bei Dateiversion 1; die neuen Felder sind zusätzliche Metadaten. Projekte aus 0.1 werden weiterhin geöffnet. Für die neuen Auswertungen müssen sie neu berechnet werden.

## Prüfung

36 Python-Tests (18 bisherige Geometrietests, 18 neue Planungs-/Hohlraumtests) sowie C#-Integration mit echtem Worker, Projekt-Roundtrip und STL-/PDF-Export. Die neuen Tests erfassen unter anderem schmale Verbindungsstellen, versiegelte Hohlräume, Materialinseln, lokale Schnittbereiche, T-Anschlüsse, leere Prüfkörper und die unabhängige Rekonstruktion des Verbindungsgraphs aus tatsächlich erzeugten Verbindern.
