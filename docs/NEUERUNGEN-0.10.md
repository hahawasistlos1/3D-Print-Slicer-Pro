# Version 0.10

- **Steckclip (Rastarme)** erzeugt zwei federnde Arme je Seite, eine engere Eintrittsöffnung und eine weitere Rastkammer. Integriert, separat und gemischt verfügbar. Die Platzierung prüft Wandreserve und vergleicht die geschätzte Dehnung mit der einstellbaren Grenze. Der Standardwert von 3 % ist eine Rechengrenze. Die Werkstoffeignung hängt von Material, Druckrichtung und dem tatsächlichen Bauteil ab.
- **Außenschraube mit Gewinde** erzeugt einen separaten Sechskantschraubenkörper, ein glattes Durchgangsloch im ersten Teil und ein blindes Innengewinde im zweiten. Durchmesser, Gewindelänge, Steigung und Spiel sind einstellbar. Die Geometrie setzt eine freie, gerade Öffnung von außen voraus und ist für gedruckte Passpaare vorgesehen. Normgewinde-Kompatibilität ist offen.
- Lose Clips und Schrauben werden mit ihren erzeugten 3D-Netzen dargestellt. Einstellungen und Zuordnung bleiben in der Projektdatei.
- Der Prüfbericht weist Rast- und Drehmontage als offene praktische Passprobe aus. Geprüft sind Endlage, Wandreserve und der gerade Außenzugang der Schraube. Biegung, Drehweg, Reibung und Festigkeit werden durch dieses Modell nicht nachgewiesen.

Die Abschätzung der Clipdehnung nutzt die Beziehung zwischen Auslenkung und Randdehnung für einen geraden Kragarm. Die gedruckte Rasterstruktur und Spannungsspitzen am Haken sind darin nicht modelliert. [MIT OCW, Development of Constitutive Equations, §4.49](https://ocw.mit.edu/courses/2-080j-structural-mechanics-fall-2013/32670f14cec210d98c5c7fe9dbf73eb6_MIT2_080JF13_Lecture4.pdf)
