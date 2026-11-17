# Änderungsverlauf OpenQuery

Neueste Version zuerst. Bedienung und Funktionen stehen in der README.

## 0.10.3

- **Fenster und Dialoge:** Das Calc-Fenster wird nicht mehr berücksichtigt; der Editor richtet sich nur nach der Arbeitsfläche des Monitors. Das Layout folgt der tatsächlichen Fenstergröße nach dem Öffnen. Dialoge werden nicht mehr vor dem Anzeigen verschoben, sondern erst nach dem Öffnen und nur bei echtem Überhang zurückgeschoben (behebt: Felder nur weit rechts anklickbar, Spalten nicht wählbar, Knöpfe unten nicht erreichbar).
- **Bedingte Spalte:** Spaltenname kann ein {Parameter} sein.
- **Neu:** „Abfragen bis zum Ende löschen“ (Abfragenmenü, Rechtsklick, Knopfleiste): löscht die markierte und alle folgenden Abfragen, Parameter bleiben; mit Liste und Rückfrage.
- **Bezeichnungen:** „Spalten verbinden“ (statt zusammenführen/vereinen), „Abfragen zusammenführen“ (statt Abfragen verbinden), „Indexspalte“, „Dateien einlesen“.
- Dialoggrau Variante B; neue Symbole für Updates, Umbenennen und Abfrage speichern; „Schritt hinzufügen“ wechselt in die Symbolansicht.
- Update-Prüfung nutzt das Repository joaswerk/LibreOffice-Calc-OpenQuery.

## 0.10.2

- Dialoge erscheinen wieder in der Nähe der Maus (Editorposition wird wieder aus der Arbeitsfläche berechnet, nicht aus den Calc-Fenstermaßen); jeder Dialog wird nach dem Aufbau noch einmal ganz auf den Bildschirm geschoben (größerer Randabstand).
- Schrittdialoge: kurze Auswahlen (bis 4 Einträge, z. B. Richtung, Position) zeigen die ganze Liste statt eines Dropdowns; gibt es Parameter in der Datei, bleibt es ein Dropdown, damit {Parameter} wählbar sind.

## 0.10.1

- Dialoge: neuer, fast weißer Hintergrund (Variante A).
- Tabellenkopf: Platz für die Markierungspfeile ist immer reserviert, die Kopfzeile springt nicht mehr; Pfeil auch rechts (► Name ◄).
- Bedingte Spalte: Knopf „Parameter einfügen…“ für die Wertfelder (Wert, Dann, Sonst).
- Eindeutige Bezeichnungen: Spalte duplizieren, Abfrage duplizieren, Schritt duplizieren, Spalten umbenennen, Abfrage-Verweis, Abfrageliste, Schrittliste, Spalten anordnen u. a.
- Symbolmodus: Symbole unter den Listen 50 % größer, Knöpfe entsprechend höher; Umschalter nur noch als schmales Symbol.
- Bekannt: Der Text in Auswahlfeldern lässt sich in LibreOffice nicht vertikal zentrieren (keine Eigenschaft dafür).

## Neu in 0.10.0 (Kopfzeile, Dialoge, Löschen, Einstellungen)

- **Keine Dateien ohne Nachfrage:** Die Einstellungsdatei im Benutzerordner wird nur nach ausdrücklicher Zustimmung angelegt (Rückfrage beim ersten Ändern einer Einstellung); ohne Zustimmung gelten Einstellungen nur für die Sitzung. Das **Absturzprotokoll** ist standardmäßig aus (Reiter Extras). Der zuletzt benutzte Reiter wird nicht mehr gespeichert.
- **Kopfzeile:** Die Reiter „Abfrage“ und „Schritte“ entfallen. „Neue Abfrage“ und „Parameter“ stehen im Start-Reiter, dazu die Menüs **Abfrage ▾** und **Schritt ▾** (alle Befehle) und „Schritt hinzufügen ▾“. Das Band nutzt jetzt die ganze Fensterbreite (kein „Mehr ▾“ mehr über der Schrittliste).
- **Neuer Reiter Extras:** Updates, **Start anpassen** (Auswahldialog: welche Knöpfe, in welcher Reihenfolge), Rechtsklick, **Symbole statt Text** (die grauen Knöpfe unter den Listen als Symbole; Umschalter auch unten neben den Breitenpfeilen), Absturzprotokoll.
- **Rechtsklick/Doppelklick:** Ist der Rechtsklick eingeschaltet, öffnet er in der Schrittliste das Menü, der Doppelklick die Bearbeitung.
- **Abfrage löschen:** eigener Dialog an der Maus; bietet an, **abhängige Abfragen** (auch indirekt) und davon abhängige **Parameter** mitzulöschen und optional die **zugehörigen Arbeitsblätter**. Dialoge nach einem Menübefehl erscheinen beim Menü; alle Dialoge erscheinen mausnah, auch nach Klicks auf Kopfzeilen-Knöpfe.
- **Fenster:** Der Editor öffnet nie größer als das Calc-Fenster (und nie über den Bildschirmrand); größer machst du ihn von Hand oder mit „Maximieren“.
- **Parameteransicht:** alle Parameter als Tabelle (Name, Wert, Typ, **Verwendet in**, Beschreibung); der angeklickte ist markiert, sein Wert lässt sich unten ändern. Die Zeilendetails der vorher gezeigten Abfrage verschwinden.
- **Letzte Spalte:** am Mac nicht mehr flexibel (schrumpfte auf wenige Pixel), Breite wird ausdrücklich nachgeführt; Mindestbreite je Spalte.
- **Manuelle Spalten:** Schlüsselspalten, die es an dieser Stelle nicht mehr gibt, werden im Dialog mit ⚠ markiert; Auswahlfeld größer, Rahmen vorhanden.
- **Dialoge:** leichtes warmes Grau, weiße Eingabefelder, dunklere Rahmen; weniger Leerraum oben und unten. Abgerundete Ecken sind mit den eingebauten Dialogfeldern nicht möglich.
- **Benutzerdefinierte Spalte:** Doppelklick auf eine Funktion umschließt markierten Text im Formelfeld; Funktionen nach Rubriken, Fehlerfunktionen ganz unten. Der Knopf heißt jetzt „Benutzerdef. Spalte“.
- Weitere Kleinigkeiten: Spaltenname samt Fehler-/Leerangabe über der Tabelle links; Pfeile für Schritte unten wie bei den Abfragen; „Schritt einfügen“ im Menü ganz oben; Ausfüllen-Menü „Nach oben/Nach unten“; Parameter-Symbol neu gezeichnet; kein unnötiger Rollbalken in der Abfrageliste.
- Bekannt, am Mac ungeprüft: Spaltenbreiten-Knöpfe, letzte Spalte, Rechtsklick.

## Neu in 0.9.9 (Zwischenspeicher, Aktualisieren, Dialoge, Dunkelmodus)

- **Zwischenspeicher:** Quellen und Ergebnisse werden nur beim ersten Öffnen einer Abfrage gelesen bzw. gerechnet, solange der Editor offen ist (auch Basisabfragen, auf die andere Abfragen aufbauen). Änderungen an Quelle oder Schritten rechnen automatisch neu. Das Umschalten zwischen Abfragen geht damit deutlich schneller.
- **Aktualisieren neu geordnet:** „Aktualisieren“ liest die Quelle der geöffneten Abfrage (und der Abfragen, auf denen sie aufbaut) neu ein. Neu: **„Alle aktualisieren“** und **„Ins Blatt schreiben“** (das, was „Aktualisieren“ früher tat). Neue Symbole.
- **Keine automatische Typenerkennung mehr:** Eine neue Abfrage aus einer Tabelle enthält nur noch den Schritt „Erste Zeile als Überschriften“. Datentypen erkennst du selbst.
- **Meldungen und Rückfragen** (z. B. Abfrage löschen) erscheinen als eigener Dialog nahe der Maus und immer ganz auf dem Bildschirm; alle Dialoge werden nach dem Öffnen zusätzlich auf den Bildschirm geschoben.
- **Neue Abfrage** öffnet sofort den Quellendialog (Abbrechen: Abfrage bleibt leer).
- **Spaltenlisten in Schritt-Dialogen** sind je nach Spaltenzahl länger (bis zu einer Obergrenze) und werden gekürzt, wenn der Dialog sonst höher als der Bildschirm wäre.
- **Warnung bei vielen Spalten:** Transponieren und Pivotieren fragen nach, wenn mehr als 50 Spalten entstehen.
- **Kopfzeile:** halber Abstand zwischen den Symbolen. Im Reiter Start stehen ganz links „Schließen und Laden“ und „Laden in …“, dann Rückgängig/Wiederholen. „Maximieren“ gibt es zusätzlich im Reiter Ansicht. Die kleinen Rückgängig/Wiederholen-Knöpfe unter den Schritten sehen aus wie normale Knöpfe, die Symbole bleiben blau.
- **Überall „Duplizieren“** statt „Kopie“.
- **Dunkelmodus:** Eingabefelder, Listen und Tabelle in warmem mittlerem Grau mit heller Schrift, Bänderung und Auswahlfarben angepasst, Symbole im Kopf flach. Nur unter Linux simuliert getestet, am Mac ungeprüft.
- Bekannt, noch offen: Die „letzte Spalte“ nach dem Einlesen einer Datei mit wenigen Spalten lässt sich hier nicht nachstellen (Screenshot nötig).

## Neu in 0.9.8 (Parameter anklicken)

- **Parameter anzeigen:** Ein Klick auf einen Parameter in der Abfrageliste zeigt in der Tabellenfläche Name, Typ, Wert und Beschreibung. Bei Listen-Parametern (feste Liste oder aus einer Abfrage) stehen alle Einträge untereinander, bei Parametern aus einer Abfrage zusätzlich die Quelle; ein Fehler (z. B. Abfrage nicht vorhanden) erscheint als Klartext. Gibt es eine benannte Zelle gleichen Namens, steht ein Hinweis, dass sie Vorrang hat. Ein Klick auf eine Abfrage zeigt wieder die Tabelle; die Schrittliste bleibt die der geöffneten Abfrage. Das Menü per Doppelklick/Rechtsklick bleibt unverändert.

## Neu in 0.9.7 (Doppelte weglassen, flache Kopfzeile, Rückgängig/Wiederholen)

- **Gruppieren:** bei „Alle Werte verketten“ gibt es die Option **„Beim Verketten doppelte Werte weglassen“** (jeder Wert nur einmal, die Reihenfolge des ersten Vorkommens bleibt). Ohne Häkchen verhält sich alles wie bisher.
- **Kopfzeile wieder flach:** kein eigener grauer Hintergrund mehr unter den Symbolen, die Fläche hat die normale Fensterfarbe (und folgt damit auch dem Farbschema von System/LibreOffice). Symbole behalten ihren hellen Rahmen, Reiter, blauer Balken und Linien bleiben.
- **Rückgängig/Wiederholen:** stehen jetzt ganz links im Reiter **Start** (mit Beschriftung). Zusätzlich zwei kleine Icon-Knöpfe (ohne Beschriftung) direkt über „Schritt hinzufügen“ unter der Schrittliste. Beide wirken nur auf die Abfrage-Definition (Quelle, Schritte, Ausgabe-Einstellungen), nicht auf Daten, Parameter oder andere Abfragen. Die alten Symbole rechts im Kopf und über dem Namensfeld entfallen.

## Neu in 0.9.6 (Gruppieren, schärfere Symbole)

- **Gruppieren:** neue Berechnungen **Median** und **Eindeutige Werte zählen**. „Texte verketten (Komma)“ heißt jetzt **„Alle Werte verketten“** und hat einen frei wählbaren **Trenner** (Standard „, “, z. B. „ / “). Bestehende Abfragen laufen unverändert mit dem Komma weiter. Median und „Eindeutige zählen“ gibt es auch beim Pivotieren (Bei mehreren Werten je Feld).
- **Symbole:** 96 × 96 Pixel statt 48 × 48, feiner gezeichnet.

## Neu in 0.9.5 (weicheres Grau, schnellere Kopfzeile)

- Weiches, sehr helles Grau (#F4F5F7) statt des kühleren Grau; Symbolrahmen weiß mit hellgrauer Kante.
- Kopfzeile baut sich deutlich schneller auf (nur noch geänderte Elemente werden gesetzt und neu gezeichnet; ausgeblendete Reiter werden nicht mehr bei jeder Größenänderung neu gesetzt).

## Neu in 0.9.4 (Kopfzeile ohne Überdeckung)

- Der **Dialoghintergrund** ist jetzt hellgrau. Dadurch gibt es keine graue Fläche mehr, die Symbole überdecken kann (Mac und neuere LibreOffice-Versionen stapeln anders als 24.2). Listen und Tabelle bleiben weiß.
- Die waagrechte Linie unter dem Kopf ist wieder da; unter den Reitern gibt es zusätzlich eine dünne Linie mit dem blauen Balken des aktiven Reiters darauf.
- Symbole 20 % größer als in 0.9.1 (in 0.9.2/0.9.3 waren es 50 %, das war zu groß); Beschriftung entsprechend kleiner.
- Der Kopf aus Streifen (0.9.3) entfällt.

## Neu in 0.9.3 (Kopfzeile am Mac)

- Der graue Kopf bestand aus einer großen Fläche *unter* den Symbolen. Am Mac liegt eine solche Fläche in der Stapelreihenfolge oben und überdeckte alle Symbole. Der Kopf besteht jetzt aus Streifen *zwischen* den Symbolen, nichts überlappt mehr (unter Linux per Pixelprüfung ohne Nahtlinien kontrolliert; am Mac unbestätigt).
- Die waagrechte Linie unter dem grauen Kopf ist entfernt.

## Neu in 0.9.2 (Kopfzeile, Rechtsklick, Updates)

- **Ansicht-Knöpfe** (Gitternetz, Zeilendetails, Abfragen/Schritte ausblenden) wirken jetzt wirklich auf die Ansicht – bisher wurde nur das Häkchen umgeschaltet.
- **Kopfzeile:** ganz hellgrau, keine Trennstriche zwischen den Reitern, aktiver Reiter fett mit blauem Balken, Symbole 50 % größer in hellem Rahmen, Beschriftung 50 % größer.
- **Rückgängig/Wiederholen** stehen über dem Namensfeld der Schrittspalte (ist die Schrittliste ausgeblendet, rechts im Kopf).
- **Dialoge erscheinen am zuletzt angeklickten Punkt** im Editor, vollständig auf dem Bildschirm (nicht mehr immer in der Mitte).
- **Rechtsklick öffnet die Menüs** unter Linux und Windows (Doppelklick geht weiter); am Mac bleibt es beim Doppelklick. Umschalter: Reiter „Ansicht“ → „Rechtsklick“.
- **Update-Prüfung:** einmal täglich beim Öffnen des Editors (still, ohne Internet passiert nichts) und im Reiter „Ansicht“ → „Updates“. Bei einer neuen Version bei GitHub (Releases von joaswerk/openquery_calc) wird sie angeboten, heruntergeladen und der Installationsdialog von LibreOffice geöffnet.
- README aufgeräumt, Änderungsverlauf in diese Datei (CHANGELOG.md) ausgelagert.

## Neu in 0.9.1 (Kopfzeile überarbeitet)

- **Flache Symbole:** Die Knöpfe haben keinen Rahmen mehr, nur Symbol und Beschriftung; beim Darüberfahren wird die Beschriftung unterstrichen. Die Beschriftungen dürfen zweizeilig sein, daher wieder die vollen Namen.
- **Reiter wie Reiter:** Trennstriche zwischen den Reitern, durchgehende Linie darunter, der aktive Reiter fett mit blauem Balken.
- **Alle Befehle in der Kopfzeile:** zwei neue Reiter „Abfrage“ (Neue Abfrage, Parameter, Öffnen/Speichern, Duplizieren, Verweis, Umbenennen, Eigenschaften, Ausgabe, Reihenfolge, Löschen, Autom. speichern) und „Schritte“ (Hinzufügen, Suchen, Ändern, Umbenennen, Duplizieren, Ein/Aus, Bedingung, Einfügen vor/nach, Reihenfolge, Löschen, Bis Ende löschen). Jeder Schritt der Engine ist über die Leiste erreichbar (Sortieren-Menü: Zeilen umkehren; Rechnen-Menü: Zahleneigenschaft; „Spalten ▾“: verschieben, Reihenfolge umkehren, sortieren; Umbenennen-Menü: mehrere Spalten).
- **„Mehr ▾“:** Passen nicht alle Knöpfe eines Reiters in die Fensterbreite, stehen die übrigen in einem Menü hinter „Mehr ▾“.
- Rückgängig/Wiederholen stehen rechts im Band, gleichfalls flach.
- Hinweis: Die Symbole lassen sich jetzt nur noch mit der Maus anklicken (nicht mehr mit der Tab-Taste).

## Neu in 0.9.0 (Reiter und Symbolleiste)

- **Reiter wie in Power Query** im Kopf: Start, Transformieren, Spalte hinzufügen, Kombinieren, Ansicht. Der zuletzt benutzte Reiter bleibt gemerkt.
- **Eigene Symbole** (40 Stück, einheitlich gezeichnet, in hellem und dunklem Fenster lesbar) mit Beschriftung darunter. Knöpfe mit ▾ öffnen ein kleines Menü. Die Knöpfe wirken auf die markierte Spalte; ohne Markierung öffnet sich der Dialog wie bisher. Passt nicht alles in die Breite, werden die letzten Knöpfe eines Reiters ausgeblendet – Fenster breiter ziehen.
- Ansicht-Reiter: Gitternetz, Zeilendetails, Spaltenbreite, Abfragen/Schritte ein- und ausblenden, Schritt suchen.
- Die Symbole werden von `tools/icons.py` gezeichnet (Quellcode-Zip) und liegen im Ordner `icons/` der Erweiterung.
- Aktualisieren, Speichern und Parameter sind jetzt Knöpfe im Reiter „Start“.

## Neu in 0.8.10

- Der Knopf „Quelle…“ oben links entfällt: Die Quelle ist Schritt 01 und wird per Doppelklick darauf (oder über das Schrittmenü) geändert.
- „Aktualisieren“ und „Dokument speichern“ tragen die Symbole aus dem Calc-Symbolsatz (Aussehen richtet sich nach dem eingestellten Symbolstil).

## Neu in 0.8.9

- **Warnung vor Überschreiben:** Wurde eine Ausgabetabelle von Hand geändert, fragt OpenQuery vor dem Aktualisieren/Laden nach (bei „Alle aktualisieren“ einmal für alle; beim automatischen Aktualisieren wird übersprungen und gemeldet). Manuell hinzugefügte Spalten zählen nicht als Änderung.
- **Fehler in Klartext:** Der fehlerhafte Schritt ist mit ⚠ markiert, darunter steht eine verständliche Meldung mit Hinweis; die Tabelle zeigt den Stand bis zum letzten fehlerfreien Schritt.
- **Schritt suchen:** „🔍 Schritt suchen …“ in den Spalten- und Tabellenmenüs; zuletzt verwendete Schritte stehen oben (★).
- **Notiz in der Ausgabetabelle** (an der linken oberen Zelle) erklärt, dass Änderungen überschrieben werden.
- **Datentyp-Hinweis** nach dem Laden einer Quelle, wenn Spalten nur Text enthalten.
- Manuelle Spalten sind im Spaltenkopf mit ✎ gekennzeichnet; die Abfrage links bleibt markiert; Eingabefelder sind höher (Schrift nicht mehr abgeschnitten); letzte Spalte füllt die Breite; „Beim Schließen alle aktualisieren“ steht in der Häkchenreihe, die Zeilen-×-Spalten-Angabe rechts über der Tabelle; Menü Abfrage/Schritte in Reihenfolge der Buttons.

## Neu in 0.8.8 (Tabellenblatt, Runden, manuelle Spalten)
- **Blattmenü (Rechtsklick im Blatt):** „OpenQuery Dieses Blatt als Quelle“ und „OpenQuery Diesen Bereich als Quelle“ legen eine neue Abfrage an (Quelle = Blatt bzw. markierter Bereich, mit den Schritten „Erste Zeile als Überschriften“ und „Datentypen erkennen“). Ist das ganze Blatt bzw. der markierte Bereich genau die Ausgabetabelle einer vorhandenen Abfrage (oder steht der Cursor nur in einer solchen Tabelle), entsteht stattdessen ein **Verweis** auf diese Abfrage ohne Schritte.
- **Ausgabe schreibt sauber:** Die alten Zeilen der Abfrage werden beim Neuschreiben vollständig geleert. Wird die Tabelle länger oder kürzer, **wandern fremde Daten direkt darunter** (nur in den Spalten der Tabelle) um die Differenz mit, der Abstand zur Tabelle bleibt. Daten neben der Tabelle bleiben stehen. Liegt unterhalb eine andere OpenQuery-Tabelle, die nur teilweise in diese Spalten reicht, wird nichts verschoben und es gilt die bisherige Prüfung (Meldung statt Überschreiben).
- **Gruppe „Standardoperationen“** (früher „Zahlen“): Rechnen, **Runden**, Zahleneigenschaft. „Prozent von“ setzt jetzt den Typ **Prozent**.
- **Runden:** Schritt mit Art (kaufmännisch, aufrunden, abrunden), Nachkommastellen und dem Häkchen **„Nur Anzeige“** (der Wert bleibt ungerundet, im Blatt wird das Zahlenformat mit der gewählten Stellenzahl gesetzt). Ohne Häkchen wird der Wert wirklich gerundet. Auch im Typ-Schritt: bei **Dezimalzahl** und **Prozent** lassen sich Nachkommastellen und „Nur Anzeige“ einstellen.
- **Zeilen-Menü:** „Erste Zeile als Überschriften“ und das Gegenstück stehen ganz oben (wie im Spaltenkopf-Menü).
- **Benutzerdefinierte Spalte:** Die Funktionsliste ist in die Kategorien **Zahl, Text, Datum, Logik** gegliedert und alphabetisch sortiert. Die Kategoriezeilen („── Zahl ──“) fügen nichts ein.
- **Manuelle Spalten behalten jetzt ihr Aussehen:** Zahlenformat, Schriftart, -größe, fett/kursiv/unterstrichen, Schrift- und Hintergrundfarbe der ersten Datenzeile werden beim Aktualisieren im Schritt gemerkt und beim Neuschreiben auf die ganze Spalte angewendet. Gemerkt wird ein Format je Spalte (aus der ersten Datenzeile); einzelne abweichende Zellen innerhalb der Spalte gehen verloren.
- Nicht verändert: Das Verhalten „Aktualisieren löscht manuelle Einträge“ ist noch nicht geklärt (zurückgestellt; ohne Schritt „Manuelle Spalten behalten“ kennt OpenQuery die Einträge nicht). Die benutzerdefinierten Formelfunktionen folgen in 0.8.9.
- Linux-getestet; am Mac/Windows unbestätigt.

## Neu in 0.8.7 (Oberfläche)
- **Spaltenkopf mit Trennstrichen:** `⚠ n | Typ | Name`, jeweils mit Leerzeichen vor und nach dem Strich (der Fehlerteil nur, wenn Fehler angezeigt werden).
- **Fenster wird nicht mehr abgeschnitten:** Ursache war eine Mindestbreite von 620 Einheiten, die bei kleineren Fenstern über den rechten Rand hinausragte (unter Linux mit 1280 Pixel Breite nachgestellt). Jetzt 520; bei schmalem Fenster werden die beiden Listen vorübergehend schmaler, damit die Tabelle mindestens ca. 190 breit bleibt. Der Editor nimmt 90 % der Arbeitsfläche, nie mehr als die Arbeitsfläche. Die Fußzeile ist enger gesetzt. Fenster und Dialoge werden aus der Modellgröße in Pixel umgerechnet zentriert (Bildschirmmitte). Wer die genauen Maße sehen will, legt `~/OpenQuery-Diagnose.txt` an (leere Datei), dann steht dort bei jedem Öffnen die Arbeitsfläche und die Fenstergröße.
- **Letzte Spalte füllt den Rest:** keine leere Fläche mehr rechts neben den Spalten (die letzte Spalte wird gestreckt). Ihre Breite wird deshalb nicht gespeichert.
- **Bänderung wieder blau** (hell und dunkel).
- **Breitenknöpfe:** `<>` macht die Liste breiter, `><` schmaler (mit Hilfetext).
- **Schritt unter der Tabelle** steht wieder vollständig; nur wenn der Platz nicht reicht, wird am Ende mit „…“ gekürzt (der volle Text steht im Hover).
- **Rückgängig/Wiederholen** mit den runden Pfeilen aus dem Calc-Symbolsatz (bei schmaler Liste nur das Symbol). Falls ein Symbolsatz sie nicht liefert, bleibt der Text stehen.
- **Parameter in der Abfrageliste:** Unter den Abfragen stehen die Parameter als `{Name}` (so schreibt man sie in Schritten). Markieren wechselt die geöffnete Abfrage nicht; Doppelklick öffnet ein Menü (Bearbeiten, Löschen, Neuer Parameter, Parameter verwalten). Knöpfe wie Löschen/Umbenennen/Eigenschaften wirken auf den markierten Parameter. Unter den Abfragen gibt es den Knopf **Neuer Parameter**. Der Hover zeigt Typ, Wert und Beschreibung.
- **Parameter verwalten** sieht aus wie in Power Query: links „Neu“ und die Liste, rechts das Formular (Name, Typ, Wert, Vorschläge, Beschreibung); „Übernehmen“ speichert, beim Wechsel mit ungespeicherten Änderungen kommt eine Rückfrage.
- **Abfrage öffnen / speichern** (unter den Abfragen, im Abfragenmenü und im Menü OpenQuery): „Speichern …“ sichert die gewählte Abfrage als Datei, „Öffnen …“ übernimmt eine Abfrage-Datei als neue Abfrage (Name wird eindeutig; fehlen die genannten Parameter in dieser Datei, kommt ein Hinweis).
- **Ausgabe …** steht jetzt unter den Schritten (und im Abfragenmenü), weil sie sich immer auf die geöffnete Abfrage bezieht.
- **Schließen und Laden in …:** zweiter Knopf, fragt vorher nach der Ausgabe (neues Blatt, bestehendes Blatt, nur Verbindung).
- **Klick in die Laufleiste** wählt nichts mehr aus und öffnet kein Menü.
- **Eigenschaften:** das Beschreibungsfeld hat einen Rahmen; der Rollbalken erscheint nur bei langem Text.
- **„© 2026 joaswerk“** unten links; Lizenz MIT (Datei `LICENSE`, auch in der Erweiterung).
- **Nicht umgesetzt:** die Nummernspalte lässt sich im Raster von LibreOffice nicht einfärben (es gibt keine Zellfarbe pro Spalte; der Zeilenkopf, der sich einfärben ließe, löst am Mac Abstürze aus).

## Neu in 0.8.6 (Listen und Vorschlagswerte)
- **Parameter mit Vorschlagswerten:** Im Parameterdialog (Typ Text, Zahl, Datum, Datum mit Uhrzeit) gibt es „Vorschläge“: *keine* (freie Eingabe), *feste Liste* (mit ; getrennt) oder *Werte aus einer Abfrage* (`Abfrage[Spalte]`, wie bei „Liste aus einer Abfrage“). Das Feld „Wert“ wird dann zur Auswahlliste; „Laden“ liest die Liste neu. Steht der gespeicherte Wert nicht in der Liste, kommt beim OK die Rückfrage „Trotzdem speichern?“. Wird eine Abfrage umbenannt, zieht der Vorschlag mit; die Abfrage ist vor dem Löschen geschützt, solange ein Parameter sie nutzt.
- **Quelle „Liste“:** eine einspaltige Tabelle aus einem Parameter (Liste mit ; oder Liste aus einer Abfrage; ein einzelner Wert ergibt eine Zeile) oder aus eingetippten Zeilen. Der Spaltenname ist wählbar (Standard „Wert“). Die Werte sind Text; „Datentypen erkennen“ macht Zahlen daraus. Eine solche Abfrage lässt sich wie jede andere als Quelle, beim Verbinden oder Anfügen verwenden.
- **Nach Einzelwerten filtern, zwei Wege:** Werte wie bisher ankreuzen **oder** oben „Werte aus Parameter“ wählen. Mit Parameter werden die Werte bei jeder Aktualisierung neu aus dem Parameter geholt (Liste, Liste aus einer Abfrage oder ein einzelner Wert); das Ankreuzen ist dann abgeschaltet. „Beibehalten“ und „Entfernen“ gelten wie sonst. Ist der Parameter leer, gibt es eine Meldung.
- **Behoben:** „Löschen“ im Parameterdialog (seit 0.8.2) fragte mit OK/Abbrechen und prüfte dann auf „Ja“, deshalb wurde nie gelöscht. Jetzt Ja/Nein.

## Neu in 0.8.5 (Zahlen- und Textschritte, eindeutige Dialoge)
- **Präfix/Suffix hinzufügen** (Gruppe Text und Werte): fügt vor und/oder hinter den Text der gewählten Spalten etwas an (`#(lf)` = Zeilenumbruch, `{Parameter}` geht). Zahlen werden dabei Text (`5` mit Suffix ` kWh` ergibt `5 kWh`). Häkchen „Leere Zellen nicht ändern“ (Standard an); Fehlerwerte bleiben unverändert.
- **Rechnen (Standardoperationen)** (Gruppe **Standardoperationen**, in 0.8.5–0.8.7 „Zahlen“): Addieren, Subtrahieren, Multiplizieren, Dividieren, Ganzzahlig dividieren, Rest (Modulo), Potenz, Prozent von (Spalte ÷ Operand × 100) und Prozentwert (Spalte × Operand ÷ 100). Operand: fester Wert (oder `{Parameter}`) oder die Werte einer anderen Spalte. Mehrere Spalten gleichzeitig möglich; „Neue Spalte“ (nur bei einer Spalte) setzt das Ergebnis hinter die Quellspalte. Leere Zellen bleiben leer, Text ergibt `#WERT!`, Division durch 0 `#DIV/0!` (beides zählt als Fehlerwert). Währung und Prozent behalten ihren Typ.
- **Zahleneigenschaft** (Gruppe Standardoperationen): Ist gerade, Ist ungerade (Ja/Nein; 2,5 ist weder noch), Vorzeichen (−1/0/1), Absolutwert.
- **Filter und Bedingte Spalte:** neue Bedingungen *ist gerade*, *ist ungerade*, *ist positiv*, *ist negativ*, *ist null* (ohne Vergleichswert).
- **Formelfunktionen:** `ISTGERADE`, `ISTUNGERADE`, `VORZEICHEN` (englisch ISEVEN, ISODD, SIGN); `REST` stand schon zur Verfügung.
- **Dialoge zeigen nur, was gebraucht wird:** Bei *Text extrahieren* erscheinen je nach Art nur Trennzeichen, Vorkommen, Anzahl oder Position; bei *Spalte teilen* je nach Modus; beim *Filter* verschwinden Wert, Groß-/Kleinschreibung und Zahlenformat bei Bedingungen ohne Wert; bei *Rechnen* wechseln Wert und Operandenspalte. Das Fenster wird entsprechend kürzer. Ausgeblendete Felder gehören nicht zum gespeicherten Schritt.

## Neu in 0.8.4 (Parameter überall, Schritt-Bedingung)
- **Parameter in Auswahlfeldern:** In allen Schrittdialogen stehen die Parameter der Datei als Einträge `{Name}` am Ende der Listen:
  - **Spalte** (z. B. Sortieren nach, Gruppieren nach): `{Name}`; der Parameter enthält den Spaltennamen. Existiert die Spalte nicht, kommt eine klare Meldung.
  - **Spalten** (Mehrfachauswahl): `{Liste}` mit einem Parameter vom Typ *Liste* (Werte mit `;`) steht für mehrere Spalten. Feste Spalten und Parameter lassen sich mischen.
  - **Auswahlfelder** (z. B. Richtung): Der Parameter enthält den Eintrag, entweder so wie in der Liste angezeigt oder den internen Wert (z. B. `ab`). Passt der Wert nicht, nennt die Meldung die erlaubten Werte.
  - **Ja/Nein-Felder:** Gibt es Ja/Nein-Parameter, wird aus dem Häkchen eine Auswahl *Ja / Nein / {Parameter}*.
  - **Zahlfelder** (Anzahl, Start, Schrittweite): `{Name}` direkt eintippen oder über **{ } Parameter…** einfügen.
- **Schritt-Bedingung:** Im Schrittmenü (Doppelklick auf den Schritt) **Bedingung …**: Der Schritt wird nur ausgeführt, wenn ein Parameter den Vergleich erfüllt (`ist gleich`, `ungleich`, `größer`, `kleiner`, `enthält` für Text oder Liste). Zahlen, Datum, Uhrzeit, Ja/Nein und Text werden passend verglichen. Ist die Bedingung nicht erfüllt, wird der Schritt wie ein ausgeschalteter übersprungen. Die Schrittliste zeigt `[nur wenn {Name} = Wert]`; die Bedingung bleibt beim Ändern erhalten. „Bedingung entfernen“ im selben Dialog.
- **Parameter aus einer Abfrage (Liste oder Wert):** Im Parameter-Dialog gibt es zwei neue Typen:
  - **Liste aus einer Abfrage (Spalte):** Wert = Abfragename, optional mit Spalte, z. B. `Aktive Häuser[Nummer]` (ohne Angabe: erste Spalte). Leere und doppelte Werte entfallen; der Parameter ist eine Liste mit `;`. Damit geht z. B. der Filter **„ist eines von“** mit `{p_Aktive}` (oder „Passende Zeilen entfernen“), und bei „Spalten behalten/entfernen“ oder „Gruppieren“ steht `{p_Aktive}` für mehrere Spalten.
  - **Wert aus einer Abfrage (erste Zelle):** erste nicht leere Zelle der Spalte, mit passendem Typ (Zahl, Datum, Text). Nutzbar überall wie jeder Parameter, auch in der Schritt-Bedingung.
  - Die Abfrage wird bei jedem Aktualisieren neu berechnet (sie muss gespeichert sein). Zirkelbezüge werden erkannt und gemeldet. Fehlende Abfrage, fehlende Spalte, leere Spalte oder ein Semikolon in einem Wert führen zu einer klaren Meldung.
  - **Abfrage löschen** wird abgebrochen, wenn ein Parameter ihren Wert holt (Meldung nennt die Parameter); **Umbenennen** einer Abfrage zieht die Parameter nach.
- Noch nicht enthalten: Vorschlagswerte (Auswahlliste) für Parameter aus einer Abfrage, Mehrfachauswahl im „Nach Einzelwerten filtern“ aus einer Liste, Quelle als Liste.

## Neu in 0.8.3 (Dateiinhalt einlesen, Unterordner)
- **Ordner-Quelle:** Häkchen **Unterordner einbeziehen** (alle Ebenen, versteckte Ordner mit `.` am Anfang werden ausgelassen). Neue Spalte **Unterordner** (relativer Pfad, leer = oberste Ebene).
- **Neuer Schritt „Dateiinhalt einlesen“** (Gruppe Tabellen): Er arbeitet auf der Dateiliste einer Ordner-Quelle (Spalte „Pfad“ muss angekreuzt sein; filtern und sortieren geht vorher wie gewohnt).
  - **Nur die Datei der ersten Zeile** (z. B. nach Sortierung die neueste) oder **alle Dateien der Liste untereinander**.
  - Navigator im Schritt: Blatt, Tabelle oder benannter Bereich der Beispieldatei (erste Zeile) wählen; bei CSV das Trennzeichen. Die Angaben gelten für jede Datei.
  - Herkunftsspalte `Quelle.Datei` (Name änderbar, leer = keine) mit dem Dateinamen.
  - Bei „alle“ müssen die Dateien gleich aufgebaut sein: andere Spaltenzahl, abweichende Überschriften, fehlendes Blatt/Tabelle oder nicht lesbare Datei **brechen die Abfrage ab**; die Meldung nennt die Datei.
- Leerzeichen, Umlaute und Sonderzeichen (`( ) { } % #`) in Datei- und Ordnernamen sind unkritisch: OpenQuery arbeitet mit normalen Pfaden; die URL-Form (`%20`) bildet LibreOffice beim Öffnen selbst. Pfade aus der Dateiliste werden nicht als `{Parameter}` gedeutet.

## Neu in 0.8.2 (Parameter in OpenQuery)

- **Parameter verwalten:** Menü OpenQuery ▸ „Parameter …“ und Knopf „Parameter…“ im Editor. Ein Parameter hat **Name, Typ, Wert und Beschreibung** und wird in der Datei gespeichert (gilt für alle Abfragen dieser Datei).
- **Typen:** Text, Zahl, Datum, Datum mit Uhrzeit, Ja/Nein, Liste (mit `;` getrennt, z. B. `Berlin;Potsdam;Cottbus`, nutzbar im Filter „ist eines von“).
- **Benutzung:** wie bei den Zellparametern `{Name}`, in Textfeldern der Schritte, im Filter, in Formeln (dort als Zahl, Text oder Datum richtig eingesetzt) und im **Pfad der Quellen „Datei“ und „Ordner“**, z. B. `{p_Ordner}\{Datei}`.
- **Zelle gewinnt:** Gibt es eine benannte Zelle gleichen Namens, gilt der Wert der Zelle. Beim Anlegen lehnt OpenQuery einen Namen ab, der schon eine benannte Zelle ist (oder schon ein Parameter). Tipp: Präfix wie `p_` für OpenQuery-Parameter.
- **Löschen** warnt, wenn der Parameter noch in Abfragen vorkommt (mit Nennung der Abfragen).
- Die Liste „{ } Parameter…“ im Formel- und Schrittdialog zeigt beide Arten (OpenQuery-Parameter mit dem Zusatz „[OpenQuery]“).

## Neu in 0.8.1 (Dateiliste eines Ordners, Datei aus einer Zelle wählen)

Gedacht für diesen Ablauf: Eine Abfrage listet einen Ordner in ein Blatt, eine Zelle mit Datenüberprüfung wählt daraus eine Datei, eine zweite Abfrage liest genau diese Datei und verarbeitet sie.

- **Neue Quelle „Ordner (Liste der Dateien)“:** Ordner und Dateimuster (z. B. `*.csv` oder `*.xlsx;*.ods`) eingeben. Gelistet werden nur die Dateien dieses einen Ordners, ohne Unterordner und ohne Sperrdateien (`~$…`, `.~lock…`), nach Name sortiert. Per Häkchen wählbare Spalten: **Name, Endung, Pfad (voll), Größe, Geändert, Erstellt** (Standard: Name, Größe, Geändert). Größe ist eine Zahl, die Zeiten sind echte Datumswerte.
- **Erstellungsdatum:** gibt es nur unter Windows und Mac. Unter Linux bleibt die Spalte leer.
- **Zellwert im Dateipfad:** Der Pfad der Quelle „Datei“ darf `{Name}` enthalten, z. B. `C:\Daten\{Datei}`. `Datei` ist eine benannte Zelle (die Zelle mit der Datenüberprüfung, in der der Dateiname steht). Bei jedem Aktualisieren wird die gerade gewählte Datei gelesen. Leere Zelle oder fehlende Datei ergeben eine klare Meldung.
- **Navigator mit `{Name}`:** Beim Öffnen des Quelldialogs wird die Datei mit dem aktuellen Zellwert gelesen und ihr Inhalt (Blätter, Tabellen, benannte Bereiche) samt Vorschau angeboten.
- Fehlt in einer anderen gewählten Datei das gespeicherte Blatt oder die Tabelle, gibt es die Meldung aus 0.8.0 (kein stilles Ersatzblatt).

## Neu in 0.8.0 (Dateiauswahl wie im Navigator)

- **Quelle „Datei“:** Nach „Suchen…“ (oder beim OK mit einem eingetippten Pfad) liest OpenQuery die Datei und bietet ihren Inhalt in einer Liste an: alle **Blätter**, alle **Tabellen** (Datenbankbereiche, auch Excel-Tabellen) und alle **benannten Bereiche**, jeweils mit Zeilen × Spalten. Bei Textdateien (CSV, TXT …) gibt es einen Eintrag.
- **Vorschau:** Darunter stehen die ersten Zeilen des gewählten Eintrags. Bei CSV ändert sich die Vorschau mit dem Trennzeichen.
- **Bereich:** Bei einem gewählten Blatt kann zusätzlich ein Zellbereich wie `A1:F500` angegeben werden.
- **Fehlt später etwas** (Blatt, Tabelle oder Bereich in der Datei umbenannt oder gelöscht), erscheint beim Aktualisieren eine klare Meldung. Früher wurde stillschweigend das erste Blatt genommen. Ohne Auswahl in alten Abfragen (kein Blatt gespeichert) wird weiterhin das erste Blatt gelesen.
- Eine ausgewählte Tabelle oder ein Bereich wird einschließlich der Kopfzeile gelesen. Die Überschrift setzt wie immer der Schritt „Erste Zeile als Überschriften“.
- Mehrere Dateien: je Datei eine eigene Abfrage, dann „Tabellen anfügen“ (die Dateien müssen gleich aufgebaut sein). Eine Ordnerquelle gibt es noch nicht.

## Neu in 0.7.8 (Absturzschutz rechts der Tabelle)

- **Freier Bereich rechts neben wenigen Spalten:** Die unsichtbare Abdeckung, die einen Rechtsklick dort abfängt (am Mac stürzte das nackte Raster dabei ab), hängt jetzt nur noch an den Spaltenbreiten und nicht mehr an der Zeilenmessung, die am Mac ausfallen kann. Sie wird dadurch auch dann gesetzt, wenn die Messung fehlschlägt.

## Neu in 0.7.7 (Löschen von Abfragen)

- **Löschen wirkt sofort und vollständig:** Eine gelöschte Abfrage wird gleich aus der Datei entfernt (auch eine neue, automatisch gesicherte). Sie taucht nach „Schließen und Laden“ bzw. „Alle aktualisieren“ nicht mehr auf, und es kommt keine Fehlermeldung „keine Quelle“ mehr von einer gelöschten Abfrage.
- **Abhängigkeitsprüfung:** Wird die Abfrage von anderen benutzt (als Quelle, in „Tabellen verbinden“ oder „Tabellen anfügen“), wird das Löschen mit einer Fehlermeldung abgebrochen, die die abhängigen Abfragen nennt. Dort zuerst Quelle/Verweis ändern oder diese Abfragen löschen.
- **Beim Schließen und Laden** werden nur noch die Abfragen aus der Liste des Editors aktualisiert.

## Neu in 0.7.6 (Formelspalten, „Manuelle Spalten“, Stabilität)
- **Umbenannt:** „Eigene Spalten“ heißen jetzt **„Manuelle Spalten“** (Schritt „Manuelle Spalten behalten“, Felder, Meldungen, Menü).
- **Formelspalten:** Steht in einer manuellen Spalte in **jeder** Zeile dieselbe (zeilenrelative) Formel, erkennt OpenQuery sie als Formelspalte, merkt die Formel im Schritt und trägt sie beim Aktualisieren für **alle** Zeilen neu ein – auch für neue Zeilen, auch nach Sortieren. Gemischte Spalten (Formeln und Werte, verschiedene Formeln) bleiben Wertespalten (Einträge über den Schlüssel). Die Erkennung läuft beim Aktualisieren, beim Öffnen im Editor und bei „Neue Spalten übernehmen“. Grenze: Verweist eine Formel auf eine *Abfragespalte* und wandert diese Spalte, zeigt die Formel auf die falsche.
- **Absturzvorsorge:** Die Tabellenzeilendetails unter der Tabelle tauschen beim Klick auf eine Zelle nicht mehr ihre Modelle aus (Spalten werden einmal angelegt, nur die Zeilen wechseln). Verdacht: Zugriff der Bedienungshilfen auf ein ausgetauschtes Spaltenobjekt. Nur Funktion unter Linux geprüft, die Wirkung gegen den Absturz am Mac/Windows ist unbestätigt.
- **Schrittbezeichnung** steht wieder – kurz (nur der Teil vor dem Doppelpunkt, z. B. „Schritt 3: Zeilen filtern“) – direkt unter der Tabelle über der waagrechten Linie; die volle Beschreibung als Hover.
- **Maximieren/Verkleinern:** Knopf in der Fußzeile (die Titelleiste hat je nach System keine Schaltfläche).
- **Umbenennen beim Verschieben:** Verschiebt man einen Umbenennen- oder Überschriften-Schritt über andere Schritte (z. B. „Manuelle Spalten behalten“), werden Schlüssel- und Spaltennamen in den Schritten dazwischen mit umgestellt. Meldung bei fehlender Schlüsselspalte nennt jetzt die mögliche Ursache „Spalte umbenannt“.
- **„Beim Schließen alle aktualisieren“** (Häkchen in der Fußzeile, Standard an): „Schließen und Laden“ schreibt die bearbeitete Abfrage, alle geänderten und davon abhängigen und danach alle übrigen Abfragen der Datei neu. Fehler einzelner Abfragen erscheinen in der Meldung.

## Neu in 0.7.5 (Eigene Spalten, Menü „Neue Spalten übernehmen“)
- **Umbenannt:** „Handeinträge/Handspalten“ heißen jetzt **„Eigene Spalten“** (Schritt „Eigene Spalten behalten“, Felder, Meldungen). Gespeicherte Abfragen bleiben gültig.
- **Neu: „Neue Spalten übernehmen“** – in der Menüleiste *OpenQuery* und im Rechtsklickmenü im Blatt. Wirkt auf die Tabelle unter dem Cursor, ohne die Abfrage neu zu rechnen: erkennt neue Spalten (innerhalb der Tabelle; rechts angrenzend nur mit dem Häkchen im Schritt), ergänzt fehlende/doppelte Überschriften, **erweitert den Tabellenbereich** (so wird beim Sortieren/Filtern die neue Spalte mitgenommen), ergänzt den Schritt und speichert die Abfrage. Danach meldet ein Hinweis, was übernommen wurde. Voraussetzung: Schritt „Eigene Spalten behalten“ und mindestens ein Aktualisieren seit 0.7.4.
- **Fehler aus 0.7.4 behoben:** Mit gesetztem Häkchen „Neue Spalten rechts … übernehmen“ konnte der Tabellenbereich weit nach rechts (bis Spalte 1000) wachsen, weil LibreOffice bei leeren Spalten ein falsches Ergebnis der Inhaltsabfrage lieferte. Das Ergebnis wird jetzt auf die geprüfte Spalte beschnitten; dieselbe Absicherung gilt für die Warnung „Zielbereich belegt“. Falls bei dir ein Bereich zu breit geworden ist: einmal aktualisieren zieht ihn auf die echte Tabelle zurück.

## Neu in 0.7.4 (Handeinträge und Tabellenort)
- **Schlüssel müssen eindeutig sein:** „Handeinträge behalten“ prüft vor dem Lauf, ob die Schlüsselspalte(n) in der neuen Ausgabe *und* im letzten Stand im Blatt eindeutig sind. Sonst Abbruch mit Meldung (Wert und Zeilennummern der Doppelten). Mehrere Schlüsselspalten gemeinsam sind möglich.
- **Die Tabelle folgt ihrem Bereich `tbl_<Name>`:** Verschieben (ausschneiden, Zeilen/Spalten davor einfügen, in anderes Blatt) ist erlaubt; beim Aktualisieren wird dort geschrieben, wo die Tabelle jetzt steht. Das Ziel der Abfrage wird dabei auf „Zelle“ mit dem neuen Blatt/Ort umgestellt. Blattnamen werden nur noch beim ersten Anlegen gebraucht; ein Blatt darf danach umbenannt werden. (Quellblatt umbenennen bleibt eine Einschränkung.)
- **Nur der Tabellenbereich wird ersetzt** (auch bei Ausgabe „neues Blatt“): Alles daneben bleibt stehen. Wächst die Tabelle in fremde Daten, kommt die Warnung („überschreiben?“). Zwei OpenQuery-Tabellen dürfen sich nicht berühren (Abbruch mit Meldung). Alte Bänderung wird mit entfernt und sammelt sich nicht an.
- **Neue Handspalten:** Spalten, die du innerhalb der Tabelle einfügst, werden als Handspalten übernommen; ohne Überschrift heißt sie „SpalteN“ (N = Position), eine doppelte Überschrift bekommt „ (2)“, „ (3)“ … (die Abfragespalte behält ihren Namen, bei doppelten gilt die erste). Die Überschrift wird sofort im Blatt geändert, der Schritt ergänzt. Mit dem Häkchen **„Neue Spalten rechts neben der Tabelle automatisch übernehmen“** (im Schritt, Standard aus) werden auch direkt rechts angrenzende Spalten übernommen – nie in eine andere Tabelle hinein.
- **Rechtsklick im Blatt:** findet die Abfrage über den Bereich unter dem Cursor.
- Grenzen: Handspalten stehen nach dem Aktualisieren hinter den Abfragespalten (in der Reihenfolge der Handspaltenliste); eine mitten eingefügte Handspalte wandert also nach rechts, ihre Werte bleiben erhalten. Übernahme geschieht beim Aktualisieren bzw. beim Öffnen/Laden im Editor (nicht live).
- Getestet nur unter Linux (LibreOffice 24.2).

## Neu in 0.7.3 (Stabilität und Oberfläche)
- **Raster-Leeren entfernt:** Das in 0.7.2 eingebaute „altes Raster leeren" (Verdacht auf die Abstürze beim Schrittwechsel) ist wieder ausgebaut.
- **Leere Abfrage löschen:** abgesichert (geparktes Raster wird geleert, Fehler werden nur noch protokolliert statt als Meldung/Absturz durchzuschlagen).
- **Freier Bereich rechts der Tabelle** (wenige Spalten) wird wie der Bereich unter den Zeilen abgedeckt, damit dort ein Rechtsklick nicht das nackte Raster trifft.
- **Pfeile** unter den Listen: schlichte Zeichen ‹ › (kein Blau mehr), unten über der Trennlinie, bei den Abfragen linksbündig, bei den Schritten rechtsbündig (springen beim Verstellen nicht); bei den Schritten ist die Richtung umgekehrt (‹ schmaler, › breiter).
- **Knöpfe unter Abfragen/Schritten:** erst zwei Spalten, dann untereinander, erst danach nur Symbole. Mindestbreite jeder Liste ca. 3 cm.
- **Neu:** Knopf „Bis Ende löschen" unter den Schritten.
- Schrittbeschreibung über der Tabelle entfällt; Spaltenname/Fehler/Leer stehen zentriert. Der aktuelle Schritt wird in der Liste nach jedem Neuaufbau wieder markiert.
- Fußzeile: „Abfragen anzeigen" / „Schritte anzeigen". „Zurück" heißt „Rückgängig"; Rückgängig/Wiederholen sehen immer gleich aus.

**Ehrlich:** Die Absturzmaßnahmen sind nur unter Linux getestet; am Mac/Windows unbestätigt. Nach einem Absturz bitte die letzten Zeilen von `~/OpenQuery-Absturzprotokoll.txt` schicken.

## Neu in 0.7.2

- **Absturzsuche:** Jeder abgefangene Fehler steht mit den letzten Traceback-Zeilen in `~/OpenQuery-Absturzprotokoll.txt`. Meldungen „row index is invalid“ erscheinen nicht mehr als Fehlerfenster, sondern nur im Protokoll. Das geparkte Raster wird nach jedem Neuaufbau geleert; die leere Fläche unter den Tabellenzeilen und unter den Schritt-Knöpfen ist abgedeckt. Der Absturz am Mac liegt laut Absturzbericht in der Bedienungshilfen-Schicht von LibreOffice (Raster-Zelle); ob die Maßnahmen helfen, ist nicht bestätigt.
- **Listen:** Abfrageliste 30 % breiter, Pfeilknöpfe ◀ ▶ über beiden Listen, Haken „Abfragen“ und „Schritte“ in der Fußzeile blenden die Listen aus.
- **Spaltenbreite optimieren** baut das Raster neu auf (am Mac wurde die Änderung sonst nicht gezeichnet).
- **Kopfzeile:** Spaltenname, Fehler und Leer in der Mitte, Schrittbeschreibung rechtsbündig.
- **Schrittdialoge:** Beschriftung näher am Feld; „Zeilen sortieren“ mit mehr Abstand zwischen den Blöcken; „Gruppieren“ mit Überschriften Spalte / Funktion / Neuer Name.
- **Neue Spalte:** Einfachklick wählt, Doppelklick fügt aus den Listen ein; Operator ^ (hoch).
- **Spalte teilen:** neu „Einmal nach den ersten n Zeichen“ und „Einmal vor den letzten n Zeichen“.
- **Werte ersetzen** wirkt auf mehrere Spalten (alte Schritte bleiben gültig).
- **Abfragen anfügen:** Auswahl, welche Spalten der angefügten Tabellen übernommen werden.

## Neu in 0.7.1

- **Knöpfe unter der Abfrageliste** für alle Menüpunkte (Neu laden, Löschen, Umbenennen, Kopie, Verweis, Eigensch., ▲, ▼) plus Haken „Autom. speichern“. Der Bereich darunter ist abgedeckt.
- **Einheitliche Breite für alle Spalten …** im Spalten- und im Tabellenmenü (ohne Nummernspalte); dort auch „Alle Spalten optimal breit“.
- **Hover über dem Spaltenkopf** zeigt den vollständigen Spaltennamen.
- **Absturzprotokoll** `~/OpenQuery-Absturzprotokoll.txt`: jede Mausaktion wird protokolliert, Fehler in Ereignissen werden abgefangen. Bei einem Absturz bitte die letzten Zeilen schicken.
- Menü „OpenQuery“ erscheint auch bei nicht deutscher Oberfläche (Windows).
- „Schließen und Laden“ springt an den Tabellenanfang bzw. in die Zielzelle.
- Vorschau standardmäßig 500 Zeilen; Vorschau komplett linksbündig; in der Ausgabetabelle Überschriften links, Zahlen rechts.
- Umbenennen eines Schritts bietet den alten Namen an; die Markierung einer Spalte ändert deren Breite nicht mehr.
- Grenzen: Die Farbe der Knöpfe beim Klick bestimmt das Betriebssystem. Die Typänderung steht im Spaltenmenü („Datentyp ändern …“) und per Doppelklick auf das Typsymbol links im Spaltenkopf. Ein Zellwähler fehlt (Zielzelle von Hand). Fenstervergrößerung unter Windows ungeprüft. Die Absturzursachen am Mac sind nicht bewiesen.

## Neu in 0.7.0

- **Neuer Name: OpenQuery** (Menü, Fenster, Meldungen, Diagnosedatei `~/OpenQuery-Diagnose.txt`, Einstellungen `~/.openquery-einstellungen.json`; alte Einstellungen werden weiter gelesen). Die interne Erweiterungs-ID bleibt gleich, die Installation ersetzt also die alte Version, die Abfragen in deinen Dateien bleiben erhalten.
- **Absturzursache (vermutet) behoben:** Die Liste, die die registrierten Maus- und Tastenlistener am Leben hält, wurde bei jedem verzögerten Rückruf auf 60 Einträge gekürzt, obwohl schon über 80 Listener darin standen (der Fehler steht schon in 0.4.0, dort waren es weniger Listener). Listener werden jetzt nie mehr entfernt; kurzlebige Rückrufe liegen in einer eigenen Liste. Das passt zu den Abstürzen nach mehreren Klicks, ist aber nur unter Linux getestet, nicht am Mac.
- **Neue Klickbelegung, Rechtsklicks werden ignoriert:**
  - Abfragen- und Schrittliste: Einfachklick wählt aus, Doppelklick öffnet das Menü.
  - Spaltenkopf: Einfachklick markiert die Spalte, Doppelklick öffnet das Spaltenmenü. Doppelklick auf den Spaltentrenner = optimale Breite.
  - Zelle: Einfachklick zeigt die Zeilendetails, Doppelklick öffnet das Kopiermenü. Zeilendetails: Doppelklick = Kopiermenü.
  - Alle Menüs und Dialoge öffnen erst nach dem Mausereignis. Die leere Restfläche der Listen ist mit unsichtbaren Feldern abgedeckt, damit ein Klick dorthin nicht das Raster trifft.
- **Tabellenmenü:** Ein Klick oben links in die Tabelle (Nummernkopf) öffnet ein Menü wie in Power Query: Vorschaudaten kopieren, Erste Zeile als Überschriften verwenden, Benutzerdefinierte/Bedingte Spalte, Indexspalte, Spalten auswählen, Obere/Untere Zeilen/Zeilenbereich beibehalten, Doppelte Werte/Fehler beibehalten bzw. entfernen, Obere/Untere/Alternative Zeilen entfernen, Abfragen zusammenführen/anfügen.
- **Schrittnamen wie in Power Query** (z. B. „Obere Zeilen beibehalten“, „Doppelte Werte entfernen“) und neuer Schritt „Doppelte Werte beibehalten“.
- **Zielzelle auch beim neuen Blatt:** Im Ausgabedialog steht das Feld „Zielzelle“ jetzt auch bei „Neues Blatt“ zur Verfügung (Standard A1). Eine Zellauswahl per Klick im Blatt gibt es nicht, die Zelle wird getippt.
- **Sonderzeichen in Trennzeichen:** `#(lf)` = Zeilenumbruch, `#(cr)` = Wagenrücklauf, `#(tab)` = Tabulator, in Text extrahieren, Spalte teilen, Werte ersetzen und Spalten zusammenführen.
- **Spaltenbreite:** Das Ziehen mit der Maus ist abgeschaltet. Bleibt: Doppelklick auf den Spaltentrenner, Menüpunkt „Spaltenbreite optimieren“ (aktuelle Spalte), „Spaltenbreite …“ (Zahl), „Alle Spalten optimal breit“.
- **Knopf „Dokument speichern“** oben: sichert alle Abfragen und speichert die ganze Datei (bei einer noch nie gespeicherten Datei erscheint ein Hinweis).
- **Löschen** (Schritt, bis zum Ende, Abfrage) läuft erst nach dem Klick-Ereignis.

## Neu in 0.6.2

- **Absturzschutz (Hypothesen, am Mac zu prüfen):** Jeder Rechtsklick liefert am Mac zwei Mausereignisse; das zweite wird jetzt verworfen, solange ein Menü offen ist oder gerade eines war. Veraltete Auswahlereignisse der Listen (nach Löschen) werden ignoriert, und jede Listener-Methode fängt Ausnahmen ab, damit nichts mehr bis ins C++ von LibreOffice durchschlägt. Unter Linux war der Absturz nie nachzustellen.
- **Automatisch speichern (Option):** Rechtsklick in der Abfragenliste ▸ „Automatisch speichern (nach jedem Schritt)“. Danach werden alle Abfragen und die Datei nach jeder Änderung gesichert (nur wenn die Datei schon gespeichert ist; sonst einmaliger Hinweis). Die Blätter werden dabei nicht neu geschrieben.
- **Spaltenüberschriften bleiben links**, Zahlen und Datum werden über Auffüllen mit Ziffernleerzeichen rechtsbündig dargestellt (am Mac noch zu bestätigen).
- **Verbindungen als Quelle:** Neue Quellenart „Andere Abfrage dieser Datei“ (auch „Nur Verbindung“).
- **Letzter Ordner** der Quelldatei wird gemerkt (Datei ~/.supercalc-einstellungen.json).
- **Kontextmenü im Blatt, flach:** „OpenQuery öffnen“, „OpenQuery Abfrage aktualisieren“, „OpenQuery Alle Abfragen aktualisieren“.
- **Neue Abfrage aus einem Blatt** legt zwei normale, löschbare Schritte an: „Erste Zeile als Überschrift“ und „Datentypen erkennen“.
- **Anfügen: Spalten zuordnen** („Angefügt = Aktuell“, eine Zeile je Paar).
- **Kopieren:** Rechtsklick auf eine Zelle der Tabelle ▸ Zelle/Zeile/Spalte kopieren; Strg/Cmd+C kopiert die zuletzt angeklickte Zelle. In den Tabellenzeilendetails: Rechtsklick ▸ Wert / Name und Wert / ganzer Datensatz, ebenfalls Strg/Cmd+C.

## Neu in 0.6.1

- **Menübefehle nach dem Menü:** Befehle aus den Popup-Menüs (Abfragen, Schritte, Spalten, Datentyp) laufen erst, wenn das Menü ganz geschlossen ist. Gedacht gegen die Abstürze am Mac beim Löschen („Bis zum Ende löschen“, Abfrage löschen) und beim Rechtsklick auf den Spaltentitel. Unter Linux war das Problem nicht nachzustellen; ob es am Mac hilft, zeigt dein Test.
- **Spaltenbreite am Mac:** Es gilt wieder das eingebaute Ziehen des Rasters wie in 0.4.0 (unsere eigene Ziehlogik bleibt dort aus). Doppelklick auf den Spaltentrenner = optimale Breite bleibt. Unter Linux/Windows bleibt die eigene Logik.
- **Reiterfarbe:** Eine Abfrage nimmt beim Abschalten des Häkchens nur die Farbe zurück, die sie selbst gesetzt hat. Von Hand gesetzte Reiterfarben anderer Blätter bleiben unberührt.
- **Kontextmenü im Blatt:** Das Menü „OpenQuery ▸“ wird jetzt auch beim Neuanlegen, beim Laden, beim Erzeugen der Ansicht, beim Aufruf eines OpenQuery-Befehls und beim Öffnen des Editors angemeldet; die Menüerkennung ist großzügiger.
- **Diagnose:** Mit der Datei `~/OpenQuery-Diagnose.txt` (Home-Ordner, reiner Text) werden jetzt auch Menübefehle, Löschen und das Kontextmenü protokolliert. Bei einem Absturz zeigt die letzte Zeile, wo es passiert ist.

## Neu in 0.6.0

- **Parameter aus Tabellenzellen:** Eine Zelle mit einem Namen versehen (Zelle markieren, Name ins Namensfeld links über der Tabelle tippen, Enter), z. B. `Startdatum`. In Schritten steht dann `{Startdatum}` als Wert (z. B. im Filter „Datum ≥ {Startdatum}“, in Ersetzen-Feldern und in Formeln: `[Datum] - {Startdatum}`). Der Knopf **„{ } Wert aus Zelle…“** unten links im Schrittdialog zeigt alle benannten Einzelzellen mit ihrem Wert und fügt den gewählten Namen ein. Wird die Zelle geändert, genügt ein Aktualisieren. Fehlt der Name, ist die Zelle leer, enthält sie einen Fehler oder bezeichnet der Name einen Bereich, nennt die Fehlermeldung den Parameternamen. Im Bedingte-Spalte-Dialog gibt es den Knopf nicht; dort `{Name}` direkt in das Wertfeld tippen.
- **Handeinträge behalten (Selbstreferenz):** Neuer Schritt „Handeinträge behalten (eigener letzter Stand)“ in der Gruppe Tabellen. Du gibst die Schlüsselspalten an (eindeutig je Zeile) und die Spalten mit Handeinträgen (ein Name pro Zeile, z. B. „Notiz“). Die Spalte wird angelegt, falls die Quelle sie nicht liefert; du trägst im Ausgabeblatt von Hand etwas ein, und beim nächsten Aktualisieren wird es anhand des Schlüssels wieder zugeordnet, auch wenn sich die Reihenfolge ändert. Gibt es die Schlüsselzeile nicht mehr, fallen ihre Handeinträge weg; das meldet die Statuszeile („n Handeinträge ohne passende Zeile verworfen“). Voraussetzung: Ausgabe im Blatt (nicht „Nur Verbindung“); der letzte Stand wird aus dem Bereich `tbl_…` bzw. dem Ausgabeblatt gelesen. Fehlt die Schlüsselspalte im letzten Stand, gibt es eine Fehlermeldung statt stillen Datenverlusts.
- **Löschen einer Abfrage lässt den Bereich `tbl_…` stehen.** Legst du später eine Abfrage gleichen Namens an, übernimmt sie den Bereich (kein `_2`).

## Neu in 0.5.0

- **Intelligente Tabelle** (Standard, im Ausgabedialog abschaltbar): Die Ausgabe wird als benannter Datenbankbereich `tbl_<Abfragename>` angelegt (Leer- und Sonderzeichen werden zu `_`). Kopfzeile in Dunkelfarbe mit weißer Fettschrift, Bänderung (abwechselnde Zeilenfarbe), Autofilter über alle Spalten. Beim Aktualisieren wächst oder schrumpft der Bereich mit; neue Spalten erhalten automatisch einen Filterpfeil. Ein gesetzter Filter bleibt beim Aktualisieren nicht erhalten.
- **Farben**: Blau (Standard), Grün, Orange, Rot, Violett, Türkis, Grau, Gold. Häkchen „Bänderung“ (Standard an) und „Reiter des Blatts in dieser Farbe einfärben“ (Standard aus, nur bei eigenem Blatt).
- **Nur Verbindung**: Ausgabeziel „Nur Verbindung (nicht ins Blatt schreiben)“. Die Abfrage schreibt nichts, lässt sich aber in Verbinden, Anfügen und Verweis verwenden. In der Abfrageliste mit „↔“ markiert. „Laden“ schreibt nichts und springt nicht zu einem Blatt.
- **Rechtsklick im Tabellenblatt**: Zusatz-Menü „OpenQuery ▸“. Auf dem Ausgabeblatt einer Abfrage: „Diese Abfrage aktualisieren“ und „Editor öffnen“ (mit dieser Abfrage). Auf einem fremden Blatt nur „Editor öffnen“ (öffnet die erste Abfrage der Liste). Das Menü wird beim Öffnen/Neuanlegen eines Calc-Dokuments angemeldet.
- Umbenennen verschiebt den Bereich `tbl_…`, Löschen einer Abfrage entfernt ihn.
- Geplant für 0.7.0: „Spalten aus Beispielen“.

## Neu in 0.4.2
- **Buttons:** „Neue Abfrage“ steht direkt unter dem letzten Eintrag der Abfragenliste, die Schrittbuttons (Hinzufügen, ▲ ▼, Ändern, Umbenennen, Löschen, Ein/Aus, Duplizieren) rechts direkt unter dem letzten Schritt. Sind die Listen voller als der Platz, kleben die Buttons unten über der Fußlinie. Unter der Linie stehen nur noch Zeilen × Spalten, Gitternetz, Zeilendetails, Vorschau und Laden/Abbrechen.
- **Senkrechte Linien** laufen von der oberen bis zur unteren waagrechten Linie.
- **Kopfzeile über der Tabelle (auf Höhe von „Abfragen“ und „Angewendete Schritte“):** links die Schrittbeschreibung (volle Breite, solange keine Spalte markiert ist; der volle Text steht als Hinweis beim Überfahren), in der Mitte der Name der markierten Spalte mit „Fehler · Leer“.
- **Rahmen:** Tabelle und Zeilendetails haben einen flachen, rundum gleichen Rahmen in der Farbe der Trennlinien (vorher dunkel links/oben, hell rechts/unten).
- **Abfragename:** Enter im Namensfeld übernimmt den Namen in die Liste, schließt den Editor nicht und schreibt nichts. Geschrieben wird erst mit „Schließen und Laden“. Enter löst nirgends mehr „Schließen und Laden“ aus.
- **Rechtsklick in den Listen:** Der Eintrag unter dem Zeiger wird erst markiert und gezeichnet, dann erscheint das Menü. Rechtsklick ins Leere (weißes Feld) öffnet kein Menü mehr.
- **Spaltenbreite:** **Doppelklick auf den Spaltentrenner** setzt die optimale Breite (zusätzlich zum Ziehen). Die eingebaute Größenänderung von LibreOffice ist abgeschaltet, damit sie unser Ziehen nicht stört.
- **Rollbalken** werden erst geprüft, wenn das Fenster sichtbar ist, mit den gemessenen Pixelmaßen (senkrecht und waagrecht getrennt gerechnet) und mehrfach nach dem Anzeigen. Listen werden vor dem Befüllen vergrößert, damit kein Rollbalken stehen bleibt. Beim Ausblenden der Zeilendetails wird die Tabelle vollständig neu gezeichnet.
- **Diagnose (nur auf Wunsch):** Liegt im Benutzerordner eine Datei `OpenQuery-Diagnose.txt` (leer anlegen), schreibt der Editor dort mit, welche Mausereignisse bei Teilern, Tabelle und Listen ankommen. Ohne die Datei wird nichts aufgezeichnet.

## Neu in 0.4.1
- **Neues Layout:** Oben ein Band für das spätere Menü (etwa 2 cm; die Knöpfe stehen vorerst darin), darunter eine Linie. Die Beschriftungen **Abfragen** und **Angewendete Schritte** sind fett; die senkrechten Teiler reichen bis zu ihnen hinauf. Unter Tabelle und Listen steht eine Fußlinie, darunter die Knöpfe, „n Zeilen × m Spalten“, Gitternetz, Zeilendetails, Vorschau und Laden/Abbrechen.
- **Abfragename** steht wie das Namensfeld in Excel über der Schrittliste und ist dort direkt änderbar (Enter übernimmt; doppelte Namen werden abgelehnt).
- **Alte Daten bleiben nicht mehr stehen:** Die Tabelle wird auf zwei Rastern im Wechsel aufgebaut, die Schritt- und die Detailliste werden nach jedem Neuaufbau zum Neuzeichnen gezwungen. Bei einer Abfrage ohne Quelle steht statt eines leeren Rasters der Hinweis „Noch keine Daten“ (dort kann man nicht mehr hineinklicken).
- **Gitternetz aus** stellt die Bänderung wieder her (hell und dunkel passend). **Listen** (Abfragen, Schritte) haben keine Bänderung.
- **Scrollleisten** erscheinen nur, wenn es etwas zu scrollen gibt.
- **Zeilendetails:** Spaltennamen linksbündig.
- **Rechtsklick auf Abfragen:** neuer Eintrag **Neue Abfrage**.
- **Schließen und Laden** springt in das Ausgabeblatt.
- **Quelle:** Das Tabellenblatt wird aus einer Liste der vorhandenen Blätter gewählt (statt „aktuelles Blatt“). Ausgabeblätter anderer Abfragen sind markiert und werden nie vorgewählt; das eigene Ausgabeblatt wird nicht angeboten (behebt den Fehler „Zielblatt ist zugleich die Quelle“).
- **Ziehen:** Teiler und Spaltenrand werden unter Linux mit echtem Mausziehen getestet (funktioniert). Die Mausposition wird jetzt einheitlich in Dialogkoordinaten gerechnet, und ein Druck auf den Teiler wird auch dann erkannt, wenn nur der Dialog das Ereignis bekommt. Am Mac unbestätigt.

## Neu in 0.4.0
- **Menü „OpenQuery“** mit nur zwei Einträgen: „Abfrage-Editor öffnen …“ (öffnet mit der Abfragenliste; ohne Abfragen wird eine neue angelegt) und „Alle Abfragen aktualisieren“. Die Auswahl der Abfrage vorab entfällt.
- **Einzelne Abfrage aktualisieren:** Button „Aktualisieren“ oben im Editor und Rechtsklick auf die Abfrage → „Aktualisieren“ (schreibt ins Blatt, ohne den Editor zu schließen).
- **Listen als Raster:** Abfragen- und Schrittliste sind jetzt Raster. **Rechtsklick wählt den Eintrag unter dem Zeiger** (Auswahl und Tabelle wechseln mit). Beim **Überfahren** zeigt ein Hinweistext Name und Beschreibung (Schritt) bzw. Quelle und Schrittzahl (Abfrage).
- **Trennlinien statt Rahmen**, Listen und Tabelle beginnen oben bündig. Die Linien sind **ziehbare Teiler**: Breite von Abfragen- und Schrittliste ändern (wird in der Datei gemerkt). Abfragenliste standardmäßig schmaler.
- **Zeilendetails unter der Tabelle** wie in Power Query: Klick auf eine Zeile zeigt den ganzen Datensatz (Spalte | Wert). Mit × oder dem Häkchen „Zeilendetails“ aus-/einblendbar.
- **Gitternetz** (Häkchen unter der Tabelle): mittelgraue Zeilen- und Spaltenlinien statt Bänderung.
- **Zahlen, Währung, Prozent, Datum und Zeit** stehen rechtsbündig.
- **Dunkelmodus:** Spaltenköpfe bekommen dunklen Grund und helle Schrift, wenn das Fenster dunkel ist (nur am Mac zu bestätigen).
- **Spaltenbreite:** Im Spaltenmenü (Rechtsklick) „Spaltenbreite …“ (Zahl) und „Alle Spalten optimal breit“. Ein Klick am Spaltenrand stört das Ziehen mit der Maus nicht mehr (am Mac zu bestätigen).
- **Absturz Rechtsklick auf Abfragenliste:** Beim Wechsel der Abfrage wird die Liste nicht mehr neu aufgebaut, nur die Auswahl geändert (am Mac zu bestätigen).
- Die Zeile „Name der markierten Spalte / Fehler“ steht jetzt unter der Tabelle, damit oben alles bündig ist.

## Neu in 0.3.0
- **Abfragenliste links** (wie in Power Query): alle Abfragen der Datei stehen in einer Spalte, ein Klick wechselt die Abfrage. Der Name steht dort, das Feld „Abfragename“ unten entfällt. **Neue Abfrage** liegt unter der Liste. Rechtsklick auf eine Abfrage:
  - **Löschen** (das Ausgabeblatt bleibt erhalten), **Umbenennen** (Verweise anderer Abfragen, auch in Verbinden/Anfügen, folgen dem neuen Namen), **Duplizieren** (Kopie mit eigenem Ausgabeblatt), **Verweis** (neue Abfrage mit der Quelle „Abfrage …“, also dem Ergebnis der gewählten), **Nach oben / Nach unten** (die Reihenfolge wird in der Datei gespeichert), **Eigenschaften** (Name und Beschreibung).
  - Neue Quellenart **Andere Abfrage** (entsteht über „Verweis“).
  - Änderungen an mehreren Abfragen bleiben beim Wechseln erhalten. Mit „Schließen und Laden“ wird die aktuelle Abfrage ins Blatt geschrieben; die übrigen geänderten Abfragen und alle, die auf geänderte verweisen, werden gesichert und ebenfalls aktualisiert. Leere neue Abfragen ohne Quelle werden verworfen. Rückgängig/Wiederholen gilt je Abfrage.
- **Schrittzeile über der Tabelle:** zeigt den gewählten Schritt als Text („Schritt 3: Erste Zeile als Spaltenüberschriften verwendet“); die Beschreibung unter der Schrittliste entfällt. Nur Anzeige; Bearbeiten per Skript ist für später geplant.
- **Schrittmenü (Rechtsklick):** „Schritt einfügen vor/nach …“ öffnet jetzt dasselbe Menü wie der Button „Schritt hinzufügen“ (nicht mehr kaskadierend).
- **Überschriften/Umbenennen zurücknehmen:** Wird „Erste Zeile als Überschriften“ oder ein „Spalte umbenennen“-Schritt gelöscht oder pausiert, bekommen die Folgeschritte ihre alten Spaltennamen zurück; beim Wiedereinschalten wieder die neuen.
- **Tabelle neu zeichnen:** Nach jedem Schrittwechsel wird das Raster zusätzlich als ungültig markiert und kurz gescrollt (gegen die Anzeige, die am Mac erst nach dem Scrollen aktualisiert wurde; am Mac unbestätigt).
- **Fix:** Der Editor nimmt seine Größe jetzt zuverlässig aus dem Fenster (zu breites Layout bei kleineren Fenstern).

## Neu in 0.2.7
- **Ansicht nach Neuaufbau:** Die Tabelle springt nach einem Schritt zurück nach oben; die horizontale Position bleibt nur, wenn die Spalten gleich geblieben sind (gedacht gegen die verrutschte Anzeige am Mac, dort unbestätigt).
- **Fehler** sind nur echte Fehlerwerte (z. B. #WERT!). „⚠ n“ steht jetzt am Anfang des Spaltenkopfs, damit es in schmalen Spalten nicht abgeschnitten wird.
- **Unter der Tabelle (links):** „Zeilen: n × Spalten: m“ der gefilterten Tabelle; oben steht nur noch die Schrittnummer.
- **Schritteliste:** Das Menü öffnet per Rechtsklick, aber erst nach dem Klick-Ereignis (Absturzvermeidung am Mac, unbestätigt). Doppelklick = Ändern. Linksklick im rechten Bereich öffnet kein Menü mehr (Schalter `SCHRITT_MENUE_KLICK`).
- **Überschriften-Schritte** („Erste Zeile als Überschriften“ / „Überschriften als erste Zeile“): neue Spaltennamen werden in die folgenden Schritte übernommen, auch bei späterem Einfügen.
- **Filter:** Standardbedingung ist überall „enthält“.
- **Schritte ohne Eingaben** (Erste Zeile als Überschriften, Überschriften als erste Zeile, Zeilen umkehren, Spaltenreihenfolge umkehren) laufen sofort ohne OK-Dialog.
- **Neu:** „Zeilen mit Fehlern beibehalten“. Gegenstücke stehen im Menü direkt nebeneinander.

## Neu in 0.2.6
- **Schritt-Gruppe „Tabellen“:**
  - **Dateiinhalt einlesen (neu in 0.8.3):** liest aus der Dateiliste einer Ordner-Quelle die Datei der ersten Zeile oder alle Dateien untereinander (siehe „Neu in 0.8.3“).
  - **Tabellen verbinden (Merge / Join):** Zweite Tabelle = Ergebnis einer **anderen gespeicherten Abfrage dieser Datei**. Bis zu 5 Schlüsselpaare (Spalte links = Spalte rechts), Verknüpfungsart: Links außen, Innen, Vollständig außen, Rechts außen, Links-Anti, Rechts-Anti, Kreuzprodukt. Auswahl der Spalten aus der zweiten Tabelle (keine Auswahl = alle außer den Schlüsselspalten) und optionaler Präfix; doppelte Spaltennamen erhalten ein „.1“. Bei „Voll“ und „Rechts“ übernehmen Zeilen ohne Treffer die Schlüsselwerte der zweiten Tabelle.
  - **Tabellen anfügen (Append / Union):** eine oder mehrere andere Abfragen unter die aktuelle Tabelle setzen, Zuordnung nach Spaltennamen (ohne Beachtung der Groß-/Kleinschreibung, fehlende Felder leer) oder nach Position, optionale Herkunftsspalte (mit frei wählbarem Wert für die aktuelle Tabelle).
  - Die andere Abfrage muss in der Datei gespeichert sein (Schließen und Laden). Zirkelbezüge (A bindet B ein, B bindet A ein) werden mit Meldung abgefangen. Die Abfrage „Gesamt“ wird beim Aktualisieren immer mit dem aktuellen Stand der eingebundenen Abfragen berechnet.
  - Wird in einer früheren Stelle eine Spalte umbenannt, folgt der linke Schlüsselname automatisch.
- **Fehler je Spalte:** Spalten mit Fehlern zeigen im Kopf „⚠ n“; für die angeklickte Spalte steht über der Tabelle „Fehler: n · Leer: n“.
- **Fix:** Schrittliste wurde in 0.2.5 nicht gezeichnet (Rahmen lag darüber) und reagierte nicht auf Klicks. Der Rahmen besteht jetzt aus schmalen Streifen.

## Neu in 0.2.5
- **Escape** schließt den Editor nicht mehr (nur „Schließen und Laden“ / „Abbrechen“).
- **Schrittliste:** Rechtsklick abgeschaltet (Absturz am Mac); das Menü öffnet per Klick im rechten Viertel der Liste, Doppelklick = Ändern. Rahmen mit Abstand um die Liste; „Zurück/Wiederholen“ über der Liste, „Schritt hinzufügen“ und „Umbenennen“ darunter.
- **Tabelle:** Neuaufbau erst nach dem Klick (nicht mehr mitten im Ereignis), erzwungenes Neuzeichnen, die Ansicht bleibt an der Scrollposition. Kopf der Nummernspalte: „Nr.“. Zeilenzahl-Auswahl unter der Tabelle.
- **Spaltenqualität** über der Tabelle für die angeklickte Spalte: „Fehler: n · Leer: n“. Fehler = Fehlerwerte (#WERT!) und bei Textspalten, die überwiegend wie Zahlen oder Datumswerte aussehen, alle Werte, die nicht dazu passen.
- **Rechtsklick in der Tabelle** setzt zuerst den Marker ►, dann öffnet das Menü.
- **Spalte umbenennen:** Beim Ändern oder Einfügen eines Umbenennen-Schritts werden die Spaltennamen in den Folgeschritten (Spaltenlisten, Filter, Sortierung, bedingte Spalten, Formeln `[Name]`) angepasst. Die Anpassung endet, wo die Spalte entfernt wird oder eine neue Spalte den alten Namen bekommt.
- „behalten“ heißt überall „beibehalten“.
- Grenze: Die Nummernspalte lässt sich nicht einfärben (das Raster von LibreOffice kennt keine Spaltenfarbe).

## Neu in 0.2.4
- **Absturz am Mac umgangen:** Der eingebaute Zeilenkopf des Rasters ist aus; statt dessen steht eine eigene Nummernspalte („#“, linksbündig) ganz links. Ein Klick auf eine Nummer markiert die Zeile wie ein Klick in jede Zelle. Die Nummernspalte wandert beim Scrollen nach rechts mit.
- **Typ ändern:** Doppelklick auf das Typ-Symbol im Spaltenkopf öffnet ein Menü mit allen Typen (aktueller mit Haken); die Auswahl legt sofort den Schritt „Typ ändern“ an (Fehler → Fehlerwert in Zelle).
- **Schrittliste rechts**, Tabelle links. Der Abfragename steht über der Schrittliste.
- Keine ●-Punkte und keine blaue Erklärzeile mehr. Der Name der angeklickten Spalte steht fett über der Tabelle, im Kopf zeigt ► die Spalte.

## Neu in 0.2.3
- **Datentyp-Symbol** links vor jedem Spaltennamen (ABC, 123, 1,2, €, %, Dat, Zeit, J/N). Neue Typen **Währung** (Tausenderpunkt, 2 Nachkommastellen, gerundet) und **Prozent** (2 Stellen), getrennt von Dezimalzahl; in Calc mit Währungs-/Prozentformat geschrieben und wieder erkannt.
- **Doppelklick im Spaltenkopf**: am linken Rand (Symbol) öffnet er den Typdialog mit der ganzen Typliste, sonst wird die Spaltenbreite optimiert (max. ca. 5 cm). Zeilennummern-Spalte wird bei vielen Zeilen breiter.
- Bei Typfehlern ist der Standard „Fehlerwert in Zelle“ (#WERT!, in Calc als Text).
- Klick auf eine Spalte lässt die Ansicht nicht mehr nach links springen.
- **Schrittliste**: führende Null (01., 02. …), Schrittnamen nur über das Menü „Umbenennen …“, die automatische Beschreibung des markierten Schritts steht unter der Liste.
- **Schrittmenü**: Rechtsklick oder Klick im rechten Viertel der Liste; Doppelklick = Ändern. Neu: Umbenennen, Bis zum Ende löschen, Schritt einfügen vor/nach.
- „Nach Einzelwerten filtern“ mit Suchfeld („enthält“), Auswahl bleibt beim Suchen erhalten.
- Rechtsklick in der Tabelle markiert zuerst die Spalte; Namensfeld größer.

## Neu in 0.2.2
- **Spaltenköpfe** sind hellgrau hinterlegt (Fettschrift ist gesetzt, wird aber nicht in jeder LibreOffice-Version dargestellt).
- **Klick auf einen Spaltenkopf** markiert die Spalte sofort mit „► “ im Kopf. Die Markierungszeile steht jetzt **über** der Tabelle. Schritt-betroffene Spalten tragen „● “.
- Die **Vorschau** wird nach Änderungen (Löschen von Schritten, Spalten oder Zeilen) sofort neu gezeichnet.
- **Fenster:** Der Editor öffnet mit 80 % der Arbeitsfläche in der Bildschirmmitte, alle anderen Dialoge ebenfalls mittig.
- **Abfragename** steht jetzt über der Schritteliste.
- **Schritteliste:** Menü per Rechtsklick oder Doppelklick (Nach oben, Nach unten, Ändern, Duplizieren, Ein/Aus, Löschen). Das Menü wirkt auf den markierten Schritt, also zuerst mit Linksklick wählen. Neuer Button **Duplizieren**. Im Quellcode lässt sich das Menü über `SCHRITT_MENUE_RECHTSKLICK` und `SCHRITT_MENUE_DOPPELKLICK` abschalten.
- **Werte ersetzen:** „Nur ganze Zelle ersetzen“ ist im Dialog vorgewählt (alte Abfragen laufen unverändert). Teiltext-Ersetzung wirkt auch in Zahlen: Das Ergebnis bleibt eine Zahl, wenn es eine gültige ist, sonst wird es Text. Außerdem im Spalten-Rechtsklickmenü: „Werte ersetzen …“.

## Neu in 0.2.1
- **Spalte mit Formel:** rechts eine Spaltenliste (Klick fügt `[Spaltenname]` ein) und eine Funktionsliste, unter dem Formelfeld eine Operatorleiste (`+ - * / & ( ) ; = <> < >`) und ein Knopf, der die Auswahl (oder die ganze Formel) mit `RUNDEN(…; n)` umschließt.
- **Bedingte Spalte wie in Power Query:** beliebig viele Klauseln (Wenn / Sonst wenn …) und ein abschließendes Sonst. Pro Klausel mit „+“ weitere Bedingungen, verknüpft mit UND oder ODER (je Klausel eines von beiden, keine Mischung). Der Wert rechts vom Operator und die Ausgabe können fester Text/Zahl, der Wert einer Spalte (derselben Zeile) oder eine Formel sein. Mit „Spalte in Formelfeld einfügen“ werden Spaltennamen in Formelfelder eingefügt. Bereits gespeicherte Abfragen mit der alten bedingten Spalte laufen unverändert weiter.
- **Ausfüllen wie in Power Query:** Rechtsklick auf eine Spalte → Ausfüllen → Unten / Oben. Beide Schritte stehen jetzt in der Gruppe „Spalten“.
