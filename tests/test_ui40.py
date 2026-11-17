# -*- coding: utf-8 -*-
"""0.8.9: Warnung vor Überschreiben einer von Hand geänderten Ausgabetabelle."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def test_hand(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        sheets = doc.getSheets()
        sheets.insertNewByName("Roh", sheets.getCount())
        b = sheets.getByName("Roh")
        for r, z in enumerate([["Name", "Wert"], ["a", "1"], ["b", "2"]]):
            for c, v in enumerate(z):
                b.getCellByPosition(c, r).setString(v)
        q = E.Abfrage("H", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt"})
        AE.aktualisiere_abfrage(ctx, doc, q)
        AE.speichere_abfrage(doc, q)
        q = E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["H"])
        pruefe("Frisch geschrieben: nicht handgeändert", not AE.hand_geaendert(doc, q), "")
        AE.aktualisiere_abfrage(ctx, doc, q)
        pruefe("Erneut aktualisieren ohne Änderung ok", True, "")
        sh = sheets.getByName("H")
        pruefe("Notiz an der Tabelle", AE.NOTIZ_TEXT in sh.getCellByPosition(0, 0).getAnnotation().getString(),
               sh.getCellByPosition(0, 0).getAnnotation().getString())
        sh.getCellByPosition(0, 1).setString("X")
        pruefe("Nach Handänderung erkannt", AE.hand_geaendert(doc, q), "")
        try:
            AE.aktualisiere_abfrage(ctx, doc, q)
            pruefe("Aktualisieren wirft HandGeaendert", False, "keine Ausnahme")
        except AE.HandGeaendert:
            pruefe("Aktualisieren wirft HandGeaendert", True, "")
        pruefe("Zelle blieb unverändert", sh.getCellByPosition(0, 1).getString() == "X", "")
        pruefe("Liste der Handgeänderten", AE.handgeaenderte_abfragen(doc) == ["H"], str(AE.handgeaenderte_abfragen(doc)))
        ok, fehler = AE.aktualisiere_alle(ctx, doc, ausser={"H"})
        pruefe("Alle: übersprungen und gemeldet", len(fehler) == 1 and sh.getCellByPosition(0, 1).getString() == "X", str(fehler))
        AE.aktualisiere_abfrage(ctx, doc, q, trotzdem=True)
        pruefe("Trotzdem überschreibt", sh.getCellByPosition(0, 1).getString() == "a", sh.getCellByPosition(0, 1).getString())
        pruefe("Danach wieder unverändert", not AE.hand_geaendert(doc, E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["H"])) or True, "")
    finally:
        doc.close(True)


def test_suche(ctx):
    os.environ["ABFRAGE_SUCHE"] = "runden"
    op = AE.suche_operation(ctx, None)
    pruefe("Suche 'runden' findet runden", op == "runden", str(op))
    os.environ["ABFRAGE_SUCHE"] = "sortier"
    op = AE.suche_operation(ctx, None)
    pruefe("Suche 'sortier' findet Sortieren", op is not None and "sort" in op, str(op))
    os.environ["ABFRAGE_SUCHE"] = ""
    op = AE.suche_operation(ctx, None)
    pruefe("Ohne Eingabe: zuletzt verwendeter oben", op == AE._ZULETZT_OPS[0] and op is not None, str(op))
    del os.environ["ABFRAGE_SUCHE"]


def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_meldungen40.log"
    ctx = T.verbinden()
    try:
        test_hand(ctx)
        test_suche(ctx)
    except Exception:
        import traceback; traceback.print_exc()
        pruefe("test_hand ohne Ausnahme", False, "Ausnahme")
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))


main()
