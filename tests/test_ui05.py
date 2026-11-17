# -*- coding: utf-8 -*-
"""Tests für 0.2.6: Verbinden/Anfügen mit anderen Abfragen, Dialoge, Zirkelbezug, ⚠ im Spaltenkopf."""
import os
import sys
import traceback

import uno

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T  # noqa: E402
from test_ui02 import titel  # noqa: E402

AE, E = T.AE, T.E
pruefe = T.pruefe


def schreibe(doc, name, zeilen):
    sh = doc.getSheets()
    if not sh.hasByName(name):
        sh.insertNewByName(name, sh.getCount())
    blatt = sh.getByName(name)
    for r, z in enumerate(zeilen):
        for c, v in enumerate(z):
            zelle = blatt.getCellByPosition(c, r)
            if isinstance(v, str):
                zelle.setString(v)
            else:
                zelle.setValue(v)


KOPF = {"op": "erste_zeile_als_kopf"}


def main():
    import faulthandler
    faulthandler.dump_traceback_later(240, exit=True)
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        schreibe(doc, "Verbrauch", [["Jahr", "Monat", "Menge"], [2025, 1, 10], [2025, 2, 20], [2026, 1, 30]])
        schreibe(doc, "Preise", [["J", "M", "Preis"], [2025, 1, 1.5], [2026, 1, 2.5], [2027, 1, 9]])
        schreibe(doc, "Mix", [["Wert"], ["1"], ["2"], ["n/a"], ["4"]])
        doc.getSheets().getByName("Mix").getCellByPosition(0, 3).setFormula("=1/0")      # echter Fehlerwert
        preise = E.Abfrage("Preise", {"art": "blatt", "blatt": "Preise"}, [KOPF])
        AE.speichere_abfrage(doc, preise)
        a = E.Abfrage("Haupt", {"art": "blatt", "blatt": "Verbrauch"}, [KOPF])
        ed = AE.Editor(ctx, frame, doc, a)
        ed.run(ohne_dialog=True)

        # Auflöser
        t = E.hole_tabelle("Preise")
        pruefe("Auflöser liefert Ergebnis der anderen Abfrage", t.spalten == ["J", "M", "Preis"] and len(t.zeilen) == 3, str(t.spalten))

        # Verbinden direkt
        ed.neuer_schritt("tabellen_verbinden", {"abfrage": "Preise", "join": "links", "spalten_rechts": [],
                                                 "schluessel": [{"links": "Jahr", "rechts": "J"}, {"links": "Monat", "rechts": "M"}]}, direkt=True)
        ed.zeige()
        pruefe("Verbinden: Spalte Preis dazu", ed.angezeigt is not None and ed.angezeigt.spalten == ["Jahr", "Monat", "Menge", "Preis"],
               str(ed.angezeigt.spalten if ed.angezeigt else None))
        pruefe("Verbinden: Werte stimmen", [z[3] for z in ed.angezeigt.zeilen] == [1.5, None, 2.5], str(ed.angezeigt.zeilen))

        # Dialoge mit Auto-OK
        os.environ["ABFRAGE_AUTOOK"] = "2.5"
        os.environ["ABFRAGE_AUTOCLOSE"] = "8"
        AE._EDITOR_KONTEXT["doc"], AE._EDITOR_KONTEXT["eigen"] = doc, "Haupt"
        AE.setze_aufloeser(ctx, doc, "Haupt")
        tab_vor = ed.tabelle_bis(1)
        vor = {"abfrage": "Preise", "join": "innen",
               "schluessel": [{"links": "Jahr", "rechts": "J"}, {"links": "Monat", "rechts": "M"}], "spalten_rechts": ["Preis"]}
        erg = AE.SchrittDialog(ctx, "tabellen_verbinden", tab_vor, None, vor, None).zeigen()
        pruefe("VerbindenDialog liefert Schritt", erg is not None and erg["join"] == "innen" and erg["spalten_rechts"] == ["Preis"]
               and len(erg["schluessel"]) == 2, str(erg))
        schreibe(doc, "Extra", [["Jahr", "Monat", "Menge"], [2030, 5, 99]])
        AE.speichere_abfrage(doc, E.Abfrage("Extra", {"art": "blatt", "blatt": "Extra"}, [KOPF]))
        erg2 = AE.SchrittDialog(ctx, "tabellen_anfuegen", tab_vor, None,
                                {"abfragen": ["Extra"], "ausrichtung": "name", "herkunft": "Quelle", "herkunft_eigen": "Haupt"}, None).zeigen()
        pruefe("AnfuegenDialog liefert Schritt", erg2 is not None and erg2["abfragen"] == ["Extra"] and erg2["herkunft"] == "Quelle", str(erg2))
        os.environ.pop("ABFRAGE_AUTOOK", None)

        # Anfügen + Ausgabe ins Blatt
        a2 = E.Abfrage("Gesamt", {"art": "blatt", "blatt": "Verbrauch"},
                       [KOPF, erg2, {"op": "tabellen_verbinden", "abfrage": "Preise", "join": "links",
                                    "schluessel": [{"links": "Jahr", "rechts": "J"}, {"links": "Monat", "rechts": "M"}]}],
                       ziel={"art": "blatt"})
        n = AE.aktualisiere_abfrage(ctx, doc, a2)
        blatt = doc.getSheets().getByName(AE.zielblatt_name(a2))
        pruefe("Anfügen + Verbinden: Zeilen im Zielblatt", n == 4, str(n))
        pruefe("Zielblatt: Herkunftswert Extra in letzter Zeile", blatt.getCellByPosition(3, 4).getString() == "Extra"
               or any(blatt.getCellByPosition(c, 4).getString() == "Extra" for c in range(6)), blatt.getCellByPosition(3, 4).getString())

        # Zirkelbezug
        AE.speichere_abfrage(doc, E.Abfrage("ZA", {"art": "blatt", "blatt": "Verbrauch"},
                                            [KOPF, {"op": "tabellen_anfuegen", "abfragen": ["ZB"]}]))
        AE.speichere_abfrage(doc, E.Abfrage("ZB", {"art": "blatt", "blatt": "Verbrauch"},
                                            [KOPF, {"op": "tabellen_anfuegen", "abfragen": ["ZA"]}]))
        AE.setze_aufloeser(ctx, doc, "ZA")
        try:
            E.fuehre_aus(AE.lies_quelle(ctx, doc, {"art": "blatt", "blatt": "Verbrauch"}),
                         [KOPF, {"op": "tabellen_anfuegen", "abfragen": ["ZB"]}])
            meld = "kein Fehler"
        except E.StepError as e:
            meld = str(e)
        pruefe("Zirkelbezug wird erkannt", "Zirkelbezug" in meld, meld)
        AE.setze_aufloeser(ctx, doc, "Haupt")

        # ⚠ im Spaltenkopf
        em = AE.Editor(ctx, frame, doc, E.Abfrage("M", {"art": "blatt", "blatt": "Mix"}, [KOPF]))
        em.run(ohne_dialog=True)
        tt = titel(em)
        pruefe("Spaltenkopf zeigt ⚠ 1 bei der Spalte mit Ausreißer", any("⚠1" in x for x in tt), str(tt))
        em.spalte_markieren("Wert")
        pruefe("Über der Tabelle: Fehler: 1", em.d.ctrl("lblQual").getModel().Label.startswith("Fehler: 1"), em.d.ctrl("lblQual").getModel().Label)
        ed2 = AE.Editor(ctx, frame, doc, E.Abfrage("H2", {"art": "blatt", "blatt": "Verbrauch"}, [KOPF]))
        ed2.run(ohne_dialog=True)
        pruefe("Keine Fehler: kein ⚠", not any("⚠" in x for x in titel(ed2)), str(titel(ed2)))
        # Menü enthält Gruppe Tabellen
        pm, ids = ed.baue_menue()
        pruefe("Menü kennt die neuen Schritte", any(isinstance(v, tuple) and v[0] == "tabellen_verbinden" for v in ids.values())
               and any(isinstance(v, tuple) and v[0] == "tabellen_anfuegen" for v in ids.values()), "")
    except Exception:
        traceback.print_exc()
        pruefe("UI-Test 0.2.6 ohne unerwartete Ausnahme", False, traceback.format_exc().splitlines()[-1])
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
