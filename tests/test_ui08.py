# -*- coding: utf-8 -*-
"""Tests für 0.4.0: Raster-Listen, Rechtsklick wählt Eintrag, Zeilendetails, Gitternetz, rechtsbündig, Teiler, Spaltenbreite."""
import os, sys, time, json, threading, types, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
import uno
AE, E = T.AE, T.E
pruefe = T.pruefe
SCRATCH = os.environ.get("SCRATCH", "/tmp")


def main():
    import faulthandler
    faulthandler.dump_traceback_later(200, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(SCRATCH, "meld08.log")
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()
        os.environ["ABFRAGE_AUTOCLOSE"] = "30"
        a = E.Abfrage("Bericht", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE))
        AE.speichere_abfrage(doc, a)
        for n in ("Zwei", "Drei", "Vier", "Fuenf"):
            AE.speichere_abfrage(doc, E.Abfrage(n, {"art": "blatt", "blatt": "Auszug"}, []))
        ed = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(a.to_json()))
        res = {}

        def tun():
            try:
                time.sleep(7)
                d = ed.d
                # Listen sind Raster, oben bündig mit der Tabelle
                pos = lambda n: d.modell(n)
                res["oben"] = (pos("lstSchritte").PositionY, pos("lstAbfragen").PositionY, pos("grid").PositionY)
                # Rechtsklick wählt den Eintrag unter dem Mauszeiger
                ps = d.ctrl("lstSchritte").getPosSize()
                z = ed.lstS.zeile_bei(30, 25)
                res["zeile_bei"] = z
                aufr = []
                orig = ed.zeige_schritt_menue
                ed.zeige_schritt_menue = lambda x, y: aufr.append(ed.lstS.pos())
                ed.lstS.waehle(len(T.SCHRITTE))
                ed.schritt_maus(types.SimpleNamespace(X=90, Y=25, PopupTrigger=True, ClickCount=1, Buttons=2))     # Rechtsklick öffnet das Menü (Doppelklick bearbeitet)
                time.sleep(1.2)
                ed.zeige_schritt_menue = orig
                res["rechts_wahl"] = (z, aufr)
                # Abfragenliste: Rechtsklick auf Eintrag 3 wechselt die Abfrage
                za = ed.lstA.zeile_bei(20, 3 * 16 - 8)
                res["za"] = za
                m = []
                oz = ed.zeige_abfragen_menue
                ed.zeige_abfragen_menue = lambda x, y: m.append(ed.aktuell)
                ed.abfragen_maus(types.SimpleNamespace(X=20, Y=3 * 16 - 8, PopupTrigger=False, ClickCount=2, Buttons=1))
                time.sleep(1.5)
                ed.zeige_abfragen_menue = oz
                res["abfr_rechts"] = (za, m, ed.aktuell, ed.abfrage.name)
                ed._wechsle_zu(next(i for i, e in enumerate(ed.arbeit) if e["a"].name == "Bericht"))
                time.sleep(1)
                # Zeilendetails
                ed.zeige_details(2)
                dm = d.model.getByName("gridDetail").GridDataModel
                res["det_rows"] = dm.RowCount
                res["det_inhalt"] = [dm.getCellData(0, i) for i in range(2)] + [dm.getCellData(1, i) for i in range(2)]
                res["det_label"] = d.ctrl("lblDetail").getModel().Label
                # Gitternetz
                d.ctrl("chkGitter").getModel().State = 1
                ed._gitter_geaendert()
                gm = d.modell("grid")
                res["gitter"] = (gm.UseGridLines, list(gm.RowBackgroundColors))
                time.sleep(1.5)
                os.system("DISPLAY=:99 import -window root %s/shot_gitter.png" % SCRATCH)
                d.ctrl("chkGitter").getModel().State = 0
                ed._gitter_geaendert()
                res["gitter_aus"] = (gm.UseGridLines, len(set(gm.RowBackgroundColors or ())))
                # Details aus/an
                ed._details_umschalten(False)
                res["det_aus_pos"] = d.model.getByName("gridDetail").PositionX
                ed._details_umschalten(True)
                res["det_an_pos"] = d.model.getByName("gridDetail").PositionX
                # Teiler ziehen
                b0 = ed.breite_a
                ed._teiler_start(1, types.SimpleNamespace(Source=d.ctrl("sp1l"), X=2))
                ps1 = d.ctrl("sp1l").getPosSize()
                ed._teiler_bewegt(types.SimpleNamespace(Source=d.ctrl("sp1l"), X=2 + 40, Buttons=1))
                ed._ziehen_ende()
                res["teiler"] = (b0, ed.breite_a)
                ed._teiler_start(2, types.SimpleNamespace(Source=d.ctrl("sp2l"), X=2))
                s0 = ed.breite_s
                ed._teiler_bewegt(types.SimpleNamespace(Source=d.ctrl("sp2l"), X=2 - 40, Buttons=1))
                ed._ziehen_ende()
                res["teiler_s"] = (s0, ed.breite_s)
                # Ansicht gespeichert
                ed._ansicht_speichern()
                res["ansicht"] = doc.getDocumentProperties().getUserDefinedProperties().getPropertyValue(AE.PROP_ANSICHT)
                # rechtsbündige Spalten
                cols = d.modell("grid").ColumnModel.getColumns()
                res["align"] = {n: str(c.HorizontalAlign.value) for n, c in zip(["Nr."] + ed._grid_namen, cols)}
                res["arten"] = {n: ed._arten[n] for n in ed._grid_namen}
                # Tooltips
                ed.lstS._bewegt(types.SimpleNamespace(X=30, Y=40))
                res["tipp"] = d.model.getByName("lstSchritte").HelpText
                # Spaltenbreite
                name = ed._grid_namen[0]
                os.environ["ABFRAGE_FRAGETEXT"] = "77"
                ed.spaltenbreite_eingeben(name)
                os.environ.pop("ABFRAGE_FRAGETEXT", None)
                res["breite"] = ed.breiten.get(name)
                # Aktualisieren einer Abfrage
                ed.ins_blatt_schreiben()
                res["aktual"] = open(os.environ["ABFRAGE_MELDUNGSLOG"], encoding="utf-8").read()[-200:]
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=tun, daemon=True)
        th.start()
        ed.run()
        th.join()
        pruefe("Listen und Tabelle beginnen oben bündig", len(set(res.get("oben", (0, 1, 2)))) == 1, str(res.get("oben")))
        pruefe("Rechtsklick: Zeile unter dem Zeiger erkannt", res.get("zeile_bei", -1) >= 0, str(res.get("zeile_bei")))
        z, aufr = res.get("rechts_wahl", (-9, []))
        pruefe("Rechtsklick wählt den Schritt unter dem Zeiger und öffnet das Menü", len(aufr) == 1 and aufr[0] == z, str(res.get("rechts_wahl")))
        za, m, akt, nm = res.get("abfr_rechts", (-9, [], -1, ""))
        pruefe("Doppelklick auf Abfrage wechselt die Abfrage und öffnet das Menü", za >= 0 and m == [za] and akt == za, str(res.get("abfr_rechts")))
        pruefe("Zeilendetails: ein Eintrag je Spalte", res.get("det_rows", 0) >= 5, str(res.get("det_rows")))
        pruefe("Zeilendetails: Spaltenname | Wert", res.get("det_inhalt", [""])[0] != "" and "Zeile 3" in res.get("det_label", ""), str(res))
        g = res.get("gitter", (False, []))
        pruefe("Gitternetz an: Linien und einfarbige Zeilen", g[0] is True and len(g[1]) == 1, str(g))
        ga = res.get("gitter_aus", (True, 9))
        pruefe("Gitternetz aus: Bänderung wie zuvor", ga[0] is False and ga[1] == 2, str(ga))
        pruefe("Zeilendetails ausblenden/einblenden", res.get("det_aus_pos", 0) < 0 and res.get("det_an_pos", -1) > 0,
               "%s %s" % (res.get("det_aus_pos"), res.get("det_an_pos")))
        t1 = res.get("teiler", (0, 0)); t2 = res.get("teiler_s", (0, 0))
        pruefe("Teiler 1 ziehen verbreitert die Abfragenliste", t1[1] > t1[0], str(t1))
        pruefe("Teiler 2 nach links ziehen verbreitert die Schrittliste", t2[1] > t2[0], str(t2))
        pruefe("Ansicht wird in der Datei gespeichert", '"a"' in res.get("ansicht", ""), res.get("ansicht", ""))
        al = res.get("align", {})
        pruefe("Alle Spaltenüberschriften linksbündig (auch Zahlen/Datum)", al and all(a == "LEFT" for a in al.values()), str(al))
        pruefe("Hover-Text der Schrittliste", res.get("tipp", "") != "", res.get("tipp", ""))
        pruefe("Spaltenbreite per Eingabe", res.get("breite") == 77, str(res.get("breite")))
        pruefe("Ins Blatt schreiben meldet die Zeilenzahl", "aktualisiert" in res.get("aktual", ""), res.get("aktual", ""))
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    for e in fehler:
        print("  FEHLER:", e[0], e[2] if len(e) > 2 else "")
    sys.exit(1 if fehler else 0)


main()
