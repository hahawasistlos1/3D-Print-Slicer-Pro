# Vorschau 0.7 · Modell frei ausrichten

## Winkel vor dem Schneiden wählen

Die Schaltfläche **⤾** neben den manuellen Schnittoptionen öffnet die Modellausrichtung. X-, Y- und Z-Winkel zwischen −360 und 360 Grad sind frei einstellbar. Die zusätzliche Drehung erfolgt in den aktuellen Modellachsen in der Reihenfolge X, dann Y, dann Z. Volle wirkungslose Drehungen können nicht unnötig übernommen werden.

Nach **Vorschau aktualisieren** zeigt eine eigene drehbare 3D-Ansicht die neue Lage. Die angezeigten Maße stammen aus dem Anzeigenetz. **Ausrichtung anwenden** berechnet die exakten Maße mit der vollständigen Geometrie. Dabei wird das Modellminimum wieder auf XYZ = 0 verschoben. Die importierte Datei und die vorherigen Sitzungsdateien bleiben unverändert.

Die Drehung setzt vorhandene Druckteile und manuelle Schnittpositionen zurück, weil sie sich auf die alte Lage beziehen. Danach neu schneiden. Rückgängig/Wiederholen stellt die vorherigen Projektzustände während der Sitzung wieder her. Winkel und letzte Drehmatrix werden als Hinweis im Projekt gespeichert.

Die [native affine Transformation](https://manifoldcad.org/docs/html/classmanifold_1_1_manifold.html) erhält die Form. Netz, Volumen, positive/negative Schalen, Ursprung und die geschriebene STL werden geprüft. Projekt und Exporte verwenden die echte gedrehte Geometrie.

## Projektzustände erst nach Vorbereitung übernehmen

Modellimport, Projektöffnung, Schnitt, Skalierung, Drehung und Historiewechsel bereiten die benötigten Anzeigenetze vor der Übernahme vor. Wird der Hintergrundvorgang abgebrochen, werden weder der bisherige Projektzustand noch die Historie vorzeitig ersetzt.

## Prüfung und Grenzen

106 Python-Tests einschließlich 13 neuer Ausrichtungstests. Die C#-Integration vergleicht Vorschau und Worker für bekannte und kombinierte Winkel und prüft den Projekt-Roundtrip mit unveränderter vorheriger Geometrie.

Die Schnittfamilien bleiben achsenparallel zur aktuellen Modellausrichtung. Unabhängige Winkel je Ebene, frei verschiebbare Schnittebenen im 3D-Fenster und selektives Neuschneiden fehlen weiterhin. Die Ausrichtung wählt keinen automatisch optimalen Winkel und ersetzt keine Wandstärken-, Montage- oder Festigkeitsprüfung.
