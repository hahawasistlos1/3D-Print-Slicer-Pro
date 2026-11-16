# Neuerungen 0.3

## Durchgehende Prüfung geradliniger Montagewege

**Geradlinige Montagewege prüfen** untersucht nach der Teilung, ob sich die Teile mit ihren Verbindern entlang einer XYZ-Achse trennen lassen. Eine erfolgreich geprüfte Demontagefolge wird für die Montage umgekehrt. Eine Zwischenpositions-Stichprobe wird nicht als Kollisionsnachweis verwendet.

Für die schnelle Freiprüfung dient die konvexe Hülle eines Körpers an Start und Ende. Überlappt diese Hülle ein Hindernis, wird daraus noch keine Kollision abgeleitet: Bei konkaven Körpern kann die Hülle Hohlräume überdecken. Dann erzeugt die Prüfung Prismen aus den in Bewegungsrichtung führenden Dreiecken. Diese Prismen decken die tatsächlich überstrichenen Flächen über den gesamten Weg ab. Sie werden mit den stationären Teilen und deren Dübeln geschnitten. Anfangsüberschneidungen werden gesondert erfasst und sperren den Export betroffener Teile.

Separate Dübel werden dem unteren Nachbarteil A zugeordnet. Die Prüfung berücksichtigt sowohl die Vorbestückung dieses einzelnen Hostteils als auch den anschließenden Transport mit dem Hostteil. Bei der Vorbestückung bleiben die anderen zugehörigen Dübel als Hindernisse erhalten. In der realen Montage müssen die vorbestückten Dübel festgehalten oder fixiert werden.

Die Freigabe gilt ausschließlich für diese Strategie: einzelne starre Teile, geradlinige Bewegungen entlang XYZ, vorbestückte Dübel und die gespeicherten Geometrien. Kontakt ohne Volumendurchdringung ist erlaubt. Numerische Restvolumina werden je Hindernis begrenzt und über Teilkörper/Prismen aufsummiert; bei nicht sicher auszuschließenden Restüberschneidungen erfolgt keine Freigabe. Die Volumentoleranz beträgt 0,000001 mm³.

Kein allgemeiner Montagebeweis: Drehungen, elastische Verformungen, gleichzeitige Gruppenbewegungen, Reibung und Festigkeit werden nicht geprüft. Mehrere gleichzeitige Einsteckrichtungen können deshalb zu „nicht vollständig nachgewiesen“ führen, obwohl eventuell eine andere Montageart existiert. Eine verbundene Baugruppe ist nicht automatisch eine geprüfte Montagefolge.

Die Suche ist auf 12.000 Boolesche Schnittprüfungen und 60.000 führende Dreiecksflächen begrenzt. Bei ausgeschöpftem Budget bleibt das Ergebnis ausdrücklich ungeprüft. Bereits nachgewiesene Demontageschritte bleiben im Projekt erhalten.

## Tatsächliche Einsteckvorschau

Bei einer vollständig geprüften Folge zeigt der Montageschritt-Regler die nachgewiesene Reihenfolge. **Einsteckposition: außen → montiert** verschiebt das aktuelle Teil und seine mitgeführten Dübel stufenlos auf dem tatsächlich geprüften Weg. Richtung, Montagegrad und Restweg werden angezeigt. Ohne vollständigen Nachweis bleibt dieser Regler deaktiviert. Die Teilefolge wird dann ausdrücklich nur als Vorschlag angezeigt.

Der PDF-Montageplan enthält Prüfstatus, erforderliche Dübelvorbestückung, Einsteckrichtungen und Wege. Bei offenen Fällen nennt er Hindernisse bzw. Einschränkungen der Suche.

## Optionale Größenautomatik

**Verbindermaß automatisch verkleinern** ist standardmäßig ausgeschaltet. Bei Aktivierung sind die gewählten Durchmesser-/Breiten- und Tiefenwerte Obergrenzen. Die Mindestwerte stehen unter Einstellungen; Standard sind 3 mm Mindestdurchmesser/-breite und 3 mm Mindesteinstecktiefe je Seite.

Die Suche versucht mehrere absteigende Größen. Sie verändert weder die Wandreserve noch das Durchmesserspiel. Jeder erzeugte Dübel/Zapfen und jede Aussparung wird als echte Geometrie berechnet und erneut auf Enthaltensein, Verbindung zum Teil, Kollisionen und Druckraum geprüft. Die Zuordnung und der PDF-Plan enthalten die tatsächlichen Einzelmaße und kennzeichnen verkleinerte Verbinder. Das ist keine automatische Festigkeitsdimensionierung.

Beim Demo-Drachen mit 220 × 220 × 250 mm Druckraum, 10 mm maximalem Durchmesser, 15 mm maximaler Einstecktiefe, 2 mm Wandreserve und **ausdrücklich gewählten 2 mm Mindestdurchmesser** entstehen 16 Teile und 52 Verbinder in einem verbundenen Graph. Die gerade Montagefolge bleibt bei diesem Modell unvollständig nachgewiesen. Dieses Regressionsergebnis ist kein allgemeines Qualitäts- oder Festigkeitsversprechen.

## Kompatibilität und Pakete

Projektdateien bleiben bei Dateiversion 1. `motion`, tatsächliche Verbindermaße und Größenautomatik-Einstellungen werden zusätzlich gespeichert. Projekte aus 0.1/0.2 können geöffnet werden; für die neuen Auswertungen ist eine Neuberechnung erforderlich. Ein veraltetes Ergebnis wird nicht stillschweigend als neu geprüft exportiert.

Portable Builds liegen nun in versionierten Ordnern, zum Beispiel `artifacts/Portable-0.3.0/`. Eine noch laufende ältere portable Anwendung wird dadurch nicht beim Paketbau überschrieben oder geschlossen.

## Prüfstand

52 Python-Tests: 18 Geometrie-, 18 Planungs-/Hohlraum- und 16 Montageweg-/Größenautomatiktests. Zusätzlich prüft die C#-Integration den echten Worker, Projekt-Roundtrip, STL-Export, PDF und die gespeicherten Bewegungsnachweise. Das Quaderbeispiel enthält eine vollständig nachgewiesene gerade Teilfolge einschließlich Dübelvorbestückung. Die Tests sind keine physisch gedruckte Passprobe oder Belastungsprüfung.
