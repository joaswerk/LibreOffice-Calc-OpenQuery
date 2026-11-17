# -*- coding: utf-8 -*-
"""0.8.7: Oberfläche – Kopf mit Trennstrichen, letzte Spalte gestreckt, Parameter in der Abfrageliste, Knöpfe unter den
Listen, Export/Import, Ausgabe-/Laden-in-Knopf, Layout ohne Abschneiden, Parameterverwaltung wie Power Query."""
import os, sys, threading, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe
LOG = "/tmp/oq_meldungen38.log"


def main():
    import faulthandler; faulthandler.dump_traceback_later(260, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = LOG
    if os.path.exists(LOG):
        os.remove(LOG)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "75"
    AE.speichere_oq_parameter(doc, "p_stadt", {"typ": "text", "wert": "Berlin", "beschreibung": "Standort"})
    AE.speichere_oq_parameter(doc, "p_liste", {"typ": "liste", "wert": "H1;H3", "beschreibung": ""})
    AE.speichere_abfrage(doc, E.Abfrage("Eins", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:5])))
    erg = {}

    def tun():
        try:
            time.sleep(4)
            d = ed.d
            # --- Spaltenkopf --------------------------------------------------------------------------------------
            cm = d.ctrl("grid").getModel().ColumnModel
            titel = [c.Title for c in cm.getColumns()]
            pruefe("Kopf: Typ | Name mit Trennstrich", any(t.strip().endswith(" | Objekt") and t.strip().startswith("ABC") for t in titel), str(titel))
            pruefe("Kopf: alter Doppel-Leerzeichen-Stil weg", not any("  " in t for t in titel), str(titel))
            e = ed._titel("X", "123")
            pruefe("Titel ohne Fehler", e.strip().endswith("123 | X"), e)
            ed._fehler = getattr(ed, "_fehler", {})
            # --- Letzte Spalte gestreckt ---------------------------------------------------------------------------
            cols = list(cm.getColumns())
            pruefe("Letzte Spalte hat Flexibilität, die anderen nicht", cols[-1].Flexibility > 0 and all(c.Flexibility == 0 for c in cols[:-1]),
                   str([c.Flexibility for c in cols]))
            # --- Abfrageliste mit Parametern ------------------------------------------------------------------------
            pruefe("Liste enthält Abfragen und dann Parameter {Name}", ed.lstA.items == ["Eins", "B", "{p_liste}", "{p_stadt}"], str(ed.lstA.items))
            pruefe("Parameter-Tipp", "Typ: Text" in ed._abfrage_tipp(3) and "Berlin" in ed._abfrage_tipp(3), ed._abfrage_tipp(3))
            ed.lstA.waehle(3, True); time.sleep(1.2)
            pruefe("Parameter markieren wechselt die Abfrage nicht", ed.aktuell == 1 and ed.abfrage.name == "B", str((ed.aktuell, ed.abfrage.name)))
            # Parameter löschen über Knopfbefehl (Ja/Nein-Rückfrage, im Test automatisch „Ja“)
            ed.abfrage_befehl("loeschen")
            pruefe("Parameter über die Liste gelöscht", "p_stadt" not in AE.lies_oq_parameter(doc) and ed.lstA.items == ["Eins", "B", "{p_liste}"],
                   str((list(AE.lies_oq_parameter(doc)), ed.lstA.items)))
            ed.lstA.waehle(2, True); time.sleep(0.8)
            ed.abfrage_befehl("dupliziere")
            log = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
            pruefe("Duplizieren auf Parameter: Hinweis statt Aktion", "nur für Abfragen" in log and ed.lstA.items == ["Eins", "B", "{p_liste}"], log[-200:])
            # --- Neuer Parameter per Knopf ------------------------------------------------------------------------------
            os.environ["ABFRAGE_AUTOOK"] = "3"
            def f():
                dd = AE._LETZTER_PARAM_DLG["d"]
                dd.ctrl("name").getModel().Text = "p_neu"
                dd.ctrl("wert").getModel().Text = "42"
                dd.ctrl("typ").selectItemPos(1, True)
            th = threading.Thread(target=lambda: (time.sleep(1.2), f()), daemon=True); th.start()
            ed.neuer_parameter(); th.join(5)
            os.environ.pop("ABFRAGE_AUTOOK", None)
            pruefe("Neuer Parameter erscheint in der Liste und ist markiert",
                   "{p_neu}" in ed.lstA.items and ed._param_an(ed.lstA.pos()) == "p_neu", str((ed.lstA.items, ed.lstA.pos())))
            # --- Export / Import --------------------------------------------------------------------------------------------
            ed.lstA.waehle(1, True); time.sleep(0.8)
            pfad = "/tmp/oq_export38.abfrage.json"
            if os.path.exists(pfad):
                os.remove(pfad)
            AE_datei = AE.datei_waehlen
            AE.datei_waehlen = lambda *a, **k: pfad
            ed.abfrage_speichern()
            ok_datei = os.path.exists(pfad) and json.load(open(pfad, encoding="utf-8")).get("name") == "B"
            pruefe("Abfrage in Datei gespeichert", ok_datei, pfad)
            n0 = len(ed.arbeit)
            ed.abfrage_oeffnen()
            AE.datei_waehlen = AE_datei
            pruefe("Abfrage aus Datei als neue Abfrage übernommen (Name eindeutig, bestehende bleibt)",
                   len(ed.arbeit) == n0 + 1 and sorted(e["a"].name for e in ed.arbeit).count("B") == 1
                   and any(e["a"].name.startswith("B (") for e in ed.arbeit), str([e["a"].name for e in ed.arbeit]))
            # --- Ausgabe / Laden in … ------------------------------------------------------------------------------------------
            gerufen = []
            orig_ziel, orig_laden = ed.ziel_waehlen, ed.laden
            ed.ziel_waehlen = lambda: (gerufen.append("ziel"), True)[1]
            ed.laden = lambda *a, **k: gerufen.append("laden")
            ed.laden_in(); time.sleep(1.0)
            ed.ziel_waehlen = lambda: (gerufen.append("ziel2"), False)[1]
            ed.laden_in(); time.sleep(1.0)
            ed.ziel_waehlen, ed.laden = orig_ziel, orig_laden
            pruefe("Laden in …: erst Ausgabe wählen, dann laden; bei Abbruch kein Laden", gerufen == ["ziel", "laden", "ziel2"], str(gerufen))
            names = [t for t, _ in ed.ABFRAGE_BEFEHLE]
            pruefe("Abfragenmenü kennt Ausgabe, Öffnen, Speichern, Neuer Parameter",
                   all(x in names for x in ("Ausgabe …", "Abfrage öffnen …", "Abfrage speichern …", "Neuer Parameter …")), str(names))
            # --- Layout: nichts ragt über das Fenster ---------------------------------------------------------------------------
            for W, H in ((538, 411), (520, 300), (700, 400), (900, 500)):
                ed.layout(W, H); time.sleep(0.3)
                zu_breit = []
                for nm in d.model.getElementNames():
                    m = d.model.getByName(nm)
                    try:
                        if m.PositionX >= 0 and m.PositionX + m.Width > W + 1:
                            zu_breit.append((nm, m.PositionX + m.Width))
                    except Exception:
                        pass
                pruefe("Layout %dx%d: alle sichtbaren Elemente innerhalb der Breite" % (W, H), not zu_breit, str(zu_breit[:5]))
            ed.layout(*ed._fenster_logik(0, 0)); time.sleep(0.3)
            erg["ok"] = True
        except Exception:
            import traceback; traceback.print_exc()
            erg["fehler"] = True
        finally:
            try:
                ed.d.schliessen(0)
            except Exception:
                pass
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(30)

    # --- Parameterverwaltung (PQ-Stil) --------------------------------------------------------------------------------------------
    os.environ["ABFRAGE_AUTOCLOSE"] = "50"
    for n in list(AE.lies_oq_parameter(doc)):
        AE.loesche_oq_parameter(doc, n)
    AE.speichere_oq_parameter(doc, "p_a", {"typ": "text", "wert": "A", "beschreibung": "erster"})
    AE.speichere_oq_parameter(doc, "p_b", {"typ": "zahl", "wert": "7", "beschreibung": ""})
    pd = AE.ParameterDialog(ctx, doc, None, "p_b")
    res = {}

    def pv():
        try:
            time.sleep(2.5)
            d = pd.d
            res["start"] = (d.ctrl("name").getText(), d.ctrl("wert").getText(), list(d.ctrl("lst").getModel().StringItemList))
            d.ctrl("wert").getModel().Text = "9"
            pd.uebernehmen(); time.sleep(0.5)
            res["gespeichert"] = AE.lies_oq_parameter(doc)["p_b"]["wert"]
            pd.neu(); time.sleep(0.5)
            res["neu_leer"] = d.ctrl("name").getText()
            d.ctrl("name").getModel().Text = "p_c"
            d.ctrl("wert").getModel().Text = "C"
            pd.uebernehmen(); time.sleep(0.5)
            res["liste"] = list(d.ctrl("lst").getModel().StringItemList)
            res["markiert"] = pd.aktuell()
            # Auswahl wechseln mit ungespeicherter Änderung: Rückfrage (Test: „Ja“ -> wird gespeichert)
            d.ctrl("wert").getModel().Text = "C2"
            d.ctrl("lst").selectItemPos(0, True); time.sleep(0.8)
            res["c_nach_wechsel"] = AE.lies_oq_parameter(doc)["p_c"]["wert"]
            res["form_a"] = (d.ctrl("name").getText(), d.ctrl("wert").getText())
            pd.loeschen(); time.sleep(0.5)
            res["nach_loeschen"] = sorted(AE.lies_oq_parameter(doc))
        except Exception:
            import traceback; traceback.print_exc()
        finally:
            try:
                pd.d.schliessen(0)
            except Exception:
                pass
    th = threading.Thread(target=pv, daemon=True); th.start()
    pd.zeigen(); th.join(20)
    pruefe("Verwaltung: Liste links, Formular rechts zum gewählten Parameter", res.get("start") == ("p_b", "7", ["p_a", "p_b"]), str(res.get("start")))
    pruefe("Verwaltung: Übernehmen speichert", res.get("gespeichert") == "9", str(res.get("gespeichert")))
    pruefe("Verwaltung: Neu leert das Formular", res.get("neu_leer") == "", str(res.get("neu_leer")))
    pruefe("Verwaltung: neuer Parameter gespeichert und in der Liste markiert", res.get("liste") == ["p_a", "p_b", "p_c"] and res.get("markiert") == "p_c", str(res))
    pruefe("Verwaltung: Wechsel mit Änderung fragt nach und übernimmt", res.get("c_nach_wechsel") == "C2" and res.get("form_a") == ("p_a", "A"), str(res))
    pruefe("Verwaltung: Löschen", res.get("nach_loeschen") == ["p_b", "p_c"], str(res.get("nach_loeschen")))

    # --- Menübefehle -------------------------------------------------------------------------------------------------------------
    pruefe("Calc-Menü: Befehle öffnen/speichern vorhanden", "oeffnen" in AE.BEFEHLE and "speichern" in AE.BEFEHLE, str(list(AE.BEFEHLE)))
    AE.speichere_abfrage(doc, E.Abfrage("Menue1", {"art": "blatt", "blatt": "Auszug"}, [{"op": "erste_zeile_als_kopf"}]))
    pfad = "/tmp/oq_menue38.abfrage.json"
    if os.path.exists(pfad):
        os.remove(pfad)
    o1, o2 = AE.datei_waehlen, AE.waehle_aus_liste
    AE.datei_waehlen = lambda *a, **k: pfad
    AE.waehle_aus_liste = lambda ctx_, titel, text, items, parent=None: items.index("Menue1")
    try:
        AE.befehl_speichern(ctx, frame, doc)
    finally:
        AE.datei_waehlen, AE.waehle_aus_liste = o1, o2
    pruefe("Menü „Abfrage speichern“ schreibt die gewählte Abfrage", os.path.exists(pfad) and json.load(open(pfad, encoding="utf-8"))["name"] == "Menue1", pfad)
    x = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "oxt", "Addons.xcu"), encoding="utf-8").read()
    pruefe("Addons.xcu enthält beide Menüpunkte", "abfrageeditor:oeffnen" in x and "abfrageeditor:speichern" in x)

    doc.close(True)
    fehl = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehl)))
    return 1 if fehl else 0
sys.exit(main())
