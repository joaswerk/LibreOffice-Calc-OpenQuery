# -*- coding: utf-8 -*-
"""0.5.0-c: Rechtsklick-Menü im Tabellenblatt."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

class Obj:
    """Einfacher Ersatz für ActionTrigger / Container (die echten erzeugt LibreOffice nur selbst)."""
    def __init__(self, dienst):
        self.__dict__["_d"] = dienst; self.__dict__["_l"] = []; self.__dict__["_p"] = {}
    def supportsService(self, n): return n == "com.sun.star.ui.ActionTrigger" and self._d == "t"
    def createInstance(self, n): return Obj({"com.sun.star.ui.ActionTrigger": "t"}.get(n, "c"))
    def setPropertyValue(self, k, v): self._p[k] = v
    def __getattr__(self, k): return self._p.get(k)
    def getCount(self): return len(self._l)
    def getByIndex(self, i): return self._l[i]
    def insertByIndex(self, i, o): self._l.insert(i, o)

def eintraege(c):
    out = []
    for i in range(c.getCount()):
        e = c.getByIndex(i)
        if e.supportsService("com.sun.star.ui.ActionTrigger"):
            out.append((e.Text, e.CommandURL, e))
    return out

def main():
    import faulthandler; faulthandler.dump_traceback_later(100, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld12.log")
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        sh = doc.getSheets()
        sh.insertNewByName("Roh", 1)
        b = sh.getByName("Roh")
        for r, z in enumerate([["Name", "Menge"], ["a", 1], ["b", 2]]):
            for c, v in enumerate(z):
                (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)
        a = E.Abfrage("Erste", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}])
        AE.aktualisiere_abfrage(ctx, doc, a)
        AE.speichere_abfrage(doc, a)
        pruefe("Blatt -> Abfrage gefunden", AE.abfrage_fuer_blatt(doc, "Erste") == "Erste", str(AE.gespeicherte_abfragen(doc).keys()))
        pruefe("Fremdes Blatt -> keine Abfrage", AE.abfrage_fuer_blatt(doc, "Roh") is None)
        smgr = ctx.ServiceManager
        m = AE.MenueAbfangen(doc)
        for blatt, erwartet in (("Erste", ["OpenQuery öffnen", "OpenQuery Dieses Blatt als Quelle", "OpenQuery Diesen Bereich als Quelle", "OpenQuery Abfrage aktualisieren", "OpenQuery Neue Spalten übernehmen", "OpenQuery Alle Abfragen aktualisieren"]), ("Roh", ["OpenQuery öffnen", "OpenQuery Dieses Blatt als Quelle", "OpenQuery Diesen Bereich als Quelle", "OpenQuery Alle Abfragen aktualisieren"])):
            doc.getCurrentController().setActiveSheet(sh.getByName(blatt))
            c = Obj("c")
            k = c.createInstance("com.sun.star.ui.ActionTrigger"); k.setPropertyValue("CommandURL", ".uno:Copy"); c.insertByIndex(0, k)
            class Ev: pass
            ev = Ev(); ev.ActionTriggerContainer = c
            r = m.notifyContextMenuExecute(ev)
            es = eintraege(c)
            tx = [e[0] for e in es if e[0] and e[0].startswith("OpenQuery")]
            pruefe("%s: flache Einträge %s" % (blatt, erwartet), tx == erwartet and r == AE._CM_MODIFIED, str([e[0] for e in es]))
        # Fremdes Menü (ohne Copy) bleibt unangetastet
        c = Obj("c")
        ev = Ev(); ev.ActionTriggerContainer = c
        pruefe("Menü ohne Zellbefehle bleibt unberührt", m.notifyContextMenuExecute(ev) == AE._CM_IGNORED and c.getCount() == 0)
        # Befehle
        doc.getCurrentController().setActiveSheet(sh.getByName("Erste"))
        sh.getByName("Erste").getCellByPosition(0, 1).setString("kaputt")
        AE.befehl_hier_aktualisieren(ctx, frame, doc)
        pruefe("Diese Abfrage aktualisieren schreibt das Blatt neu", sh.getByName("Erste").getCellByPosition(0, 1).getString() == "a")
        # Auto-Job registriert den Interceptor
        AE.registriere_menue(doc)
        pruefe("Interceptor am Controller registriert", len([r for r in AE._MENUE_REFS if r[0] == doc.getCurrentController()]) == 1)
        AE.registriere_menue(doc)
        pruefe("Nicht doppelt registriert", len([r for r in AE._MENUE_REFS if r[0] == doc.getCurrentController()]) == 1)
    finally:
        doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
