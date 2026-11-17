# -*- coding: utf-8 -*-
"""Tests für 0.2: Fenstergröße, Spaltenmarkierung, Rückgängig, Ein/Aus, Vorschau, Zielzelle, Auto-Aktualisieren."""
import os
import sys
import threading
import time
import traceback
import types

import uno

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T  # noqa: E402
from test_ui import screenshot  # noqa: E402

AE, E = T.AE, T.E
SCRATCH = os.environ.get("SCRATCH", "/tmp")
pruefe = T.pruefe


def neuer_editor(ctx, frame, doc, name="Bericht", schritte=None, ziel=None, quelle=None):
    a = E.Abfrage(name, quelle or {"art": "blatt", "blatt": "Auszug"}, [], ziel=ziel)
    ed = AE.Editor(ctx, frame, doc, a)
    ed.run(ohne_dialog=True)
    for s in (schritte if schritte is not None else T.SCHRITTE):
        ed.neuer_schritt(s["op"], {k: v for k, v in s.items() if k != "op"}, direkt=True)
    return ed


def titel(ed):
    cm = ed.d.ctrl("grid").getModel().ColumnModel
    return [c.Title for c in cm.getColumns()][1:]      # Spalte 0 = Zeilennummern


def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    tmp = os.path.join(SCRATCH, "ae_test02")
    os.makedirs(tmp, exist_ok=True)
    try:
        T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()

        # ---- Spaltenmarkierung ----------------------------------------------------------------
        ed = neuer_editor(ctx, frame, doc)
        ed.lstS.waehle(len(T.SCHRITTE))
        ed.zeige()
        t = titel(ed)
        pruefe("Keine ●-Punkte in den Köpfen", not any("●" in x for x in t), str(t))
        pruefe("Nicht markierte Spalte ohne ►", any(x.strip().endswith(" | Zähler") and not x.startswith("►") for x in t), str(t))
        ed.spalte_markieren("Kosten je kWh")
        t = titel(ed)
        lbl = ed.d.ctrl("lblMarkiert").getModel().Label
        pruefe("Markierungs-Label nennt nur den Spaltennamen", lbl == "Kosten je kWh", lbl)
        ed.spalte_markieren("Zähler")
        t = titel(ed)
        pruefe("Geklickte Spalte mit ► markiert", any(x.startswith(AE.MARKER_GEKLICKT) and x.strip(" ◄").endswith(" | Zähler") for x in t), str(t))
        pruefe("Label nennt geklickte Spalte", "Zähler" in ed.d.ctrl("lblMarkiert").getModel().Label)
        ed.lstS.waehle(len(T.SCHRITTE))
        ed.zeige()
        pruefe("Markierung der Klick-Spalte bleibt nach Schrittwechsel",
               any(x.startswith(AE.MARKER_GEKLICKT) and x.strip(" ◄").endswith(" | Zähler") for x in titel(ed)))

        # ---- Rückgängig / Wiederholen / Ein-Aus -------------------------------------------------
        n = len(ed.abfrage.schritte)
        pruefe("Zurück ist aktiv", ed.d.ctrl("btnUndo").getModel().Enabled)
        ed.rueckgaengig()
        pruefe("Rückgängig entfernt letzten Schritt", len(ed.abfrage.schritte) == n - 1, str(len(ed.abfrage.schritte)))
        ed.wiederholen()
        pruefe("Wiederholen stellt ihn wieder her", len(ed.abfrage.schritte) == n and
               ed.abfrage.schritte[-1]["op"] == "sortieren")
        ed.lstS.waehle(n)   # Sortieren
        ed.ein_aus()
        pruefe("Ein/Aus: Schritt deaktiviert", ed.abfrage.schritte[-1].get("aktiv") is False)
        pruefe("Deaktivierter Schritt in Liste gekennzeichnet", "aus" in ed.schritt_texte()[-1])
        ed.ein_aus()
        pruefe("Ein/Aus: wieder aktiv", "aktiv" not in ed.abfrage.schritte[-1])
        ed.rueckgaengig()
        ed.rueckgaengig()
        pruefe("Zwei Rückgängig nach Ein/Aus", len(ed.abfrage.schritte) == n)

        # ---- Vorschau-Größe ---------------------------------------------------------------------
        zeilen = [["Z%d" % i, i] for i in range(3000)]
        sh2 = doc.getSheets()
        sh2.insertNewByName("Gross", 1)
        g = sh2.getByName("Gross")
        g.getCellRangeByPosition(0, 0, 1, 3000).setDataArray(tuple([("Name", "Nr")] + [tuple(z) for z in zeilen]))
        eg = neuer_editor(ctx, frame, doc, "Gr", [], quelle={"art": "blatt", "blatt": "Gross"})
        anz = eg.d.ctrl("grid").getModel().GridDataModel.RowCount
        pruefe("Standardvorschau 500 Zeilen", anz == 500, str(anz))
        eg.vorschau_limit = 500
        eg.zeige()
        pruefe("Vorschau 500 Zeilen", eg.d.ctrl("grid").getModel().GridDataModel.RowCount == 500)
        eg.vorschau_limit = 10000
        t0 = time.time()
        eg.zeige()
        pruefe("Vorschau alle 3001 Zeilen (%.2fs)" % (time.time() - t0),
               eg.d.ctrl("grid").getModel().GridDataModel.RowCount == 3001)
        # Spaltenbreite bleibt
        cm = eg.d.ctrl("grid").getModel().ColumnModel
        cm.getColumns()[1].ColumnWidth = 222
        eg.breiten_merken()
        eg.zeige()
        pruefe("Gezogene Spaltenbreite bleibt erhalten",
               eg.d.ctrl("grid").getModel().ColumnModel.getColumns()[1].ColumnWidth == 222)
        sh2.removeByName("Gross")

        # ---- Fenstergröße ändern ----------------------------------------------------------------
        os.environ["ABFRAGE_AUTOCLOSE"] = "9"
        er = neuer_editor(ctx, frame, doc, "Rz")
        er.d.dlg.setVisible(False)
        er.d.model.Sizeable
        res = {}

        def grosser():
            time.sleep(2.5)
            try:
                gm = er.d.modell("grid")
                res["vor"] = (gm.Width, gm.Height)
                pk = er.d.peer()
                px = pk.getPosSize()
                pk.setPosSize(px.X, px.Y, px.Width + 300, px.Height + 200, 12)
                time.sleep(1.0)
                res["nach"] = (gm.Width, gm.Height)
                res["btn"] = er.d.model.getByName("btnAbbr").PositionX
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=grosser, daemon=True)
        sc = screenshot("shot_gross.png", 4.5)
        th.start()
        er.d.zeigen(er.parent)
        th.join()
        sc.join()
        er.d.weg()
        ok = "vor" in res and "nach" in res and res["nach"][0] > res["vor"][0] + 50 and res["nach"][1] > res["vor"][1] + 40
        pruefe("Fenster vergrößern: Raster wächst mit", ok, str(res))

        # ---- Zielzelle ---------------------------------------------------------------------------
        sheets = doc.getSheets()
        sheets.insertNewByName("Ablage", 2)
        ab = sheets.getByName("Ablage")
        ab.getCellRangeByName("A1").setString("Notiz")
        ez = neuer_editor(ctx, frame, doc, "Zell",
                          ziel={"art": "zelle", "blatt": "Ablage", "zelle": "C3"})
        ez.abfrage.ziel = {"art": "zelle", "blatt": "Ablage", "zelle": "C3"}
        ez.laden()
        pruefe("Zielzelle: Kopf in C3", ab.getCellRangeByName("C3").getString() != "")
        pruefe("Zielzelle: fremde Zelle A1 unberührt", ab.getCellRangeByName("A1").getString() == "Notiz")
        z = E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Zell"])
        pruefe("Letzter Ausgabebereich gemerkt", bool(z.ziel.get("letzter")), str(z.ziel))
        n1 = AE.aktualisiere_abfrage(ctx, doc, z)
        pruefe("Zielzelle: Aktualisieren ohne Konflikt", n1 > 0, str(n1))
        # Konflikt
        ab.getCellRangeByName("C3").clearContents(1023)
        ab.getCellRangeByName("D5").setString("fremd")
        z2 = E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Zell"])
        z2.ziel["letzter"] = None
        if z2.ziel.get("bereich") and doc.DatabaseRanges.hasByName(z2.ziel["bereich"]):
            doc.DatabaseRanges.removeByName(z2.ziel["bereich"])        # ohne Bereich (0.7.4: der Bereich gehört der Abfrage)
        z2.ziel.pop("bereich", None)
        try:
            tab = E.fuehre_aus(AE.lies_quelle(ctx, doc, z2.quelle), z2.schritte)
            AE.schreibe_ergebnis(doc, tab, z2)
            pruefe("Konflikt wird erkannt", False)
        except AE.ZielBelegt:
            pruefe("Konflikt wird erkannt", True)
        pruefe("Fremde Daten bleiben bei Konflikt", ab.getCellRangeByName("D5").getString() == "fremd")
        AE.schreibe_ergebnis(doc, tab, z2, bestaetigt=True)
        pruefe("Nach Bestätigung geschrieben", ab.getCellRangeByName("C3").getString() != "")

        # ---- Fehlerzellen aus Calc lesen --------------------------------------------------------
        ab.getCellRangeByName("H1").setString("W")
        ab.getCellRangeByName("H2").setFormula("=1/0")
        ab.getCellRangeByName("H3").setValue(5)
        _, tf = AE.lese_blatt(doc, "Ablage", "H1:H3")
        pruefe("Fehlerzelle -> FehlerWert", E.ist_fehler(tf.zeilen[1][0]), repr(tf.zeilen))
        pruefe("Normale Zelle daneben bleibt Zahl", tf.zeilen[2][0] == 5.0, repr(tf.zeilen))

        # ---- Ausgabe-Dialog ----------------------------------------------------------------------
        os.environ["ABFRAGE_AUTOOK"] = "2"
        os.environ["ABFRAGE_AUTOCLOSE"] = "6"
        sc = screenshot("shot_ziel.png", 1.2)
        zd = AE.ZielDialog(ctx, doc, E.Abfrage("Zell", {}, [], ziel={"art": "zelle", "blatt": "Ablage", "zelle": "C3"}), None).zeigen()
        sc.join()
        pruefe("Ausgabe-Dialog liefert Zielzelle", isinstance(zd, tuple) and zd[0].get("art") == "zelle"
               and zd[0].get("zelle") == "C3" and zd[0].get("blatt") == "Ablage", str(zd))

        # ---- Neue Operationen im Schrittdialog -------------------------------------------------
        tab = E.fuehre_aus(ed.roh, T.SCHRITTE[:7])
        sc = screenshot("shot_gruppe.png", 1.2)
        s = AE.SchrittDialog(ctx, "gruppieren", tab, None,
                             {"spalten": ["Objekt"],
                              "aggregationen": [{"spalte": "Kosten", "fn": "summe", "name": "Summe Kosten"},
                                                {"spalte": "Zähler", "fn": "anzahl", "name": "Anz"}]}, None).zeigen()
        sc.join()
        pruefe("Gruppieren-Dialog liefert Aggregationen",
               s and s["spalten"] == ["Objekt"] and len(s["aggregationen"]) == 2
               and s["aggregationen"][0]["fn"] == "summe", str(s))
        s = AE.SchrittDialog(ctx, "text_extrahieren", tab, None,
                             {"spalte": "Gebäude", "art": "nach_trenner", "trenner": " ", "neu": "Nr"}, None).zeigen()
        pruefe("Text-extrahieren-Dialog", s and s["trenner"] == " " and s["art"] == "nach_trenner", str(s))
        s = AE.SchrittDialog(ctx, "entpivotieren", tab, None,
                             {"spalten": ["Verbrauch kWh", "Kosten"], "modus": "ausgewaehlte"}, None).zeigen()
        pruefe("Entpivotieren-Dialog", s and s["spalten"] == ["Verbrauch kWh", "Kosten"], str(s))

        # ---- Formel-Dialog: Spaltenliste rechts, Operatoren, Runden ----------------------------
        os.environ["ABFRAGE_AUTOOK"] = "5"
        os.environ["ABFRAGE_AUTOCLOSE"] = "9"
        tabf = E.fuehre_aus(ed.roh, T.SCHRITTE[:7])
        fd = AE.SchrittDialog(ctx, "benutzerdefinierte_spalte", tabf, None, {"neu": "Netto"}, None)
        erg = {}

        def klicks():
            time.sleep(1.5)
            try:
                d_ = fd.d
                d_.ctrl("ins_sp").selectItemPos(tabf.spalten.index("Kosten"), True)
                fd._liste_einfuegen("ins_sp", lambda t: "[%s]" % t)       # Doppelklick
                time.sleep(0.3)
                fd._text_einfuegen(" * ")
                d_.ctrl("ins_sp").selectItemPos(tabf.spalten.index("Verbrauch kWh"), True)
                fd._liste_einfuegen("ins_sp", lambda t: "[%s]" % t)       # Doppelklick
                time.sleep(0.3)
                erg["text"] = d_.ctrl("f_formel").getText()
                d_.ctrl("stellen").getModel().Text = "3"
                d_.ctrl("f_formel").setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, 0))
                fd._runden()
                erg["rund"] = d_.ctrl("f_formel").getText()
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=klicks, daemon=True)
        sc = screenshot("shot_formel.png", 3)
        th.start()
        res_f = fd.zeigen()
        th.join()
        sc.join()
        pruefe("Spaltenliste rechts fügt [Kosten] ein", erg.get("text", "").startswith("[Kosten] * [Verbrauch kWh]"),
               str(erg))
        pruefe("Runden umschließt die Formel", erg.get("rund", "").startswith("RUNDEN(") and erg["rund"].endswith("; 3)"),
               str(erg))
        pruefe("Dialog liefert die Formel", res_f and res_f["formel"].startswith("RUNDEN("), str(res_f))

        # ---- Formel-Dialog: Spaltenliste rechts, Operatoren, Runden ----------------------------
        os.environ["ABFRAGE_AUTOOK"] = "5"
        os.environ["ABFRAGE_AUTOCLOSE"] = "9"
        tabf = E.fuehre_aus(ed.roh, T.SCHRITTE[:7])
        fd = AE.SchrittDialog(ctx, "benutzerdefinierte_spalte", tabf, None, {"neu": "Netto"}, None)
        erg = {}

        def klicks():
            time.sleep(1.5)
            try:
                d_ = fd.d
                d_.ctrl("ins_sp").selectItemPos(tabf.spalten.index("Kosten"), True)
                fd._liste_einfuegen("ins_sp", lambda t: "[%s]" % t)       # Doppelklick
                time.sleep(0.3)
                fd._text_einfuegen(" * ")
                d_.ctrl("ins_sp").selectItemPos(tabf.spalten.index("Verbrauch kWh"), True)
                fd._liste_einfuegen("ins_sp", lambda t: "[%s]" % t)       # Doppelklick
                time.sleep(0.3)
                erg["text"] = d_.ctrl("f_formel").getText()
                d_.ctrl("stellen").getModel().Text = "3"
                d_.ctrl("f_formel").setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, 0))
                fd._runden()
                erg["rund"] = d_.ctrl("f_formel").getText()
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=klicks, daemon=True)
        sc = screenshot("shot_formel.png", 3)
        th.start()
        res_f = fd.zeigen()
        th.join()
        sc.join()
        pruefe("Spaltenliste rechts fügt [Kosten] ein", erg.get("text", "").startswith("[Kosten] * [Verbrauch kWh]"),
               str(erg))
        pruefe("Runden umschließt die Formel", erg.get("rund", "").startswith("RUNDEN(") and erg["rund"].endswith("; 3)"),
               str(erg))
        pruefe("Formel-Dialog liefert die Formel", res_f and res_f["formel"].startswith("RUNDEN("), str(res_f))

        # ---- Bedingte Spalte (Klauseln-Dialog) -----------------------------------------------------
        os.environ["ABFRAGE_AUTOOK"] = ""
        os.environ.pop("ABFRAGE_AUTOOK", None)
        os.environ["ABFRAGE_AUTOCLOSE"] = "12"
        start = {"neu": "Stufe", "klauseln": [
            {"verknuepfung": "und", "bedingungen": [{"spalte": "Verbrauch kWh", "bedingung": "groesser",
                                                     "wert_art": "text", "wert": "1000"}],
             "dann_art": "text", "dann": "hoch"}], "sonst_art": "text", "sonst": "niedrig"}
        bd = AE.SchrittDialog(ctx, "bedingte_spalte", tabf, None, start, None)
        e2 = {}

        def bedingt_klicks():
            time.sleep(2.0)
            try:
                inst = bd._inst
                a = inst._aktionen
                a["plus"](0)                    # zweite Bedingung in Klausel 1
                a["klausel"]()                  # zweite Klausel
                d_ = inst.d
                def setz(name, pos):
                    d_.ctrl(name).getModel().SelectedItems = uno.Any("[]short", (pos,))
                sp = ["(Spalte)"] + tabf.spalten
                setz("r1_sp", sp.index("Kosten"))
                setz("r1_op", [v for v, _ in E.BEDINGUNGEN].index("groesser"))
                setz("r1_wa", 1)                # Wert = Spalte
                setz("r1_ws", sp.index("Verbrauch kWh"))
                setz("r1_und", 1)               # ODER
                setz("r2_sp", sp.index("Zähler"))
                d_.ctrl("r2_dt").getModel().Text = "Sonderfall"
                inst._lies()
                e2["s"] = inst._sammeln()
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=bedingt_klicks, daemon=True)
        sc = screenshot("shot_bedingt.png", 4)
        th.start()
        bd.zeigen()
        th.join()
        sc.join()
        s2 = e2.get("s") or {}
        kl = s2.get("klauseln") or [{}]
        pruefe("Klauseln-Dialog: Start-Klausel übernommen", kl[0].get("dann") == "hoch", str(s2))
        pruefe("Klauseln-Dialog: zweite Bedingung mit ODER",
               len(kl[0].get("bedingungen", [])) == 2 and kl[0].get("verknuepfung") == "oder"
               and kl[0]["bedingungen"][1]["wert_art"] == "spalte"
               and kl[0]["bedingungen"][1]["wert"] == "Verbrauch kWh", str(kl))
        pruefe("Klauseln-Dialog: zweite Klausel", len(kl) == 2 and kl[1].get("dann") == "Sonderfall", str(kl))
        os.environ["ABFRAGE_AUTOCLOSE"] = "6"

        # ---- Ausfüllen-Untermenü im Spaltenmenü ---------------------------------------------------
        pm, ids = ed.baue_menue("Objekt")
        fuell = [v for v in ids.values() if v[0] in ("fuellen_unten", "fuellen_oben")]
        pruefe("Spaltenmenü: Ausfüllen Unten/Oben mit Spalte vorbelegt",
               sorted(v[0] for v in fuell if v[1] == {"spalten": ["Objekt"]} and v[2]) == ["fuellen_oben", "fuellen_unten"],
               str(fuell))
        pruefe("Spaltenmenü: Untermenü 'Ausfüllen'", any(pm.getItemText(pm.getItemId(i)) == "Ausfüllen"
                                                       for i in range(pm.getItemCount())))
        # alter Schritt 'Bedingte Spalte' wird im neuen Dialog geöffnet und im neuen Format zurückgegeben
        os.environ["ABFRAGE_AUTOOK"] = "2"
        os.environ["ABFRAGE_AUTOCLOSE"] = "6"
        alt = {"op": "bedingte_spalte", "neu": "Alt", "spalte": "Zähler", "bedingung": "gleich", "wert": "Gas",
               "dann": "JA", "sonst": "NEIN", "ort": "de"}
        r_alt = AE.SchrittDialog(ctx, "bedingte_spalte", tabf, alt, None, None).zeigen()
        pruefe("Alter Schritt im neuen Dialog bearbeitbar",
               r_alt and r_alt["klauseln"][0]["bedingungen"][0]["wert"] == "Gas" and r_alt["sonst"] == "NEIN", str(r_alt))
        os.environ.pop("ABFRAGE_AUTOOK", None)

        # ---- Schritte: Duplizieren und Menü auf der Schritteliste ----------------------------------
        n0 = len(ed.abfrage.schritte)
        ed.lstS.waehle(3)
        ed.dupliziere()
        pruefe("Duplizieren: Kopie direkt dahinter",
               len(ed.abfrage.schritte) == n0 + 1 and ed.abfrage.schritte[3] == ed.abfrage.schritte[2]
               and ed.abfrage.schritte[3] is not ed.abfrage.schritte[2], str(ed.abfrage.schritte[2:4]))
        ed.rueckgaengig()
        pruefe("Duplizieren ist rückgängig machbar", len(ed.abfrage.schritte) == n0)
        pm_s, ids_s = ed.baue_schritt_menue()
        pruefe("Schrittmenü: alle neun Befehle (inkl. Bedingung) + Einfügen vor/nach",
               sorted(v for v in ids_s.values() if isinstance(v, str)) == sorted(
                   ["hoch", "runter", "aendern", "umbenennen", "dupliziere", "ein_aus", "bedingung", "loeschen", "bis_ende"])
               and any(isinstance(v, tuple) and v == ("menue", "vor") for v in ids_s.values())
               and any(isinstance(v, tuple) and v == ("menue", "nach") for v in ids_s.values()),
               str(ids_s))
        os.environ["ABFRAGE_AUTOCLOSE"] = "12"
        es = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(ed.abfrage.to_json()))
        ms = {"rechts": None, "doppel": None}

        def schritt_menues():
            time.sleep(5)
            AE.schreibe_einstellung("rechtsklick", False)       # dieser Test prüft die Doppelklick-Bedienung
            try:
                es.lstS.waehle(3)
                aufrufe = []
                orig_menue = es.zeige_schritt_menue
                es.zeige_schritt_menue = lambda x, y: aufrufe.append(threading.get_ident())
                es.schritt_maus(types.SimpleNamespace(X=30, Y=30, PopupTrigger=True, ClickCount=1, Buttons=2))
                time.sleep(1.0)
                ms["rechts"] = not aufrufe                    # Rechtsklick wird ignoriert
                es._letzter_rechtsklick = 0
                es.schritt_maus(types.SimpleNamespace(X=30, Y=30, PopupTrigger=False, ClickCount=1, Buttons=1))
                time.sleep(0.5)
                ms["einfach_kein_menue"] = not aufrufe         # Einfachklick öffnet nie ein Menü
                es._letzter_rechtsklick = 0
                es.schritt_maus(types.SimpleNamespace(X=90, Y=30, PopupTrigger=False, ClickCount=2, Buttons=1))
                time.sleep(1.2)
                ms["doppel"] = len(aufrufe) == 1 and aufrufe[0] != threading.get_ident()   # Menü erst nach dem Ereignis, im Hauptthread
                es.zeige_schritt_menue = orig_menue
            except Exception:
                traceback.print_exc()
        ta = threading.Thread(target=schritt_menues, daemon=True)
        sc = screenshot("shot_schrittmenue.png", 2.8)
        ta.start()
        es.run()
        ta.join()
        sc.join()
        AE.schreibe_einstellung("rechtsklick", None)
        pruefe("Rechtsklick in der Schrittliste wird ignoriert", ms.get("rechts") is True, str(ms))
        pruefe("Doppelklick auf Schritt öffnet das Menü (nach dem Ereignis)", ms.get("doppel") is True, str(ms))
        pruefe("Einfachklick öffnet kein Menü", ms.get("einfach_kein_menue") is True, str(ms))
        os.environ["ABFRAGE_AUTOCLOSE"] = "6"

        # ---- Sichtbare Markierung beim Klick und Neuzeichnen nach Löschen (nur per Screenshot prüfbar) -----
        os.environ["ABFRAGE_AUTOCLOSE"] = "14"
        ev_ = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(ed.abfrage.to_json()))

        def klick_und_loeschen():
            try:
                time.sleep(2.5)
                ev_.grid_maus(types.SimpleNamespace(X=250, Y=8, PopupTrigger=False, ClickCount=1, Buttons=1))
                time.sleep(3)      # Screenshot "shot_klick.png" um ~3.0 s nach Start der Klick-Thread-Zeit
                ev_.lstS.waehle(len(T.SCHRITTE))
                ev_.loeschen()     # letzten Schritt (Sortieren) löschen -> Vorschau muss sofort neu gezeichnet sein
                time.sleep(0.5)
                ev_.lstS.waehle(8)
                ev_.loeschen()     # Formel-Spalte löschen -> weniger Spalten
            except Exception:
                traceback.print_exc()
        tk = threading.Thread(target=klick_und_loeschen, daemon=True)
        sc1 = screenshot("shot_klick.png", 4.5)
        sc2 = screenshot("shot_nach_loeschen.png", 9.5)
        tk.start()
        ev_.run()
        tk.join()
        sc1.join()
        sc2.join()
        os.environ["ABFRAGE_AUTOCLOSE"] = "6"

        # ---- Abfrage löschen ---------------------------------------------------------------------
        AE.loesche_abfrage(doc, "Zell")
        pruefe("Abfrage löschen", "Zell" not in AE.gespeicherte_abfragen(doc))

        # ---- Auto-Aktualisieren beim Öffnen ------------------------------------------------------
        csvp = os.path.join(tmp, "quelle.csv")
        with open(csvp, "w", encoding="utf-8") as f:
            f.write("Name;Wert\nA;1\nB;2\n")
        doc2 = T.neues_calc(ctx)[1]
        fr2 = doc2.getCurrentController().getFrame()
        e2 = AE.Editor(ctx, fr2, doc2, E.Abfrage("Auto", {"art": "datei", "pfad": csvp, "trenner": "auto"}, [],
                                                  auto=True))
        e2.run(ohne_dialog=True)
        e2.laden()
        pfad = os.path.join(tmp, "mappe.ods")
        url = uno.systemPathToFileUrl(pfad)
        doc2.storeToURL(url, (T.PropertyValue("FilterName", 0, "calc8", 0),))
        doc2.close(True)
        with open(csvp, "w", encoding="utf-8") as f:
            f.write("Name;Wert\nA;1\nB;2\nC;3\nD;4\n")
        d3 = desk.loadComponentFromURL(url, "_blank", 0, (T.PropertyValue("Hidden", 0, False, 0),))
        zeilen3 = 0
        for _ in range(40):
            time.sleep(0.5)
            try:
                zeilen3 = d3.getSheets().getByName("Auto").getCellRangeByName("A6").getString()
                if zeilen3:
                    break
            except Exception:
                pass
        pruefe("Beim Öffnen automatisch aktualisiert (Job feuert)", zeilen3 == "D", repr(zeilen3))
        d3.close(True)
        # ohne auto-Flag: nicht aktualisieren
        doc4 = T.neues_calc(ctx)[1]
        fr4 = doc4.getCurrentController().getFrame()
        with open(csvp, "w", encoding="utf-8") as f:
            f.write("Name;Wert\nA;1\nB;2\n")
        e4 = AE.Editor(ctx, fr4, doc4, E.Abfrage("Manuell", {"art": "datei", "pfad": csvp, "trenner": "auto"}, []))
        e4.run(ohne_dialog=True)
        e4.laden()
        p4 = os.path.join(tmp, "mappe2.ods")
        u4 = uno.systemPathToFileUrl(p4)
        doc4.storeToURL(u4, (T.PropertyValue("FilterName", 0, "calc8", 0),))
        doc4.close(True)
        with open(csvp, "w", encoding="utf-8") as f:
            f.write("Name;Wert\nA;1\nB;2\nC;3\n")
        d5 = desk.loadComponentFromURL(u4, "_blank", 0, (T.PropertyValue("Hidden", 0, False, 0),))
        time.sleep(4)
        pruefe("Ohne Auto-Flag bleibt alles unverändert", d5.getSheets().getByName("Manuell").getCellRangeByName("A5").getString() == "",
               d5.getSheets().getByName("Manuell").getCellRangeByName("A5").getString())
        d5.close(True)
    except Exception:
        traceback.print_exc()
        pruefe("UI-Test 0.2 ohne unerwartete Ausnahme", False, traceback.format_exc().splitlines()[-1])
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
