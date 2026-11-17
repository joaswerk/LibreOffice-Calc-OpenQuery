# -*- coding: utf-8 -*-
"""0.7.7: Löschen wirkt sofort; Abhängigkeitsprüfung; Schließen+Laden ignoriert Karteileichen."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx); T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "30"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:2])))
    meld = []; res = {}
    ed.meld = lambda t, *a, **k: meld.append(t)
    def tun():
        time.sleep(3)
        orig = AE.meldung
        texte = []
        def m(ctx_, peer, text, art="INFOBOX", knoepfe=1, *a, **k):
            texte.append((art, text)); return 2
        AE.meldung = m
        orig_ld = AE.loesch_dialog
        ld = {"v": {"abh": True, "par": True, "blatt": False}, "args": None}
        AE.loesch_dialog = lambda c, p, name, abh, par, bl, folg=None: (ld.__setitem__("args", (name, list(abh), list(par), list(bl))), ld["v"])[1]
        try:
            # 1) neue Abfrage (Autosave) sofort löschen
            ed.neue_abfrage(); time.sleep(1.5)
            ed.abfrage.quelle.update({"art": "blatt", "blatt": "Auszug"}); ed.abfrage.schritte[:] = []
            ed._abfragen_sichern(); time.sleep(0.5)
            neu = ed.abfrage.name
            res["da"] = neu in AE.gespeicherte_abfragen(doc)
            ed.abfrage_loeschen(); time.sleep(2)
            res["weg"] = neu not in AE.gespeicherte_abfragen(doc)
            # 2) Abhängigkeit
            ed.lstA.waehle(0); time.sleep(1)
            ed.neue_abfrage(); time.sleep(1.5)
            ed.abfrage.quelle.clear(); ed.abfrage.quelle.update({"art": "abfrage", "name": "B"})
            ed._abfragen_sichern(); time.sleep(0.5)
            ib = next(k for k, e in enumerate(ed.arbeit) if e["a"].name == "B")
            ed._wechsle_zu(ib); time.sleep(1.5)
            res["sel"] = ed.abfrage.name
            n0 = len(ed.arbeit); texte.clear()
            ld["v"] = {"abh": False, "par": True, "blatt": False}          # Nutzer lässt die abhängige Abfrage stehen
            ed.abfrage_loeschen(); time.sleep(2)
            res["blockiert"] = (len(ed.arbeit) == n0 and "B" in AE.gespeicherte_abfragen(doc), texte[:1])
            res["angeboten"] = ld["args"]
            ld["v"] = {"abh": True, "par": True, "blatt": False}           # jetzt mit abhängigen Abfragen löschen
            ed.abfrage_loeschen(); time.sleep(2.5)
            res["mit_abh"] = (len(ed.arbeit), "B" in AE.gespeicherte_abfragen(doc), [e["a"].name for e in ed.arbeit])
            # 2b) Abfragen bis zum Ende löschen
            for _ in range(3):
                ed.neue_abfrage(); time.sleep(1.2)
            namen = [e["a"].name for e in ed.arbeit]
            ed._wechsle_zu(len(namen) - 2); time.sleep(1.2)
            ld["v"] = {"abh": True, "par": True, "blatt": False}
            ed.abfragen_bis_ende_loeschen(); time.sleep(2.5)
            res["bis_ende"] = ([e["a"].name for e in ed.arbeit], namen[:-2], ld["args"])
        finally:
            AE.meldung = orig
            AE.loesch_dialog = orig_ld
        # 3) Karteileiche im Dokument, Schließen+Laden
        res["leiche"] = True
        doc.getDocumentProperties().getUserDefinedProperties().addProperty("AE:Geist", 0, E.Abfrage("Geist", {}, []).to_json() if hasattr(E.Abfrage, "to_json") else "{}")
    th = threading.Thread(target=tun, daemon=True); th.start(); ed.run(); th.join()
    try: fehler_l = ed._andere_speichern()
    except Exception as ex: fehler_l = ["EX %s" % ex]
    try: doc.close(True)
    except Exception: pass
    print("RES", res, "FEHLER", fehler_l)
    pruefe("Neue Abfrage sofort aus Dokument entfernt", res.get("da") and res.get("weg"), str(res))
    pruefe("Löschen mit Abhängigen blockiert", res.get("blockiert", (False,))[0] and res["blockiert"][1] and res["blockiert"][1][0][0] == "ERRORBOX", str(res.get("blockiert")))
    pruefe("Löschen bietet die abhängige Abfrage an", bool(res.get("angeboten")) and res["angeboten"][0] == "B" and len(res["angeboten"][1]) == 1, str(res.get("angeboten")))
    pruefe("Löschen mit abhängigen Abfragen entfernt beide", res.get("mit_abh", (9, True))[0] <= 1 and not res.get("mit_abh", (9, True))[1], str(res.get("mit_abh")))
    pruefe("Abfragen bis zum Ende löschen: nur die davor bleiben", bool(res.get("bis_ende")) and res["bis_ende"][0] == res["bis_ende"][1] and len(res["bis_ende"][2][1]) == 0, str(res.get("bis_ende")))
    pruefe("Geist-Eintrag löst keinen Fehler aus", not any("Geist" in f for f in fehler_l), str(fehler_l))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
