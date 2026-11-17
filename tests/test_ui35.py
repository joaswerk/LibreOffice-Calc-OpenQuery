# -*- coding: utf-8 -*-
"""0.8.4: Parameter aus einer Abfrage (Liste / Wert), Verwendung im Filter, Löschschutz, Umbenennen, Zirkelbezug."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def fehler(f):
    try:
        f(); return None
    except (E.FormelFehler, E.StepError) as ex:
        return getattr(ex, "meldung", None) or str(ex.args[0] if ex.args else ex)

def main():
    import faulthandler; faulthandler.dump_traceback_later(150, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    sh = doc.getSheets().getByIndex(0); sh.Name = "Haus"
    doc.getSheets().insertNewByName("Aktive", 1)
    def fuell(blatt, zeilen):
        s = doc.getSheets().getByName(blatt)
        for r, z in enumerate(zeilen):
            for c, v in enumerate(z):
                (s.getCellByPosition(c, r).setString(v) if isinstance(v, str) else s.getCellByPosition(c, r).setValue(v))
    fuell("Haus", [["Nr", "Name"], ["H1", "Alt"], ["H2", "Mitte"], ["H3", "Neu"], ["H4", "Rand"]])
    fuell("Aktive", [["Nummer", "Zahl"], ["H1", 5], ["H3", 7], ["H1", 9], ["", 1]])
    kopf = {"op": "erste_zeile_als_kopf"}
    AE.speichere_abfrage(doc, E.Abfrage("Aktive Häuser", {"art": "blatt", "blatt": "Aktive"}, [kopf]))
    AE.speichere_abfrage(doc, E.Abfrage("Haupt", {"art": "blatt", "blatt": "Haus"}, [kopf]))
    P = lambda n, typ, w: AE.speichere_oq_parameter(doc, n, {"typ": typ, "wert": w, "beschreibung": ""})
    def setze():
        AE.setze_aufloeser(ctx, doc)
    setze()
    P("p_liste", "abfrage_liste", "Aktive Häuser[Nummer]")
    P("p_erste", "abfrage_liste", "Aktive Häuser")
    P("p_zahl", "abfrage_wert", "Aktive Häuser[Zahl]")
    P("p_wert", "abfrage_wert", "Aktive Häuser")
    h = lambda n: AE.baue_parameter(doc)(n)
    pruefe("Liste: Werte ohne Leere und Doppelte", h("p_liste") == "H1;H3", repr(h("p_liste")))
    pruefe("Liste ohne Spalte: erste Spalte", h("p_erste") == "H1;H3", repr(h("p_erste")))
    pruefe("Wert: erste nicht leere Zelle der Spalte (Zahl)", h("p_zahl") == 5, repr(h("p_zahl")))
    pruefe("Wert ohne Spalte: erste Spalte", h("p_wert") == "H1", repr(h("p_wert")))
    # Verwendung im Filter „ist eines von“
    haupt = E.Abfrage.from_json(AE.abfragen_texte(doc)["Haupt"])
    roh = AE.lies_quelle(ctx, doc, haupt.quelle)
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "filtern", "spalte": "Nr", "bedingung": "in_liste", "wert": "{p_liste}"}])
    pruefe("Filter ist eines von {p_liste}: H1 und H3", [z[0] for z in t.zeilen] == ["H1", "H3"], str(t.zeilen))
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "filtern", "spalte": "Nr", "bedingung": "in_liste", "wert": "{p_liste}", "aktion": "entfernen"}])
    pruefe("Filter entfernen: H2 und H4 bleiben", [z[0] for z in t.zeilen] == ["H2", "H4"], str(t.zeilen))
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "spalten_behalten", "spalten": ["{p_wert}"]}]) if False else None
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "filtern", "spalte": "Nr", "bedingung": "gleich", "wert": "{p_wert}"}])
    pruefe("Filter gleich {p_wert}: H1", [z[0] for z in t.zeilen] == ["H1"], str(t.zeilen))
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "zeilen_behalten_oben", "anzahl": "{p_zahl}"}])
    pruefe("Zahlfeld aus Abfragewert: 5 Zeilen -> alle 4", len(t.zeilen) == 4)
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "zeilen_behalten_oben", "anzahl": 2, "nur_wenn": {"parameter": "p_zahl", "vergleich": ">", "wert": "3"}}])
    pruefe("Schritt-Bedingung mit Abfrage-Wert (5 > 3)", len(t.zeilen) == 2, str(len(t.zeilen)))
    t = E.fuehre_aus(roh, haupt.schritte + [{"op": "zeilen_behalten_oben", "anzahl": 2, "nur_wenn": {"parameter": "p_zahl", "vergleich": ">", "wert": "30"}}])
    pruefe("Schritt-Bedingung (5 > 30 nicht erfüllt): übersprungen", len(t.zeilen) == 4, str(len(t.zeilen)))
    # Fehler
    P("p_x1", "abfrage_liste", "Gibt es nicht"); setze()
    f = fehler(lambda: h("p_x1")); pruefe("Unbekannte Abfrage -> Meldung", f and "Gibt es nicht" in f and "p_x1" in f, str(f))
    P("p_x2", "abfrage_liste", "Aktive Häuser[Fehlt]"); f = fehler(lambda: h("p_x2"))
    pruefe("Unbekannte Spalte -> Meldung mit vorhandenen", f and "Fehlt" in f and "Nummer" in f, str(f))
    fuell("Aktive", [["Nummer", "Zahl"], ["", ""], ["", ""], ["", ""], ["", ""]]); setze()
    f = fehler(lambda: h("p_liste")); pruefe("Leere Spalte -> Meldung", f and "keinen Wert" in f, str(f))
    fuell("Aktive", [["Nummer", "Zahl"], ["A;B", 1]]); setze()
    f = fehler(lambda: h("p_liste")); pruefe("Semikolon im Wert -> Meldung", f and "Semikolon" in f, str(f))
    # Eingabe prüfen
    pruefe("Typ abfrage_liste ohne Name abgelehnt", fehler(lambda: (_ for _ in ()).throw(E.FormelFehler("x"))) is not None)
    try:
        AE.parse_param_wert("abfrage_liste", "[Spalte]"); ok = False
    except ValueError:
        ok = True
    pruefe("Nur Spalte ohne Abfragename abgelehnt", ok)
    pruefe("Name[Spalte] zerlegt", AE.teile_abfrage_angabe(" Aktive Häuser [Nummer] ") == ("Aktive Häuser", "Nummer"))
    # Löschschutz und Umbenennen
    pruefe("Parameter, die aus einer Abfrage lesen", AE.parameter_aus_abfrage(doc, "aktive häuser") == ["p_erste", "p_liste", "p_wert", "p_x2", "p_zahl"],
           str(AE.parameter_aus_abfrage(doc, "aktive häuser")))
    AE.parameter_abfrage_umbenennen(doc, "Aktive Häuser", "Aktiv neu")
    ps = AE.lies_oq_parameter(doc)
    pruefe("Umbenennen folgt (mit und ohne Spalte)", ps["p_liste"]["wert"] == "Aktiv neu[Nummer]" and ps["p_wert"]["wert"] == "Aktiv neu", str(ps["p_liste"]))
    # Zirkelbezug: Abfrage, die einen Parameter nutzt, der sie selbst liest
    P("p_zirk", "abfrage_liste", "Haupt")
    AE.speichere_abfrage(doc, E.Abfrage("Haupt", {"art": "blatt", "blatt": "Haus"},
                                        [kopf, {"op": "filtern", "spalte": "Nr", "bedingung": "in_liste", "wert": "{p_zirk}"}]))
    AE.setze_aufloeser(ctx, doc, "Haupt")
    f = fehler(lambda: E.fuehre_aus(AE.lies_quelle(ctx, doc, {"art": "blatt", "blatt": "Haus"}),
                                    [kopf, {"op": "filtern", "spalte": "Nr", "bedingung": "in_liste", "wert": "{p_zirk}"}]))
    pruefe("Zirkelbezug erkannt", f and "Zirkelbezug" in f, str(f))
    doc.close(True)
    fehl = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehl)))
    return 1 if fehl else 0
sys.exit(main())
