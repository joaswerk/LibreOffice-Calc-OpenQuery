# -*- coding: utf-8 -*-
"""Tests für 0.5.0: Nur Verbindung, intelligente Tabelle (tbl_…, Farben, Bänderung, Autofilter, Reiter)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def schreibe(doc, name, rows):
    sh = doc.getSheets()
    if not sh.hasByName(name):
        sh.insertNewByName(name, sh.getCount())
    b = sh.getByName(name)
    for r, z in enumerate(rows):
        for c, v in enumerate(z):
            cell = b.getCellByPosition(c, r)
            cell.setString(v) if isinstance(v, str) else cell.setValue(v)


def main():
    import faulthandler
    faulthandler.dump_traceback_later(100, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld11.log")
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        schreibe(doc, "Roh", [["Name", "Menge", "Preis"], ["a", 1, 2], ["b", 3, 4], ["c", 5, 6], ["d", 7, 8]])
        sh = doc.getSheets()
        db = doc.DatabaseRanges

        # --- Intelligente Tabelle (Standard) ---
        a = E.Abfrage("Zähler Strom", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}])
        n = AE.aktualisiere_abfrage(ctx, doc, a)
        ausg = sh.getByName(AE.gueltiger_blattname("Zähler Strom"))
        pruefe("Bereichsname tbl_ + Abfragename, Sonderzeichen zu _", a.ziel.get("bereich") == "tbl_Zähler_Strom", str(a.ziel))
        pruefe("Datenbankbereich vorhanden", db.hasByName("tbl_Zähler_Strom"))
        d = db.getByName("tbl_Zähler_Strom")
        ad = d.getDataArea()
        pruefe("Bereich umfasst Kopf + Daten", (ad.StartRow, ad.EndRow, ad.StartColumn, ad.EndColumn) == (0, 4, 0, 2), str((ad.StartRow, ad.EndRow, ad.EndColumn)))
        pruefe("Autofilter an, Kopfzeile erkannt", d.AutoFilter is True and d.ContainsHeader is True)
        pruefe("Kopfzeile dunkelblau, Schrift weiß", ausg.getCellByPosition(0, 0).CellBackColor == 0x1F4E79 and ausg.getCellByPosition(0, 0).CharColor == 0xFFFFFF)
        cf = ausg.getCellRangeByPosition(0, 1, 2, 4).ConditionalFormat
        pruefe("Bänderung als bedingte Formatierung", cf.getCount() == 1, str(cf.getCount()))
        pruefe("Reiterfarbe standardmäßig aus", ausg.TabColor == -1, str(ausg.TabColor))

        # Spalte kommt dazu, Zeilen werden weniger: Bereich folgt
        a.schritte = [{"op": "erste_zeile_als_kopf"}, {"op": "benutzerdefinierte_spalte", "neu": "Summe", "formel": "[Menge] + [Preis]"},
                      {"op": "zeilen_entfernen_unten", "anzahl": 1}]
        AE.aktualisiere_abfrage(ctx, doc, a)
        ad = db.getByName("tbl_Zähler_Strom").getDataArea()
        pruefe("Aktualisieren: Bereich wächst in den Spalten, schrumpft in den Zeilen", (ad.EndColumn, ad.EndRow) == (3, 3), str((ad.EndColumn, ad.EndRow)))
        pruefe("Nur ein Bereich (kein Rest)", sum(1 for nme in db.getElementNames() if nme.startswith("tbl_")) == 1, str(list(db.getElementNames())))

        # Farbe + Reiter (Opt-in) + Bänderung aus
        a.ziel.update(farbe="gruen", reiter=True, baender=False)
        AE.aktualisiere_abfrage(ctx, doc, a)
        ausg = sh.getByName(AE.gueltiger_blattname("Zähler Strom"))
        pruefe("Farbe Grün: Kopf und Reiter", ausg.getCellByPosition(0, 0).CellBackColor == 0x375623 and ausg.TabColor == 0x375623,
               "%x %x" % (ausg.getCellByPosition(0, 0).CellBackColor, ausg.TabColor))
        pruefe("Bänderung aus: keine bedingte Formatierung", ausg.getCellRangeByPosition(0, 1, 2, 3).ConditionalFormat.getCount() == 0)
        a.ziel.update(reiter=False)
        AE.aktualisiere_abfrage(ctx, doc, a)
        pruefe("Reiterfarbe wird zurückgenommen", sh.getByName(AE.gueltiger_blattname("Zähler Strom")).TabColor == -1)
        a.ziel.update(tabelle=False)
        AE.aktualisiere_abfrage(ctx, doc, a)
        ausg = sh.getByName(AE.gueltiger_blattname("Zähler Strom"))
        pruefe("Ohne intelligente Tabelle: kein Bereich, keine Farbe", not db.hasByName("tbl_Zähler_Strom") and ausg.getCellByPosition(0, 0).CellBackColor == -1 and "bereich" not in a.ziel,
               str(a.ziel))

        # Zielzelle: Bereich dort
        b = E.Abfrage("Ziel", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}],
                      {"art": "zelle", "blatt": "Zielblatt", "zelle": "C3"})
        sh.insertNewByName("Zielblatt", sh.getCount())
        AE.aktualisiere_abfrage(ctx, doc, b)
        ad = db.getByName("tbl_Ziel").getDataArea()
        pruefe("Zielzelle: Bereich ab C3", (ad.StartColumn, ad.StartRow) == (2, 2), str((ad.StartColumn, ad.StartRow)))
        pruefe("Zielzelle: Reiter bleibt unberührt", sh.getByName("Zielblatt").TabColor == -1)

        # --- Nur Verbindung ---
        v = E.Abfrage("Basis", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "keine"})
        AE.speichere_abfrage(doc, v)
        AE.aktualisiere_abfrage(ctx, doc, v)
        pruefe("Verbindung: kein Blatt, kein Bereich", not sh.hasByName("Basis") and not db.hasByName("tbl_Basis"))
        w = E.Abfrage("Abgeleitet", {"art": "abfrage", "name": "Basis"}, [{"op": "spalten_entfernen", "spalten": ["Preis"]}])
        n = AE.aktualisiere_abfrage(ctx, doc, w)
        pruefe("Verweis auf Verbindungs-Abfrage liefert Daten", n == 4 and sh.getByName("Abgeleitet").getCellByPosition(1, 1).Value == 1, str(n))
        ok, fehler = AE.aktualisiere_alle(ctx, doc)
        pruefe("Alle aktualisieren: Verbindung ohne Fehler, als solche genannt", not fehler and any("nur Verbindung" in t for t in ok), str((ok, fehler)))

        # Editor: Markierung in der Liste, Laden schreibt nichts
        AE.speichere_abfrage(doc, w)
        ed = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(v.to_json()))
        ed.run(ohne_dialog=True)
        pruefe("Liste kennzeichnet die Verbindung", any(t == "↔ Basis" for t in ed.lstA.items), str(ed.lstA.items))
        ed.abfrage.name = "Basis"
        r = ed.laden(schliessen=False)
        pruefe("Laden schreibt für eine Verbindung kein Blatt", not sh.hasByName("Basis"))
        ed._zum_ausgabeblatt()
        # Umbenennen: Bereich folgt dem neuen Namen
        c = E.Abfrage("Alt", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}])
        AE.aktualisiere_abfrage(ctx, doc, c)
        AE.speichere_abfrage(doc, c)
        pruefe("Bereich tbl_Alt", db.hasByName("tbl_Alt"))
        c.name = "Neu"
        AE.aktualisiere_abfrage(ctx, doc, c)
        pruefe("Nach Umbenennen: tbl_Neu da, tbl_Alt weg", db.hasByName("tbl_Neu") and not db.hasByName("tbl_Alt"))
        AE.loesche_abfrage(doc, "Neu", True)
        pruefe("0.6.0: Löschen lässt den Bereich tbl_Neu stehen", db.hasByName("tbl_Neu"))
        d2 = E.Abfrage("Neu", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}])
        AE.aktualisiere_abfrage(ctx, doc, d2)
        pruefe("Neue Abfrage gleichen Namens übernimmt den verwaisten Bereich (kein _2)",
               d2.ziel.get("bereich") == "tbl_Neu" and not db.hasByName("tbl_Neu_2"), str(d2.ziel.get("bereich")))
    finally:
        doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
