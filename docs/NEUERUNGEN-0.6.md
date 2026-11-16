# Vorschau 0.6 · Geschlossene Anzeige großer Modelle

## Keine ausgelassenen Dreiecke

Bisher reduzierte der WPF-Renderer große Modelle, indem er nur jedes n-te Dreieck anzeigte. Dadurch konnten sichtbare Lücken entstehen, obwohl die Fertigungsgeometrie geschlossen war. Der Renderer lädt jetzt sämtliche Dreiecke seines Anzeigenetzes.

Große Anzeigenetze entstehen separat mit der nativen [Manifold-Vereinfachung](https://manifoldcad.org/docs/html/classmanifold_1_1_manifold.html). Die Ausgabe wird auf geschlossene Netze, konsistente Normalen, positive/negative Schalen und deren Henkelzahl, Volumen und Lage geprüft. Hohlräume und Durchbrüche werden dabei berücksichtigt. Das maximale Toleranzmaß ist min(0,25 mm, 0,1 % der größten Körperausdehnung), die maximale relative Volumenänderung 0,5 %.

Ein nicht erreichtes Dreiecksziel führt zu einer vollständig erhaltenen Darstellung mit entsprechender Meldung. Qualitätsgrenzen werden nicht gelockert und einzelne Flächen werden nicht ausgelassen. Die Anzeige kann dann weiterhin aufwendig sein.

## Originalgeometrie bleibt erhalten

Unter Vorschau lässt sich „Vollständige Originalnetze anzeigen“ aktivieren. Die Anzeige nennt ihre tatsächliche Dreieckszahl; weitere Details stehen im Vorschau-Dialog. Für unveränderte Quellen wird das Anzeigenetz während der Sitzung wiederverwendet. Cachedateien werden getrennt von Modell und Druckteilen gespeichert.

Schnittberechnung, Projekt und STL-/OBJ-/3MF-Export verwenden immer die vollständigen Modelle. Der Cache verändert keine Montagekoordinaten und wird nicht als Fertigungsgeometrie ins Projekt aufgenommen. Der Originalnetzmodus kann mehr Arbeitsspeicher benötigen.

## Prüfung

93 Python-Tests einschließlich 13 neuer Vorschautests. Die C#-Integration prüft außerdem den echten Worker, WPF mit mehr als 120.000 Dreiecken, Anzeige-/Originalmodus, Cache und Cacheerneuerung, Montageposition, unveränderte Quelldateien und vollständigen Export trotz vereinfachter Anzeige. Keine N95-Leistungsmessung oder feste RAM-Freigabe.
