# -*- coding: utf-8 -*-
"""End-to-End-Test gegen ein laufendes LibreOffice (socket 2002). Start über run_lo_tests.sh."""
import datetime as dt
import os
import sys
import time
import traceback

import uno
from com.sun.star.beans import PropertyValue

os.environ.setdefault("ABFRAGE_LOESCH_AUTO", "1")          # Tests: Lösch-Dialog antwortet selbst (alles mitlöschen, Blatt behalten)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build", "pkg"))
import abfrage_engine as E  # noqa: E402
import abfrage_editor as AE  # noqa: E402

ergebnisse = []


def pruefe(name, bedingung, detail=""):
    ergebnisse.append((name, bool(bedingung), detail))
    print(("OK    " if bedingung else "FEHLER"), name, ("-> %s" % detail) if (detail and not bedingung) else "")


def verbinden():
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(60):
        try:
            return resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        except Exception:
            time.sleep(1)
    raise RuntimeError("LibreOffice nicht erreichbar")


def neues_calc(ctx):
    desk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    pvh = PropertyValue()
    pvh.Name, pvh.Value = "Hidden", False
    return desk, desk.loadComponentFromURL("private:factory/scalc", "_blank", 0, (pvh,))


def fuelle_auszug(doc):
    sh = doc.getSheets().getByIndex(0)
    sh.Name = "Auszug"
    nf = doc.getNumberFormats()
    loc = doc.CharLocale
    k_dt, k_d, k_t = nf.getStandardFormat(6, loc), nf.getStandardFormat(2, loc), nf.getStandardFormat(4, loc)
    zeilen = [
        ["Liegenschaftsbericht", "", "", "", "", ""],
        ["Stand: 27.10.2026", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ["Objekt", "Gebäude", "Zähler", "Datum", "Verbrauch kWh", "Kosten"],
        ["Schule A", "Haus 1", "Strom", dt.datetime(2026, 10, 1, 8, 30), 1234.5, 356.12],
        ["", "", "Gas", dt.datetime(2026, 10, 2, 9, 0), 980.0, 88.4],
        ["", "", "Wasser", dt.datetime(2026, 10, 3, 10, 15), 12.5, 4.3],
        ["Zwischensumme", "", "", "", 2227.0, 448.82],
        ["", "", "", "", "", ""],
        ["Schule B", "Haus 2", "Strom", dt.datetime(2026, 10, 1, 8, 30), 2000.0, 500.0],
        ["", "", "Gas", dt.datetime(2026, 10, 4, 7, 45), 1500.0, 120.0],
        ["Summe gesamt", "", "", "", 5727.0, 1068.82],
    ]
    for r, z in enumerate(zeilen):
        for c, v in enumerate(z):
            if v == "":
                continue
            zelle = sh.getCellByPosition(c, r)
            if isinstance(v, dt.datetime):
                zelle.setValue(E.datetime_zu_serie(v))
                zelle.NumberFormat = k_dt
            elif isinstance(v, float):
                zelle.setValue(v)
            else:
                zelle.setString(v)
    # Datumszelle nur mit Datum + Zeit-Zelle + Text, der wie eine Zahl aussieht
    sh.getCellByPosition(7, 4).setValue(E.datetime_zu_serie(dt.date(2026, 10, 1)))
    sh.getCellByPosition(7, 4).NumberFormat = k_d
    sh.getCellByPosition(8, 4).setValue(0.5)
    sh.getCellByPosition(8, 4).NumberFormat = k_t
    sh.getCellByPosition(9, 4).setString("007")
    return sh


SCHRITTE = [
    {"op": "zeilen_entfernen_oben", "anzahl": 3},
    {"op": "erste_zeile_als_kopf"},
    {"op": "fuellen_unten", "spalten": ["Objekt", "Gebäude"]},
    {"op": "filtern", "spalte": "Objekt", "bedingung": "beginnt_mit", "wert": "Summe", "aktion": "entfernen"},
    {"op": "filtern", "spalte": "Objekt", "bedingung": "beginnt_mit", "wert": "Zwischensumme", "aktion": "entfernen"},
    {"op": "leere_zeilen_entfernen", "spalten": ["Zähler"]},
    {"op": "typ_aendern", "spalten": ["Verbrauch kWh", "Kosten"], "typ": "dezimal"},
    {"op": "benutzerdefinierte_spalte", "neu": "Kosten je kWh",
     "formel": "RUNDEN([Kosten] / [Verbrauch kWh]; 3)"},
    {"op": "benutzerdefinierte_spalte", "neu": "Ort", "formel": '[Objekt] & " / " & [Gebäude]'},
    {"op": "sortieren", "spalte1": "Objekt", "richtung1": "ab", "spalte2": "Datum", "richtung2": "auf"},
]


def main():
    ctx = verbinden()
    desk, doc = neues_calc(ctx)
    try:
        sh = fuelle_auszug(doc)

        # 1) Quelle: Blatt lesen, Datumsformate erkennen
        name, tab = AE.lese_blatt(doc, "Auszug")
        pruefe("Blatt lesen: 12 Zeilen", len(tab.zeilen) == 12, str(len(tab.zeilen)))
        pruefe("Datum+Zeit erkannt", tab.zeilen[4][3] == dt.datetime(2026, 10, 1, 8, 30), repr(tab.zeilen[4][3]))
        pruefe("Nur-Datum erkannt", tab.zeilen[4][7] == dt.date(2026, 10, 1), repr(tab.zeilen[4][7]))
        pruefe("Zeit erkannt", tab.zeilen[4][8] == dt.time(12, 0), repr(tab.zeilen[4][8]))
        pruefe("Zahl bleibt Zahl", tab.zeilen[4][4] == 1234.5)
        pruefe("Text '007' bleibt Text", tab.zeilen[4][9] == "007", repr(tab.zeilen[4][9]))
        pruefe("Leere Zelle -> None", tab.zeilen[5][0] is None)
        bereich = AE.lese_blatt(doc, "Auszug", "A4:C6")[1]
        pruefe("Bereichsangabe", len(bereich.zeilen) == 3 and len(bereich.spalten) == 3, str(len(bereich.zeilen)))
        try:
            AE.lese_blatt(doc, "GibtsNicht")
            pruefe("Unbekanntes Blatt -> Fehler", False)
        except E.FormelFehler:
            pruefe("Unbekanntes Blatt -> Fehler", True)

        # 2) Editor ohne Dialog-Anzeige: Aufbau, Schritte, Vorschau
        frame = doc.getCurrentController().getFrame()
        a = E.Abfrage("Bericht", {"art": "blatt", "blatt": "Auszug"}, [])
        ed = AE.Editor(ctx, frame, doc, a)
        ed.run(ohne_dialog=True)
        pruefe("Editor baut Dialog + lädt Quelle", ed.roh is not None and len(ed.roh.zeilen) == 12)
        for s in SCHRITTE:
            op = s["op"]
            vor = {k: v for k, v in s.items() if k != "op"}
            ed.neuer_schritt(op, vor, direkt=True)
        pruefe("Alle Schritte angelegt", len(ed.abfrage.schritte) == len(SCHRITTE), str(len(ed.abfrage.schritte)))
        pruefe("Keine Fehlermarkierung", ed.fehler_schritt is None)
        pruefe("Schrittliste hat Quelle + Schritte",
               len(ed.lstS.items) == len(SCHRITTE) + 1)
        pruefe("Vorschau-Raster gefüllt",
               ed.d.ctrl("grid").getModel().GridDataModel.RowCount == 5,
               str(ed.d.ctrl("grid").getModel().GridDataModel.RowCount))
        pruefe("Info-Zeile", "5 Zeilen" in ed.d.ctrl("lblZeilen").getModel().Label,
               ed.d.ctrl("lblInfo").getModel().Label)

        # Schritt mittendrin ansehen
        ed.lstS.waehle(2)
        ed.zeige()
        pruefe("Vorschau bei Schritt 2 (Kopf)", "Schritt 3" in ed.d.ctrl("lblInfo").getModel().Label,
               ed.d.ctrl("lblInfo").getModel().Label)
        ed.lstS.waehle(len(SCHRITTE))
        ed.zeige()

        # Fehlerfall: kaputten Schritt einfügen -> Meldung statt Absturz
        ed.abfrage.schritte.insert(1, {"op": "spalten_entfernen", "spalten": ["GibtsNicht"]})
        ed.zeige()
        pruefe("Fehler im Schritt wird angezeigt", ed.fehler_schritt == 1 and
               "GibtsNicht" in ed.d.ctrl("lblFehler").getModel().Label, ed.d.ctrl("lblFehler").getModel().Label)
        del ed.abfrage.schritte[1]
        ed.fehler_schritt = None
        ed.zeige()

        # 3) Laden ins Blatt
        ed.d.ctrl("txtName").getModel().Text = "Bericht"
        ed.laden()
        pruefe("Zielblatt angelegt", doc.getSheets().hasByName("Bericht"))
        ziel = doc.getSheets().getByName("Bericht")
        kopf = [ziel.getCellByPosition(c, 0).getString() for c in range(12)]
        pruefe("Kopfzeile im Zielblatt", kopf[:6] == ["Objekt", "Gebäude", "Zähler", "Datum", "Verbrauch kWh", "Kosten"]
               and "Kosten je kWh" in kopf and "Ort" in kopf, str(kopf))
        sp_ort, sp_je = kopf.index("Ort"), kopf.index("Kosten je kWh")
        pruefe("Erste Zeile: Schule B (absteigend sortiert)", ziel.getCellByPosition(0, 1).getString() == "Schule B",
               ziel.getCellByPosition(0, 1).getString())
        pruefe("Ort zusammengesetzt", ziel.getCellByPosition(sp_ort, 1).getString() == "Schule B / Haus 2",
               ziel.getCellByPosition(sp_ort, 1).getString())
        zelle = ziel.getCellByPosition(3, 1)
        pruefe("Datum als echter Datumswert", abs(zelle.getValue() - E.datetime_zu_serie(dt.datetime(2026, 10, 1, 8, 30))) < 1e-6,
               str(zelle.getValue()))
        pruefe("Datum als Datum formatiert", "2026" in zelle.getString() or "26" in zelle.getString(), zelle.getString())
        zahl = ziel.getCellByPosition(4, 1)
        pruefe("Zahl als Zahl (nicht Text)", zahl.getType().value == "VALUE" and zahl.getValue() == 2000.0,
               "%s %s" % (zahl.getType().value, zahl.getValue()))
        pruefe("Berechnete Spalte", abs(ziel.getCellByPosition(sp_je, 1).getValue() - 0.25) < 1e-9,
               str(ziel.getCellByPosition(sp_je, 1).getValue()))
        pruefe("Quellblatt unverändert", sh.getCellByPosition(0, 0).getString() == "Liegenschaftsbericht"
               and sh.getCellByPosition(0, 11).getString() == "Summe gesamt")
        gesp = AE.gespeicherte_abfragen(doc)
        pruefe("Abfrage im Dokument gespeichert", "Bericht" in gesp)
        pruefe("Gespeicherte Abfrage lesbar",
               len(E.Abfrage.from_json(gesp["Bericht"]).schritte) == len(SCHRITTE))

        # 4) Aktualisieren: Quelle ändern, neu rechnen
        sh.getCellByPosition(4, 9).setValue(4000.0)       # Schule B Strom 2000 -> 4000
        AE.befehl_aktualisieren.__wrapped__ if False else None
        a2 = E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Bericht"])
        n = AE.aktualisiere_abfrage(ctx, doc, a2)
        pruefe("Aktualisieren: 5 Zeilen", n == 5, str(n))
        pruefe("Aktualisieren: neuer Wert", ziel.getCellByPosition(4, 1).getValue() in (1500.0, 4000.0))
        werte = sorted(ziel.getCellByPosition(4, r).getValue() for r in range(1, 6))
        pruefe("Aktualisieren übernimmt Änderung", 4000.0 in werte and 2000.0 not in werte, str(werte))
        pruefe("Zielblatt hat keine Reste", ziel.getCellByPosition(0, 6).getString() == "")

        # Zielblatt = Quellblatt wird abgelehnt
        a3 = E.Abfrage("Auszug", {"art": "blatt", "blatt": "Auszug"}, [])
        ed3 = AE.Editor(ctx, frame, doc, a3)
        ed3.run(ohne_dialog=True)
        meldungen = []
        ed3.meld = lambda text, art="WARNINGBOX", knoepfe=1: meldungen.append(text) or 1
        ed3.laden()
        pruefe("Zielblatt = Quellblatt wird abgelehnt", meldungen and "Quelle" in meldungen[0],
               str(meldungen))
        pruefe("... und Quellblatt bleibt intakt", sh.getCellByPosition(0, 0).getString() == "Liegenschaftsbericht")

        # 5) Datei-Quellen: CSV (cp1252), XLSX, ODS
        tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "ae_test")
        os.makedirs(tmp, exist_ok=True)
        csvp = os.path.join(tmp, "auszug.csv")
        with open(csvp, "wb") as f:
            f.write(("Titel;;\nObjekt;Menge;Datum\nA;1.234,5;01.10.2026\n;7;02.10.2026\n").encode("cp1252"))
        t = AE.lies_quelle(ctx, doc, {"art": "datei", "pfad": csvp, "trenner": "auto"})
        pruefe("CSV (cp1252, ;) gelesen", len(t.zeilen) == 4 and t.zeilen[2][1] == "1.234,5", str(t.zeilen))
        r = E.fuehre_aus(t, [{"op": "zeilen_entfernen_oben", "anzahl": 1}, {"op": "erste_zeile_als_kopf"},
                             {"op": "fuellen_unten", "spalten": ["Objekt"]},
                             {"op": "typen_erkennen"}])
        pruefe("CSV: Typen erkannt", r.zeilen[0][1] == 1234.5 and r.zeilen[1][2] == dt.date(2026, 10, 2), str(r.zeilen))

        for ext, filt in (("xlsx", "Calc MS Excel 2007 XML"), ("ods", "calc8"), ("xls", "MS Excel 97")):
            p = os.path.join(tmp, "auszug." + ext)
            args = (PropertyValue("FilterName", 0, filt, 0),)
            doc.storeToURL(uno.systemPathToFileUrl(p), args)
            t = AE.lies_quelle(ctx, doc, {"art": "datei", "pfad": p, "blatt": "Auszug"})
            pruefe("Datei %s gelesen (12 Zeilen)" % ext, len(t.zeilen) == 12, str(len(t.zeilen)))
            pruefe("Datei %s: Datum erkannt" % ext, t.zeilen[4][3] == dt.datetime(2026, 10, 1, 8, 30), repr(t.zeilen[4][3]))
        t = AE.lies_quelle(ctx, doc, {"art": "datei", "pfad": os.path.join(tmp, "auszug.xlsx")})
        pruefe("Datei ohne Blattname -> erstes Blatt", len(t.zeilen) >= 12)
        try:
            AE.lies_quelle(ctx, doc, {"art": "datei", "pfad": os.path.join(tmp, "gibtsnicht.csv")})
            pruefe("Fehlende Datei -> Fehler", False)
        except E.FormelFehler:
            pruefe("Fehlende Datei -> Fehler", True)

        # 6) Größere Tabelle: 5000 Zeilen schreiben und zurücklesen
        gross = E.Tabelle(["Nr", "Zeit", "Wert", "Text", "Ja"],
                          [[i, dt.datetime(2026, 1, 1) + dt.timedelta(minutes=i * 7), i * 1.5, "T%d" % (i % 9), i % 2 == 0]
                           for i in range(5000)])
        t0 = time.time()
        AE.schreibe_tabelle(doc, gross, "Gross")
        dauer_schreiben = time.time() - t0
        g = doc.getSheets().getByName("Gross")
        pruefe("5000 Zeilen schreiben (%.1fs)" % dauer_schreiben, dauer_schreiben < 20)
        zurueck = AE.lese_blatt(doc, "Gross")[1]
        pruefe("5000 Zeilen zurücklesen", len(zurueck.zeilen) == 5001, str(len(zurueck.zeilen)))
        pruefe("Zeitwerte stimmen nach Roundtrip", zurueck.zeilen[1 + 4999][1] == gross.zeilen[4999][1],
               "%r vs %r" % (zurueck.zeilen[5000][1], gross.zeilen[4999][1]))
        pruefe("Ja/Nein-Spalte als bool", zurueck.zeilen[1][4] is True and zurueck.zeilen[2][4] is False,
               "%r %r" % (zurueck.zeilen[1][4], zurueck.zeilen[2][4]))
        # Text mit Zahlenlook bleibt Text, "=..." wird nicht zur Formel
        spezial = E.Tabelle(["a", "b"], [["007", "=1+1"], ["1.5", "+3"]])
        AE.schreibe_tabelle(doc, spezial, "Spezial")
        s2 = doc.getSheets().getByName("Spezial")
        pruefe("Text '007' bleibt Text im Blatt", s2.getCellByPosition(0, 1).getType().value == "TEXT"
               and s2.getCellByPosition(0, 1).getString() == "007",
               "%s %r" % (s2.getCellByPosition(0, 1).getType().value, s2.getCellByPosition(0, 1).getString()))
        pruefe("Text '=1+1' bleibt Text (keine Formel)", s2.getCellByPosition(1, 1).getType().value == "TEXT",
               s2.getCellByPosition(1, 1).getType().value)
        # große Abfrage-Property
        grosse = E.Abfrage("Lang", {"art": "blatt"}, [{"op": "filtern", "spalte": "a", "wert": "x" * 300}] * 200)
        AE.speichere_abfrage(doc, grosse)
        pruefe("Große Abfrage (>60 KB) im Dokument speicherbar",
               len(AE.gespeicherte_abfragen(doc).get("Lang", "")) == len(grosse.to_json()))
        # Dokument speichern/laden: Abfragen überleben
        pfad = os.path.join(tmp, "mitabfrage.xlsx")
        doc.storeToURL(uno.systemPathToFileUrl(pfad), (PropertyValue("FilterName", 0, "Calc MS Excel 2007 XML", 0),))
        d2 = desk.loadComponentFromURL(uno.systemPathToFileUrl(pfad), "_blank", 0,
                                       (PropertyValue("Hidden", 0, True, 0),))
        g2 = AE.gespeicherte_abfragen(d2)
        pruefe("Abfragen überleben Speichern als XLSX", "Bericht" in g2, str(list(g2)))
        d2.close(True)
        pfad = os.path.join(tmp, "mitabfrage.ods")
        doc.storeToURL(uno.systemPathToFileUrl(pfad), (PropertyValue("FilterName", 0, "calc8", 0),))
        d3 = desk.loadComponentFromURL(uno.systemPathToFileUrl(pfad), "_blank", 0,
                                       (PropertyValue("Hidden", 0, True, 0),))
        pruefe("Abfragen überleben Speichern als ODS", "Bericht" in AE.gespeicherte_abfragen(d3))
        d3.close(True)
    except Exception:
        traceback.print_exc()
        pruefe("Test ohne unerwartete Ausnahme", False, traceback.format_exc().splitlines()[-1])
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(ergebnisse), len(fehler)))
    for n, _, d in fehler:
        print("  FEHLER:", n, d)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
