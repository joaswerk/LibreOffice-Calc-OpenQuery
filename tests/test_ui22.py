# -*- coding: utf-8 -*-
"""Probe: bleiben Handeinträge bei verschiedenen Schlüsselarten erhalten (Text 007, Zahl, Datum, Dezimal, leer)?"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E

def lauf(ctx, name, rohdaten, typschritte, fmt=None):
    desk, doc = T.neues_calc(ctx)
    try:
        sheets = doc.getSheets(); sheets.insertNewByName("Roh", 1); b = sheets.getByName("Roh")
        b.getCellByPosition(0, 0).setString("K"); b.getCellByPosition(1, 0).setString("V")
        for r, (k, v) in enumerate(rohdaten, start=1):
            c = b.getCellByPosition(0, r)
            (c.setString if isinstance(k, str) else c.setValue)(k)
            b.getCellByPosition(1, r).setValue(v)
        if fmt:
            nf = doc.getNumberFormats(); loc = uno_locale()
            key = nf.queryKey(fmt, loc, False)
            if key == -1: key = nf.addNew(fmt, loc)
            b.getCellRangeByPosition(0, 1, 0, len(rohdaten)).NumberFormat = key
        schr = [{"op": "erste_zeile_als_kopf"}] + typschritte + [{"op": "hand_behalten", "schluessel": ["K"], "handspalten": "Notiz"}]
        q = E.Abfrage("Q", {"art": "blatt", "blatt": "Roh"}, schr, {"art": "blatt"})
        AE.aktualisiere_abfrage(ctx, doc, q); AE.speichere_abfrage(doc, q)
        sh = sheets.getByName("Q")
        for r in range(1, len(rohdaten) + 1):
            sh.getCellByPosition(2, r).setString("N%d" % r)
        q2 = E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Q"])
        AE.aktualisiere_abfrage(ctx, doc, q2)
        sh = sheets.getByName("Q")
        notizen = [sh.getCellByPosition(2, r).getString() for r in range(1, len(rohdaten) + 1)]
        ok = notizen == ["N%d" % r for r in range(1, len(rohdaten) + 1)]
        print("%-34s %s %s %s" % (name, "OK    " if ok else "VERLUST", notizen, "; ".join(E.HINWEISE)))
    finally:
        try: doc.close(True)
        except Exception: pass

def uno_locale():
    import uno
    l = uno.createUnoStruct("com.sun.star.lang.Locale"); l.Language = "de"; l.Country = "DE"; return l

def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden()
    lauf(ctx, "Text", [("a", 1), ("b", 2), ("c", 3)], [])
    lauf(ctx, "Text 007 (Typ Text)", [("007", 1), ("010", 2), ("1E3", 3)], [{"op": "typ_aendern", "spalten": ["K"], "typ": "text"}])
    lauf(ctx, "Zahl (Typ Zahl)", [(5, 1), (6.5, 2), (1000000, 3)], [{"op": "typ_aendern", "spalten": ["K"], "typ": "dezimal"}])
    lauf(ctx, "Zahl als Text getippt", [(5, 1), (6.5, 2), (7, 3)], [{"op": "typ_aendern", "spalten": ["K"], "typ": "text"}])
    lauf(ctx, "Datum (Typ Datum)", [(45000, 1), (45001, 2), (45002, 3)], [{"op": "typ_aendern", "spalten": ["K"], "typ": "datum"}], "TT.MM.JJJJ")
    lauf(ctx, "Datum+Zeit", [(45000.5, 1), (45001.25, 2), (45002.75, 3)], [{"op": "typ_aendern", "spalten": ["K"], "typ": "datumzeit"}], "TT.MM.JJJJ HH:MM")
    lauf(ctx, "Währung", [(5.5, 1), (6.25, 2), (7, 3)], [{"op": "typ_aendern", "spalten": ["K"], "typ": "waehrung"}])
    lauf(ctx, "Text mit Leerzeichen", [("a ", 1), (" b", 2), ("c", 3)], [])
    lauf(ctx, "Gleiche Schlüssel doppelt", [("a", 1), ("a", 2), ("c", 3)], [])
    return 0
sys.exit(main())
