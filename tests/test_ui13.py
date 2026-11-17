# -*- coding: utf-8 -*-
"""0.6.0: Parameter aus benannten Zellen, Handeinträge behalten (Selbstreferenz), Dialog-Knopf „Wert aus Zelle“."""
import os, sys, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uno
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def schreibe(doc, name, rows, col0=0, row0=0):
    sh = doc.getSheets()
    if not sh.hasByName(name):
        sh.insertNewByName(name, sh.getCount())
    b = sh.getByName(name)
    for r, z in enumerate(rows):
        for c, v in enumerate(z):
            cell = b.getCellByPosition(col0 + c, row0 + r)
            cell.setString(v) if isinstance(v, str) else cell.setValue(v)
    return b


def main():
    import faulthandler
    faulthandler.dump_traceback_later(150, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld13.log")
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        schreibe(doc, "Roh", [["Name", "Menge"], ["a", 1], ["b", 3], ["c", 5], ["d", 7]])
        par = schreibe(doc, "Parameter", [["Schwelle", 3]])
        adr = par.getCellByPosition(1, 0).getCellAddress()
        doc.NamedRanges.addNewByName("Schwelle", "$Parameter.$B$1", adr, 0)
        AE._EDITOR_KONTEXT["doc"] = doc

        # --- Parameter ---
        a = E.Abfrage("Gross", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "erste_zeile_als_kopf"}, {"op": "filtern", "spalte": "Menge", "bedingung": "groesser_gleich", "wert": "{Schwelle}"}])
        n = AE.aktualisiere_abfrage(ctx, doc, a)
        pruefe("Parameter {Schwelle}=3 im Filter: 3 Zeilen", n == 3, str(n))
        par.getCellByPosition(1, 0).setValue(5)
        n = AE.aktualisiere_abfrage(ctx, doc, a)
        pruefe("Zelle geändert auf 5: 2 Zeilen", n == 2, str(n))
        pruefe("Parameterliste enthält Schwelle mit Wert", ("Schwelle", "5") in AE.parameter_liste(doc), str(AE.parameter_liste(doc)))
        b = E.Abfrage("Fehl", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "erste_zeile_als_kopf"}, {"op": "filtern", "spalte": "Menge", "bedingung": "groesser_gleich", "wert": "{Gibtsnicht}"}])
        try:
            AE.aktualisiere_abfrage(ctx, doc, b)
            pruefe("Fehlender Parameter -> Fehler", False)
        except Exception as e:
            pruefe("Fehlender Parameter -> Fehler mit Parameternamen", "Gibtsnicht" in str(e), str(e))
        par.getCellByPosition(1, 0).setString("")
        try:
            AE.aktualisiere_abfrage(ctx, doc, a)
            pruefe("Leere Parameterzelle -> Fehler", False)
        except Exception as e:
            pruefe("Leere Parameterzelle -> Fehler mit Parameternamen", "Schwelle" in str(e), str(e))
        par.getCellByPosition(1, 0).setValue(3)

        # --- Handeinträge behalten ---
        p = E.Abfrage("Pflege", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "erste_zeile_als_kopf"}, {"op": "hand_behalten", "schluessel": ["Name"], "handspalten": "Notiz"}])
        AE.aktualisiere_abfrage(ctx, doc, p)
        AE.speichere_abfrage(doc, p)
        sh = doc.getSheets().getByName("Pflege")
        pruefe("Spalte Notiz angelegt (leer)", sh.getCellByPosition(2, 0).getString() == "Notiz" and sh.getCellByPosition(2, 2).getString() == "")
        sh.getCellByPosition(2, 2).setString("handschriftlich")          # Zeile b
        AE.aktualisiere_abfrage(ctx, doc, p)
        sh = doc.getSheets().getByName("Pflege")
        pruefe("Handeintrag bleibt nach Aktualisieren", sh.getCellByPosition(2, 2).getString() == "handschriftlich")
        p.schritte.insert(1, {"op": "sortieren", "spalte1": "Name", "richtung1": "ab"})
        AE.aktualisiere_abfrage(ctx, doc, p)
        sh = doc.getSheets().getByName("Pflege")
        zeilen = {sh.getCellByPosition(0, r).getString(): sh.getCellByPosition(2, r).getString() for r in range(1, 5)}
        pruefe("Handeintrag folgt dem Schlüssel (auch nach Umsortieren)", zeilen.get("b") == "handschriftlich" and zeilen.get("a") == "", str(zeilen))
        roh = doc.getSheets().getByName("Roh")
        roh.getCellByPosition(0, 2).setString("zz")                      # Schlüssel b verschwindet
        AE.aktualisiere_abfrage(ctx, doc, p)
        pruefe("Verworfene Handeinträge werden gemeldet", any("verworfen" in h for h in E.HINWEISE), str(E.HINWEISE))
        roh.getCellByPosition(0, 2).setString("b")

        # --- Knopf „Wert aus Zelle…“ im Schrittdialog ---
        os.environ["ABFRAGE_AUTOOK"] = "6"
        os.environ["ABFRAGE_AUTOCLOSE"] = "9"
        tab = E.Tabelle(["Name", "Menge"], [["a", 1]])
        fd = AE.SchrittDialog(ctx, "filtern", tab, None, {"spalte": "Name", "bedingung": "gleich", "wert": ""}, None)
        erg = {}
        alt = AE.waehle_aus_liste
        AE.waehle_aus_liste = lambda *a, **k: 0

        def klick():
            time.sleep(1.5)
            try:
                erg["knopf"] = "btnParam" in list(fd.d.model.getElementNames())
                fd._parameter_einfuegen()
                erg["text"] = fd.d.ctrl("f_wert").getText()
            except Exception as e:
                import traceback; traceback.print_exc(); erg["fehler"] = str(e)
        th = threading.Thread(target=klick, daemon=True); th.start()
        fd.zeigen()
        th.join(10)
        AE.waehle_aus_liste = alt
        pruefe("Schrittdialog hat den Knopf „Wert aus Zelle…“", erg.get("knopf") is True, str(erg))
        pruefe("Auswahl fügt {Schwelle} ins Feld ein", erg.get("text") == "{Schwelle}", str(erg))
    finally:
        doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
