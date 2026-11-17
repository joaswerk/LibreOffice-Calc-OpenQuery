# -*- coding: utf-8 -*-
"""0.8.5: Präfix/Suffix, Rechnen, Zahleneigenschaft, Filter gerade/ungerade/…, Formelfunktionen, Felder je Auswahl ausblenden."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def fehler(f):
    try:
        f(); return None
    except (E.FormelFehler, E.StepError) as ex:
        return getattr(ex, "meldung", None) or str(ex.args[0] if ex.args else ex)

def lauf(tab, *schritte):
    return E.fuehre_aus(tab, list(schritte))

def sichtbar_dialog(ctx, op, tab, start, aktionen, wartezeit=1.5):
    """Dialog öffnen; aktionen(dlg) läuft nach wartezeit in einem Thread; danach klickt AUTOOK auf OK."""
    os.environ["ABFRAGE_AUTOOK"] = str(wartezeit + 2.5)
    dlg = AE.SchrittDialog(ctx, op, tab, None, start, None)
    ergebnis = {}
    def thread():
        time.sleep(wartezeit)
        try:
            ergebnis["a"] = aktionen(dlg)
        except Exception as ex:
            import traceback; traceback.print_exc(); ergebnis["fehler"] = str(ex)
    t = threading.Thread(target=thread, daemon=True); t.start()
    res = dlg.zeigen()
    t.join(5)
    return res, ergebnis

def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    AE.setze_aufloeser(ctx, doc)
    t = E.Tabelle(["A", "B", "C"], [[5, "x", 2], [6, None, 0], [-3, "7,5", 4], [2.5, "", 1], [E.Waehrung(10.0), "a", 3]])
    # --- Präfix/Suffix
    r = lauf(t, {"op": "praefix_suffix", "spalten": ["A", "B"], "praefix": "Nr ", "suffix": " kWh"})
    pruefe("Präfix/Suffix: Zahl wird Text, Leere bleiben leer", r.zeilen[0][:2] == ["Nr 5 kWh", "Nr x kWh"] and r.zeilen[1][1] is None and r.zeilen[3][1] == "", str(r.zeilen[:4]))
    r = lauf(t, {"op": "praefix_suffix", "spalten": ["B"], "praefix": ">", "leere_auslassen": False})
    pruefe("Präfix auch bei leeren Zellen", r.zeilen[1][1] == ">" and r.zeilen[3][1] == ">", str(r.zeilen))
    r = lauf(t, {"op": "praefix_suffix", "spalten": ["B"], "praefix": "a#(lf)"})
    pruefe("Präfix mit Zeilenumbruch #(lf)", r.zeilen[0][1] == "a\nx", repr(r.zeilen[0][1]))
    f = fehler(lambda: lauf(t, {"op": "praefix_suffix", "spalten": ["A"]}))
    pruefe("Weder Präfix noch Suffix -> Meldung", f and "Präfix oder ein Suffix" in f, str(f))
    # --- Rechnen
    r = lauf(t, {"op": "rechnen", "spalten": ["A"], "rechenart": "multiplizieren", "operand_art": "wert", "operand": "1,19"})
    pruefe("Rechnen × 1,19 (Komma-Zahl)", [round(z[0], 3) for z in r.zeilen] == [5.95, 7.14, -3.57, 2.975, 11.9], str([z[0] for z in r.zeilen]))
    pruefe("Rechnen: Währung bleibt Währung", isinstance(r.zeilen[4][0], E.Waehrung), type(r.zeilen[4][0]).__name__)
    r = lauf(t, {"op": "rechnen", "spalten": ["A"], "rechenart": "dividieren", "operand_art": "spalte", "operand_spalte": "C", "neu": "Q"})
    pruefe("Rechnen ÷ Spalte -> neue Spalte Q hinter A, Division durch 0 = Fehlerwert",
           r.spalten == ["A", "Q", "B", "C"] and r.zeilen[0][1] == 2.5 and E.ist_fehler(r.zeilen[1][1]) and r.zeilen[1][1] == "#DIV/0!", str(r.zeilen))
    r = lauf(t, {"op": "rechnen", "spalten": ["B"], "rechenart": "addieren", "operand_art": "wert", "operand": "1"})
    pruefe("Rechnen: Text -> #WERT!, leer bleibt leer, '7,5' wird Zahl", E.ist_fehler(r.zeilen[0][1]) and r.zeilen[1][1] is None and r.zeilen[2][1] == 8.5, str(r.zeilen))
    for art, soll in (("rest", [1, 0, 1, 0.5]), ("ganzzahlig", [2, 3, -2, 1]), ("potenz", [25, 36, 9, 6.25]),
                      ("prozent_von", [0.1, 0.12, -0.06, 0.05]), ("prozentwert", [2.5, 3, -1.5, 1.25]), ("subtrahieren", [3, 4, -5, 0.5])):
        r = lauf(t, {"op": "rechnen", "spalten": ["A"], "rechenart": art, "operand_art": "wert", "operand": "2" if art not in ("prozent_von", "prozentwert") else "50"})
        pruefe("Rechnen %s" % art, [round(float(z[0]), 6) for z in r.zeilen[:4]] == [float(x) for x in soll], str([z[0] for z in r.zeilen[:4]]))
    f = fehler(lambda: lauf(t, {"op": "rechnen", "spalten": ["A"], "rechenart": "addieren", "operand_art": "wert", "operand": "abc"}))
    pruefe("Operand keine Zahl -> Meldung", f and "keine Zahl" in f, str(f))
    f = fehler(lambda: lauf(t, {"op": "rechnen", "spalten": ["A", "C"], "rechenart": "addieren", "operand_art": "wert", "operand": "1", "neu": "X"}))
    pruefe("Neue Spalte bei mehreren Spalten -> Meldung", f and "genau eine Spalte" in f, str(f))
    r = lauf(t, {"op": "rechnen", "spalten": ["A"], "rechenart": "addieren", "operand_art": "wert", "operand": "{Z}"})   if False else None
    E.PARAMETER["fn"] = lambda n: {"Z": 10}[n]
    r = lauf(t, {"op": "rechnen", "spalten": ["C"], "rechenart": "addieren", "operand_art": "wert", "operand": "{Z}"})
    pruefe("Rechnen mit {Parameter}", [z[2] for z in r.zeilen] == [12, 10, 14, 11, 13], str([z[2] for z in r.zeilen]))
    # --- Zahleneigenschaft
    r = lauf(t, {"op": "zahleneigenschaft", "spalten": ["A"], "eigenschaft": "ist_gerade", "neu": "g"})
    pruefe("Zahleneigenschaft ist gerade (2,5 weder noch)", [z[1] for z in r.zeilen] == [False, True, False, False, True], str([z[1] for z in r.zeilen]))
    r = lauf(t, {"op": "zahleneigenschaft", "spalten": ["A"], "eigenschaft": "ist_ungerade"})
    pruefe("Zahleneigenschaft ist ungerade", [z[0] for z in r.zeilen] == [True, False, True, False, False], str([z[0] for z in r.zeilen]))
    r = lauf(t, {"op": "zahleneigenschaft", "spalten": ["A"], "eigenschaft": "vorzeichen"})
    pruefe("Vorzeichen", [z[0] for z in r.zeilen] == [1, 1, -1, 1, 1])
    r = lauf(t, {"op": "zahleneigenschaft", "spalten": ["A"], "eigenschaft": "absolutwert"})
    pruefe("Absolutwert", [float(z[0]) for z in r.zeilen] == [5, 6, 3, 2.5, 10])
    # --- Filter
    for bed, soll in (("gerade", [6, 10.0]), ("ungerade", [5, -3]), ("positiv", [5, 6, 2.5, 10.0]), ("negativ", [-3]), ("null", [])):
        r = lauf(t, {"op": "filtern", "spalte": "A", "bedingung": bed, "aktion": "behalten"})
        pruefe("Filter %s" % bed, [float(z[0]) for z in r.zeilen] == [float(x) for x in soll], str([z[0] for z in r.zeilen]))
    r = lauf(t, {"op": "filtern", "spalte": "C", "bedingung": "null", "aktion": "entfernen"})
    pruefe("Filter ist null entfernen", len(r.zeilen) == 4)
    r = lauf(t, {"op": "bedingte_spalte", "neu": "k", "klauseln": [{"bedingungen": [{"spalte": "A", "bedingung": "negativ", "wert": "", "wert_art": "text"}],
                "verknuepfung": "und", "dann_art": "text", "dann": "minus"}], "sonst_art": "text", "sonst": "plus"})
    pruefe("Bedingte Spalte mit „ist negativ“ (ohne Wert)", [z[3] for z in r.zeilen] == ["plus", "plus", "minus", "plus", "plus"], str([z[3] for z in r.zeilen]))
    # --- Formelfunktionen
    r = lauf(t, {"op": "benutzerdefinierte_spalte", "neu": "v", "formel": "VORZEICHEN([A]) & \"|\" & ISTGERADE([C]) & \"|\" & ISTUNGERADE([C])"})
    pruefe("Formel VORZEICHEN/ISTGERADE/ISTUNGERADE", r.zeilen[0][3] == "1|WAHR|FALSCH" and r.zeilen[2][3] == "-1|WAHR|FALSCH", str([z[3] for z in r.zeilen]))
    # --- Dialoge: Felder ausblenden
    def sicht(dlg, n):
        return bool(dlg.d.modell("f_" + n).EnableVisible)
    def a_extr(dlg):
        z = {}
        z["start"] = {n: sicht(dlg, n) for n in ("trenner", "trenner2", "vorkommen", "anzahl", "start")}
        z["hoehe1"] = dlg.d.model.Height
        c = dlg.d.ctrl("f_art"); c.selectItemPos(2, True); time.sleep(0.3)
        z["zwischen"] = {n: sicht(dlg, n) for n in ("trenner", "trenner2", "vorkommen", "anzahl", "start")}
        z["hoehe2"] = dlg.d.model.Height
        z["px2"] = dlg.d.dlg.getPosSize().Height
        c.selectItemPos(5, True); time.sleep(0.3)
        z["abpos"] = {n: sicht(dlg, n) for n in ("trenner", "trenner2", "vorkommen", "anzahl", "start")}
        c.selectItemPos(7, True); time.sleep(0.3)
        z["ziffern"] = {n: sicht(dlg, n) for n in ("trenner", "trenner2", "vorkommen", "anzahl", "start")}
        z["hoehe3"] = dlg.d.model.Height
        z["px3"] = dlg.d.dlg.getPosSize().Height
        c.selectItemPos(3, True); time.sleep(0.3)
        dlg.d.ctrl("f_anzahl").setText("4")
        z["y_anzahl"] = dlg.d.modell("f_anzahl").PositionY
        return z
    res, erg = sichtbar_dialog(ctx, "text_extrahieren", E.Tabelle(["Text"], [["ab-cd"]]), {"art": "vor_trenner", "trenner": "-"}, a_extr)
    z = erg.get("a", {})
    pruefe("Extrahieren vor Trennzeichen: Trennzeichen+Vorkommen sichtbar, Rest weg",
           z.get("start") == {"trenner": True, "trenner2": False, "vorkommen": True, "anzahl": False, "start": False}, str(z.get("start")))
    pruefe("Extrahieren zwischen zwei Trennern: auch zweites Trennzeichen", z.get("zwischen") == {"trenner": True, "trenner2": True, "vorkommen": True, "anzahl": False, "start": False}, str(z.get("zwischen")))
    pruefe("Extrahieren n Zeichen ab Position: Anzahl und Start", z.get("abpos") == {"trenner": False, "trenner2": False, "vorkommen": False, "anzahl": True, "start": True}, str(z.get("abpos")))
    pruefe("Extrahieren nur Ziffern: keine Zusatzfelder", z.get("ziffern") == {"trenner": False, "trenner2": False, "vorkommen": False, "anzahl": False, "start": False}, str(z.get("ziffern")))
    pruefe("Dialog wird bei weniger Feldern kürzer", z.get("hoehe3", 0) < z.get("hoehe2", 0) and z.get("hoehe1", 0) < z.get("hoehe2", 0), str((z.get("hoehe1"), z.get("hoehe2"), z.get("hoehe3"))))
    pruefe("Fenster wird tatsächlich kleiner (Pixel)", z.get("px3", 0) < z.get("px2", 0), str((z.get("px2"), z.get("px3"))))
    pruefe("Ergebnis: ausgeblendete Felder nicht im Schritt",
           res and res["art"] == "erste_zeichen" and res["anzahl"] == 4 and "trenner2" not in res and "start" not in res and "trenner" not in res, str(res))
    def a_filter(dlg):
        z = {"vorher": sicht(dlg, "wert")}
        dlg.d.ctrl("f_bedingung").selectItemPos([v for v, _ in E.BEDINGUNGEN].index("gerade"), True); time.sleep(0.3)
        z["gerade"] = (sicht(dlg, "wert"), sicht(dlg, "gross_klein"), sicht(dlg, "ort"))
        return z
    res, erg = sichtbar_dialog(ctx, "filtern", E.Tabelle(["Zahl"], [[2], [3]]), {"spalte": "Zahl", "bedingung": "enthaelt", "wert": "x"}, a_filter)
    z = erg.get("a", {})
    pruefe("Filter: Wertfelder bei „ist gerade“ weg", z.get("vorher") is True and z.get("gerade") == (False, False, False), str(z))
    pruefe("Filter gerade: Schritt ohne Wert, Ergebnis 1 Zeile", res and res["bedingung"] == "gerade" and "wert" not in res and len(E.fuehre_aus(E.Tabelle(["Zahl"], [[2], [3]]), [res]).zeilen) == 1, str(res))
    def a_rechnen(dlg):
        z = {"wert": (sicht(dlg, "operand"), sicht(dlg, "operand_spalte"), sicht(dlg, "ort"))}
        dlg.d.ctrl("f_operand_art").selectItemPos(1, True); time.sleep(0.3)
        z["spalte"] = (sicht(dlg, "operand"), sicht(dlg, "operand_spalte"), sicht(dlg, "ort"))
        dlg.d.ctrl("f_operand_spalte").selectItemPos(2, True); time.sleep(0.2)
        return z
    res, erg = sichtbar_dialog(ctx, "rechnen", E.Tabelle(["A", "B"], [[1, 2]]), {"spalten": ["A"], "rechenart": "addieren"}, a_rechnen)
    z = erg.get("a", {})
    pruefe("Rechnen: Operand-Felder wechseln mit der Operandenart", z.get("wert") == (True, False, True) and z.get("spalte") == (False, True, False), str(z))
    pruefe("Rechnen-Dialog liefert Schritt mit Spalte als Operand", res and res.get("operand_art") == "spalte" and res.get("operand_spalte") == "B" and "operand" not in res, str(res))
    doc.close(True)
    fehl = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehl)))
    return 1 if fehl else 0
sys.exit(main())
