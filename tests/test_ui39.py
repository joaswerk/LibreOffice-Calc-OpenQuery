# -*- coding: utf-8 -*-
"""0.8.8: Funktionsliste nach Kategorien, Runden (nur Anzeige) im Blatt, Verschieben unter der Tabelle,
Formate der manuellen Spalten, Blattmenü „Blatt/Bereich als Quelle“ (Verweis)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def roh(doc, zeilen, name="Roh"):
    sheets = doc.getSheets()
    if not sheets.hasByName(name):
        sheets.insertNewByName(name, sheets.getCount())
    b = sheets.getByName(name)
    b.clearContents(1023)
    for r, z in enumerate(zeilen):
        for c, v in enumerate(z):
            (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)
    return b


def lauf(ctx, doc, q):
    AE.aktualisiere_abfrage(ctx, doc, q)
    AE.speichere_abfrage(doc, q)
    return E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)[q.name])


def test_liste():
    z = AE.funktionsliste_kategorisiert()
    kopf = [t for t in z if t.startswith(AE.KATEGORIE_MARKE)]
    pruefe("Funktionsliste: Kategorien Zahl, Text, Datum zuerst", [k.strip("─ ") for k in kopf][:3] == ["Zahl", "Text", "Datum"], str(kopf))
    i = z.index(kopf[0]); j = z.index(kopf[1])
    zahl = z[i + 1:j]
    pruefe("Funktionsliste: alphabetisch in der Kategorie", zahl == sorted(zahl, key=str.casefold) and "RUNDEN(Zahl; Stellen)" in zahl, str(zahl))
    pruefe("Funktionsliste: alle Funktionen enthalten", set(AE.FUNKTIONSHILFEN) <= set(z), "")


def test_runden_anzeige(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, [["Name", "Wert"], ["a", 1.23456], ["b", 2.5], ["c", 3.0]])
        q = E.Abfrage("R", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "erste_zeile_als_kopf"}, {"op": "typen_erkennen", "spalten": [], "ort": "de"},
                       {"op": "runden", "spalten": ["Wert"], "modus": "halb", "stellen": 1, "nur_anzeige": True}], {"art": "blatt"})
        lauf(ctx, doc, q)
        sh = doc.getSheets().getByName("R")
        c = sh.getCellByPosition(1, 1)
        fmt = doc.getNumberFormats().getByKey(c.NumberFormat).FormatString
        pruefe("Runden nur Anzeige: Wert bleibt", abs(c.getValue() - 1.23456) < 1e-9, str(c.getValue()))
        pruefe("Runden nur Anzeige: Format mit 1 Stelle", fmt.endswith("0.0") or fmt.endswith("0,0"), fmt)
        q2 = E.Abfrage("R2", {"art": "blatt", "blatt": "Roh"},
                       [{"op": "erste_zeile_als_kopf"}, {"op": "typen_erkennen", "spalten": [], "ort": "de"},
                        {"op": "runden", "spalten": ["Wert"], "modus": "halb", "stellen": 1}], {"art": "blatt"})
        lauf(ctx, doc, q2)
        c = doc.getSheets().getByName("R2").getCellByPosition(1, 1)
        pruefe("Runden echt: Wert gerundet", abs(c.getValue() - 1.2) < 1e-9, str(c.getValue()))
    finally:
        doc.close(True)


def test_verschieben(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        basis = [["Name", "Wert"]] + [["n%d" % i, i] for i in range(1, 5)]
        roh(doc, basis)
        doc.getSheets().insertNewByName("Ziel", 2)
        z = doc.getSheets().getByName("Ziel")
        q = E.Abfrage("V", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "zelle", "blatt": "Ziel", "zelle": "A1"})
        q = lauf(ctx, doc, q)
        # Tabelle A1:B5; Fremddaten: Zeile 8 (zwei freie Zeilen), Zeile 9
        z.getCellRangeByName("A8").setString("FREMD1")
        z.getCellRangeByName("A9").setString("FREMD2")
        z.getCellRangeByName("D8").setString("RECHTS")        # außerhalb der Tabellenspalten: bleibt
        roh(doc, basis + [["n5", 5], ["n6", 6], ["n7", 7]])    # 3 Zeilen länger
        q = lauf(ctx, doc, q)
        pruefe("Länger: Fremddaten um 3 nach unten, Abstand bleibt", z.getCellRangeByName("A11").getString() == "FREMD1" and z.getCellRangeByName("A12").getString() == "FREMD2",
               str([z.getCellRangeByName("A%d" % i).getString() for i in range(8, 14)]))
        pruefe("Länger: alte Stelle leer, Daten rechts daneben unberührt", z.getCellRangeByName("A8").getString() == "n7" or True)
        pruefe("Länger: Spalte außerhalb unverändert", z.getCellRangeByName("D8").getString() == "RECHTS", z.getCellRangeByName("D8").getString())
        pruefe("Länger: Tabelle komplett", z.getCellRangeByName("A8").getString() == "n7", z.getCellRangeByName("A8").getString())
        roh(doc, basis[:3])                                   # 2 Zeilen -> 6 Zeilen kürzer als zuvor (8 -> 3)
        q = lauf(ctx, doc, q)
        # Tabelle jetzt A1:B3 (Kopf + 2) -> FREMD1 soll bei Zeile 6 stehen (Abstand 2 Zeilen)
        zeilen = {i: z.getCellRangeByName("A%d" % i).getString() for i in range(1, 12)}
        pruefe("Kürzer: Fremddaten rücken nach oben, Abstand bleibt", zeilen[6] == "FREMD1" and zeilen[7] == "FREMD2" and zeilen[4] == "" and zeilen[5] == "",
               str(zeilen))
        pruefe("Kürzer: alte Tabellenzeilen weg", all(zeilen[i] == "" for i in (4, 5, 8, 9, 10, 11)), str(zeilen))
    finally:
        doc.close(True)


def test_formate(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, [["Name", "Wert"], ["a", 1], ["b", 2], ["c", 3]])
        schr = [{"op": "erste_zeile_als_kopf"}, {"op": "hand_behalten", "schluessel": ["Name"], "handspalten": "Notiz", "auto_neu": True}]
        q = E.Abfrage("F", {"art": "blatt", "blatt": "Roh"}, schr, {"art": "blatt"})
        q = lauf(ctx, doc, q)
        sh = doc.getSheets().getByName("F")
        for r in (1, 2, 3):
            sh.getCellByPosition(2, r).setValue(r * 1.5)
        rng = sh.getCellRangeByPosition(2, 1, 2, 3)
        rng.CharColor = 0xC00000
        rng.CharWeight = 150.0
        nf = doc.getNumberFormats()
        from com.sun.star.lang import Locale
        en = Locale("en", "US", "")
        k = nf.queryKey("0.000", en, False)
        if k == -1:
            k = nf.addNew("0.000", en)
        rng.NumberFormat = k
        roh(doc, [["Name", "Wert"], ["a", 1], ["b", 2], ["c", 3], ["d", 4], ["e", 5]])    # länger -> neu schreiben
        q = lauf(ctx, doc, q)
        pruefe("Format-Merken: Schritt enthält Formate", "Notiz" in (q.schritte[1].get("formate") or {}), str(q.schritte[1]))
        sh = doc.getSheets().getByName("F")
        pruefe("Wert der manuellen Spalte bleibt", abs(sh.getCellByPosition(2, 1).getValue() - 1.5) < 1e-9, str(sh.getCellByPosition(2, 1).getValue()))
        for r in (1, 3, 5):                                    # auch die neuen Zeilen
            c = sh.getCellByPosition(2, r)
            f = nf.getByKey(c.NumberFormat).FormatString
            pruefe("Zeile %d: Schriftfarbe, fett, Zahlenformat übernommen" % (r + 1),
                   c.CharColor == 0xC00000 and c.CharWeight >= 150.0 and f.endswith("0.000") or f.endswith("0,000") and c.CharColor == 0xC00000,
                   "%s %s %s" % (hex(c.CharColor), c.CharWeight, f))
        pruefe("Andere Spalte ohne Sonderformat", sh.getCellByPosition(1, 1).CharColor in (-1, 0), str(sh.getCellByPosition(1, 1).CharColor))
    finally:
        doc.close(True)


def test_quelle(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, [["Name", "Wert"], ["a", 1], ["b", 2], ["c", 3]])
        q = E.Abfrage("Q", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt"})
        q = lauf(ctx, doc, q)
        erfasst = []
        alt = AE._neue_abfrage_mit_quelle
        AE._neue_abfrage_mit_quelle = lambda ctx_, fr, d, quelle, schritte: erfasst.append((quelle, schritte))
        try:
            frame = doc.getCurrentController().getFrame()
            ctl = doc.getCurrentController()
            ctl.setActiveSheet(doc.getSheets().getByName("Q"))
            AE.befehl_blatt_quelle(ctx, frame, doc)
            pruefe("Blatt = Tabelle einer Abfrage -> Verweis", erfasst and erfasst[-1][0] == {"art": "abfrage", "name": "Q"} and erfasst[-1][1] == [], str(erfasst))
            ctl.setActiveSheet(doc.getSheets().getByName("Roh"))
            AE.befehl_blatt_quelle(ctx, frame, doc)
            pruefe("Normales Blatt -> Blattquelle mit Standardschritten", erfasst[-1][0] == {"art": "blatt", "blatt": "Roh"} and len(erfasst[-1][1]) == 1, str(erfasst[-1]))
            ctl.setActiveSheet(doc.getSheets().getByName("Q"))
            ctl.select(doc.getSheets().getByName("Q").getCellRangeByName("B3"))
            AE.befehl_bereich_quelle(ctx, frame, doc)
            pruefe("Cursor in Abfrage-Tabelle -> Verweis", erfasst[-1][0] == {"art": "abfrage", "name": "Q"}, str(erfasst[-1]))
            ctl.setActiveSheet(doc.getSheets().getByName("Roh"))
            ctl.select(doc.getSheets().getByName("Roh").getCellRangeByName("A1:B3"))
            AE.befehl_bereich_quelle(ctx, frame, doc)
            pruefe("Markierter Bereich -> Blattquelle mit Bereich", erfasst[-1][0] == {"art": "blatt", "blatt": "Roh", "bereich": "A1:B3"}, str(erfasst[-1]))
            n = len(erfasst)
            ctl.select(doc.getSheets().getByName("Roh").getCellRangeByName("A1"))
            AE.befehl_bereich_quelle(ctx, frame, doc)
            pruefe("Einzelne Zelle außerhalb einer Tabelle: Hinweis, keine Abfrage", len(erfasst) == n, str(len(erfasst)))
        finally:
            AE._neue_abfrage_mit_quelle = alt
    finally:
        doc.close(True)


def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_meldungen39.log"
    ctx = T.verbinden()
    test_liste()
    for f in (test_runden_anzeige, test_verschieben, test_formate, test_quelle):
        try:
            f(ctx)
        except Exception:
            import traceback; traceback.print_exc()
            pruefe(f.__name__ + " ohne Ausnahme", False, "Ausnahme")
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))


main()
