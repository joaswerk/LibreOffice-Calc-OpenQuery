# -*- coding: utf-8 -*-
"""0.8.6: Parameter-Vorschlagswerte, Quelle „Liste“, Filter „Werte aus Parameter“, Löschen im Parameterdialog."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe
LOG = "/tmp/oq_meldungen37.log"


def fehler(f):
    try:
        f(); return None
    except (E.FormelFehler, E.StepError, ValueError) as ex:
        return getattr(ex, "meldung", None) or str(ex.args[0] if ex.args else ex)


def im_thread(aktion, wartezeit):
    erg = {}
    def t():
        time.sleep(wartezeit)
        try:
            erg["a"] = aktion()
        except Exception as ex:
            import traceback; traceback.print_exc(); erg["fehler"] = str(ex)
    th = threading.Thread(target=t, daemon=True); th.start()
    return th, erg


def main():
    import faulthandler; faulthandler.dump_traceback_later(250, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = LOG
    if os.path.exists(LOG):
        os.remove(LOG)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    sh = doc.getSheets().getByIndex(0); sh.Name = "Haus"
    doc.getSheets().insertNewByName("Aktive", 1)
    def fuell(blatt, zeilen):
        s = doc.getSheets().getByName(blatt)
        for r, z in enumerate(zeilen):
            for c, v in enumerate(z):
                (s.getCellByPosition(c, r).setString(v) if isinstance(v, str) else s.getCellByPosition(c, r).setValue(v))
    fuell("Haus", [["Nr", "Name"], ["H1", "Alt"], ["H2", "Mitte"], ["H3", "Neu"], ["H4", "Rand"]])
    fuell("Aktive", [["Nummer", "Zahl"], ["H1", 5], ["H3", 7], ["H1", 9], ["", 1]])
    kopf = {"op": "erste_zeile_als_kopf"}
    AE.speichere_abfrage(doc, E.Abfrage("Aktive Häuser", {"art": "blatt", "blatt": "Aktive"}, [kopf]))
    AE.speichere_abfrage(doc, E.Abfrage("Haupt", {"art": "blatt", "blatt": "Haus"}, [kopf]))
    P = lambda n, typ, w, **k: AE.speichere_oq_parameter(doc, n, dict({"typ": typ, "wert": w, "beschreibung": ""}, **k))
    AE.setze_aufloeser(ctx, doc)
    P("p_liste", "liste", "H1;H3")
    P("p_abf", "abfrage_liste", "Aktive Häuser[Nummer]")
    P("p_eins", "text", "H2")
    P("p_leer", "text", " ; ")
    AE.setze_aufloeser(ctx, doc)
    haupt = E.Abfrage.from_json(AE.abfragen_texte(doc)["Haupt"])
    roh = AE.lies_quelle(ctx, doc, haupt.quelle)
    def lauf(*schritte):
        return E.fuehre_aus(roh, haupt.schritte + list(schritte))
    nr = lambda t: [z[0] for z in t.zeilen]

    # --- Filter „Werte aus Parameter“ --------------------------------------------------------------------------
    t = lauf({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_liste", "aktion": "behalten"})
    pruefe("Einzelwerte aus Listenparameter: H1, H3", nr(t) == ["H1", "H3"], str(nr(t)))
    t = lauf({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_liste", "aktion": "entfernen"})
    pruefe("… entfernen: H2, H4 bleiben", nr(t) == ["H2", "H4"], str(nr(t)))
    t = lauf({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_abf"})
    pruefe("Werte aus Parameter „Liste aus Abfrage“", nr(t) == ["H1", "H3"], str(nr(t)))
    t = lauf({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_eins"})
    pruefe("Einzelner Textparameter = ein Wert", nr(t) == ["H2"], str(nr(t)))
    t = lauf({"op": "filtern_werte", "spalte": "Nr", "werte": ["H4"]})
    pruefe("Ankreuzen funktioniert weiter", nr(t) == ["H4"], str(nr(t)))
    t = lauf({"op": "filtern_werte", "spalte": "Nr", "werte": ["H4"], "listenparameter": "p_liste"})
    pruefe("Mit Parameter: angekreuzte Werte werden ignoriert", nr(t) == ["H1", "H3"], str(nr(t)))
    f = fehler(lambda: lauf({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_leer"}))
    pruefe("Leerer Listenparameter -> Meldung", f and "keine Werte" in f, str(f))
    f = fehler(lambda: lauf({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "gibt_es_nicht"}))
    pruefe("Unbekannter Parameter -> Meldung mit Namen", f and "gibt_es_nicht" in f, str(f))
    f = fehler(lambda: lauf({"op": "filtern_werte", "spalte": "Nr"}))
    pruefe("Weder Werte noch Parameter -> Meldung", f and "mindestens einen Wert" in f, str(f))
    bt = E.beschreibe({"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_liste"})
    pruefe("Beschreibung nennt die Liste", "{p_liste}" in bt, bt)

    # --- Quelle „Liste“ -----------------------------------------------------------------------------------------
    q = {"art": "liste", "parameter": "p_liste", "spalte": "Haus"}
    tl = AE.lies_quelle(ctx, doc, q)
    pruefe("Quelle Liste aus Parameter: Spalte und Werte", tl.spalten == ["Haus"] and [z[0] for z in tl.zeilen] == ["H1", "H3"], str((tl.spalten, tl.zeilen)))
    tl = AE.lies_quelle(ctx, doc, {"art": "liste", "parameter": "p_abf"})
    pruefe("Quelle Liste aus Abfrage-Parameter, Spalte „Wert“", tl.spalten == ["Wert"] and len(tl.zeilen) == 2, str((tl.spalten, tl.zeilen)))
    tl = AE.lies_quelle(ctx, doc, {"art": "liste", "werte": "Nord\n Süd \n\nOst", "spalte": "Richtung"})
    pruefe("Quelle Liste aus eingetippten Zeilen (ohne Leerzeilen)", [z[0] for z in tl.zeilen] == ["Nord", "Süd", "Ost"] and tl.spalten == ["Richtung"], str(tl.zeilen))
    f = fehler(lambda: AE.lies_quelle(ctx, doc, {"art": "liste", "werte": "  \n "}))
    pruefe("Leere Liste -> Meldung", f and "leer" in f, str(f))
    pruefe("Quellenbeschreibung", AE.beschreibe_quelle({"art": "liste", "parameter": "p_liste"}) == "Liste aus Parameter {p_liste}"
           and AE.beschreibe_quelle({"art": "liste", "werte": "a\nb"}) == "Liste mit 2 Wert(en)",
           AE.beschreibe_quelle({"art": "liste", "werte": "a\nb"}))
    AE.speichere_abfrage(doc, E.Abfrage("Liste1", {"art": "liste", "parameter": "p_liste", "spalte": "Haus"}, []))
    AE.speichere_abfrage(doc, E.Abfrage("Filter1", {"art": "blatt", "blatt": "Haus"},
                                        [kopf, {"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_eins"}]))
    pruefe("Verwendung: Quelle Liste und Filter gefunden", AE.parameter_verwendung(doc, "p_liste") == ["Liste1"]
           and AE.parameter_verwendung(doc, "p_eins") == ["Filter1"], str((AE.parameter_verwendung(doc, "p_liste"), AE.parameter_verwendung(doc, "p_eins"))))
    # Abfrage mit Quelle Liste als Verbinden-Quelle (zweite Tabelle)
    AE.setze_aufloeser(ctx, doc)
    t = E.hole_tabelle("Liste1")
    pruefe("Abfrage mit Quelle Liste ist als Quelle anderer Abfragen lesbar", [z[0] for z in t.zeilen] == ["H1", "H3"], str(t.zeilen))

    # --- Vorschlagswerte ---------------------------------------------------------------------------------------
    pruefe("Vorschläge feste Liste ohne Doppelte", AE.vorschlag_werte(ctx, doc, {"art": "liste", "wert": "a; b;A ;;c"}) == ["a", "b", "c"],
           str(AE.vorschlag_werte(ctx, doc, {"art": "liste", "wert": "a; b;A ;;c"})))
    pruefe("Vorschläge aus Abfrage", AE.vorschlag_werte(ctx, doc, {"art": "abfrage", "wert": "Aktive Häuser[Nummer]"}) == ["H1", "H3"],
           str(AE.vorschlag_werte(ctx, doc, {"art": "abfrage", "wert": "Aktive Häuser[Nummer]"})))
    f = fehler(lambda: AE.vorschlag_werte(ctx, doc, {"art": "abfrage", "wert": "Nichts[X]"}))
    pruefe("Vorschläge aus unbekannter Abfrage -> Meldung", f and "Nichts" in f, str(f))
    f = fehler(lambda: AE.vorschlag_werte(ctx, doc, {"art": "abfrage", "wert": "Aktive Häuser[Gibtsnicht]"}))
    pruefe("Vorschläge: unbekannte Spalte -> Meldung", f and "Gibtsnicht" in f, str(f))
    P("p_vs", "text", "H1", vorschlag={"art": "abfrage", "wert": "Aktive Häuser[Nummer]"})
    pp = AE.lies_oq_parameter(doc)["p_vs"]
    pruefe("Vorschlag wird gespeichert und gelesen", pp["vorschlag"] == {"art": "abfrage", "wert": "Aktive Häuser[Nummer]"}, str(pp))
    pruefe("Parameter ohne Vorschlag: None", AE.lies_oq_parameter(doc)["p_eins"]["vorschlag"] is None)
    pruefe("Abfrage-Vorschlag zählt als Verwendung der Abfrage", "p_vs" in AE.parameter_aus_abfrage(doc, "Aktive Häuser"),
           str(AE.parameter_aus_abfrage(doc, "Aktive Häuser")))
    AE.parameter_abfrage_umbenennen(doc, "Aktive Häuser", "Aktive Objekte")
    pruefe("Umbenennen der Abfrage zieht den Vorschlag nach", AE.lies_oq_parameter(doc)["p_vs"]["vorschlag"]["wert"] == "Aktive Objekte[Nummer]",
           str(AE.lies_oq_parameter(doc)["p_vs"]))
    AE.parameter_abfrage_umbenennen(doc, "Aktive Objekte", "Aktive Häuser")
    pruefe("… und der Parameter p_abf mit", AE.lies_oq_parameter(doc)["p_abf"]["wert"] == "Aktive Häuser[Nummer]", str(AE.lies_oq_parameter(doc)["p_abf"]))
    AE.loesche_oq_parameter(doc, "p_vs")

    # --- Dialog: Parameter mit Vorschlagsliste ------------------------------------------------------------------
    os.environ["ABFRAGE_AUTOOK"] = "7"
    def dlg1():
        d = AE._LETZTER_PARAM_DLG["d"]
        d.ctrl("name").getModel().Text = "p_stadt"
        d.ctrl("vtext").getModel().Text = "Berlin;Potsdam;Cottbus"
        d.ctrl("vart").selectItemPos(1, True); time.sleep(0.8)
        erg = {"wahl_sichtbar": d.ctrl("wertwahl").getModel().PositionX == 72, "edit_weg": d.ctrl("wert").getModel().PositionX < 0,
               "eintraege": list(d.ctrl("wertwahl").getModel().StringItemList), "hinweis": d.ctrl("vhinweis").getModel().Label}
        d.ctrl("wertwahl").selectItemPos(1, True); time.sleep(0.5)
        erg["text"] = d.ctrl("wert").getText()
        return erg
    th, erg = im_thread(dlg1, 2.5)
    n = AE.parameter_bearbeiten(ctx, doc, None); th.join(10)
    e = erg.get("a", {})
    pp = AE.lies_oq_parameter(doc).get("p_stadt")
    pruefe("Dialog: Wert wird zur Auswahlliste", e.get("wahl_sichtbar") and e.get("edit_weg") and e.get("eintraege") == ["Berlin", "Potsdam", "Cottbus"], str(e))
    pruefe("Dialog: Hinweis zählt Vorschläge", "3 Vorschläge" in e.get("hinweis", ""), e.get("hinweis", ""))
    pruefe("Dialog: gewählter Wert und Vorschlag gespeichert",
           n == "p_stadt" and pp and pp["wert"] == "Potsdam" and pp["vorschlag"] == {"art": "liste", "wert": "Berlin;Potsdam;Cottbus"}, str((n, pp)))

    # bestehender Parameter ändern: Wert nicht in der Liste -> Rückfrage (Test beantwortet mit Ja)
    os.remove(LOG) if os.path.exists(LOG) else None
    P("p_ort", "text", "Dresden")
    os.environ["ABFRAGE_AUTOOK"] = "6"
    def dlg2():
        d = AE._LETZTER_PARAM_DLG["d"]
        d.ctrl("vtext").getModel().Text = "Berlin;Potsdam"
        d.ctrl("vart").selectItemPos(1, True); time.sleep(0.8)
        return d.ctrl("vhinweis").getModel().Label
    th, erg = im_thread(dlg2, 2.5)
    n = AE.parameter_bearbeiten(ctx, doc, None, "p_ort"); th.join(10)
    pp = AE.lies_oq_parameter(doc).get("p_ort")
    log = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
    pruefe("Dialog: bisheriger Wert nicht in der Liste -> Hinweis", "Dresden" in erg.get("a", "") and "steht nicht" in erg.get("a", ""), str(erg))
    pruefe("Dialog: Rückfrage „Trotzdem speichern?“ und gespeichert", "Trotzdem speichern" in log and pp and pp["wert"] == "Dresden" and pp["vorschlag"]["art"] == "liste", log + str(pp))

    # Vorschläge aus Abfrage per Dialog; danach Vorschlag wieder entfernen
    os.environ["ABFRAGE_AUTOOK"] = "7"
    def dlg3():
        d = AE._LETZTER_PARAM_DLG["d"]
        d.ctrl("vtext").getModel().Text = "Aktive Häuser[Nummer]"
        d.ctrl("vart").selectItemPos(2, True); time.sleep(1.0)
        erg = list(d.ctrl("wertwahl").getModel().StringItemList)
        d.ctrl("wertwahl").selectItemPos(1, True); time.sleep(0.4)
        return erg
    th, erg = im_thread(dlg3, 2.5)
    n = AE.parameter_bearbeiten(ctx, doc, None, "p_ort"); th.join(10)
    pp = AE.lies_oq_parameter(doc).get("p_ort")
    pruefe("Dialog: Vorschläge aus Abfrage geladen", erg.get("a") == ["H1", "H3"], str(erg))
    pruefe("Dialog: Wert H3 gewählt, Vorschlag = Abfrage", pp and pp["wert"] == "H3" and pp["vorschlag"] == {"art": "abfrage", "wert": "Aktive Häuser[Nummer]"}, str(pp))
    os.environ["ABFRAGE_AUTOOK"] = "5"
    def dlg4():
        d = AE._LETZTER_PARAM_DLG["d"]
        d.ctrl("vart").selectItemPos(0, True); time.sleep(0.8)
        return d.ctrl("wert").getModel().PositionX == 72, d.ctrl("wert").getText()
    th, erg = im_thread(dlg4, 2.5)
    n = AE.parameter_bearbeiten(ctx, doc, None, "p_ort"); th.join(10)
    pp = AE.lies_oq_parameter(doc).get("p_ort")
    pruefe("Dialog: „keine“ -> wieder freie Eingabe, Vorschlag entfernt", erg.get("a") == (True, "H3") and pp and not pp.get("vorschlag") and pp["wert"] == "H3", str((erg, pp)))

    # Typ ohne Vorschläge (Ja/Nein): Felder gesperrt
    os.environ["ABFRAGE_AUTOOK"] = "5"
    def dlg5():
        d = AE._LETZTER_PARAM_DLG["d"]
        d.ctrl("name").getModel().Text = "p_jn"
        d.ctrl("typ").selectItemPos(4, True); time.sleep(0.6)
        d.ctrl("wert").getModel().Text = "ja"
        return d.ctrl("vart").getModel().Enabled
    th, erg = im_thread(dlg5, 2.5)
    AE.parameter_bearbeiten(ctx, doc, None); th.join(10)
    pruefe("Dialog: bei Ja/Nein sind Vorschläge gesperrt", erg.get("a") is False and AE.lies_oq_parameter(doc)["p_jn"]["wert"] == "ja", str(erg))

    # --- Dialog: Quelle „Liste“ ---------------------------------------------------------------------------------
    arten = [a for a, _ in AE.QuellenDialog.ARTEN]
    pruefe("Quellenart „liste“ vorhanden", "liste" in arten, str(arten))
    os.environ["ABFRAGE_AUTOOK"] = "5"
    qd = AE.QuellenDialog(ctx, doc, None, None)
    def dq1():
        d = qd.d
        d.ctrl("art").selectItemPos(arten.index("liste"), True); time.sleep(0.8)
        sichtbar = d.ctrl("listewerte").getModel().PositionX == 80
        d.ctrl("listewerte").getModel().Text = "Eins\nZwei\n\nDrei"
        d.ctrl("listespalte").getModel().Text = "Zahlwort"
        return sichtbar
    th, erg = im_thread(dq1, 2.5)
    q = qd.zeigen(); th.join(10)
    pruefe("Quellen-Dialog: Liste eintippen", erg.get("a") is True and q == {"art": "liste", "werte": "Eins\nZwei\nDrei", "spalte": "Zahlwort"}, str((erg, q)))
    qd = AE.QuellenDialog(ctx, doc, None, None)
    def dq2():
        d = qd.d
        d.ctrl("art").selectItemPos(arten.index("liste"), True); time.sleep(0.8)
        d.ctrl("listewahl").selectItemPos(1 + AE.parameter_namen(doc).index("p_liste"), True); time.sleep(0.3)
    th, erg = im_thread(dq2, 2.5)
    q = qd.zeigen(); th.join(10)
    pruefe("Quellen-Dialog: Liste aus Parameter", q == {"art": "liste", "parameter": "p_liste", "spalte": "Wert"}, str(q))
    qd = AE.QuellenDialog(ctx, doc, {"art": "liste", "parameter": "p_abf", "spalte": "X"}, None)
    th, erg = im_thread(lambda: None, 1)
    q = qd.zeigen(); th.join(10)
    pruefe("Quellen-Dialog: bestehende Quelle wird vorbelegt", q == {"art": "liste", "parameter": "p_abf", "spalte": "X"}, str(q))
    os.remove(LOG) if os.path.exists(LOG) else None
    qd = AE.QuellenDialog(ctx, doc, {"art": "liste"}, None)
    os.environ["ABFRAGE_AUTOOK"] = "3"; os.environ["ABFRAGE_AUTOCLOSE"] = "6"
    def dq3():
        qd.d.ctrl("art").selectItemPos(arten.index("liste"), True)
    th, erg = im_thread(dq3, 1.5)
    q = qd.zeigen(); th.join(10)
    log = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
    pruefe("Quellen-Dialog: ohne Parameter und Werte -> Hinweis, kein Ergebnis", q is None and "eintippen" in log, log + str(q))
    os.environ.pop("ABFRAGE_AUTOCLOSE", None)

    # --- Dialog: Filter „Werte aus Parameter“ -------------------------------------------------------------------
    tab = E.hole_tabelle("Haupt")
    AE._EDITOR_KONTEXT["doc"] = doc
    os.environ["ABFRAGE_AUTOOK"] = "5"
    dlg = AE.SchrittDialog(ctx, "filtern_werte", tab, None, {"op": "filtern_werte", "spalte": "Nr", "werte": ["H2"]}, None)
    def ds1():
        d = dlg.d
        n0 = list(d.ctrl("f_listenparameter").getModel().StringItemList)
        an0 = d.ctrl("f_werte").getModel().Enabled
        d.ctrl("f_listenparameter").selectItemPos(n0.index("p_liste"), True); time.sleep(0.6)
        return n0[0], "p_liste" in n0, an0, d.ctrl("f_werte").getModel().Enabled, d.ctrl("such").getModel().Enabled
    th, erg = im_thread(ds1, 2.5)
    res = dlg.zeigen(); th.join(10)
    pruefe("Filter-Dialog: Auswahl „Werte aus Parameter“ sperrt das Ankreuzen",
           erg.get("a") == ("(Werte unten ankreuzen)", True, True, False, False), str(erg))
    pruefe("Filter-Dialog: Schritt enthält den Parameter",
           res and res.get("listenparameter") == "p_liste" and res["op"] == "filtern_werte", str(res))
    dlg = AE.SchrittDialog(ctx, "filtern_werte", tab, None, {"op": "filtern_werte", "spalte": "Nr", "werte": ["H2"]}, None)
    res = dlg.zeigen()
    pruefe("Filter-Dialog: ohne Parameter wie bisher (Werte, kein Parameter-Schlüssel)", res and res.get("werte") == ["H2"] and "listenparameter" not in res, str(res))
    dlg = AE.SchrittDialog(ctx, "filtern_werte", tab, None, {"op": "filtern_werte", "spalte": "Nr", "listenparameter": "p_liste"}, None)
    def ds2():
        d = dlg.d
        return d.ctrl("f_listenparameter").getModel().SelectedItems[0], d.ctrl("f_werte").getModel().Enabled
    th, erg = im_thread(ds2, 2.5)
    res = dlg.zeigen(); th.join(10)
    pruefe("Filter-Dialog: gespeicherter Parameter ist vorgewählt, Liste gesperrt", erg.get("a", (0, True))[1] is False and erg["a"][0] > 0, str(erg))
    pruefe("… und bleibt beim OK erhalten", res and res.get("listenparameter") == "p_liste", str(res))

    # --- Parameter löschen im Dialog (Rückfrage Ja/Nein) --------------------------------------------------------
    os.remove(LOG) if os.path.exists(LOG) else None
    P("p_zzz", "text", "x")
    pd = AE.ParameterDialog(ctx, doc, None)
    os.environ["ABFRAGE_AUTOCLOSE"] = "6"
    def dl():
        pd.fuellen("p_zzz")
        pd.loeschen()
        return "p_zzz" in AE.lies_oq_parameter(doc)
    th, erg = im_thread(dl, 2.5)
    pd.zeigen(); th.join(10)
    pruefe("Parameter löschen im Dialog funktioniert (Ja/Nein-Rückfrage)", erg.get("a") is False, str(erg))

    doc.close(True)
    fehl = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehl)))
    return 1 if fehl else 0
sys.exit(main())
