# -*- coding: utf-8 -*-
"""0.8.4: Schritt-Bedingung im Editor (Menü „Bedingung …“, Anzeige in der Schrittliste, bleibt beim Ändern erhalten)."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def main():
    import faulthandler; faulthandler.dump_traceback_later(150, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx); T.fuelle_auszug(doc)
    AE.speichere_oq_parameter(doc, "p_modus", {"typ": "text", "wert": "voll", "beschreibung": ""})
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOOK"] = "2"; os.environ["ABFRAGE_AUTOCLOSE"] = "28"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:2]) + [{"op": "zeilen_entfernen_oben", "anzahl": 1}]))
    res = {}
    ed.meld = lambda t, *a, **k: res.setdefault("meld", []).append(t)
    def tun():
        time.sleep(3)
        pruefe("Menü enthält „Bedingung …“", ("Bedingung …", "bedingung") in ed.SCHRITT_BEFEHLE)
        ed.lstS.waehle(3); time.sleep(1)
        ed.schritt_befehl("bedingung"); time.sleep(3)
        b = ed.abfrage.schritte[2].get("nur_wenn")
        res["b"] = b
        res["text"] = E.beschreibe(ed.abfrage.schritte[2])
        ed.lstS.waehle(3); time.sleep(1)
        ed.aendern(); time.sleep(4)
        res["nach_aendern"] = ed.abfrage.schritte[2].get("nur_wenn")
        # Quelle (Position 0) hat keine Bedingung
        ed.lstS.waehle(0); time.sleep(0.5)
        n = dict(ed.abfrage.schritte[0]) if ed.abfrage.schritte else {}
        ed.bedingung()
        res["quelle_ok"] = True
        # verwendet
        res["verw"] = AE.parameter_verwendung(doc, "p_modus")
        ed._abfragen_sichern(); time.sleep(0.5)
        res["verw2"] = AE.parameter_verwendung(doc, "p_modus")
    th = threading.Thread(target=tun, daemon=True); th.start(); ed.run(); th.join()
    try: doc.close(True)
    except Exception: pass
    print("RES", res)
    pruefe("Bedingung gesetzt (Parameter p_modus, =)", res.get("b") and res["b"]["parameter"] == "p_modus" and res["b"]["vergleich"] == "=", str(res.get("b")))
    pruefe("Beschreibung der Schrittliste nennt die Bedingung", "nur wenn {p_modus}" in res.get("text", ""), res.get("text", ""))
    pruefe("Bedingung bleibt nach „Ändern“ erhalten", res.get("nach_aendern") == res.get("b"), str(res.get("nach_aendern")))
    pruefe("Parameter-Verwendung findet die Bedingung", "B" in res.get("verw2", []), str(res.get("verw2")))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
