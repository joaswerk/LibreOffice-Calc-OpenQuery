# -*- coding: utf-8 -*-
"""0.9.0: Reiter und Symbolknöpfe im Kopfband."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def test_statisch():
    ops = [e[3][1] for _, es in AE.LEISTE for e in es if e and e[3][0] == "op"]
    ops += [o for _, es in AE.LEISTE for e in es if e and e[3][0] == "menu" for _, o in e[3][1] if isinstance(o, str)]
    fehl = [o for o in ops if o not in E.OPS]
    pruefe("Leiste: alle Schritte existieren", not fehl, str(fehl))
    ohne = [e[2] for _, es in AE.LEISTE for e in es if e and not os.path.exists(os.path.join(AE._hier, "icons", e[2] + ".png"))]
    pruefe("Leiste: alle Symbole vorhanden", not ohne, str(ohne))
    alle = set(ops)
    pruefe("Leiste: jeder Schritt ist erreichbar", alle >= set(E.OPS), str(set(E.OPS) - alle))
    ids = [e[0] for _, es in AE.LEISTE for e in es if e]
    pruefe("Leiste: Kennungen eindeutig", len(ids) == len(set(ids)), "")


def test_editor(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()
        os.environ["ABFRAGE_AUTOCLOSE"] = "0"
        ed = AE.Editor(ctx, frame, doc, E.Abfrage("L", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:3])))
        ed.run(ohne_dialog=True)
        d = ed.d
        ed.leiste_reiter(0)
        px = lambda n: d.ctrl(n).getPosSize()
        pruefe("Rückgängig/Wiederholen ganz links im Start-Reiter, vor Aktualisieren",
               0 < px("tbi_u_rueck").X < px("tbi_u_wied").X < px("tbi_aktual").X, "%s %s %s" % (px("tbi_u_rueck").X, px("tbi_u_wied").X, px("tbi_aktual").X))
        pruefe("Kleine Icon-Knöpfe unter den Schritten sichtbar, rechts von der Schrittliste",
               px("btnUndoK").X >= px("lstSchritte").X - 1 and px("btnRedoK").X > px("btnUndoK").X and px("btnUndoK").Y > px("lstSchritte").Y,
               "%s %s" % (px("btnUndoK").X, px("lstSchritte").X))
        pruefe("Start: Aktualisieren sichtbar", px("tbi_aktual").X > 0, str(px("tbi_aktual").X))
        pruefe("Start: Gitternetz (Ansicht) geparkt", px("tbi_gitter").X < 0, "")
        ed.leiste_reiter(4)
        pruefe("Ansicht: Gitternetz sichtbar, Start geparkt", px("tbi_gitter").X > 0 and px("tbi_aktual").X < 0, "")
        pruefe("Reiter gemerkt", AE._LETZTER_TAB[0] == 4, "")
        vorher = d.ctrl("chkGitter").getModel().State
        g0 = ed.gitter
        ed.leiste_klick(("gitter", "", "gitter", ("tgl", "chkGitter"), ""))
        pruefe("Gitternetz-Knopf schaltet das Häkchen", d.ctrl("chkGitter").getModel().State != vorher,
               "%s -> %s" % (vorher, d.ctrl("chkGitter").getModel().State))
        pruefe("Gitternetz-Knopf ändert die Ansicht", ed.gitter != g0 and d.model.getByName(ed.d.alias.get("grid", "grid")).UseGridLines == ed.gitter,
               str(ed.gitter))
        d0 = ed.details_an
        ed.leiste_klick(("det", "", "details", ("tgl", "chkDetails"), ""))
        pruefe("Zeilendetails-Knopf ändert die Ansicht", ed.details_an != d0, str(ed.details_an))
        s0 = ed.schritte_an
        ed.leiste_klick(("schl", "", "x", ("tgl", "chkSchr"), ""))
        pruefe("Schrittliste-Knopf blendet die Liste aus/ein", ed.schritte_an != s0, str(ed.schritte_an))
        ed.leiste_klick(("schl", "", "x", ("tgl", "chkSchr"), ""))
        pruefe("Schrittliste wieder an", ed.schritte_an == s0, "")
        ed._leiste_xs = 330
        ed.leiste_reiter(6)
        pruefe("Schmal: Überlauf-Menü „Mehr“ erscheint", len(ed._ueberlauf) > 0 and px("tbi_u_mehr").X > 0, str(len(ed._ueberlauf)))
        ed._leiste_xs = 2000
        ed.leiste_platzieren()
        ed._leiste_undo_x = None; ed.leiste_platzieren()
        pruefe("Breit: kein Überlauf", not ed._ueberlauf and px("tbi_u_mehr").X < 0, "")
        ed._leiste_xs = 640
        ed.leiste_reiter(4)
        pruefe("Vorbelegung Spalte", ed._vorbelegung("spalten_entfernen", "Objekt") == {"spalten": ["Objekt"]}, str(ed._vorbelegung("spalten_entfernen", "Objekt")))
        n0 = len(ed.abfrage.schritte)
        ed.leiste_schritt("zeilen_umkehren") if "zeilen_umkehren" in E.OPS else None
        pruefe("Schritt über die Leiste hinzugefügt", len(ed.abfrage.schritte) == n0 + 1, str(len(ed.abfrage.schritte)))
        AE._LETZTER_TAB[0] = 0
    finally:
        doc.close(True)


def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_meldungen41.log"
    ctx = T.verbinden()
    test_statisch()
    try:
        test_editor(ctx)
    except Exception:
        import traceback; traceback.print_exc()
        pruefe("test_editor ohne Ausnahme", False, "Ausnahme")
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))


main()
