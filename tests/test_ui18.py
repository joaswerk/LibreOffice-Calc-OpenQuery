# -*- coding: utf-8 -*-
"""0.7.1: Knöpfe unter der Abfrageliste, einheitliche Breite, Hover am Kopf, Absturzprotokoll, Ausgabe-Ausrichtung."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def main():
    import faulthandler; faulthandler.dump_traceback_later(150, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld18.log")
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        sh = doc.getSheets()
        sh.insertNewByName("Roh", 1)
        b = sh.getByName("Roh")
        for r, z in enumerate([["Name", "Menge", "Datum"], ["a", 1, 45000], ["b", 2, 45001]]):
            for c, v in enumerate(z):
                (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)
        q = E.Abfrage("Q1", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt", "zelle": "B2"})
        ed = AE.Editor(ctx, frame, doc, q)
        ed.run(ohne_dialog=True)
        for n in ("btnAbfAktual", "btnAbfLoeschen", "btnAbfUmben", "btnAbfDupl", "btnAbfVerweis", "btnAbfEigen",
                  "btnAbfHoch", "btnAbfRunter", "chkAuto", "deckLinks"):
            try:
                ed.d.ctrl(n); ok = True
            except Exception:
                ok = False
            pruefe("Steuerelement %s" % n, ok)
        # Einheitliche Breite
        ed.zeige()
        AE.frage_text_orig = AE.frage_text
        AE.frage_text = lambda *a, **k: "77"
        try:
            ed.einheitliche_breite()
        finally:
            AE.frage_text = AE.frage_text_orig
        pruefe("Einheitliche Breite gesetzt", ed._grid_namen and all(int(ed.breiten[n]) == 77 for n in ed._grid_namen),
               str(ed.breiten))
        pm, ids = ed.baue_tabellenmenue()
        pruefe("Tabellenmenü: Breite einheitlich", ("breite_einheit",) in ids.values())
        # Hover
        class Ev: X = 100; Y = 2
        ed._tipp_kopf = None
        g = ed.d.alias.get("grid")
        try:
            ed._kopf_tipp(Ev, g)
            pruefe("Hover: Methode läuft", True)
        except Exception as e:
            pruefe("Hover: Methode läuft", False, str(e))
        # Ausgabe: Kopf links, Zahlen rechts
        AE.aktualisiere_abfrage(ctx, doc, q)
        z = sh.getByName("Q1") if sh.hasByName("Q1") else None
        if z is not None:
            kopf = z.getCellRangeByName("B2")
            pruefe("Ausgabe: Kopf linksbündig", kopf.HoriJustify.value == "LEFT", kopf.HoriJustify.value)
        pruefe("Absturzprotokoll angelegt", os.path.exists(AE._ABSTURZLOG))
    finally:
        try: doc.close(True)
        except Exception: pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
