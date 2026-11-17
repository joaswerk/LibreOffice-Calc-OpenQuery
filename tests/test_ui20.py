# -*- coding: utf-8 -*-
"""0.7.2: Engine-Neuerungen (Ersetzen mehrere Spalten, Teilen einmalig, Anfügen nur gewählte Spalten) und Oberfläche
(Ausblenden, Pfeilknöpfe, Deckfelder)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def main():
    import faulthandler; faulthandler.dump_traceback_later(150, exit=True)
    # Engine
    t = E.Tabelle(["a", "b"], [["x-1", "x-2"], ["y", "x"]])
    r = E.wende_schritt(t, {"op": "ersetzen", "spalten": ["a", "b"], "suchen": "x", "ersetzen_durch": "Z", "ganze_zelle": False})
    pruefe("Ersetzen in zwei Spalten", r.zeilen == [["Z-1", "Z-2"], ["y", "Z"]], str(r.zeilen))
    r = E.wende_schritt(t, {"op": "ersetzen", "spalte": "a", "suchen": "x", "ersetzen_durch": "Q", "ganze_zelle": False})
    pruefe("Ersetzen: altes Format", r.zeilen[0][0] == "Q-1" and r.zeilen[0][1] == "x-2", str(r.zeilen))
    pruefe("Beschreibung altes Format", "a" in E.beschreibe({"op": "ersetzen", "spalte": "a", "suchen": "x", "ersetzen_durch": "Q"}))
    t2 = E.Tabelle(["c"], [["ABCDEFG"], ["AB"], [None]])
    r = E.wende_schritt(t2, {"op": "spalte_teilen", "spalte": "c", "modus": "einmal_links", "anzahl_zeichen": 3})
    pruefe("Einmal nach 3 Zeichen", r.spalten == ["c.1", "c.2"] and r.zeilen[0][:2] == ["ABC", "DEFG"] and r.zeilen[1][:2] == ["AB", None], str(r.zeilen))
    r = E.wende_schritt(t2, {"op": "spalte_teilen", "spalte": "c", "modus": "einmal_rechts", "anzahl_zeichen": 2})
    pruefe("Einmal vor den letzten 2", r.zeilen[0][:2] == ["ABCDE", "FG"], str(r.zeilen))
    pruefe("Formel mit ^", E.rechne_formel_text("2^3") == 8 if hasattr(E, "rechne_formel_text") else True)
    # Anfügen mit Spaltenauswahl
    E.AUFLOESER["fn"] = lambda n: E.Tabelle(["a", "x", "y"], [[1, 2, 3]])
    base = E.Tabelle(["a"], [[0]])
    r = E.wende_schritt(base, {"op": "tabellen_anfuegen", "abfragen": ["B"], "ausrichtung": "name", "nur_spalten": ["x"]})
    pruefe("Anfügen: nur Spalte x", r.spalten == ["a", "x"] and r.zeilen[1] == [None, 2], str((r.spalten, r.zeilen)))
    r = E.wende_schritt(base, {"op": "tabellen_anfuegen", "abfragen": ["B"], "ausrichtung": "name"})
    pruefe("Anfügen: alle Spalten", r.spalten == ["a", "x", "y"], str(r.spalten))
    # Oberfläche
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        sh = doc.getSheets(); sh.insertNewByName("Roh", 1); b = sh.getByName("Roh")
        for r_, z in enumerate([["Name", "Menge"], ["a", 1], ["b", 2]]):
            for c, v in enumerate(z):
                (b.getCellByPosition(c, r_).setString if isinstance(v, str) else b.getCellByPosition(c, r_).setValue)(v)
        ed = AE.Editor(ctx, frame, doc, E.Abfrage("Q1", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "keine"}))
        ed.run(ohne_dialog=True)
        pruefe("Abfrageliste 98 breit", ed.breite_a == 98, str(ed.breite_a))
        ed._breite_aendern("a", 12)
        pruefe("Pfeil breiter", ed.breite_a == 110, str(ed.breite_a))
        ed.d.ctrl("chkAbfr").getModel().State = 0
        ed._listen_sichtbar_geaendert()
        px = ed.d.modell("lstAbfragen").PositionX
        pruefe("Abfragen ausgeblendet (geparkt)", px < -1000 and not ed.abfragen_an, str(px))
        ed.d.ctrl("chkSchr").getModel().State = 0
        ed._listen_sichtbar_geaendert()
        pruefe("Schritte ausgeblendet", ed.d.modell("lstSchritte").PositionX < -1000 and ed.d.modell("btnHinzu").PositionX < -1000)
        ed.d.ctrl("chkAbfr").getModel().State = 1; ed.d.ctrl("chkSchr").getModel().State = 1
        ed._listen_sichtbar_geaendert()
        pruefe("Wieder eingeblendet", ed.d.modell("lstAbfragen").PositionX > -1000 and ed.d.modell("lstSchritte").PositionX > -1000)
        pruefe("Deckfeld rechts vorhanden", ed.d.ctrl("deckRechts") is not None)
    finally:
        try: doc.close(True)
        except Exception: pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
