# -*- coding: utf-8 -*-
"""0.9.8: Klick auf einen Parameter zeigt seinen Wert in der Tabellenfläche."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def zeilen_von(ed, n):
    return next((z for z in ed.angezeigt.zeilen if z[0] == n), None)


def test_editor(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        T.fuelle_auszug(doc)
        AE.speichere_oq_parameter(doc, "Stadt", {"typ": "text", "wert": "Berlin", "beschreibung": "Teststadt"})
        AE.speichere_oq_parameter(doc, "Orte", {"typ": "liste", "wert": "Berlin;Potsdam;Cottbus", "beschreibung": ""})
        AE.speichere_oq_parameter(doc, "Kaputt", {"typ": "abfrage_wert", "wert": "GibtEsNicht[X]", "beschreibung": ""})
        frame = doc.getCurrentController().getFrame()
        os.environ["ABFRAGE_AUTOCLOSE"] = "0"
        ed = AE.Editor(ctx, frame, doc, E.Abfrage("L", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:3])))
        ed.run(ohne_dialog=True)
        ed.parameter_anzeigen("Stadt")
        tab = ed.angezeigt
        zeilen = {z[0]: z for z in tab.zeilen}
        pruefe("Parameter als Tabelle: alle Parameter mit Wert, Typ, Verwendet in und Beschreibung",
               tab.spalten == ["Parameter", "Wert", "Typ", "Verwendet in", "Beschreibung"] and set(zeilen) == {"Stadt", "Orte", "Kaputt"}
               and zeilen["Stadt"][1] == "Berlin" and zeilen["Stadt"][4] == "Teststadt" and ed._param_ansicht == "Stadt", str(tab.zeilen))
        pruefe("Angeklickter Parameter ist die Detailzeile (Zeilendetails der Vorabfrage verschwunden)",
               ed._detail_zeile == ed._param_zeilen.index("Stadt"), str(ed._detail_zeile))
        ed.parameter_anzeigen("Orte")
        pruefe("Listen-Parameter: Wert steht in der Tabelle", zeilen_von(ed, "Orte")[1] == "Berlin;Potsdam;Cottbus", str(ed.angezeigt.zeilen))
        ed.parameter_anzeigen("Kaputt")
        pruefe("Parameter aus nicht vorhandener Abfrage: kein Absturz, Zeile vorhanden", zeilen_von(ed, "Kaputt") is not None, str(ed.angezeigt.zeilen))
        # Wert ändern über das Wertfeld
        ed.parameter_anzeigen("Stadt")
        ed._param_steuer_platzieren()
        ed.d.ctrl("txtParamWert").getModel().Text = "Potsdam"
        ed._param_wert_speichern()
        pruefe("Parameterwert im Wertfeld änderbar", AE.lies_oq_parameter(doc)["Stadt"]["wert"] == "Potsdam", str(AE.lies_oq_parameter(doc)["Stadt"]))
        ed._param_ansicht = None
        ed.zeige()
        pruefe("Zurück zur Abfrage: Tabelle wieder da", not ed._leer and len(ed._grid_namen) > 0, str(ed._grid_namen))
        n = len(ed.arbeit)
        ed.lstA.waehle(n + 1)
        pruefe("Parameterzeile ist in der Liste wählbar", ed._param_an(ed.lstA.pos()) is not None, str(ed.lstA.pos()))
    finally:
        doc.close(True)


def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_meldungen43.log"
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
