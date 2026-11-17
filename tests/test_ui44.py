# -*- coding: utf-8 -*-
"""0.9.9: Zwischenspeicher, Aktualisieren-Knöpfe, Warnung bei vielen Spalten, Dunkelmodus, Meldungsdialog, Start-Reiter."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def test_editor(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()
        os.environ["ABFRAGE_AUTOCLOSE"] = "0"
        zaehler = {"n": 0}
        orig = AE.lies_quelle

        def zaehlend(c, d_, q):
            zaehler["n"] += 1
            return orig(c, d_, q)
        AE.lies_quelle = zaehlend
        try:
            ed = AE.Editor(ctx, frame, doc, E.Abfrage("L", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:3])))
            ed.run(ohne_dialog=True)
            n0 = zaehler["n"]
            ed.quelle_laden()
            ed.quelle_laden()
            pruefe("Zwischenspeicher: Quelle wird nicht erneut gelesen", zaehler["n"] == n0, "%d -> %d" % (n0, zaehler["n"]))
            ed.quelle_laden(neu=True)
            pruefe("neu=True liest die Quelle neu", zaehler["n"] == n0 + 1, "%d" % zaehler["n"])
            t1 = ed.tabelle_bis(2)
            t2 = ed.tabelle_bis(2)
            pruefe("Schrittergebnis kommt aus dem Zwischenspeicher (dasselbe Objekt)", t1 is t2)
            ed.abfrage.schritte.append({"op": "zeilen_umkehren"})
            t3 = ed.tabelle_bis(len(ed.abfrage.schritte))
            pruefe("Geänderte Schritte werden neu gerechnet", t3 is not t2 and len(t3.zeilen) == len(t2.zeilen))
            ed.abfrage.schritte.pop()
            n1 = zaehler["n"]
            ed.vorschau_aktualisieren()
            pruefe("Aktualisieren liest die Quelle der geöffneten Abfrage neu", zaehler["n"] == n1 + 1, "%d -> %d" % (n1, zaehler["n"]))
            ed.alle_vorschau_aktualisieren()
            pruefe("Alle aktualisieren leert alle Zwischenspeicher",
                   zaehler["n"] >= n1 + 2 and len(ed._cache_q) <= 1, "%d %d" % (zaehler["n"], len(ed._cache_q)))
            # Start-Reiter und Ansicht
            start = [e for e in AE.LEISTE[0][1] if e]
            ids = [e[0] for e in start]
            pruefe("Start: Schließen und Laden, dann Laden in, dann Rückgängig/Wiederholen",
                   ids[:2] == ["laden", "ladenin"] and ids.index("u_rueck") > 1 and ids.index("u_wied") == ids.index("u_rueck") + 1, str(ids[:6]))
            pruefe("Start: Aktualisieren, Alle aktualisieren, Ins Blatt schreiben", all(i in ids for i in ("aktual", "aktalle", "insblatt")))
            pruefe("Ansicht: Maximieren mit Symbol", any(e and e[0] == "maxi" and e[2] == "maximieren" for e in AE.LEISTE[4][1]))
            pruefe("Alle Symbole der Leiste gibt es als Datei",
                   all(AE.symbol_url(e[2]) for _, liste in AE.LEISTE for e in liste if e), "")
            pruefe("Kleine Undo/Redo-Symbole vorhanden", bool(AE.symbol_url("rueckgaengig_k")) and bool(AE.symbol_url("wiederholen_k")))
            pruefe("Abfrageliste: „Duplizieren“ statt „Kopie“", "Kopie" not in str(ed.d.modell("btnAbfDupl").Label) and ed.d.modell("btnAbfDupl").Label == "Duplizieren")
            # neue Abfrage fragt sofort nach der Quelle
            gerufen = []
            ed._spaeter = lambda f: gerufen.append(f)
            ed.quelle_waehlen = lambda: gerufen.append("quelle")
            ed.neue_abfrage()
            pruefe("Neue Abfrage plant den Quellendialog", any(isinstance(g, type(lambda: 0)) for g in gerufen), str(gerufen))
            # Warnung bei vielen Spalten
            log = "/tmp/oq_meldungen44.log"
            if os.path.exists(log):
                os.remove(log)
            viele = E.Tabelle(["Spalte%d" % i for i in range(3)], [[i, "x", i * 2] for i in range(120)])
            ok = ed._spaltenwarnung(viele, {"op": "transponieren"})
            txt = open(log, encoding="utf-8").read() if os.path.exists(log) else ""
            pruefe("Transponieren mit >50 Spalten warnt (Meldung vorhanden)", "erzeugt" in txt and "Spalten" in txt, txt[:120])
            pruefe("... und lässt mit „Ja“ weitermachen", ok is True)
            wenige = E.Tabelle(["A", "B"], [[1, 2], [3, 4]])
            os.remove(log)
            pruefe("Wenige Spalten: keine Warnung", ed._spaltenwarnung(wenige, {"op": "transponieren"}) is True and not os.path.exists(log))
        finally:
            AE.lies_quelle = orig
        # Meldungsdialog (eigener Dialog): schließt mit Ergebnis, ohne Absturz
        os.environ.pop("ABFRAGE_MELDUNGSLOG", None)
        os.environ["ABFRAGE_AUTOCLOSE"] = "1"
        r1 = AE._meldung_dialog(ctx, None, "Eine Meldung\nmit zwei Zeilen", "INFOBOX", 1, "T")
        r3 = AE._meldung_dialog(ctx, None, "Eine Frage?", "QUERYBOX", 3, "T")
        pruefe("Eigene Meldung: OK-Rückgabe 1, Ja/Nein beim Schließen = Nein (3)", (r1, r3) == (1, 3), "%s %s" % (r1, r3))
        os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_meldungen44.log"
        # Dunkelmodus
        d = AE.Dlg(ctx, "Dunkel", 200, 100)
        d.add("Edit", "e", 5, 5, 100, 14)
        d.add("ListBox", "l", 5, 25, 100, 40)
        d.add("ImageControl", "tbi_x", 120, 5, 27, 26, BackgroundColor=0xFFFFFF, Border=2)
        d.add("Grid", "g", 5, 70, 100, 25)
        os.environ["OQ_DUNKEL"] = "1"
        try:
            d.dlg.createPeer(AE.toolkit(ctx), None)
            pruefe("Dunkelmodus wird erkannt (erzwungen)", d.ist_dunkel())
            d.faerbe_dunkel()
            pruefe("Eingabefeld und Liste: warmes mittleres Grau, helle Schrift",
                   d.modell("e").BackgroundColor == AE.Dlg.DUNKEL_FELD and d.modell("l").BackgroundColor == AE.Dlg.DUNKEL_FELD
                   and d.modell("e").TextColor == AE.Dlg.DUNKEL_TEXT)
            pruefe("Symbol im Kopf: flach (kein weißer Kasten)", d.modell("tbi_x").BackgroundColor != 0xFFFFFF and d.modell("tbi_x").Border == 0)
            pruefe("Raster: Grau mit heller Schrift", d.modell("g").BackgroundColor == AE.Dlg.DUNKEL_FELD and d.modell("g").TextColor == AE.Dlg.DUNKEL_TEXT)
        finally:
            os.environ.pop("OQ_DUNKEL", None)
            d.weg()
        # Spaltenliste im Schritt-Dialog: so lang wie sinnvoll, mit Obergrenze
        sd = AE.SchrittDialog.__new__(AE.SchrittDialog)
        f = {"art": "spalten", "label": "Spalten"}
        sd.tab = E.Tabelle(["A", "B", "C"], [])
        h_klein = sd._hoehe(f)
        sd.tab = E.Tabelle(["S%d" % i for i in range(60)], [])
        h_gross = sd._hoehe(f)
        sd._kuerzen = 50
        h_gekuerzt = sd._hoehe(f)
        pruefe("Spaltenliste wächst mit der Spaltenzahl, hat eine Obergrenze und lässt sich kürzen",
               h_klein == 62 and h_gross == 150 and h_gekuerzt == 100, "%s %s %s" % (h_klein, h_gross, h_gekuerzt))
        # Dialog liegt nach dem Setzen ganz auf dem Bildschirm
        d2 = AE.Dlg(ctx, "Rand", 150, 80)
        d2.add("Button", "b", 5, 5, 50, 14, Label="x")
        d2.dlg.createPeer(AE.toolkit(ctx), None)
        wa = AE.toolkit(ctx).getWorkArea()
        d2.dlg.setPosSize(wa.X + wa.Width - 30, wa.Y + wa.Height - 20, 0, 0, 3)
        d2._auf_schirm()
        ps = d2.dlg.getPosSize()
        pruefe("Fenster am Rand wird ganz auf den Bildschirm geschoben",
               ps.X + ps.Width <= wa.X + wa.Width and ps.Y + ps.Height <= wa.Y + wa.Height, "%s %s" % (ps.X + ps.Width, ps.Y + ps.Height))
        d2.weg()
    finally:
        doc.close(True)


def main():
    import faulthandler; faulthandler.dump_traceback_later(250, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_meldungen44.log"
    ctx = T.verbinden()
    try:
        test_editor(ctx)
    except Exception:
        import traceback; traceback.print_exc()
        pruefe("test_editor ohne Ausnahme", False, "Ausnahme")
    fehler = [e for e in T.ergebnisse if not e[1]]
    for e in fehler:
        print("FEHLER", e[0], "->", str(e[2])[:300])
    print("%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))


sys.exit(main())
