# OpenQuery für LibreOffice Calc (Version 0.10.3)

Power-Query-Stil: Daten laden, in nachvollziehbaren Schritten umformen, als Tabellenblatt ausgeben.
Die Schritte werden in der Datei gespeichert und lassen sich per Klick neu abspielen.
Änderungsverlauf: siehe [CHANGELOG.md](CHANGELOG.md).

## Installation und Update
1. Alte Version zuerst entfernen: *Extras → Erweiterungen → OpenQuery → Entfernen*, LibreOffice schließen.
2. `OpenQuery.oxt` per Doppelklick oder über *Extras → Erweiterungen → Hinzufügen …* installieren, LibreOffice neu starten.
3. Updates: Der Editor prüft einmal täglich bei GitHub (https://github.com/joaswerk/LibreOffice-Calc-OpenQuery/releases), ob es eine neuere Version gibt, und bietet sie an. Manuell: Reiter **Extras → Updates**. Ausschalten: in `~/.openquery-einstellungen.json` den Eintrag `"update_auto": false` setzen (die Datei gibt es nur, wenn du das dauerhafte Speichern von Einstellungen erlaubt hast).

## Menü in Calc: „OpenQuery“
- **Neue Abfrage …** – Quelle wählen, Editor öffnen
- **Abfrage bearbeiten …** – gespeicherte Abfrage dieser Datei ändern
- **Alle Abfragen aktualisieren** – Quellen neu einlesen, alle Zielblätter neu berechnen
- **Abfrage aus Datei öffnen …** – Schrittliste (.abfrage.json) laden, z. B. für den nächsten Auszug
- **Abfrage löschen …** – Abfrage aus der Datei entfernen (auf Wunsch auch das Ausgabeblatt bzw. den Ausgabebereich)

## Quellen
Aktuelles Tabellenblatt (optional mit Bereich), CSV/TXT (Trennzeichen automatisch), XLSX, XLS, ODS, Zwischenablage, Ordner (Dateiliste, auch mit Unterordnern), Liste (aus einem Parameter oder eingetippten Werten).

## Bedienung im Editor
**Kopfzeile.** Reiter *Start, Transformieren, Spalte hinzufügen, Kombinieren, Ansicht, Extras*; jeder Befehl des Editors ist dort erreichbar (die Befehle für Abfragen und Schritte stehen im Start-Reiter hinter **Abfrage ▾** und **Schritt ▾**). Welche Knöpfe der **Start**-Reiter zeigt und in welcher Reihenfolge, bestimmst du unter *Extras → Start anpassen*. Knöpfe mit ▾ öffnen ein kleines Menü, passt nicht alles in die Breite, steht der Rest hinter „Mehr ▾“. Knöpfe wirken auf die markierte Spalte, ohne Markierung öffnet sich der Dialog. **Rückgängig/Wiederholen** (bis 200 Schritte) stehen ganz links im Reiter Start und als kleine Icon-Knöpfe über „Schritt hinzufügen“ unter der Schrittliste; sie wirken nur auf die Abfrage (Quelle, Schritte, Ausgabe-Einstellungen).

**Parameter.** Sie stehen unter den Abfragen als {Name}. Ein Klick zeigt Typ, Wert (bei Listen alle Einträge) und Beschreibung in der Tabellenfläche, Doppelklick/Rechtsklick öffnet das Menü. Ein Klick auf eine Abfrage zeigt wieder die Tabelle.

**Maus.** Ein Klick wählt (Schritt: Vorschau *nach diesem Schritt*; Spaltenkopf: Spalte mit „► “ markiert; Zelle: Zeilendetails). **Rechtsklick** (Linux/Windows) oder **Doppelklick** öffnet das passende Menü (Spalte, Schritt, Abfrage, Tabelle, Zelle). Am Mac gilt nur der Doppelklick; wer den Rechtsklick dort ausprobieren will, schaltet ihn im Reiter *Extras → Rechtsklick* ein. Ist der Rechtsklick eingeschaltet, öffnet er das Menü und der Doppelklick die Bearbeitung des Schritts. Doppelklick auf einen Spaltentrenner optimiert die Breite, Doppelklick auf Schritt 01 ändert die Quelle. Dialoge erscheinen am zuletzt angeklickten Punkt (vollständig auf dem Bildschirm).

**Weiteres.**
- Neue Schritte werden hinter dem gewählten Schritt eingefügt; **Schritt suchen** findet jeden Schritt per Suchfeld (zuletzt benutzte oben).
- Der Spaltenkopf zeigt den Datentyp: ABC (Text), 123 (Zahl), Datum, Dat+Zeit, Zeit, J/N, Mix; „● “ kennzeichnet Spalten, die der gewählte Schritt betrifft, „✎“ manuelle Spalten.
- **Ein/Aus** schaltet einen Schritt ab, ohne ihn zu löschen. **Bedingung** am Schritt: nur ausführen, wenn …
- **Vorschau:** 500 / 2.000 / 10.000 / 100.000 Zeilen wählbar; Spaltenbreiten bleiben erhalten. Fenster in der Größe veränderbar.
- **Ausgabe …:** neues Blatt oder ab einer Zielzelle; fremde Daten werden nicht ohne Nachfrage überschrieben; optional „Beim Öffnen aktualisieren“. Von Hand geänderte Ausgabetabellen werden vor dem Überschreiben gemeldet.
- **Schließen und Laden** schreibt das Ergebnis und speichert die Abfrage in der Datei. Die Quelle wird nie verändert.
- Fehler stehen im Klartext unter dem markierten Schritt (⚠); die Tabelle zeigt den Stand bis zum letzten fehlerfreien Schritt.

## Schritte
**Zeilen**
- Obere Zeilen entfernen
- Untere Zeilen entfernen
- Erste Zeilen behalten
- Untere Zeilen behalten, Zeilenbereich behalten/entfernen, jede n-te Zeile
- Zeilen mit Fehlern entfernen, Zeilen umkehren
- Leere Zeilen entfernen
- Duplikate entfernen
- Zeilen filtern
- Nach Werten filtern (Auswahlliste)
- Zeilen sortieren
- Erste Zeile als Überschriften
- Überschriften als erste Zeile

**Spalten**
- Nach unten / oben ausfüllen (Gruppe Spalten)
- Spalten entfernen
- Nur Spalten behalten
- Spalte umbenennen
- Spalten verschieben
- Spalte duplizieren
- Mehrere Spalten auf einmal umbenennen, Spaltenreihenfolge umkehren, Spalten alphabetisch sortieren

**Text und Werte**
- Werte ersetzen
- Leere Werte ersetzen
- Text umformatieren
- Fehlerwerte ersetzen
- Text extrahieren: vor/nach/zwischen Trennzeichen, erste/letzte Zeichen, ab Position, nur Ziffern, ohne Ziffern

**Gruppieren und Drehen**
- Gruppieren und aggregieren (Summe, Anzahl, Anzahl Werte, Mittelwert, Median, Min, Max, Eindeutige Werte zählen, Erster, Letzter, Alle Werte verketten mit frei wählbarem Trenner, wahlweise ohne doppelte Werte)
- Spalten entpivotieren / Pivotieren
- Transponieren
- Zeilen umkehren

**Neue Spalten**
- Spalten verbinden
- Spalte teilen
- Bedingte Spalte
- Spalte mit Formel
- Indexspalte

**Typen**
- Datentyp ändern
- Datentypen automatisch erkennen

## Formeln (Spalte mit Formel)
Spalten in eckigen Klammern: `[Menge] * [Preis]`, `[Vorname] & " " & [Nachname]`. Argumente mit `;` getrennt.
Text: LINKS, RECHTS, TEIL, LAENGE, GROSS, KLEIN, GLAETTEN, SAEUBERN, WECHSELN, FINDEN, SUCHEN, VERKETTEN, WIEDERHOLEN, TEXT
Logik: WENN, WENNFEHLER, UND, ODER, NICHT, ISTLEER, ISTZAHL, ISTTEXT
Zahlen: RUNDEN, AUFRUNDEN, ABRUNDEN, ABS, GANZZAHL, REST, SUMME, MITTELWERT, MAX, MIN, WERT
Datum: DATUM, JAHR, MONAT, TAG, STUNDE, MINUTE, WOCHENTAG, HEUTE, JETZT, DATWERT
Rechnen mit Datum: `[Datum] + 7`, `[Ende] - [Start]` (Tage). TEXT-Muster: `TEXT([Datum]; "TT.MM.JJJJ")`, `TEXT([Betrag]; "#.##0,00")`.

## Grenzen
- Getestet nur unter Linux mit LibreOffice 24.2. **macOS und Windows sind ungetestet**; Mac-Besonderheiten (Abstürze bei Zeilenkopf-Klicks, Menüs, Rechtsklick-Doppelereignisse) sind dort nur durch Rückmeldungen überprüfbar.
- Die Update-Prüfung ist gegen einen lokalen Mock getestet, nicht gegen das echte GitHub.
- Fette Spaltenköpfe stellt das Raster von LibreOffice nicht dar (grau hinterlegt wird); Spalten lassen sich nicht ganz markieren (► im Kopf).
- Bedingte Spalte: höchstens 14 Zeilen; Mix aus UND und ODER innerhalb einer Klausel geht nicht (dafür „Spalte mit Formel“).
- Eigene Formelsprache, nicht Power Query M. Keine Datenbank-Konnektoren.
- „Nach Werten filtern“ ist eine Mehrfachauswahlliste (Strg/Umschalt-Klick), keine Häkchenliste.
- „Beim Öffnen aktualisieren“ läuft nur bei sichtbar geöffneten Dateien; Zwischenablage-Quellen lassen sich nicht automatisch aktualisieren.
- Oberfläche nur auf Deutsch (Englisch ist vorgemerkt). Die Symbole der Kopfzeile lassen sich nur mit der Maus bedienen.

## Einstellungen und Dateien
OpenQuery legt **keine Datei ohne Nachfrage** an. Einstellungen (Rechtsklick, Start-Reiter, Symbole statt Text, automatisches Speichern …) gelten sofort für diese Sitzung. Beim ersten Ändern fragt OpenQuery, ob sie dauerhaft in `~/.openquery-einstellungen.json` gespeichert werden sollen, damit sie auch für andere Tabellen gelten. Ein **Absturzprotokoll** schreibt OpenQuery nur, wenn du es unter *Extras → Absturzprotokoll* einschaltest.
