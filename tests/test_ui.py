# -*- coding: utf-8 -*-
"""UI-Test: Menübefehle (Handler in LibreOffice), echte Dialoge, Screenshots."""
import os
import subprocess
import sys
import threading
import time
import traceback

import uno

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T  # noqa: E402

AE, E = T.AE, T.E
SCRATCH = os.environ.get("SCRATCH", "/tmp")
LOG = os.path.join(SCRATCH, "meldungen.log")


def screenshot(name, verzoegerung):
    def tun():
        time.sleep(verzoegerung)
        subprocess.run(["import", "-window", "root", os.path.join(SCRATCH, name)],
                       env=dict(os.environ, DISPLAY=":99"), timeout=30)
    t = threading.Thread(target=tun, daemon=True)
    t.start()
    return t


def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        sh = T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()
        smgr = ctx.ServiceManager

        # --- Menüeinträge in der Konfiguration vorhanden? ---------------------------------
        prov = smgr.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
        cfg = prov.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess",
            (T.PropertyValue("nodepath", 0, "/org.openoffice.Office.Addons/AddonUI/OfficeMenuBar", 0),))
        T.pruefe("Menü 'Abfrage-Editor' in der Konfiguration", cfg.hasByName("org.joaswerk.abfrageeditor.menu"),
                 str(cfg.getElementNames()))
        sub = cfg.getByName("org.joaswerk.abfrageeditor.menu").getByName("Submenu")
        T.pruefe("6 Menüeinträge (OpenQuery)", len(sub.getElementNames()) == 6, str(sub.getElementNames()))

        # --- Abfrage anlegen (wie nach 'Schließen und Laden') ----------------------------------
        a = E.Abfrage("Bericht", {"art": "blatt", "blatt": "Auszug"}, [])
        ed = AE.Editor(ctx, frame, doc, a)
        ed.run(ohne_dialog=True)
        for s in T.SCHRITTE:
            ed.neuer_schritt(s["op"], {k: v for k, v in s.items() if k != "op"}, direkt=True)
        ed.laden()
        T.pruefe("Abfrage geladen (Vorbereitung)", doc.getSheets().hasByName("Bericht"))

        # --- Handler: aktualisieren (läuft im LibreOffice-Prozess über die installierte .oxt) -----
        sh.getCellByPosition(4, 9).setValue(4000.0)
        helper = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
        if os.path.exists(LOG):
            os.remove(LOG)
        helper.executeDispatch(frame, "org.joaswerk.abfrageeditor:aktualisieren", "", 0, ())
        log = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
        T.pruefe("Handler 'aktualisieren' meldet Erfolg", "Aktualisiert" in log and "Bericht" in log, log)
        ziel = doc.getSheets().getByName("Bericht")
        kopf = [ziel.getCellByPosition(c, 0).getString() for c in range(12)]
        sp = kopf.index("Verbrauch kWh")
        werte = sorted(ziel.getCellByPosition(sp, r).getValue() for r in range(1, 6))
        T.pruefe("Handler hat Zielblatt aktualisiert", 4000.0 in werte, str(werte))

        # --- Handler: neu (Quellendialog, schließt per Timer) -------------------------------------
        sc = screenshot("shot_quelle.png", 2.5)
        t0 = time.time()
        helper.executeDispatch(frame, "org.joaswerk.abfrageeditor:neu", "", 0, ())
        sc.join()
        log = open(LOG, encoding="utf-8").read()
        T.pruefe("Handler 'neu': Quellendialog öffnet ohne Fehlermeldung", "ERRORBOX" not in log and time.time() - t0 > 2,
                 "%.1fs, Log: %s" % (time.time() - t0, log[-300:]))

        # --- Hauptdialog sichtbar, Screenshot ------------------------------------------------------
        os.environ["ABFRAGE_AUTOCLOSE"] = "7"
        ed2 = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Bericht"]))
        sc = screenshot("shot_haupt.png", 4)
        ed2.run()
        sc.join()
        T.pruefe("Hauptdialog läuft und schließt", True)

        # Rechtsklick-Menü baut sich auf
        ed3 = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Bericht"]))
        ed3.run(ohne_dialog=True)
        pm, ids = ed3.baue_menue("Objekt")
        T.pruefe("Spaltenmenü: Einträge", pm.getItemCount() >= 9 and len(ids) > 20, "%d / %d" % (pm.getItemCount(), len(ids)))
        pm2, ids2 = ed3.baue_menue(None)
        T.pruefe("Schritt-hinzufügen-Menü: alle Operationen",
                 {v[0] for v in ids2.values() if v[0] != "__suche"} == set(E.OPS), str(set(E.OPS) - {v[0] for v in ids2.values()}))

        # --- Schrittdialog echt (automatisches OK nach 2 s) ----------------------------------------
        os.environ["ABFRAGE_AUTOCLOSE"] = "6"
        os.environ["ABFRAGE_AUTOOK"] = "2"
        tab = E.fuehre_aus(ed3.roh, T.SCHRITTE[:6])
        s = AE.SchrittDialog(ctx, "filtern", tab, None,
                             {"spalte": "Objekt", "bedingung": "beginnt_mit", "wert": "Schule A"}, None).zeigen()
        T.pruefe("Schrittdialog Filtern: Eingaben übernommen",
                 s and s["spalte"] == "Objekt" and s["bedingung"] == "beginnt_mit" and s["wert"] == "Schule A"
                 and s["aktion"] == "behalten", str(s))
        s = AE.SchrittDialog(ctx, "typ_aendern", tab, None,
                             {"spalten": ["Verbrauch kWh", "Kosten"], "typ": "dezimal"}, None).zeigen()
        T.pruefe("Schrittdialog Datentyp: Mehrfachauswahl", s and s["spalten"] == ["Verbrauch kWh", "Kosten"]
                 and s["typ"] == "dezimal", str(s))
        s = AE.SchrittDialog(ctx, "benutzerdefinierte_spalte", tab, None,
                             {"neu": "Summe", "formel": "[Verbrauch kWh] + 1"}, None).zeigen()
        T.pruefe("Schrittdialog Formel: Text übernommen", s is None or s["formel"] == "[Verbrauch kWh] + 1", str(s))
        tab_typ = E.fuehre_aus(ed3.roh, T.SCHRITTE[:7])
        s = AE.SchrittDialog(ctx, "benutzerdefinierte_spalte", tab_typ, None,
                             {"neu": "Summe", "formel": "[Verbrauch kWh] + 1"}, None).zeigen()
        T.pruefe("Schrittdialog Formel auf Zahlenspalte", s and s["formel"] == "[Verbrauch kWh] + 1" and s["neu"] == "Summe",
                 str(s))
        s = AE.SchrittDialog(ctx, "benutzerdefinierte_spalte", tab_typ, None,
                             {"neu": "Summe", "formel": "[GibtsNicht] + 1"}, None).zeigen()
        T.pruefe("Schrittdialog Formel mit Fehler: Dialog bleibt offen, kein Ergebnis", s is None, str(s))
        s = AE.SchrittDialog(ctx, "filtern_werte", tab, None, {"spalte": "Zähler", "werte": ["Gas", "Strom"]}, None).zeigen()
        T.pruefe("Schrittdialog Häkchenliste (Werte)", s and s["werte"] == ["Gas", "Strom"] and s["spalte"] == "Zähler", str(s))
        s = AE.SchrittDialog(ctx, "spalten_verschieben", tab, None,
                             {"spalten": ["Kosten"], "position": "vor", "ziel": "Objekt"}, None).zeigen()
        T.pruefe("Schrittdialog Spalten verschieben", s and s["ziel"] == "Objekt" and s["position"] == "vor", str(s))
        s = AE.SchrittDialog(ctx, "zeilen_entfernen_oben", tab, None, {"anzahl": 2}, None).zeigen()
        T.pruefe("Schrittdialog Zahlenfeld", s and s["anzahl"] == 2, str(s))
        # Bearbeiten eines bestehenden Schritts übernimmt dessen Werte
        alt = {"op": "sortieren", "spalte1": "Objekt", "richtung1": "ab", "spalte2": "Datum", "richtung2": "auf"}
        s = AE.SchrittDialog(ctx, "sortieren", tab, alt, None, None).zeigen()
        T.pruefe("Schritt bearbeiten: Werte bleiben erhalten", s and s["spalte1"] == "Objekt"
                 and s["richtung1"] == "ab" and s["spalte2"] == "Datum", str(s))

        # --- Klick auf einen Spaltenkopf im echten Raster ------------------------------------------
        import types
        os.environ["ABFRAGE_AUTOCLOSE"] = "8"
        ed4 = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Bericht"]))

        def klick():
            time.sleep(7)
            try:
                ed4.grid_maus(types.SimpleNamespace(X=70, Y=8, PopupTrigger=False))
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=klick, daemon=True)
        th.start()
        ed4.run()
        th.join()
        T.pruefe("Klick auf Spaltenkopf erkennt die Spalte", ed4.sel_spalte == "Objekt", str(ed4.sel_spalte))

        # --- Rechtsklick-Menü wirklich aufklappen --------------------------------------------------
        os.environ["ABFRAGE_AUTOCLOSE"] = "9"
        ed5 = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Bericht"]))
        menue = {"ok": None}

        def oeffne_menue():
            time.sleep(2)
            try:
                ed5.zeige_menue(150, 90, "Objekt")
                menue["ok"] = True
            except Exception:
                traceback.print_exc()
                menue["ok"] = False

        def schliesse_menue():
            time.sleep(4.5)
            try:
                ed5._pm.endExecute()
            except Exception:
                traceback.print_exc()
        ta = threading.Thread(target=oeffne_menue, daemon=True)
        tb = threading.Thread(target=schliesse_menue, daemon=True)
        sc = screenshot("shot_menue.png", 3.5)
        ta.start()
        tb.start()
        ed5.run()
        ta.join()
        tb.join()
        sc.join()
        T.pruefe("Spaltenmenü klappt auf und schließt ohne Fehler", menue["ok"] is True, str(menue))

        # --- Schritte verschieben / löschen -------------------------------------------------------
        n = len(ed3.abfrage.schritte)
        vorher = [s["op"] for s in ed3.abfrage.schritte]
        ed3.lstS.waehle(9)
        ed3.verschiebe(1)
        nachher = [s["op"] for s in ed3.abfrage.schritte]
        T.pruefe("Schritt nach unten verschieben", nachher[8] == vorher[9] and nachher[9] == vorher[8], str(nachher))
        T.pruefe("Auswahl folgt dem verschobenen Schritt", ed3.lstS.pos() == 10)
        ed3.verschiebe(-1)
        T.pruefe("Schritt wieder nach oben", [s["op"] for s in ed3.abfrage.schritte] == vorher)
        ed3.loeschen()
        T.pruefe("Schritt löschen", len(ed3.abfrage.schritte) == n - 1 and ed3.fehler_schritt is None,
                 "%d" % len(ed3.abfrage.schritte))

        # --- Zwischenablage ---------------------------------------------------------------------
        import unohelper
        from com.sun.star.datatransfer import XTransferable

        class Text(unohelper.Base, XTransferable):
            def __init__(self, text):
                self.text = text
                fl = uno.createUnoStruct("com.sun.star.datatransfer.DataFlavor")
                fl.MimeType = "text/plain;charset=utf-16"
                fl.HumanPresentableName = "Unicode-Text"
                fl.DataType = uno.getTypeByName("string")
                self.fl = fl

            def getTransferData(self, flavor):
                return self.text

            def getTransferDataFlavors(self):
                return (self.fl,)

            def isDataFlavorSupported(self, flavor):
                return flavor.MimeType.startswith("text/plain")

        clip = smgr.createInstanceWithContext("com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)
        clip.setContents(Text("Objekt\tMenge\tDatum\nA\t1.234,5\t01.10.2026\n\t7\t02.10.2026\n"), None)
        tz = AE.lies_quelle(ctx, doc, {"art": "zwischenablage", "trenner": "auto"})
        T.pruefe("Zwischenablage (Tabulator) gelesen", len(tz.zeilen) == 3 and tz.zeilen[1][1] == "1.234,5"
                 and len(tz.spalten) == 3, str(tz.zeilen))

        sc = screenshot("shot_schritt.png", 1.2)
        os.environ["ABFRAGE_AUTOOK"] = "4"
        AE.SchrittDialog(ctx, "benutzerdefinierte_spalte", tab_typ, None,
                         {"neu": "Je kWh", "formel": "RUNDEN([Kosten] / [Verbrauch kWh]; 3)"}, None).zeigen()
        sc.join()
        sc = screenshot("shot_filter.png", 1.2)
        AE.SchrittDialog(ctx, "filtern_werte", tab, None, {"spalte": "Zähler", "werte": ["Gas"]}, None).zeigen()
        sc.join()
    except Exception:
        traceback.print_exc()
        T.pruefe("UI-Test ohne unerwartete Ausnahme", False, traceback.format_exc().splitlines()[-1])
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    for n, _, d in fehler:
        print("  FEHLER:", n, d)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
