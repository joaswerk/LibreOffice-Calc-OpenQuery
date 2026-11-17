# -*- coding: utf-8 -*-
"""Tests für 0.2.7: Überschriften-Schritte geben neue Namen weiter, Schritte ohne Eingaben, Menüreihenfolge."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def schreibe(doc, name, rows):
    sh = doc.getSheets()
    if not sh.hasByName(name):
        sh.insertNewByName(name, sh.getCount())
    b = sh.getByName(name)
    for r, z in enumerate(rows):
        for c, v in enumerate(z):
            cell = b.getCellByPosition(c, r)
            cell.setString(v) if isinstance(v, str) else cell.setValue(v)

def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        schreibe(doc, "Roh", [["Menge", "Preis"], [1, 2], [3, 4]])
        a = E.Abfrage("R", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "spalten_entfernen", "spalten": ["Spalte2"]}])
        ed = AE.Editor(ctx, frame, doc, a)
        ed.run(ohne_dialog=True)
        tab = ed.tabelle_bis(-1) if False else E.fuehre_aus(AE.lies_quelle(ctx, doc, a.quelle), [])
        a = ed.abfrage
        neu = {"op": "erste_zeile_als_kopf"}
        a.schritte.insert(0, neu)
        ed._umbenennung_weitergeben(0, None, neu, tab)
        pruefe("Überschriften-Schritt nachträglich: Folgeschritt nutzt neuen Namen",
               a.schritte[1]["spalten"] == ["Preis"], str(a.schritte[1]))
        res = E.fuehre_aus(AE.lies_quelle(ctx, doc, a.quelle), a.schritte)
        pruefe("... und die Abfrage läuft", res.spalten == ["Menge"], str(res.spalten))
        ops = [o for o, _ in E.ops_der_gruppe("Zeilen")]
        pruefe("Inverse Paare stehen nebeneinander",
               ops.index("fehler_zeilen_behalten") == ops.index("fehler_zeilen_entfernen") + 1)
        for op in ("erste_zeile_als_kopf", "kopf_als_erste_zeile", "zeilen_umkehren", "spaltenreihenfolge_umkehren"):
            pruefe("Ohne Felder: " + op, not E.OPS[op]["felder"])
    finally:
        doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    sys.exit(1 if fehler else 0)

main()
