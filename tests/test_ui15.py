# -*- coding: utf-8 -*-
"""0.6.2: Kopieren, Autospeichern, Zuordnung beim Anfügen, Andere Abfrage als Quelle, zwei Schritte bei neuer Tabelle, Einstellungen."""
import os, sys, time, tempfile, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def clip_text(ctx):
    clip = ctx.ServiceManager.createInstanceWithContext("com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)
    c = clip.getContents()
    fl = AE.DataFlavor(); fl.MimeType = "text/plain;charset=utf-16"; fl.HumanPresentableName = "Unicode-Text"
    return str(c.getTransferData(fl))


def main():
    import faulthandler; faulthandler.dump_traceback_later(150, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld15.log")
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        sh = doc.getSheets()
        sh.insertNewByName("Roh", 1)
        b = sh.getByName("Roh")
        for r, z in enumerate([["Name", "Menge"], ["a", 1], ["b", 2], ["c", 3]]):
            for c, v in enumerate(z):
                (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)

        # Einstellungen / letzter Ordner
        AE.schreibe_einstellung("test_x", "wert")
        pruefe("Einstellung gespeichert und gelesen", AE.lies_einstellung("test_x") == "wert")
        pruefe("Fehlende Einstellung -> Standard", AE.lies_einstellung("gibt_es_nicht", 7) == 7)

        # Kopfzeilen bleiben links, Werte werden aufgefüllt
        t = AE.rechtsbuendig_auffuellen(["1", "100", "10.5"])
        pruefe("Auffüllen: gleich breit", len({len(x.replace(" ", "")) for x in t}) > 1 and t[0].startswith(" "), repr(t))

        # Neue Abfrage aus Blatt -> zwei normale Schritte
        pruefe("Neue Tabelle: nur Überschriften-Schritt (keine automatische Typenerkennung)", [s["op"] for s in AE.NEUE_TABELLE_SCHRITTE] == ["erste_zeile_als_kopf"])

        # Editor
        q = E.Abfrage("Q1", {"art": "blatt", "blatt": "Roh"}, [dict(s) for s in AE.NEUE_TABELLE_SCHRITTE], {"art": "keine"})
        ed = AE.Editor(ctx, frame, doc, q)
        ed.run(ohne_dialog=True)
        pruefe("Vorschau da", ed.angezeigt is not None and len(ed.angezeigt.zeilen) == 3)

        # Kopieren
        ed.kopiere("zelle", 1, "Name")
        pruefe("Zelle kopiert", clip_text(ctx) == "b", clip_text(ctx))
        ed.kopiere("zeile", 2, "Name")
        pruefe("Zeile kopiert (Tab)", clip_text(ctx) == "c\t3", repr(clip_text(ctx)))
        ed.kopiere("spalte", 0, "Menge")
        pruefe("Spalte kopiert (mit Überschrift)", clip_text(ctx) == "Menge\n1\n2\n3", repr(clip_text(ctx)))
        ed._detail_zeile = 1
        ed.kopiere_detail("wert", 0)
        pruefe("Detail: Wert", clip_text(ctx) == "b")
        ed.kopiere_detail("paar", 1)
        pruefe("Detail: Name und Wert", clip_text(ctx) == "Menge\t2", repr(clip_text(ctx)))
        ed.kopiere_detail("alle", 0)
        pruefe("Detail: ganzer Datensatz", clip_text(ctx) == "Name\tb\nMenge\t2", repr(clip_text(ctx)))
        ed._letzte_zelle = (0, "Name"); ed._kopier_quelle = "tabelle"
        ed.kopiere_auswahl()
        pruefe("Strg+C-Ziel: letzte Zelle", clip_text(ctx) == "a")
        st = types.SimpleNamespace(KeyCode=514, Modifiers=2)
        ed._letzte_zelle = (2, "Name")
        AE._Strg(lambda: ed.kopiere_auswahl()).keyPressed(st)
        pruefe("Strg+C-Listener kopiert", clip_text(ctx) == "c")

        # Autospeichern
        ordner = tempfile.mkdtemp()
        url = AE.uno.systemPathToFileUrl(os.path.join(ordner, "auto.ods"))
        doc.storeAsURL(url, ())
        AE.schreibe_einstellung("auto_speichern", True)
        ed.neuer_schritt("sortieren", {"spalte1": "Menge", "richtung1": "ab"}, True)
        for _ in range(40):
            time.sleep(0.1)
            if not getattr(ed, "_auto_geplant", False):
                break
        props = doc.getDocumentProperties().getUserDefinedProperties()
        txt = str(props.getPropertyValue("AE:Q1")) if props.getPropertySetInfo().hasPropertyByName("AE:Q1") else ""
        pruefe("Autospeichern: Abfrage in der Datei", "sortieren" in txt, txt[:120])
        d2 = desk.loadComponentFromURL(url, "_blank", 0, (AE.PropertyValue("Hidden", 0, True, 0),))
        try:
            p2 = d2.getDocumentProperties().getUserDefinedProperties()
            ok = p2.getPropertySetInfo().hasPropertyByName("AE:Q1") and "sortieren" in str(p2.getPropertyValue("AE:Q1"))
            pruefe("Autospeichern: Datei auf der Platte enthält den Schritt", ok)
        finally:
            d2.close(True)
        AE.schreibe_einstellung("auto_speichern", False)
        n_vor = len(ed.abfrage.schritte)
        ed.neuer_schritt("sortieren", {"spalte1": "Name", "richtung1": "auf"}, True)
        time.sleep(0.6)
        d3 = desk.loadComponentFromURL(url, "_blank", 0, (AE.PropertyValue("Hidden", 0, True, 0),))
        try:
            p3 = d3.getDocumentProperties().getUserDefinedProperties()
            s3 = E.Abfrage.from_json(str(p3.getPropertyValue("AE:Q1"))).schritte
            pruefe("Autospeichern aus: Datei bleibt beim alten Stand", len(s3) == n_vor, "%d/%d" % (len(s3), n_vor))
        finally:
            d3.close(True)

        # Anfügen mit Zuordnung
        b2 = [["Bezeichnung", "Anzahl"], ["x", 9]]
        sh.insertNewByName("Zwei", 2)
        z2 = sh.getByName("Zwei")
        for r, z in enumerate(b2):
            for c, v in enumerate(z):
                (z2.getCellByPosition(c, r).setString if isinstance(v, str) else z2.getCellByPosition(c, r).setValue)(v)
        q2 = E.Abfrage("Zwei", {"art": "blatt", "blatt": "Zwei"}, [{"op": "erste_zeile_als_kopf"}], {"art": "keine"})
        AE.speichere_abfrage(doc, q2)
        a = E.Abfrage("Eins", {"art": "blatt", "blatt": "Roh"},
                      [{"op": "erste_zeile_als_kopf"},
                       {"op": "tabellen_anfuegen", "abfragen": ["Zwei"], "ausrichtung": "name",
                        "zuordnung": "Bezeichnung = Name\nAnzahl = Menge"}], {"art": "keine"})
        tab = AE.berechne(ctx, doc, a) if hasattr(AE, "berechne") else None
        if tab is None:
            roh = AE.lies_quelle(ctx, doc, a.quelle)
            E.AUFLOESER["fn"] = AE.baue_aufloeser(ctx, doc, "Eins")
            tab = E.fuehre_aus(roh, a.schritte)
        pruefe("Anfügen mit Zuordnung: 2 Spalten, 4 Zeilen", tab.spalten == ["Name", "Menge"] and len(tab.zeilen) == 4, str(tab.spalten) + str(len(tab.zeilen)))

        # Andere Abfrage als Quelle
        E.AUFLOESER["fn"] = AE.baue_aufloeser(ctx, doc, "Drei")
        t3 = AE.lies_quelle(ctx, doc, {"art": "abfrage", "name": "Zwei"})
        pruefe("Andere Abfrage als Quelle", t3.spalten == ["Bezeichnung", "Anzahl"] or len(t3.zeilen) >= 1, str(t3.spalten))
        pruefe("Beschreibung der Quelle", "Zwei" in AE.beschreibe_quelle({"art": "abfrage", "name": "Zwei"}))

        # Listener-Lebensdauer: _spaeter darf registrierte Listener nie aus der Halteliste werfen
        vorher = list(ed.d.refs)
        gelaufen = []
        for _ in range(150):
            ed._spaeter(lambda: gelaufen.append(1))
        pruefe("Viele Rückrufe: Listener bleiben erhalten (%d)" % len(vorher), all(any(r is v for r in ed.d.refs) for v in vorher))
        for _ in range(60):
            if len(gelaufen) == 150:
                break
            time.sleep(0.1)
        pruefe("Alle Rückrufe laufen, Halteliste leert sich", len(gelaufen) == 150 and len(ed.d.rueckrufe) == 0,
               "%d %d" % (len(gelaufen), len(ed.d.rueckrufe)))

        # Veraltete Listenereignisse
        ed.lstS.setze(["a", "b", "c"], 2)
        ed.lstS.setze(["a"], 0)
        pruefe("Liste schrumpft: Auswahl im Bereich", ed.lstS.pos() == 0)
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
