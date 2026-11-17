# -*- coding: utf-8 -*-
"""0.8.4: Parameter in Zahl-, Spalten-, Auswahl- und Ja/Nein-Feldern; Schritt-Bedingung; Dialoge."""
import os, sys, faulthandler, datetime as dt
faulthandler.enable(); sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def fehler_von(f):
    try:
        f(); return None
    except (E.FormelFehler, E.StepError) as ex:
        return str(ex.args[0] if ex.args else ex)

def main():
    faulthandler.dump_traceback_later(150, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    AE.setze_aufloeser(ctx, doc)
    AE._EDITOR_KONTEXT["doc"] = doc
    P = lambda n, typ, w: AE.speichere_oq_parameter(doc, n, {"typ": typ, "wert": w, "beschreibung": ""})
    P("p_n", "zahl", "2"); P("p_sp", "text", "Betrag"); P("p_ri", "text", "ab"); P("p_sps", "liste", "Region;Menge")
    P("p_jn", "janein", "Ja"); P("p_r", "text", "Nord"); P("p_g", "zahl", "10"); P("p_dat", "datum", "31.12.2025")
    P("p_flag", "janein", "Nein"); P("p_stadt", "liste", "Berlin;Potsdam"); P("p_falsch", "text", "seitwärts")
    t = E.Tabelle(["Region", "Betrag", "Menge"], [["Nord", 5.0, 1.0], ["Nordost", 20.0, 2.0], ["Süd", 7.0, 3.0], ["Nord", 1.0, 4.0]])
    ex = lambda st: E.fuehre_aus(t, [st])
    # A1 Zahl
    r = ex({"op": "zeilen_entfernen_oben", "anzahl": "{p_n}"})
    pruefe("Zahlfeld aus Parameter: 2 Zeilen entfernt", len(r.zeilen) == 2 and r.zeilen[0][0] == "Süd", str(r.zeilen))
    # A2 Spalte + Wahl
    r = ex({"op": "sortieren", "spalte1": "{p_sp}", "richtung1": "{p_ri}"})
    pruefe("Spalte und Richtung aus Parameter", [z[1] for z in r.zeilen] == [20.0, 7.0, 5.0, 1.0], str(r.zeilen))
    # A3 Spalten
    r = ex({"op": "spalten_behalten", "spalten": ["{p_sps}"]})
    pruefe("Spaltenliste aus Listen-Parameter", r.spalten == ["Region", "Menge"], str(r.spalten))
    r = ex({"op": "spalten_behalten", "spalten": ["Betrag", "{p_sps}"]})
    pruefe("Spaltenliste gemischt (feste + Parameter)", r.spalten == ["Region", "Betrag", "Menge"] or sorted(r.spalten) == ["Betrag", "Menge", "Region"], str(r.spalten))
    f = fehler_von(lambda: ex({"op": "sortieren", "spalte1": "Region", "richtung1": "{p_falsch}"}))
    pruefe("Auswahlfeld: falscher Parameterwert -> Meldung mit Erlaubtem", f and "passt nicht" in f and "auf" in f, str(f))
    f = fehler_von(lambda: ex({"op": "sortieren", "spalte1": "{p_r}", "richtung1": "auf"}))
    pruefe("Spaltenname aus Parameter existiert nicht -> Meldung", f and "Nord" in f, str(f))
    # A5 Ja/Nein
    st = {"op": "ersetzen", "spalten": ["Region"], "suchen": "Nord", "ersetzen_durch": "N", "ganze_zelle": "{p_jn}", "gross_klein": False}
    r = ex(st)
    pruefe("Ja/Nein aus Parameter = Ja: nur ganze Zelle", [z[0] for z in r.zeilen] == ["N", "Nordost", "Süd", "N"], str([z[0] for z in r.zeilen]))
    P("p_jn", "janein", "Nein")
    r = ex(st)
    pruefe("Ja/Nein aus Parameter = Nein: auch Teiltext", [z[0] for z in r.zeilen] == ["N", "Nost", "Süd", "N"], str([z[0] for z in r.zeilen]))
    # B6 Bedingung
    s0 = {"op": "sortieren", "spalte1": "Betrag", "richtung1": "ab"}
    first = lambda st: ex(st).zeilen[0][1]
    pruefe("Ohne Bedingung sortiert", first(s0) == 20.0)
    pruefe("Bedingung Text = erfüllt (Groß/Klein egal)", first(dict(s0, nur_wenn={"parameter": "p_r", "vergleich": "=", "wert": "NORD"})) == 20.0)
    pruefe("Bedingung Text = nicht erfüllt: Schritt übersprungen", first(dict(s0, nur_wenn={"parameter": "p_r", "vergleich": "=", "wert": "Süd"})) == 5.0)
    pruefe("Bedingung <> erfüllt", first(dict(s0, nur_wenn={"parameter": "p_r", "vergleich": "<>", "wert": "Süd"})) == 20.0)
    pruefe("Bedingung Zahl > erfüllt (10 > 5)", first(dict(s0, nur_wenn={"parameter": "p_g", "vergleich": ">", "wert": "5"})) == 20.0)
    pruefe("Bedingung Zahl <= nicht erfüllt (10 <= 5)", first(dict(s0, nur_wenn={"parameter": "p_g", "vergleich": "<=", "wert": "5"})) == 5.0)
    pruefe("Bedingung Datum > erfüllt", first(dict(s0, nur_wenn={"parameter": "p_dat", "vergleich": ">", "wert": "01.01.2025"})) == 20.0)
    pruefe("Bedingung Datum < nicht erfüllt", first(dict(s0, nur_wenn={"parameter": "p_dat", "vergleich": "<", "wert": "01.01.2025"})) == 5.0)
    pruefe("Bedingung Ja/Nein: Nein = Ja nicht erfüllt", first(dict(s0, nur_wenn={"parameter": "p_flag", "vergleich": "=", "wert": "Ja"})) == 5.0)
    pruefe("Bedingung Ja/Nein: Nein = Nein erfüllt", first(dict(s0, nur_wenn={"parameter": "p_flag", "vergleich": "=", "wert": "nein"})) == 20.0)
    pruefe("Bedingung Liste enthält erfüllt", first(dict(s0, nur_wenn={"parameter": "p_stadt", "vergleich": "enthält", "wert": "potsdam"})) == 20.0)
    pruefe("Bedingung Liste enthält nicht erfüllt", first(dict(s0, nur_wenn={"parameter": "p_stadt", "vergleich": "enthält", "wert": "Cottbus"})) == 5.0)
    f = fehler_von(lambda: ex(dict(s0, nur_wenn={"parameter": "gibt_es_nicht", "vergleich": "=", "wert": "x"})))
    pruefe("Bedingung mit unbekanntem Parameter -> Meldung mit Schrittnummer", f and "gibt_es_nicht" in f and "Schritt 1" in f, str(f))
    f = fehler_von(lambda: ex(dict(s0, nur_wenn={"parameter": "p_g", "vergleich": ">", "wert": "abc"})))
    pruefe("Bedingung mit unlesbarem Vergleichswert -> Meldung", bool(f), str(f))
    b = dict(s0, nur_wenn={"parameter": "p_r", "vergleich": "=", "wert": "Nord"})
    pruefe("Beschreibung nennt die Bedingung", "nur wenn {p_r} = Nord" in E.beschreibe(b), E.beschreibe(b))
    pruefe("Ausgeschaltet + Bedingung: bleibt übersprungen", first(dict(b, aktiv=False)) == 5.0)
    sf = {"op": "filtern", "spalte": "Region", "bedingung": "enthaelt", "wert": "Nord"}
    pruefe("Filter-Schritt mit eigenem Feld „bedingung“ unberührt", len(ex(sf).zeilen) == 3, str(len(ex(sf).zeilen)))
    pruefe("Filter + nur_wenn (erfüllt)", len(ex(dict(sf, nur_wenn={"parameter": "p_r", "vergleich": "=", "wert": "Nord"})).zeilen) == 3)
    pruefe("Filter + nur_wenn (nicht erfüllt): nicht gefiltert", len(ex(dict(sf, nur_wenn={"parameter": "p_r", "vergleich": "=", "wert": "Süd"})).zeilen) == 4)
    pruefe("Beschreibung Filter mit nur_wenn", "nur wenn" in E.beschreibe(dict(sf, nur_wenn={"parameter": "p_r", "vergleich": "=", "wert": "Nord"})))
    # Parameternamen
    pruefe("parameter_namen enthält alle", set(AE.parameter_namen(doc)) >= {"p_n", "p_sp", "p_jn", "p_r"}, str(AE.parameter_namen(doc)))
    pruefe("parameter_namen Ja/Nein: nur Ja/Nein-Parameter", sorted(AE.parameter_namen(doc, True)) == ["p_flag", "p_jn"], str(AE.parameter_namen(doc, True)))
    # Dialoge
    os.environ["ABFRAGE_AUTOOK"] = "3"
    res = AE.SchrittDialog(ctx, "sortieren", t, None, {"spalte1": "{p_sp}", "richtung1": "{p_ri}"}, None).zeigen()
    pruefe("Dialog: Spalte und Richtung als {Parameter} bleiben erhalten", res and res["spalte1"] == "{p_sp}" and res["richtung1"] == "{p_ri}", str(res))
    res = AE.SchrittDialog(ctx, "zeilen_entfernen_oben", t, None, {"anzahl": "{p_n}"}, None).zeigen()
    pruefe("Dialog: Zahlfeld mit {Parameter} bleibt Text", res and res["anzahl"] == "{p_n}", str(res))
    res = AE.SchrittDialog(ctx, "ersetzen", t, None, {"spalten": ["{p_sp}", "Region"], "suchen": "Nord", "ersetzen_durch": "N", "ganze_zelle": "{p_jn}"}, None).zeigen()
    pruefe("Dialog: Ja/Nein als {Parameter} und Spalten-Parameter", res and res["ganze_zelle"] == "{p_jn}" and "{p_sp}" in res["spalten"] and "Region" in res["spalten"], str(res))
    res = AE.SchrittDialog(ctx, "ersetzen", t, None, {"spalten": ["Region"], "suchen": "Nord", "ersetzen_durch": "N", "ganze_zelle": False}, None).zeigen()
    pruefe("Dialog: Ja/Nein ohne Parameter-Wahl bleibt bool (Nein)", res and res["ganze_zelle"] is False, str(res))
    res = AE.bedingung_bearbeiten(ctx, doc, None, {"parameter": "p_g", "vergleich": ">=", "wert": "7"})
    pruefe("Bedingungsdialog liefert die Bedingung", res == {"parameter": "p_g", "vergleich": ">=", "wert": "7"}, str(res))
    doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
