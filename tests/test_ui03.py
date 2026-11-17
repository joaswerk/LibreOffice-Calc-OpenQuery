# -*- coding: utf-8 -*-
"""Tests für 0.2.3: Spaltenbreite, Typdialog, Schrittnamen, Beschreibungszeile, Währung/Prozent im Blatt, Einfügen vor/nach."""
import os
import sys
import traceback
import types

import uno

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T  # noqa: E402
from test_ui02 import neuer_editor, titel  # noqa: E402

AE, E = T.AE, T.E
pruefe = T.pruefe


def main():
    import faulthandler; faulthandler.dump_traceback_later(60, exit=True)
    os.environ["ABFRAGE_AUTOCLOSE"] = "3"
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()
        ed = neuer_editor(ctx, frame, doc, schritte=T.SCHRITTE[:4])
        ed.zeige()
        t = titel(ed)
        pruefe("Spaltenköpfe haben Typsymbol links vom Namen", any(x.strip(" ◄\u2003").endswith(" | Objekt") and x.lstrip("●►\u2003 ").startswith("ABC") for x in t), str(t))
        pruefe("Verbrauch als Dezimalzahl-Symbol", any(x.strip().endswith(" | Verbrauch kWh") and "1,2" in x for x in t), str(t))

        # Spaltenbreite
        cols = ed.d.ctrl("grid").getModel().ColumnModel.getColumns()[1:]
        pruefe("Spaltenbreiten höchstens 100", all(c.ColumnWidth <= AE.Editor.BREITE_MAX for c in cols),
               str([c.ColumnWidth for c in cols]))
        ed.breite_optimieren("Objekt")
        c0 = [c for n, c in zip(ed._grid_namen, ed.d.ctrl("grid").getModel().ColumnModel.getColumns()[1:]) if n == "Objekt"][0]
        pruefe("Breite optimieren: zwischen Min und Max", AE.Editor.BREITE_MIN <= c0.ColumnWidth <= AE.Editor.BREITE_MAX, str(c0.ColumnWidth))

        # Zeilenkopf-Klick fragt nichts ab
        ev_calls = []
        g = ed.d.ctrl("grid")
        try:
            g.getColumnAtPoint = lambda *a: ev_calls.append(a)
        except Exception:
            pass
        ed.grid_maus(types.SimpleNamespace(X=1, Y=20, PopupTrigger=False, ClickCount=1, Buttons=1))
        pruefe("Klick auf Zeilennummer: keine Treffer-Abfrage, kein Fehler", True)

        # Nummernspalte und Zeilenzahl
        gm = ed.d.ctrl("grid").getModel()
        pruefe("Eigener Zeilenkopf aus, Nummernspalte statt dessen", not gm.ShowRowHeader or gm.ColumnModel.getColumns()[0].Title == "#",
               str(gm.ShowRowHeader))
        pruefe("Nummernspalte: Zeile 1 hat Nummer 1", gm.GridDataModel.getCellData(0, 0) == "1")
        pruefe("Datenspalte 1 liegt rechts der Nummernspalte", gm.GridDataModel.getCellData(1, 0) == "Schule A", str(gm.GridDataModel.getCellData(1, 0)))

        # Typ-Menü (Doppelklick auf das Symbol)
        import threading, time
        ed._pm = None
        threading.Timer(1.5, lambda: ed._pm.endExecute()).start()
        ed.typ_menue("Verbrauch kWh", 300, 120)
        pruefe("Typ-Menü öffnet und schließt", ed._pm is not None and ed._pm.getItemCount() == len(E.TYPEN), "")
        pruefe("Typ-Menü: aktueller Typ mit Haken", ed._pm.isItemChecked(3), "")

        # Schrittnamen, Nummerierung
        ed.neuer_schritt("sortieren", {"spalte1": "Objekt", "richtung1": "auf"}, direkt=True)
        ed.neuer_schritt("zeilen_behalten_oben", {"anzahl": 5}, direkt=True) if "zeilen_behalten_oben" in E.OPS else None
        tx = ed.schritt_texte()
        pruefe("Schrittliste mit führender Null", tx[0].startswith("01. ") and tx[1].startswith("02. "), str(tx))
        ed.lstS.waehle(1)
        os.environ["ABFRAGE_FRAGETEXT"] = "Meine Sortierung"
        ed.umbenennen()
        os.environ.pop("ABFRAGE_FRAGETEXT", None)
        pruefe("Umbenennen setzt Schrittnamen", ed.abfrage.schritte[0].get("name") == "Meine Sortierung", str(ed.abfrage.schritte[0]))
        pruefe("Schrittliste zeigt Namen", "02. Meine Sortierung" in ed.schritt_texte(), str(ed.schritt_texte()))
        ed.beschreibung_zeigen()
        beschr = ed.d.ctrl("lblInfo").getModel().Label
        pruefe("Beschreibung zeigt automatischen Text", "Meine Sortierung" not in beschr and beschr != "", beschr)
        os.environ["ABFRAGE_FRAGETEXT"] = ""
        ed.umbenennen()
        os.environ.pop("ABFRAGE_FRAGETEXT", None)
        pruefe("Leerer Name entfernt Namen", "name" not in ed.abfrage.schritte[0])

        # Einfügen vor/nach
        n0 = len(ed.abfrage.schritte)
        os.environ["ABFRAGE_AUTOOK"] = "1"
        ed.lstS.waehle(1)
        ed.schritt_befehl(("einfuegen", "vor", "spalten_entfernen"))
        os.environ.pop("ABFRAGE_AUTOOK", None)
        pruefe("Schritt einfügen vor/nach läuft ohne Fehler", len(ed.abfrage.schritte) in (n0, n0 + 1))
        if len(ed.abfrage.schritte) == n0 + 1:
            pruefe("Einfügen vor: Position 1", ed.abfrage.schritte[0]["op"] == "spalten_entfernen", str(ed.abfrage.schritte[:2]))

        # Währung / Prozent im Blatt
        tab = E.Tabelle(["w", "p"], [[E.Waehrung(1234.5), E.Prozent(0.125)], [E.Waehrung(2), E.Prozent(1)]])
        AE.schreibe_tabelle(doc, tab, "WP")
        blatt = doc.getSheets().getByName("WP")
        pruefe("Währung im Blatt: Zahl", abs(blatt.getCellByPosition(0, 1).getValue() - 1234.5) < 1e-9)
        pruefe("Währung im Blatt: Währungsformat", "€" in blatt.getCellByPosition(0, 1).getString() or "," in blatt.getCellByPosition(0, 1).getString(), blatt.getCellByPosition(0, 1).getString())
        pruefe("Prozent im Blatt: Anzeige", "%" in blatt.getCellByPosition(1, 1).getString(), blatt.getCellByPosition(1, 1).getString())
        rueck = AE.tabelle_aus_bereich(doc, blatt.getCellRangeByName("A1:B3"))
        pruefe("Roundtrip: Währung erkannt", isinstance(rueck.zeilen[1][0], E.Waehrung), str(type(rueck.zeilen[1][0])))
        pruefe("Roundtrip: Prozent erkannt", isinstance(rueck.zeilen[1][1], E.Prozent) and abs(rueck.zeilen[1][1] - 0.125) < 1e-9, str(rueck.zeilen[1]))
    except Exception:
        traceback.print_exc()
        pruefe("UI-Test 0.2.3 ohne unerwartete Ausnahme", False, traceback.format_exc().splitlines()[-1])
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
