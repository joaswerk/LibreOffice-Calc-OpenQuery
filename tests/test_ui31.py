# -*- coding: utf-8 -*-
"""0.8.2: OpenQuery-Parameter (Name, Typ, Wert, Beschreibung), Zelle gewinnt, Verwendung in Quelle/Filter/Formel, Dialog."""
import os, sys, threading, time, shutil, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe
S = os.environ.get("SCRATCH", "/tmp")

def klick(d, x, y):
    d.screen().root.warp_pointer(x, y); d.sync(); time.sleep(0.3)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.05)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync(); time.sleep(0.2)

def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    import uno
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    P = lambda n, typ, w, b="": AE.speichere_oq_parameter(doc, n, {"typ": typ, "wert": w, "beschreibung": b})
    h = lambda: AE.baue_parameter(doc)
    # Typen
    P("p_text", "text", "C:\\Daten"); P("p_zahl", "zahl", "12,5"); P("p_datum", "datum", "31.01.2026")
    P("p_dz", "datumzeit", "31.01.2026 06:00"); P("p_jn", "janein", "Ja"); P("p_liste", "liste", "Berlin; Potsdam ;Cottbus")
    pruefe("Text", h()("p_text") == "C:\\Daten", repr(h()("p_text")))
    pruefe("Zahl 12,5", h()("p_zahl") == 12.5, repr(h()("p_zahl")))
    pruefe("Datum", h()("p_datum") == dt.date(2026, 1, 31), repr(h()("p_datum")))
    pruefe("Datum mit Uhrzeit", h()("p_dz") == dt.datetime(2026, 1, 31, 6, 0), repr(h()("p_dz")))
    pruefe("Ja/Nein", h()("p_jn") is True, repr(h()("p_jn")))
    pruefe("Liste bereinigt", h()("p_liste") == "Berlin;Potsdam;Cottbus", repr(h()("p_liste")))
    pruefe("Name ohne Groß/Klein", h()("P_ZAHL") == 12.5)
    props = AE.lies_oq_parameter(doc)
    pruefe("Beschreibung gespeichert", (P("p_b", "text", "x", "Mein Ordner"), AE.lies_oq_parameter(doc)["p_b"]["beschreibung"])[1] == "Mein Ordner")
    # Eingabefehler
    for typ, w in (("zahl", "abc"), ("datum", "kein Datum"), ("janein", "vielleicht"), ("text", ""), ("liste", " ; ")):
        try:
            AE.parse_param_wert(typ, w); ok = False
        except ValueError:
            ok = True
        pruefe("Ungültig abgelehnt: %s '%s'" % (typ, w), ok)
    # Namen
    sh = doc.getSheets().getByIndex(0)
    adr = sh.getCellByPosition(0, 0).getCellAddress()
    doc.NamedRanges.addNewByName("Ordner", "$Sheet1.$A$1", adr, 0)
    sh.getCellByPosition(0, 0).setString("ZELLE")
    for n in ("Ordner", "ordner", "", "a{b}", "p_text", "P_TEXT"):
        try:
            AE.pruefe_param_name(doc, n); ok = False
        except ValueError:
            ok = True
        pruefe("Name '%s' abgelehnt" % n, ok)
    pruefe("Neuer Name erlaubt", AE.pruefe_param_name(doc, "p_neu") == "p_neu")
    pruefe("Beim Ändern darf der eigene Name bleiben", AE.pruefe_param_name(doc, "p_text", "p_text") == "p_text")
    # Zelle gewinnt
    P("Ordner", "text", "AUS_OPENQUERY")
    pruefe("Zelle gewinnt gegen OpenQuery-Parameter", h()("Ordner") == "ZELLE", repr(h()("Ordner")))
    sh.getCellByPosition(0, 0).setString("")
    # Parameterliste
    pl = dict(AE.parameter_liste(doc))
    pruefe("Parameterliste zeigt OpenQuery-Parameter", "[OpenQuery]" in pl.get("p_text", ""), str(pl))
    # Benutzung in Quelle, Filter, Formel
    ordner = S + "/pdateien"
    shutil.rmtree(ordner, ignore_errors=True); os.makedirs(ordner)
    for n in ("a.csv", "b.csv", "c.txt"):
        open(ordner + "/" + n, "w").write("x;y\n1;2\n")
    P("p_ordner", "text", ordner); P("p_muster", "text", "*.csv")
    t = AE.lies_quelle(ctx, doc, {"art": "ordner", "pfad": "{p_ordner}", "muster": "*.csv"})
    pruefe("Ordnerquelle mit {p_ordner}", [z[0] for z in t.zeilen] == ["a.csv", "b.csv"], str(t.zeilen))
    P("p_datei", "text", "b.csv")
    t = AE.lies_quelle(ctx, doc, {"art": "datei", "pfad": "{p_ordner}/{p_datei}"})
    pruefe("Dateiquelle mit {p_ordner}/{p_datei}", len(t.zeilen) == 2, str(t.zeilen))
    AE.setze_aufloeser(ctx, doc)
    tab = E.Tabelle(["Standort", "Menge"], [["Berlin", 1], ["Hamburg", 2], ["cottbus", 3]])
    r = E.wende_schritt(tab, {"op": "filtern", "spalte": "Standort", "bedingung": "in_liste", "wert": "{p_liste}"})
    pruefe("Filter mit Liste", [z[0] for z in r.zeilen] == ["Berlin", "cottbus"], str(r.zeilen))
    r = E.wende_schritt(tab, {"op": "benutzerdefinierte_spalte", "neu": "F", "formel": "[Menge] * {p_zahl}"})
    pruefe("Formel mit Zahlparameter", [z[2] for z in r.zeilen] == [12.5, 25.0, 37.5], str(r.zeilen))
    r = E.wende_schritt(tab, {"op": "benutzerdefinierte_spalte", "neu": "D", "formel": "{p_datum}"})
    pruefe("Formel mit Datumsparameter", r.zeilen[0][2] == dt.date(2026, 1, 31), str(r.zeilen[0]))
    try:
        E.wende_schritt(tab, {"op": "filtern", "spalte": "Standort", "bedingung": "gleich", "wert": "{gibtsnicht}"}); ok = False; m = ""
    except Exception as ex:
        ok = "gibtsnicht" in str(ex) and "OpenQuery-Parameter" in str(ex); m = str(ex)
    pruefe("Fehlender Parameter: Meldung nennt beide Möglichkeiten", ok, m)
    # Verwendung / Löschen
    AE.speichere_abfrage(doc, E.Abfrage("Q1", {"art": "ordner", "pfad": "{p_ordner}"}, []))
    pruefe("Verwendung gefunden", AE.parameter_verwendung(doc, "p_ordner") == ["Q1"], str(AE.parameter_verwendung(doc, "p_ordner")))
    AE.loesche_oq_parameter(doc, "p_neu"); AE.loesche_oq_parameter(doc, "p_text")
    pruefe("Gelöscht", "p_text" not in AE.lies_oq_parameter(doc))
    # Dialog Neu/Ändern
    res = {}
    os.environ["ABFRAGE_AUTOCLOSE"] = "40"
    def tun():
        time.sleep(3)
        try:
            from_dlg = AE._LETZTER_PARAM_DLG["d"]
            from_dlg.ctrl("name").getModel().Text = "p_dialog"
            from_dlg.ctrl("wert").getModel().Text = "7,5"
            from_dlg.ctrl("besch").getModel().Text = "per Dialog"
            from_dlg.ctrl("typ").selectItemPos(1, True); time.sleep(0.5)
            res["hinweis"] = from_dlg.ctrl("hinweis").getModel().Label
            os.system("DISPLAY=:99 import -window root %s/s_param.png" % S)
            xd = display.Display(":99")
            ps, bp = from_dlg.dlg.getPosSize(), from_dlg.ctrl("ok").getPosSize()
            klick(xd, ps.X + bp.X + bp.Width // 2, ps.Y + bp.Y + bp.Height // 2)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    n = AE.parameter_bearbeiten(ctx, doc, None); th.join()
    pp = AE.lies_oq_parameter(doc).get("p_dialog")
    pruefe("Dialog Neu: gespeichert als Zahl", n == "p_dialog" and pp and pp["typ"] == "zahl" and pp["wert"] == "7,5" and pp["beschreibung"] == "per Dialog", str((n, pp)))
    pruefe("Dialog: Hinweis passend zum Typ", "Zahl" in res.get("hinweis", ""), res.get("hinweis", ""))
    # Parameterdialog (Liste)
    texte = AE.ParameterDialog(ctx, doc)._zeilen()[1]
    pruefe("Parameterliste im Dialog mit Typ und Wert", any("p_dialog" in t and "Zahl" in t and "7,5" in t and "per Dialog" in t for t in texte), str(texte))
    doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
