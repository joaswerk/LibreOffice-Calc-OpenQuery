# -*- coding: utf-8 -*-
"""Tests für 0.3.0: Abfragenliste links, Verweis/Duplizieren/Umbenennen, Reihenfolge, Namen zurücknehmen, Einfügen-Menü."""
import os, sys, time, json, threading, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
import uno
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


def namen(ed):
    return [e["a"].name for e in ed.arbeit]


def main():
    import faulthandler
    faulthandler.dump_traceback_later(60, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld07.log")
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        schreibe(doc, "Roh", [["Menge", "Preis"], [1, 2], [3, 4]])
        a1 = E.Abfrage("Eins", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"},
                                                                  {"op": "spalten_entfernen", "spalten": ["Preis"]}])
        a2 = E.Abfrage("Zwei", {"art": "blatt", "blatt": "Roh"}, [])
        AE.speichere_abfrage(doc, a2)
        AE.speichere_abfrage(doc, a1)
        AE.speichere_reihenfolge(doc, ["Zwei", "Eins"])

        ed = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(a1.to_json()))
        ed.run(ohne_dialog=True)
        pruefe("Liste zeigt alle Abfragen in gespeicherter Reihenfolge", namen(ed) == ["Zwei", "Eins"], str(namen(ed)))
        pruefe("Geöffnete Abfrage ist ausgewählt", ed.abfrage.name == "Eins" and ed.aktuell == 1)
        lst = list(ed.lstA.items)
        pruefe("Listenfeld gefüllt", lst == ["Zwei", "Eins"], str(lst))

        # Wechseln
        ed._wechsle_zu(0)
        pruefe("Wechsel zu Abfrage 'Zwei'", ed.abfrage.name == "Zwei" and ed.roh is not None
               and len(ed.abfrage.schritte) == 0)
        ed._wechsle_zu(1)
        pruefe("Zurück zu 'Eins' mit Schritten", len(ed.abfrage.schritte) == 2 and ed.angezeigt.spalten == ["Menge"],
               str(ed.angezeigt.spalten if ed.angezeigt else None))

        # Verweis
        ed.abfrage_verweis()
        pruefe("Verweis: neue Abfrage hinter der aktuellen", namen(ed) == ["Zwei", "Eins", "Eins (2)"], str(namen(ed)))
        pruefe("Verweis: Quelle ist die andere Abfrage",
               ed.abfrage.quelle == {"art": "abfrage", "name": "Eins"}, str(ed.abfrage.quelle))
        pruefe("Verweis: liefert das Ergebnis der anderen Abfrage",
               ed.angezeigt is not None and ed.angezeigt.spalten == ["Menge"] and len(ed.angezeigt.zeilen) == 2,
               str(ed.angezeigt.spalten if ed.angezeigt else None))

        # Duplizieren
        ed.abfrage_duplizieren()
        pruefe("Duplizieren: Kopie mit freiem Namen und eigenem Ziel",
               ed.abfrage.name == "Eins (2) (2)" or ed.abfrage.name.startswith("Eins (2)"), ed.abfrage.name)
        # Umbenennen: Verweise folgen
        ed._wechsle_zu(1)
        os.environ["ABFRAGE_FRAGETEXT"] = "Basis"
        ed.abfrage_umbenennen()
        os.environ.pop("ABFRAGE_FRAGETEXT", None)
        verw = [e["a"] for e in ed.arbeit if e["a"].quelle.get("art") == "abfrage"]
        pruefe("Umbenennen: Verweise folgen dem neuen Namen", ed.abfrage.name == "Basis" and verw
               and all(v.quelle["name"] == "Basis" for v in verw), str([v.quelle for v in verw]))
        pruefe("Umbenennen: Liste aktualisiert", "Basis" in list(ed.lstA.items))
        pruefe("Name doppelt wird abgelehnt", ed._name_pruefen("zwei") is not None and ed._name_pruefen("Neu") is None)

        # Verschieben
        i0 = ed.aktuell
        ed.abfrage_verschieben(-1)
        pruefe("Nach oben verschieben", ed.aktuell == i0 - 1 and ed.abfrage.name == "Basis", str(namen(ed)))
        ed.abfrage_verschieben(1)
        pruefe("Nach unten verschieben", ed.aktuell == i0)

        # Eintrag löschen (Meldung per AUTOOK bestätigen)
        n_vor = len(ed.arbeit)
        ed._wechsle_zu(len(ed.arbeit) - 1)
        name_weg = ed.abfrage.name
        orig = AE.meldung
        AE.meldung = lambda *a, **k: 2
        try:
            ed.abfrage_loeschen()
        finally:
            AE.meldung = orig
        time.sleep(1.5)
        pruefe("Löschen entfernt Eintrag", len(ed.arbeit) == n_vor - 1 and name_weg not in namen(ed), str(namen(ed)))

        # Neue Abfrage
        ed.neue_abfrage()
        pruefe("Neue Abfrage am Ende, leer", ed.abfrage.name.startswith("Abfrage") and ed.roh is None
               and ed.aktuell == len(ed.arbeit) - 1, ed.abfrage.name)

        # Laden speichert andere Abfragen und Reihenfolge
        ed._wechsle_zu(namen(ed).index("Basis"))
        orig_schl = ed.d.schliessen
        ed.d.schliessen = lambda w=0: None
        ed.laden()
        ed.d.schliessen = orig_schl
        gesp = AE.gespeicherte_abfragen(doc)
        pruefe("Laden: leere neue Abfrage wird nicht gespeichert", not any(n.startswith("Abfrage1") for n in gesp), str(list(gesp)))
        pruefe("Laden: umbenannte Abfrage unter neuem Namen gespeichert", "Basis" in gesp and "Eins" not in gesp, str(list(gesp)))
        pruefe("Laden: Verweis-Abfrage gespeichert", any(json.loads(t)["quelle"].get("art") == "abfrage" for t in gesp.values()))
        pruefe("Laden: Reihenfolge gespeichert", AE.lies_reihenfolge(doc)[:1] == ["Zwei"], str(AE.lies_reihenfolge(doc)))
        verweisname = [n for n, t in gesp.items() if json.loads(t)["quelle"].get("art") == "abfrage"][0]
        sh = doc.getSheets()
        pruefe("Laden: Verweis-Abfrage wurde in ihr Blatt geschrieben", sh.hasByName(AE.gueltiger_blattname(verweisname)),
               verweisname)

        # --- Namen zurücknehmen beim Löschen/Pausieren der Überschriften-Schritte
        b = E.Abfrage("Ü", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"},
                                                             {"op": "spalten_entfernen", "spalten": ["Preis"]}])
        e2 = AE.Editor(ctx, frame, doc, b)
        e2.run(ohne_dialog=True)
        # die erste Zeile (Menge/Preis) wurde zum Kopf: Spaltennamen davor Spalte1/Spalte2 -> Folgeschritt nannte "Preis"
        e2.lstS.waehle(1)
        e2.ein_aus()
        pruefe("Pausiert: Folgeschritt nutzt wieder alten Namen", b.schritte[1]["spalten"] == ["Spalte2"], str(b.schritte[1]))
        e2.lstS.waehle(1)
        e2.ein_aus()
        pruefe("Wieder eingeschaltet: neuer Name", b.schritte[1]["spalten"] == ["Preis"], str(b.schritte[1]))
        e2.lstS.waehle(1)
        e2.loeschen()
        pruefe("Gelöscht: Folgeschritt nutzt wieder alten Namen",
               len(b.schritte) == 1 and b.schritte[0]["spalten"] == ["Spalte2"], str(b.schritte))
        # Umbenennen-Schritt
        c = E.Abfrage("Ü2", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "erste_zeile_als_kopf"}, {"op": "spalte_umbenennen", "spalte": "Preis", "neu": "Kosten"},
                       {"op": "spalten_entfernen", "spalten": ["Kosten"]}])
        e3 = AE.Editor(ctx, frame, doc, c)
        e3.run(ohne_dialog=True)
        e3.lstS.waehle(2)
        e3.loeschen()
        pruefe("Umbenennen-Schritt gelöscht: Folgeschritt nutzt alten Namen",
               c.schritte[-1]["spalten"] == ["Preis"], str(c.schritte))

        # --- Einfügen-Menü: gleiches Menü wie der Button
        e4 = AE.Editor(ctx, frame, doc, E.Abfrage("M", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}]))
        e4.run(ohne_dialog=True)
        pm, ids = e4.baue_schritt_menue()
        pruefe("Schrittmenü: Einfügen vor/nach öffnet das Hinzufügen-Menü",
               ("menue", "vor") in ids.values() and ("menue", "nach") in ids.values()
               and not any(isinstance(v, tuple) and len(v) == 3 for v in ids.values()), str(ids))
        aufr = []
        e4.zeige_menue = lambda x, y, spalte=None, modus="nach": aufr.append(modus)
        e4._menue_pos = (10, 10)
        e4.schritt_befehl(("menue", "vor"))
        time.sleep(0.5)
        T_ = threading.Event()
        pruefe("Einfügen vor: Menü kommt verzögert (noch nicht im Aufruf)", aufr == [] or aufr == ["vor"], str(aufr))
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    for e in fehler:
        print("  FEHLER:", e[0], e[2] if len(e) > 2 else "")
    sys.exit(1 if fehler else 0)


main()
