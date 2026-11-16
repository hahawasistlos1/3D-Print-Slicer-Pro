# Vorschau 0.4 · Gerade Nut und Feder

## Reale Geometrie

- Neuer freigegebener Typ „Nut und Feder (gerade)“ mit Breite, Länge entlang der Fläche und Einstecktiefe je Seite.
- Integrierte Feder am unteren Nachbarteil oder separat gedruckte lose Feder mit Nuten in beiden Teilen; kombinierte Variante ebenfalls verfügbar.
- Beide tangentialen Achsenrichtungen werden geprüft. Rechteckige Kandidaten erlauben lange Federn auf schmalen Platten, ohne eine unnötig große kreisförmige Platzreserve zu verlangen.
- Die vollständige dreidimensionale Hülle einschließlich Spiel und Wandreserve muss in beiden Nachbarteilen liegen. Eckprüfungen allein erteilen keine Freigabe; eine Feder kann daher keine Löcher überbrücken.
- Spiel ist die Gesamtzugabe in Breite und Länge, axial kommt es je Seite hinzu. Die optionale Größenautomatik verkleinert Breite und Tiefe; die eingegebene Federlänge bleibt fest.
- Projekt, Prüfbericht, Montage-PDF und Vorschau enthalten tatsächliche Abmessungen und Flächenrichtung. Rechteckige Verbindermarkierungen werden als Quader dargestellt.

## Korrekturen

- Bewegungsprüfungen speichern Zwischenwerte nach tatsächlicher Geometrie statt Anzeigenamen. Erneut verwendete Bezeichnungen können keine Ergebnisse einer früheren Form übernehmen.
- Die Einzelteil-Schaltfläche setzt einen zuvor eingeschränkten Montageschritt zurück. Das ausgewählte Teil bleibt dadurch sichtbar.
- Montagehinweise beziehen sich auch auf separate Federn statt ausschließlich auf Dübel.

## Prüfung und Grenzen

66 Python-Tests einschließlich zwölf neuer Nut/Feder-Tests und zwei Cache-Regressionsprüfungen; C#-Integration mit echtem Worker, Projekt-Roundtrip, STL und Montageplan. Es wurden keine physischen Teile gedruckt.

Unterstützt werden gerade, begrenzte rechteckige Federsegmente mit geschlossenen Nutenden. Es gibt keine umlaufenden Konturen, Hinterschneidungen, Schwalbenschwänze, Clips oder Gewinde. Die adaptive Bewertung verwendet weiterhin eine Heuristik; nur die Platzierung und die gespeicherten geraden Montagewege werden vollständig geometrisch geprüft. Keine Festigkeits- oder Reibungsfreigabe.
