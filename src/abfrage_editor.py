# -*- coding: utf-8 -*-
"""
OpenQuery für LibreOffice Calc (Power-Query-Stil), Version 0.9.9.
UNO-Komponenten: ProtocolHandler für die Menübefehle, Job für „Aktualisieren beim Öffnen“
und der Editor-Dialog. Die Rechenlogik steckt in abfrage_engine.py (reines Python).
"""
import datetime as dt
import json
import hashlib
import os
import re
import sys
import types
import threading
import time
import traceback

import uno
import unohelper
from com.sun.star.awt.grid import XGridSelectionListener
from com.sun.star.awt import XMouseMotionListener
from com.sun.star.awt import (XCallback, XKeyHandler, XActionListener, XFocusListener, XItemListener, XTextListener, XMouseListener, XWindowListener, XKeyListener,
                              Rectangle, Size)
from com.sun.star.beans import PropertyValue
from com.sun.star.datatransfer import XTransferable, DataFlavor
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo
from com.sun.star.task import XJob
from com.sun.star.ui import XContextMenuInterceptor
from com.sun.star.ui.ContextMenuInterceptorAction import IGNORED as _CM_IGNORED, CONTINUE_MODIFIED as _CM_MODIFIED

try:
    _hier = os.path.dirname(os.path.abspath(__file__))
    if _hier not in sys.path:
        sys.path.insert(0, _hier)
except NameError:
    pass
import abfrage_engine as E  # noqa: E402

TYP_SYMBOL_PX = 46                              # linker Rand des Spaltenkopfs mit dem Typsymbol
TRENNER_PX = 15                                 # Trefferzone um einen Spaltentrenner (4 mm)
NR_BREITE_PX = 34                               # Bereich der Schrittnummer („01.“) am linken Rand der Schrittliste
NATIVE_SPALTEN = sys.platform == "darwin"     # Mac: Spaltenbreite mit dem eingebauten Ziehen des Rasters (wie 0.4.0)


def diag_global(text):
    """Diagnose-Eintrag auch außerhalb des Editors (nur wenn ~/OpenQuery-Diagnose.txt existiert)."""
    try:
        p = os.path.join(os.path.expanduser("~"), "OpenQuery-Diagnose.txt")
        if os.path.exists(p):
            with open(p, "a", encoding="utf-8") as f:
                f.write("%s %s\n" % (time.strftime("%H:%M:%S"), text))
    except Exception:
        pass


_EINSTELLUNGEN = os.path.join(os.path.expanduser("~"), ".openquery-einstellungen.json")
_ALTE_EINSTELLUNGEN = os.path.join(os.path.expanduser("~"), ".supercalc-einstellungen.json")


_EINST_SPEICHER = {}                      # Einstellungen dieser Sitzung (gelten sofort, auch wenn nichts auf die Platte darf)
_EINST_STATUS = {"nein": False}           # Nutzer hat das dauerhafte Speichern in dieser Sitzung abgelehnt
_EINST_KONTEXT = {"ctx": None, "parent": None}


def lies_einstellung(schluessel, standard=None):
    if schluessel in _EINST_SPEICHER:
        return _EINST_SPEICHER[schluessel]
    for pfad in (_EINSTELLUNGEN, _ALTE_EINSTELLUNGEN):
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                d = json.load(f)
            if schluessel in d:
                return d[schluessel]
        except Exception:
            continue
    return standard


def rechtsklick_aktiv():
    """Rechtsklick öffnet die Menüs: Linux/Windows standardmäßig ja (Doppelklick geht weiter), Mac standardmäßig nein
    (dort meldet ein Rechtsklick zwei Ereignisse). Einstellung "rechtsklick" überschreibt das."""
    w = lies_einstellung("rechtsklick", None)
    if w is None:
        return sys.platform != "darwin"
    return bool(w)


def menue_geste(ev):
    """Gehört das Mausereignis zu einer Menügeste? -> "doppel", "rechts" oder None."""
    rechts = bool(getattr(ev, "PopupTrigger", False)) or getattr(ev, "Buttons", 1) == 2
    if rechts:
        return "rechts" if rechtsklick_aktiv() else None
    if getattr(ev, "Buttons", 1) == 1 and getattr(ev, "ClickCount", 1) >= 2:
        return "doppel"
    return None


def einstellungen_datei_erlaubt(fragen=False):
    """Darf die Einstellungsdatei geschrieben werden? Es gibt sie nur, wenn der Nutzer zugestimmt hat: Existiert sie,
    gilt das als Zustimmung. Sonst wird (nur bei einer vom Nutzer selbst geänderten Einstellung, fragen=True) einmal gefragt."""
    if os.path.exists(_EINSTELLUNGEN):
        return True
    if not fragen or _EINST_STATUS["nein"]:
        return False
    ctx = _EINST_KONTEXT.get("ctx")
    if ctx is None:
        return False
    wahl = meldung(ctx, _EINST_KONTEXT.get("parent"),
                   "Soll OpenQuery diese Einstellung dauerhaft speichern, damit sie auch für andere Tabellen gilt?\n\n"
                   "Dazu legt OpenQuery eine kleine Datei an:\n%s\n\n"
                   "Bei „Nein“ gilt die Einstellung nur, bis LibreOffice geschlossen wird." % _EINSTELLUNGEN,
                   "QUERYBOX", 3)
    if wahl != 2:
        _EINST_STATUS["nein"] = True
        return False
    return True


def schreibe_einstellung(schluessel, wert, fragen=False):
    """Merkt die Einstellung für diese Sitzung und schreibt sie nur dann in die Datei im Benutzerordner, wenn der
    Nutzer das erlaubt hat (siehe einstellungen_datei_erlaubt). Es entstehen keine Dateien ohne Nachfrage."""
    _EINST_SPEICHER[schluessel] = wert
    try:
        if not einstellungen_datei_erlaubt(fragen):
            return
        d = {}
        for pfad in (_ALTE_EINSTELLUNGEN, _EINSTELLUNGEN):        # alte Werte übernehmen, neue gewinnen
            try:
                with open(pfad, "r", encoding="utf-8") as f:
                    d.update(json.load(f))
            except Exception:
                pass
        d.update(_EINST_SPEICHER)
        with open(_EINSTELLUNGEN, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


_ABSTURZLOG = os.path.join(os.path.expanduser("~"), "OpenQuery-Absturzprotokoll.txt")
_LOG_OHNE = ("mouseMoved", "mouseDragged", "mouseEntered", "mouseExited", "windowMoved")


def _log_beschneiden():
    """Protokoll beim Start auf die letzten 300 Zeilen kürzen, damit es nicht wächst."""
    try:
        if os.path.getsize(_ABSTURZLOG) > 60000:
            with open(_ABSTURZLOG, "r", encoding="utf-8", errors="replace") as f:
                zeilen = f.readlines()[-300:]
            with open(_ABSTURZLOG, "w", encoding="utf-8") as f:
                f.writelines(zeilen)
    except Exception:
        pass


_log_beschneiden()


_ABSTURZ_AN = [os.path.exists(_ABSTURZLOG) or bool(os.environ.get("OQ_ABSTURZLOG"))]


def absturzlog(text):
    """Nur wenn der Nutzer das Protokoll eingeschaltet hat (Reiter Extras) bzw. die Datei schon existiert: schreibt vor
    jedem Ereignis eine Zeile. Nach einem Absturz zeigt die letzte Zeile, welches Ereignis zuletzt in unseren Code kam
    (~/OpenQuery-Absturzprotokoll.txt). Standardmäßig wird nichts geschrieben und keine Datei angelegt."""
    if not _ABSTURZ_AN[0]:
        return
    try:
        with open(_ABSTURZLOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), text))
    except Exception:
        pass


def _ereignis_text(a):
    try:
        ev = a[0] if a else None
        if ev is None:
            return ""
        teile = []
        for k in ("X", "Y", "Buttons", "PopupTrigger", "ClickCount", "KeyCode", "Width", "Height"):
            if hasattr(ev, k):
                teile.append("%s=%s" % (k, getattr(ev, k)))
        return " ".join(teile)
    except Exception:
        return "?"


def _ohne_durchschlag(f):
    """Listener-Methode so verpacken, dass nie eine Ausnahme in LibreOffice durchschlägt (am Mac beendet eine
    unbehandelte Ausnahme in der Ereignisverarbeitung das ganze Programm). Vor jedem Ereignis (außer reinen
    Mausbewegungen) kommt eine Zeile ins Absturzprotokoll."""
    name = getattr(f, "__name__", "?")

    def w(self, *a, **k):
        if name not in _LOG_OHNE:
            absturzlog("%s.%s %s" % (type(self).__name__, name, _ereignis_text(a)))
        try:
            return f(self, *a, **k)
        except BaseException:
            traceback.print_exc()
            try:
                diag_global("Listener-Fehler in %s: %s" % (getattr(f, "__name__", "?"), traceback.format_exc().strip().splitlines()[-1]))
            except Exception:
                pass
            return None
    w.__name__ = getattr(f, "__name__", "w")
    return w


IMPL_NAME = "org.joaswerk.abfrageeditor.Handler"
JOB_NAME = "org.joaswerk.abfrageeditor.AutoJob"
PROTOKOLL = "org.joaswerk.abfrageeditor:"
TITEL = "OpenQuery"
PROP_PRAEFIX = "AE:"
PROP_ANSICHT = "AEO:ansicht"                  # Breiten der Listen, Gitternetz, Zeilendetails
PROP_REIHENFOLGE = "AEO:reihenfolge"      # Reihenfolge der Abfragen (Liste links), JSON-Liste von Namen
MAX_SPALTEN_VORSCHAU = 150
VORSCHAU_STUFEN = [("500 Zeilen", 500), ("2.000 Zeilen", 2000), ("10.000 Zeilen", 10000),
                   ("bis 100.000 Zeilen", 100000)]
VORSCHAU_STANDARD = 0
MASSEINHEIT_APPFONT = 17      # com.sun.star.util.MeasureUnit.APPFONT (Dialogeinheiten)
TRENNLINIE = 0x9A9A9A                # mittelgraue Trennlinien / Gitternetz
MARKER_GEKLICKT = "► "
MARKER_SCHRITT = "● "
MARKER_RECHTS = " ◄"
MARKER_LEER = "\u2003"       # reservierter Platz ohne Pfeil
MARKER_LEER_R = "\u2003"
SCHRITT_MENUE_RECHTSKLICK = True     # Menü auf der Schritteliste per Rechtsklick (öffnet nach dem Klick-Ereignis; bei Absturz am Mac: False)

FUNKTIONS_KATEGORIEN = [
    ("Zahl", ["ABS(Zahl)", "ISTGERADE(Zahl)", "ISTUNGERADE(Zahl)", "MAX(a; b)", "MIN(a; b)", "MITTELWERT(a; b)",
              "REST(Zahl; Teiler)", "RUNDEN(Zahl; Stellen)", "SUMME(a; b)", "VORZEICHEN(Zahl)"]),
    ("Text", ["FINDEN(Suchtext; Text)", "GLAETTEN(Text)", "GROSS(Text)", "KLEIN(Text)", "LAENGE(Text)",
              "LINKS(Text; Anzahl)", "RECHTS(Text; Anzahl)", "TEIL(Text; Start; Anzahl)", "TEXT(Wert; \"TT.MM.JJJJ\")",
              "VERKETTEN(a; b)", "WECHSELN(Text; Alt; Neu)", "WERT(Text)"]),
    ("Datum", ["DATUM(Jahr; Monat; Tag)", "JAHR(Datum)", "MONAT(Datum)", "TAG(Datum)", "WOCHENTAG(Datum; 2)"]),
    ("Logik", ["ISTLEER(Wert)", "ODER(a; b)", "UND(a; b)", "WENN(Bedingung; Dann; Sonst)", "WENNFEHLER(Wert; Ersatz)"]),
]
KATEGORIE_MARKE = "── "
FUNKTIONSHILFEN = [f for _, fl in FUNKTIONS_KATEGORIEN for f in fl]


def funktionsliste_kategorisiert():
    """Zeilen der Funktionsliste: Kategorieüberschrift („── Zahl ──“, nicht einfügbar), darunter die Funktionen alphabetisch."""
    zeilen = []
    for kat, fl in FUNKTIONS_KATEGORIEN:
        zeilen.append("%s%s ──" % (KATEGORIE_MARKE, kat))
        zeilen.extend(sorted(fl, key=lambda t: t.casefold()))
    return zeilen


# ---------------------------------------------------------------------------
# kleine UNO-Helfer
# ---------------------------------------------------------------------------
def pv(name, wert):
    p = PropertyValue()
    p.Name, p.Value = name, wert
    return p


class _Aktion(unohelper.Base, XActionListener):
    def __init__(self, fn):
        self.fn = fn

    def actionPerformed(self, ev):
        self.fn()

    def disposing(self, ev):
        pass


class _Auswahl(unohelper.Base, XItemListener):
    def __init__(self, fn):
        self.fn = fn

    def itemStateChanged(self, ev):
        self.fn(ev)

    def disposing(self, ev):
        pass


class _Maus(unohelper.Base, XMouseListener):
    def __init__(self, fn_press, beim_loslassen=False):
        self.fn = fn_press
        self.los = beim_loslassen

    def mousePressed(self, ev):
        if not self.los:
            self.fn(ev)

    def mouseReleased(self, ev):
        if self.los:
            self.fn(ev)

    def mouseEntered(self, ev):
        pass

    def mouseExited(self, ev):
        pass

    def disposing(self, ev):
        pass


class _Zeiger(unohelper.Base, XMouseListener):
    """Flache Leistenelemente: Klick (beim Loslassen) und Unterstreichen der Beschriftung beim Darüberfahren."""
    def __init__(self, klick, modell_text):
        self.klick, self.mt = klick, modell_text

    def mousePressed(self, ev):
        pass

    def mouseReleased(self, ev):
        if getattr(ev, "Buttons", 1) == 1 and not bool(ev.PopupTrigger):
            self.klick()

    def mouseEntered(self, ev):
        try:
            self.mt.FontUnderline = 1
        except Exception:
            pass

    def mouseExited(self, ev):
        try:
            self.mt.FontUnderline = 0
        except Exception:
            pass

    def disposing(self, ev):
        pass


class _MausBew(unohelper.Base, XMouseMotionListener):
    def __init__(self, bewegt=None, gezogen=None):
        self.b, self.g = bewegt, gezogen

    def mouseMoved(self, ev):
        if self.b:
            self.b(ev)

    def mouseDragged(self, ev):
        if self.g:
            self.g(ev)

    def disposing(self, ev):
        pass


class _GridAuswahl(unohelper.Base, XGridSelectionListener):
    def __init__(self, fn):
        self.fn = fn

    def selectionChanged(self, ev):
        self.fn(ev)

    def disposing(self, ev):
        pass


class Liste:
    """Einspaltige Liste auf Raster-Basis. Die Auswahl steht hier (auch ohne sichtbaren Dialog); das Raster zeigt sie an.
    Vorteil gegenüber dem Listenfeld: der Eintrag unter dem Mauszeiger ist bekannt (Rechtsklick, Hover-Text)."""

    def __init__(self, dlg, name, bei_wahl, tipp=None):
        self.d, self.name, self.bei_wahl, self.tipp = dlg, name, bei_wahl, tipp
        self.items, self.sel, self._still, self._tipp_zeile = [], -1, False, -2
        self._ignoriere_bis = 0.0
        self.vorab = None
        smgr = dlg.ctx.ServiceManager
        m = dlg.model.getByName(name)
        self.nach = None
        for k, v in (("ShowColumnHeader", False), ("ShowRowHeader", False), ("HScroll", False), ("VScroll", False)):
            try:
                setattr(m, k, v)
            except Exception:
                pass
        try:
            m.SelectionModel = uno.Enum("com.sun.star.view.SelectionType", "SINGLE")
        except Exception:
            pass
        cm = smgr.createInstance("com.sun.star.awt.grid.DefaultGridColumnModel")
        c = cm.createColumn()
        c.Flexibility = 1
        c.ColumnWidth = 100
        cm.addColumn(c)
        m.ColumnModel = cm
        m.GridDataModel = smgr.createInstance("com.sun.star.awt.grid.DefaultGridDataModel")
        ctrl = dlg.ctrl(name)
        l = _GridAuswahl(self._gewaehlt)
        dlg.refs.append(l)
        ctrl.addSelectionListener(l)
        if tipp:
            mb = _MausBew(self._bewegt)
            dlg.refs.append(mb)
            ctrl.addMouseMotionListener(mb)

    def _gewaehlt(self, ev):
        if self._still or time.time() < self._ignoriere_bis:
            return          # (am Mac kommen Auswahlmeldungen verzögert, auch mit Zeilen, die es nicht mehr gibt)
        idx = list(ev.SelectedRowIndexes)
        if idx and idx[0] != self.sel and 0 <= int(idx[0]) < len(self.items):
            self.sel = int(idx[0])
            self.bei_wahl()

    def _bewegt(self, ev):
        z = self.zeile_bei(ev.X, ev.Y)
        if z != self._tipp_zeile:
            self._tipp_zeile = z
            try:
                self.d.model.getByName(self.name).HelpText = self.tipp(z) if 0 <= z < len(self.items) else ""
            except Exception:
                pass

    def zeile_bei(self, x, y):
        try:
            return int(self.d.ctrl(self.name).getRowAtPoint(x, y))
        except Exception:
            return -1

    def setze(self, items, sel=None):
        if self.vorab and len(items) > len(self.items):        # wächst die Liste: erst größer machen, dann befüllen
            try:
                self.vorab(len(items))          # Größe zuerst anpassen, dann befüllen (sonst bleibt ein Rollbalken stehen)
            except Exception:
                pass
        self.items = [str(t) for t in items]
        m = self.d.model.getByName(self.name)
        dm = self.d.ctx.ServiceManager.createInstance("com.sun.star.awt.grid.DefaultGridDataModel")
        if self.items:
            dm.addRows(tuple(str(i) for i in range(len(self.items))), tuple((t,) for t in self.items))
        self._still = True
        try:
            try:
                self.d.ctrl(self.name).deselectAllRows()        # alte Auswahl weg, bevor die Zeilen weniger werden
            except Exception:
                pass
            m.GridDataModel = dm          # neu zugewiesenes Modell wird sofort neu gezeichnet
            self.sel = -1 if sel is None else max(-1, min(int(sel), len(self.items) - 1))
            self._anzeigen()
        finally:
            self._still = False
            self._ignoriere_bis = time.time() + 0.25
        self.auffrischen()
        if self.nach:
            self.nach()

    def auffrischen(self):
        """Raster zum vollständigen Neuzeichnen zwingen (sonst bleibt unter kürzeren Listen Altbestand stehen):
        kurz aus dem Fenster und wieder zurück setzen."""
        try:
            m = self.d.model.getByName(self.name)
            x, y, w, h = m.PositionX, m.PositionY, m.Width, m.Height
            if x < -1000:
                return
            m.PositionX = -3000
            m.PositionX = x
        except Exception:
            pass
        try:
            self.markierung_erneuern()
        except Exception:
            pass

    def markierung_erneuern(self):
        """Die Markierung der gewählten Zeile neu setzen (nach Verschieben/Neuzeichnen des Rasters)."""
        if not (0 <= self.sel < len(self.items)):
            return
        self._still = True
        try:
            self._anzeigen()
        finally:
            self._still = False
            self._ignoriere_bis = time.time() + 0.25

    def waehle(self, i, melden=False):
        self.sel = max(-1, min(int(i), len(self.items) - 1))
        self._still = True
        try:
            self._anzeigen()
        finally:
            self._still = False
            self._ignoriere_bis = time.time() + 0.25
        if melden:
            self.bei_wahl()

    def pos(self):
        return self.sel

    def _anzeigen(self):
        try:
            c = self.d.ctrl(self.name)
            c.deselectAllRows()
            if 0 <= self.sel < len(self.items):
                c.selectRow(self.sel)
                c.goToCell(0, self.sel)
        except Exception:
            pass


class _Fenster(unohelper.Base, XWindowListener):
    def __init__(self, fn_groesse):
        self.fn = fn_groesse

    def windowResized(self, ev):
        self.fn(ev)

    def windowMoved(self, ev):
        pass

    def windowShown(self, ev):
        pass

    def windowHidden(self, ev):
        pass

    def disposing(self, ev):
        pass


def _sicher(fn, ctx_fn=None):
    """Listener-Funktion so verpacken, dass Fehler als Meldung statt als Absturz erscheinen."""
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa
            traceback.print_exc()
            try:
                absturzlog("FEHLER in %s: %s" % (getattr(fn, "__name__", "?"), " | ".join(
                    z.strip() for z in traceback.format_exc().strip().splitlines()[-6:])))
            except Exception:
                pass
            text = str(e).lower()
            if "index" in text and ("invalid" in text or "ungültig" in text or "range" in text):
                return None          # veralteter Zeilen-/Spaltenindex nach einer Änderung: nur ins Protokoll, keine Meldung
            if ctx_fn:
                ctx_fn("Unerwarteter Fehler: %s" % e)
    return wrapper


def toolkit(ctx):
    return ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)


def meldung(ctx, parent, text, art="INFOBOX", knoepfe=1, titel=TITEL):
    """art: INFOBOX/WARNINGBOX/ERRORBOX/QUERYBOX; knoepfe 1=OK, 3=Ja/Nein. Rückgabe 1=OK, 2=Ja, 3=Nein."""
    log = os.environ.get("ABFRAGE_MELDUNGSLOG")
    if log:   # Testbetrieb: Meldung protokollieren statt anzeigen
        with open(log, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (art, text))
        return 2 if knoepfe == 3 else 1
    try:
        return _meldung_dialog(ctx, parent, text, art, knoepfe, titel)       # eigener Dialog: erscheint nahe der Maus
    except Exception:
        traceback.print_exc()
    try:
        mb = toolkit(ctx).createMessageBox(parent, uno.Enum("com.sun.star.awt.MessageBoxType", art),
                                           knoepfe, titel, text)
        return mb.execute()
    except Exception:
        print("MELDUNG:", text)
        return 1


def _meldung_dialog(ctx, parent, text, art, knoepfe, titel):
    """Meldung/Rückfrage als eigener Dialog (die Standard-Meldungsfenster lassen sich nicht platzieren).
    Rückgabe wie bei den Standard-Meldungen: 1 = OK, 2 = Ja, 3 = Nein."""
    breite = 250
    zeilen = 0
    for absatz in str(text).split("\n"):
        zeilen += max(1, -(-len(absatz) // 50))
    th = min(zeilen * 8 + 4, 220)
    d = Dlg(ctx, titel, breite, th + 38)
    d.add("FixedText", "t", 8, 8, breite - 16, th, Label=str(text), MultiLine=True)
    erg = {"v": 0}

    def knopf(name, x, w, wert, label, vorgabe=False):
        d.add("Button", name, x, th + 18, w, 14, Label=label, DefaultButton=vorgabe)
        d.on_click(name, lambda: (erg.__setitem__("v", wert), d.dlg.endExecute()))
    if knoepfe == 3:
        knopf("ja", breite // 2 - 55, 50, 2, "Ja", True)
        knopf("nein", breite // 2 + 5, 50, 3, "Nein")
    else:
        knopf("ok", breite // 2 - 25, 50, 1, "OK", True)
    try:
        d.zeigen(parent)
    finally:
        d.weg()
    if erg["v"]:
        return erg["v"]
    return 3 if knoepfe == 3 else 1          # Fenster per X geschlossen: bei Ja/Nein = Nein


def loesch_dialog(ctx, parent, name, abhaengige, parameter, blaetter, folgende=None):
    """Rückfrage beim Löschen einer Abfrage: abhängige Abfragen, Parameter und Arbeitsblätter mitlöschen?
    -> dict(abh, par, blatt) oder None (abgebrochen). Erscheint mausnah wie alle Dialoge."""
    log = os.environ.get("ABFRAGE_MELDUNGSLOG")
    if log or os.environ.get("ABFRAGE_LOESCH_AUTO"):
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write("[QUERYBOX] Abfrage „%s“ löschen? abh=%s par=%s blatt=%s folgende=%s\n" % (name, abhaengige, parameter, blaetter, folgende))
        return {"abh": True, "par": True, "blatt": False}
    breite = 260
    d = Dlg(ctx, "Abfrage löschen", breite, 100)
    y = 8
    d.add("FixedText", "t", 8, y, breite - 16, 10,
          Label=("Abfrage „%s“ und alle folgenden Abfragen löschen?" % name) if folgende is not None else "Abfrage „%s“ löschen?" % name)
    y += 14
    zeilen = {}

    if folgende:
        d.add("FixedText", "folgT0", 12, y, breite - 24, 10, Label="Folgende Abfragen werden mitgelöscht (%d), Parameter bleiben:" % len(folgende))
        y += 11
        text = ", ".join(folgende)
        n = max(1, -(-len(text) // 52))
        d.add("FixedText", "folgT", 24, y, breite - 36, n * 8 + 1, Label=text, MultiLine=True, TextColor=0x555555)
        y += n * 8 + 6

    def block(chk, label, namen, vorgabe):
        nonlocal y
        d.add("CheckBox", chk, 12, y, breite - 24, 10, Label=label, State=1 if vorgabe else 0)
        y += 11
        text = ", ".join(namen)
        n = max(1, -(-len(text) // 52))
        d.add("FixedText", chk + "T", 24, y, breite - 36, n * 8 + 1, Label=text, MultiLine=True, TextColor=0x555555)
        y += n * 8 + 6
    if abhaengige:
        block("chkAbh", "Abhängige Abfragen mitlöschen (%d):" % len(abhaengige), abhaengige, True)
    if parameter:
        block("chkPar", "Parameter, die ihren Wert daraus holen, mitlöschen:", parameter, True)
    if blaetter:
        block("chkBlatt", "Zugehörige Arbeitsblätter ebenfalls löschen:", blaetter, False)
    else:
        d.add("FixedText", "hinw", 8, y, breite - 16, 10, Label="Ein vorhandenes Ausgabeblatt bleibt erhalten.", TextColor=0x555555)
        y += 14
    d.add("Button", "ok", breite // 2 - 56, y + 2, 52, 14, Label="Löschen", DefaultButton=True)
    d.add("Button", "abbr", breite // 2 + 4, y + 2, 52, 14, Label="Abbrechen")
    d.model.Height = y + 22
    erg = {"v": None}

    def ok():
        def an(n):
            try:
                return bool(d.ctrl(n).getModel().State)
            except Exception:
                return False
        erg["v"] = {"abh": an("chkAbh"), "par": an("chkPar"), "blatt": an("chkBlatt")}
        d.dlg.endExecute()
    d.on_click("ok", ok)
    d.on_click("abbr", lambda: d.dlg.endExecute())
    try:
        d.zeigen(parent)
    finally:
        d.weg()
    return erg["v"]


# ---------------------------------------------------------------------------
# Update-Prüfung (GitHub-Releases)
# ---------------------------------------------------------------------------
VERSION = "0.10.3"
GITHUB_REPO = "joaswerk/LibreOffice-Calc-OpenQuery"


def _version_tupel(t):
    return tuple(int(n) for n in re.findall(r"\d+", t or "")[:4])


def ist_neuere_version(neu, alt):
    a, b = _version_tupel(neu), _version_tupel(alt)
    return bool(a) and a > b


def hole_neueste_version(url=None, timeout=5):
    """Fragt das neueste Release bei GitHub ab. -> dict(version, tag, seite, datei_name, datei_url, text).
    Wirft bei Netzwerk-/Formatfehlern eine Ausnahme (Aufrufer entscheidet, ob still oder mit Meldung)."""
    import urllib.request
    url = url or os.environ.get("ABFRAGE_UPDATE_URL") or "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO
    req = urllib.request.Request(url, headers={"User-Agent": "OpenQuery/" + VERSION,
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    tag = j.get("tag_name") or ""
    oxt = next((a for a in j.get("assets", []) if str(a.get("name", "")).lower().endswith(".oxt")), None)
    return {"version": tag.lstrip("vV"), "tag": tag, "seite": j.get("html_url", ""),
            "datei_name": oxt["name"] if oxt else "", "datei_url": oxt.get("browser_download_url", "") if oxt else "",
            "text": (j.get("body") or "").strip()}


def lade_update_datei(info, timeout=30):
    """Lädt die .oxt in einen eigenen Temp-Ordner und prüft, dass es eine Erweiterung ist. -> Pfad."""
    import tempfile
    import urllib.request
    import zipfile
    ordner = tempfile.mkdtemp(prefix="openquery-update-")
    pfad = os.path.join(ordner, os.path.basename(info["datei_name"]) or "OpenQuery.oxt")
    req = urllib.request.Request(info["datei_url"], headers={"User-Agent": "OpenQuery/" + VERSION})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(pfad, "wb") as f:
        f.write(r.read())
    if not zipfile.is_zipfile(pfad) or "description.xml" not in zipfile.ZipFile(pfad).namelist():
        raise ValueError("Die heruntergeladene Datei ist keine Erweiterung (.oxt).")
    return pfad


def oeffne_erweiterung(ctx, pfad):
    """Öffnet die .oxt: LibreOffice zeigt dann seinen Installationsdialog."""
    url = uno.systemPathToFileUrl(pfad)
    try:
        desk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        desk.loadComponentFromURL(url, "_blank", 0, ())
        return True
    except Exception:
        traceback.print_exc()
    try:
        if sys.platform.startswith("win"):
            os.startfile(pfad)
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", pfad])
        return True
    except Exception:
        traceback.print_exc()
        return False


def update_pruefen(ctx, parent, still=False):
    """still=True (automatisch): nur melden, wenn es etwas Neues gibt; Fehler werden verschluckt.
    still=False (Menü): meldet auch „aktuell“ und Fehler. -> True, wenn ein Update angeboten wurde."""
    try:
        info = hole_neueste_version()
    except Exception as ex:
        if not still:
            meldung(ctx, parent, "Die Update-Prüfung hat nicht geklappt (kein Internet, Proxy oder GitHub nicht erreichbar).\n\n%s" % ex,
                    "WARNINGBOX")
        return False
    try:
        schreibe_einstellung("update_letzte_pruefung", time.time())
    except Exception:
        pass
    if not ist_neuere_version(info["version"], VERSION):
        if not still:
            meldung(ctx, parent, "OpenQuery ist aktuell (installiert: %s, neueste Version bei GitHub: %s)." % (VERSION, info["version"] or "?"))
        return False
    if still and lies_einstellung("update_ignoriert", "") == info["tag"]:
        return False
    text = "Neue Version %s ist verfügbar (installiert: %s)." % (info["version"], VERSION)
    if info["text"]:
        text += "\n\nÄnderungen:\n" + info["text"][:700]
    if not info["datei_url"]:
        text += "\n\nDie Release-Seite öffnen?"
        if meldung(ctx, parent, text, "QUERYBOX", 3) == 2 and info["seite"]:
            import webbrowser
            webbrowser.open(info["seite"])
        return True
    text += "\n\nJetzt herunterladen und installieren?"
    if meldung(ctx, parent, text, "QUERYBOX", 3) != 2:
        if still:
            schreibe_einstellung("update_ignoriert", info["tag"])
        return True
    try:
        pfad = lade_update_datei(info)
    except Exception as ex:
        meldung(ctx, parent, "Der Download hat nicht geklappt.\n\n%s" % ex, "ERRORBOX")
        return True
    if oeffne_erweiterung(ctx, pfad):
        meldung(ctx, parent, "Der Installationsdialog von LibreOffice öffnet sich. Bitte dort bestätigen (die alte Version wird "
                "ersetzt) und danach LibreOffice komplett neu starten.\n\nFalls LibreOffice die Installation ablehnt: unter "
                "Extras > Erweiterungen die alte Version zuerst entfernen und die Datei danach erneut öffnen:\n" + pfad)
    else:
        meldung(ctx, parent, "Die Datei konnte nicht geöffnet werden. Sie liegt hier:\n%s\n\nBitte per Doppelklick installieren." % pfad,
                "WARNINGBOX")
    return True


def update_automatisch_faellig():
    if os.environ.get("ABFRAGE_UPDATE_URL"):
        return True
    if os.environ.get("ABFRAGE_AUTOCLOSE") or not lies_einstellung("update_auto", True):
        return False
    try:
        return time.time() - float(lies_einstellung("update_letzte_pruefung", 0)) > 86400
    except Exception:
        return True


def _ausfuehren(dlg):
    """dlg.execute(); in Tests schließt ABFRAGE_AUTOCLOSE=<sek> den Dialog automatisch."""
    sek = os.environ.get("ABFRAGE_AUTOCLOSE")
    if sek:
        t = threading.Timer(float(sek), lambda: dlg.endExecute())
        t.daemon = True
        t.start()
    return dlg.execute()


_OFFENE_DLGS = []        # Stapel der gerade angezeigten Dialoge (der oberste hat den Fokus)
TASTE_ESCAPE = 1281      # com.sun.star.awt.Key.ESCAPE


class _Rueckruf(unohelper.Base, XCallback):
    """Führt eine Funktion später im Hauptthread aus (nach dem laufenden Ereignis)."""

    def __init__(self, fn, liste=None):
        self.fn = fn
        self.liste = liste          # Halteliste: der Rückruf bleibt dort, bis er gelaufen ist

    def notify(self, daten):
        absturzlog("Rückruf %s" % getattr(self.fn, "__name__", "?"))
        try:
            self.fn()
        except BaseException:
            traceback.print_exc()
        finally:
            try:
                if self.liste is not None and self in self.liste:
                    self.liste.remove(self)
            except Exception:
                pass


class _EscSperre(unohelper.Base, XKeyHandler):
    """Verschluckt Escape, solange der geschützte Dialog der oberste offene ist (Editor: Escape bewirkt nichts)."""

    def __init__(self, dlg):
        self.dlg = dlg

    def keyPressed(self, ev):
        try:
            return ev.KeyCode == TASTE_ESCAPE and bool(_OFFENE_DLGS) and _OFFENE_DLGS[-1] is self.dlg
        except Exception:
            return False

    def keyReleased(self, ev):
        try:
            return ev.KeyCode == TASTE_ESCAPE and bool(_OFFENE_DLGS) and _OFFENE_DLGS[-1] is self.dlg
        except Exception:
            return False

    def disposing(self, ev):
        pass


_KLICK = {"pos": None, "fenster": None}      # letzter Klick im Editor (Bildschirmpixel) / Fensterursprung des Editors
KOPFZEILE_PX = 34                             # grobe Höhe der Fensterleiste (Titel) für die Umrechnung


class _KlickMerker(unohelper.Base, XMouseListener):
    """Merkt sich, wo im Editor zuletzt geklickt wurde, damit Dialoge dort erscheinen können."""

    def __init__(self, dlg):
        self.dlg = dlg

    def mousePressed(self, ev):
        try:
            self.dlg.merke_klick(ev)
        except Exception:
            pass

    def mouseReleased(self, ev):
        pass

    def mouseEntered(self, ev):
        pass

    def mouseExited(self, ev):
        pass

    def disposing(self, src):
        pass


class Dlg:
    """Schlanker Helfer zum Bauen von UNO-Dialogen."""

    def __init__(self, ctx, titel, breite, hoehe, groesse_aenderbar=False):
        self.ctx = ctx
        smgr = ctx.ServiceManager
        self.model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.Width, self.model.Height, self.model.Title = breite, hoehe, titel
        if groesse_aenderbar:
            self.model.Sizeable = True
        self.dlg = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
        self.dlg.setModel(self.model)
        self.refs = []   # Listener am Leben halten (nie kürzen!)
        self.rueckrufe = []   # ausstehende AsyncCallback-Objekte (werden nach dem Lauf entfernt)
        self.esc_sperren = False
        self.alias = {}  # logischer Name -> tatsächlicher Name (z. B. "grid" -> das gerade angezeigte von zwei Rastern)

    EINGABE_HOEHE = 14

    def add(self, art, name, x, y, w, h, **props):
        if art == "Grid":
            m = self.model.createInstance("com.sun.star.awt.grid.UnoControlGridModel")
        else:
            m = self.model.createInstance("com.sun.star.awt.UnoControl%sModel" % art)
        self.model.insertByName(name, m)
        if h < self.EINGABE_HOEHE and not props.get("MultiLine") and (
                art in ("Edit", "ComboBox", "NumericField", "DateField", "TimeField", "CurrencyField", "FormattedField",
                        "PatternField") or (art == "ListBox" and props.get("Dropdown"))):
            h = self.EINGABE_HOEHE          # 12 DU schneiden die Schrift unten ab (Mac): Eingabefelder mindestens 14 hoch
        m.PositionX, m.PositionY, m.Width, m.Height = x, y, w, h
        for k, v in props.items():
            setattr(m, k, v)   # Attributzugriff: pyuno wandelt Sequenzen anhand des Typs richtig um
        return m

    def modell(self, name):
        return self.model.getByName(self.alias.get(name, name))

    def platziere(self, name, x, y, w, h):
        """Setzt Position und Größe, aber nur, was sich wirklich ändert (jede Änderung löst Layout/Neuzeichnen aus).
        -> True, wenn etwas geändert wurde."""
        m = self.model.getByName(self.alias.get(name, name))
        x, y, w, h = int(x), int(y), max(int(w), 1), max(int(h), 1)
        if m.PositionX == x and m.PositionY == y and m.Width == w and m.Height == h:
            return False
        m.PositionX, m.PositionY, m.Width, m.Height = x, y, w, h
        return True

    def neu_platziere(self, name, x, y, w, h):
        """Wie platziere; ändert sich dabei die Größe, wird das Element kurz aus dem Fenster gesetzt, damit es
        vollständig neu gezeichnet wird (sonst bleiben Zeichenreste wie Rollbalken stehen)."""
        m = self.model.getByName(self.alias.get(name, name))
        geaendert = m.Width != max(int(w), 1) or m.Height != max(int(h), 1)
        self.platziere(name, x, y, w, h)
        if geaendert:
            self.auffrischen(name)

    def auffrischen(self, name):
        """Element ausblenden und wieder einblenden: erzwingt das vollständige Neuzeichnen."""
        try:
            c = self.ctrl(name)
            c.setVisible(False)
            c.setVisible(True)
        except Exception:
            pass

    def ctrl(self, name):
        return self.dlg.getControl(self.alias.get(name, name))

    def on_click(self, name, fn, ctx_fn=None):
        l = _Aktion(_sicher(fn, ctx_fn))
        self.refs.append(l)
        self.ctrl(name).addActionListener(l)

    def on_select(self, name, fn, ctx_fn=None):
        l = _Auswahl(_sicher(fn, ctx_fn))
        self.refs.append(l)
        self.ctrl(name).addItemListener(l)

    def _px_groesse(self):
        """Fenstergröße in Pixeln aus der Modellgröße (Dialogeinheiten). getPosSize liefert vor dem Anzeigen teils noch
        Dialogeinheiten – dann sitzt ein Fenster nicht mittig."""
        try:
            sz = self.dlg.getPeer().convertSizeToPixel(Size(int(self.model.Width), int(self.model.Height)), MASSEINHEIT_APPFONT)
            if sz.Width > 20 and sz.Height > 20:
                return sz.Width, sz.Height
        except Exception:
            pass
        ps = self.dlg.getPosSize()
        return ps.Width, ps.Height

    def mittig(self, anteil=None):
        """Fenster in die Bildschirmmitte setzen; mit anteil (z. B. 0.8) zugleich auf diesen Anteil der Arbeitsfläche.
        Nie größer als die Arbeitsfläche (sonst wird das Fenster rechts/unten abgeschnitten)."""
        try:
            wa = toolkit(self.ctx).getWorkArea()
            if anteil:
                w, h = int(wa.Width * anteil), int((wa.Height - 40) * anteil)       # 40 px: Titelleiste/Dock werden mitgezählt; Calc-Fenster bleibt unberücksichtigt
            else:
                w, h = self._px_groesse()
            w, h = min(w, wa.Width), min(h, wa.Height)
            x, y = wa.X + (wa.Width - w) // 2, wa.Y + (wa.Height - h) // 2
            if getattr(self, "_merker", None) is not None:
                _KLICK["fenster"] = (x, y)
            elif not anteil and self.am_klick(w, h):
                return
            self.dlg.setPosSize(x, y, w, h, 15)
            diag_global("Fenster %s: Arbeitsfläche %d,%d %dx%d -> Fenster %d,%d %dx%d (Modell %dx%d DE)" % (
                self.model.Title[:30], wa.X, wa.Y, wa.Width, wa.Height, x, y, w, h, self.model.Width, self.model.Height))
            if anteil and getattr(self, "bei_groesse", None):
                self.bei_groesse(w, h)         # Größenänderung kommt nicht überall als Ereignis: Layout selbst anstoßen
        except Exception:
            traceback.print_exc()

    # Dunkelmodus: eigene warme mittelgraue Farben (die Systemfarben ergeben schwarze Eingabefelder und weiße Listen)
    DUNKEL_FELD, DUNKEL_BAND, DUNKEL_TEXT, DUNKEL_KOPF = 0x58544F, 0x625E58, 0xF0ECE6, 0x47443F
    _FELD_ARTEN = ("Edit", "ComboBox", "ListBox", "NumericField", "DateField", "TimeField", "CurrencyField",
                   "FormattedField", "PatternField")

    def ist_dunkel(self):
        """Hat dieses Fenster einen dunklen Hintergrund? (nur nach createPeer; OQ_DUNKEL=1 erzwingt es für Tests)"""
        if os.environ.get("OQ_DUNKEL"):
            return True
        try:
            bg = int(self.dlg.getPeer().getProperty("BackgroundColor"))
            return ((bg >> 16) & 255) * 0.3 + ((bg >> 8) & 255) * 0.59 + (bg & 255) * 0.11 < 110
        except Exception:
            return False

    def faerbe_dunkel(self):
        """Eingabefelder, Listen und Raster in warmem mittlerem Grau mit heller Schrift; Symbole im Kopf flach."""
        try:
            bg = int(self.dlg.getPeer().getProperty("BackgroundColor"))
        except Exception:
            bg = 0x3A3835
        for n in self.model.getElementNames():
            try:
                m = self.model.getByName(n)
                dienst = m.getServiceName()
                art = dienst.rsplit(".", 1)[-1]                    # "stardiv.vcl.controlmodel.Edit" / "…UnoControlGridModel"
                if art.startswith("UnoControl"):
                    art = art[len("UnoControl"):]
                if art.endswith("Model"):
                    art = art[:-5]
                if art in self._FELD_ARTEN:
                    m.BackgroundColor = self.DUNKEL_FELD
                    m.TextColor = self.DUNKEL_TEXT
                elif art == "ImageControl" and n.startswith(("tbi_", "btnUndoK", "btnRedoK")):
                    m.BackgroundColor = bg                       # flach: kein weißer Kasten hinter dem Symbol
                    m.Border = 0
                elif "grid" in dienst.lower():
                    m.BackgroundColor = self.DUNKEL_FELD
                    m.TextColor = self.DUNKEL_TEXT
                    m.RowBackgroundColors = (self.DUNKEL_FELD,)
                    m.HeaderBackgroundColor = self.DUNKEL_KOPF
                    m.HeaderTextColor = self.DUNKEL_TEXT
                    m.ActiveSelectionBackgroundColor = 0x3B6EA5
                    m.ActiveSelectionTextColor = 0xFFFFFF
                    m.InactiveSelectionBackgroundColor = 0x6B6760
                    m.InactiveSelectionTextColor = self.DUNKEL_TEXT
            except Exception:
                pass

    HELL_HINTERGRUND, RAHMEN_FARBE = 0xF4F4F4, 0x8A847C       # helles Grau (Variante B); kräftigere Rahmen um alle Felder
    warm = True                                              # Hintergrund einfärben (der Editor bleibt flach/systemfarben)

    def faerbe_hell(self):
        """Helles Aussehen: warmgrauer Dialoghintergrund, weiße Eingabe-/Auswahlfelder mit dunklerem Rahmen."""
        if self.warm:
            try:
                self.model.BackgroundColor = self.HELL_HINTERGRUND
            except Exception:
                pass
        for n in self.model.getElementNames():
            try:
                m = self.model.getByName(n)
                dienst = m.getServiceName()
                art = dienst.rsplit(".", 1)[-1]
                if art.startswith("UnoControl"):
                    art = art[len("UnoControl"):]
                if art.endswith("Model"):
                    art = art[:-5]
                if art in self._FELD_ARTEN or "grid" in dienst.lower():
                    if self.warm and art in self._FELD_ARTEN:
                        m.BackgroundColor = 0xFFFFFF
                    if getattr(m, "Border", 2) != 0 or art in ("Edit", "ListBox", "ComboBox"):
                        m.Border = 2
                        m.BorderColor = self.RAHMEN_FARBE
            except Exception:
                pass

    def zeigen(self, parent=None, anteil=None):
        tk = toolkit(self.ctx)
        self.dlg.createPeer(tk, parent)
        self.dunkel = self.ist_dunkel()
        if self.dunkel:
            self.faerbe_dunkel()
        else:
            self.faerbe_hell()
        if getattr(self, "nach_farbe", None):
            try:
                self.nach_farbe(self.dunkel)
            except Exception:
                traceback.print_exc()
        if getattr(self, "nach_peer", None):
            try:
                self.nach_peer()
            except Exception:
                traceback.print_exc()
        self.mittig(anteil)
        sperre = None
        if self.esc_sperren:
            try:
                sperre = _EscSperre(self)
                tk.addKeyHandler(sperre)
            except Exception:
                traceback.print_exc()
                sperre = None
        if not anteil:
            self._nach_oeffnen_pruefen()       # erst wenn das Fenster offen ist: ragt es über den Bildschirm, zurückschieben
        _OFFENE_DLGS.append(self)
        try:
            return _ausfuehren(self.dlg)
        finally:
            if self in _OFFENE_DLGS:
                _OFFENE_DLGS.remove(self)
            if sperre is not None:
                try:
                    tk.removeKeyHandler(sperre)
                except Exception:
                    pass

    def schliessen(self, wert=0):
        self.dlg.endExecute()
        self._ergebnis = wert

    def peer(self):
        return self.dlg.getPeer()

    def klick_verfolgen(self):
        """Nur für das Hauptfenster: Klicks auf jedes Element merken (siehe am_klick)."""
        self._merker = _KlickMerker(self)
        for n in self.model.getElementNames():
            try:
                self.dlg.getControl(n).addMouseListener(self._merker)
            except Exception:
                pass

    def klick_beenden(self):
        _KLICK["pos"] = _KLICK["fenster"] = None
        self._merker = None

    def merke_klick(self, ev):
        fx = _KLICK.get("fenster")
        if fx is None:
            return
        p = ev.Source.getPosSize()
        if p.X < -500:
            return
        _KLICK["pos"] = (fx[0] + p.X + ev.X, fx[1] + KOPFZEILE_PX + p.Y + ev.Y)

    def am_klick(self, w, h):
        """Fenster mit linker oberer Ecke nahe dem letzten Klick, aber vollständig auf dem Bildschirm."""
        pos = _KLICK.get("pos")
        if not pos:
            return False
        wa = toolkit(self.ctx).getWorkArea()
        w, h = min(w, wa.Width), min(h, wa.Height)
        x = max(wa.X, min(pos[0] - 30, wa.X + wa.Width - w))
        y = max(wa.Y, min(pos[1] - 20, wa.Y + wa.Height - h))
        self.dlg.setPosSize(int(x), int(y), int(w), int(h), 15)
        self.letzte_pos = (int(x), int(y), int(w), int(h))
        return True

    def _nach_oeffnen_pruefen(self):
        try:
            svc = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", self.ctx)
            cb = _Rueckruf(self._auf_schirm, self.rueckrufe)
            cb.dienst = svc
            self.rueckrufe.append(cb)
            svc.addCallback(cb, None)
        except Exception:
            pass

    def _auf_schirm(self):
        """Letzte Sicherung: nach dem Setzen die tatsächliche Fensterlage prüfen und ganz auf die Arbeitsfläche
        schieben (auch wenn die berechnete Größe vom echten Fenster abweicht, z. B. durch Rahmen oder Skalierung)."""
        try:
            wa = toolkit(self.ctx).getWorkArea()
            ps = self.dlg.getPosSize()
            if ps.Width < 20 or ps.Height < 20:
                return
            x = max(wa.X, min(ps.X, wa.X + wa.Width - ps.Width))        # nur bei echtem Überhang verschieben
            y = max(wa.Y, min(ps.Y, wa.Y + wa.Height - ps.Height))
            if (x, y) != (ps.X, ps.Y):
                self.dlg.setPosSize(int(x), int(y), 0, 0, 3)
                self.letzte_pos = (int(x), int(y), int(ps.Width), int(ps.Height))
        except Exception:
            pass

    def weg(self):
        try:
            self.dlg.dispose()
        except Exception:
            pass


def sel_pos(ctrl):
    """Gewählter Listeneintrag (-1 = keiner); liest das Modell, das auch ohne sichtbaren Dialog stimmt."""
    try:
        sel = ctrl.getModel().SelectedItems
        return int(sel[0]) if len(sel) else -1
    except Exception:
        return ctrl.getSelectedItemPos()


def sel_multi(ctrl):
    try:
        return [int(i) for i in ctrl.getModel().SelectedItems]
    except Exception:
        return list(ctrl.getSelectedItemsPos())


def setze_liste(model, items, auswahl=None):
    model.StringItemList = tuple(items)
    if auswahl is not None:
        model.SelectedItems = uno.Any("[]short", tuple(auswahl))


# ---------------------------------------------------------------------------
# Quellen lesen
# ---------------------------------------------------------------------------
def _zelle_int(v):
    return int(v) if isinstance(v, float) and v.is_integer() and abs(v) < 1e15 else v


def _serie_zu_zeit(x):
    sek = int(round((x % 1) * 86400)) % 86400
    return dt.time(sek // 3600, (sek // 60) % 60, sek % 60)


def tabelle_aus_bereich(doc, rng):
    """Zellbereich -> Tabelle (Spalte1..N). Datum/Zeit/Ja-Nein werden anhand der Zellformate erkannt,
    Fehlerzellen (#DIV/0! usw.) als Fehlerwerte übernommen."""
    daten = [list(r) for r in rng.getDataArray()]
    ra = rng.getRangeAddress()
    r0, c0 = ra.StartRow, ra.StartColumn
    nf = doc.getNumberFormats()
    try:
        uniq = rng.getUniqueCellFormatRanges()
        for i in range(uniq.getCount()):
            grp = uniq.getByIndex(i)
            for j in range(grp.getCount()):
                r = grp.getByIndex(j)
                try:
                    typ = nf.getByKey(r.NumberFormat).Type
                except Exception:
                    continue
                if typ & 1024:
                    art = "bool"
                elif (typ & 2) and (typ & 4):
                    art = "datumzeit"
                elif typ & 2:
                    art = "datum"
                elif typ & 4:
                    art = "zeit"
                elif typ & 128:
                    art = "prozent"
                elif typ & 8:
                    art = "waehrung"
                else:
                    continue
                a = r.getRangeAddress()
                for zr in range(a.StartRow - r0, a.EndRow - r0 + 1):
                    if zr < 0 or zr >= len(daten):
                        continue
                    zeile = daten[zr]
                    for sc in range(a.StartColumn - c0, a.EndColumn - c0 + 1):
                        if sc < 0 or sc >= len(zeile):
                            continue
                        v = zeile[sc]
                        if isinstance(v, str):
                            continue
                        if art == "bool":
                            zeile[sc] = bool(v)
                        elif art == "prozent":
                            zeile[sc] = E.Prozent(v)
                        elif art == "waehrung":
                            zeile[sc] = E.Waehrung(v)
                        elif art == "zeit":
                            zeile[sc] = _serie_zu_zeit(v)
                        else:
                            d = E.seriennummer_zu_datetime(v)
                            if art == "datum" and v == int(v):
                                zeile[sc] = d.date()
                            else:   # auf ganze Sekunden runden (Gleitkomma-Rauschen)
                                zeile[sc] = (d + dt.timedelta(milliseconds=500)).replace(microsecond=0)
    except Exception:
        traceback.print_exc()
    for z in daten:
        for k, v in enumerate(z):
            if isinstance(v, str):
                if v == "":
                    z[k] = None
            elif isinstance(v, float) and not isinstance(v, (E.Waehrung, E.Prozent)):
                z[k] = _zelle_int(v)
    # Fehlerzellen: Calc liefert dafür keinen brauchbaren Wert, also als Fehlerwert übernehmen
    try:
        fehler = rng.queryFormulaCells(4)       # FormulaResult.ERROR
        for adr in fehler.getRangeAddresses():
            for zr in range(adr.StartRow, adr.EndRow + 1):
                for sc in range(adr.StartColumn, adr.EndColumn + 1):
                    if 0 <= zr - r0 < len(daten) and 0 <= sc - c0 < len(daten[zr - r0]):
                        text = rng.getCellByPosition(sc - c0, zr - r0).getString()
                        daten[zr - r0][sc - c0] = E.FehlerWert(text or "#FEHLER!")
    except Exception:
        traceback.print_exc()
    breite = max([len(z) for z in daten] + [1])
    return E.Tabelle(["Spalte%d" % (i + 1) for i in range(breite)], daten)


def aktives_blatt_name(doc):
    try:
        return doc.getCurrentController().getActiveSheet().Name
    except Exception:
        return None


def lese_blatt(doc, blatt=None, bereich=None):
    sheets = doc.getSheets()
    if blatt and sheets.hasByName(blatt):
        sh = sheets.getByName(blatt)
    elif blatt:
        raise E.FormelFehler("Das Tabellenblatt '%s' gibt es in diesem Dokument nicht" % blatt)
    else:
        try:
            sh = doc.getCurrentController().getActiveSheet()
        except Exception:
            sh = sheets.getByIndex(0)
    if bereich:
        try:
            rng = sh.getCellRangeByName(bereich)
        except Exception:
            raise E.FormelFehler("Ungültiger Bereich '%s'" % bereich)
    else:
        cur = sh.createCursor()
        cur.gotoEndOfUsedArea(False)
        ra = cur.getRangeAddress()
        rng = sh.getCellRangeByPosition(0, 0, ra.EndColumn, ra.EndRow)
    return sh.Name, tabelle_aus_bereich(doc, rng)


CSV_ENDUNGEN = (".csv", ".txt", ".tsv", ".dat", ".asc")


def _datei_oeffnen(ctx, pfad):
    """Tabellendatei unsichtbar und schreibgeschützt öffnen."""
    try:
        os.path.abspath(pfad).encode("utf-8")
    except UnicodeEncodeError:                 # Dateiname in der Systemkodierung nicht als Unicode lesbar: pyuno würde abstürzen
        raise E.FormelFehler("Der Dateiname enthält Zeichen, die das System nicht als Unicode liefert (Zeichenkodierung): %s"
                             % os.path.basename(pfad).encode("utf-8", "replace").decode("utf-8", "replace"))
    url = uno.systemPathToFileUrl(os.path.abspath(pfad))
    desk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    d = desk.loadComponentFromURL(url, "_blank", 0, (pv("Hidden", True), pv("ReadOnly", True)))
    if d is None:
        raise E.FormelFehler("Die Datei konnte nicht geöffnet werden: %s" % pfad)
    return d


def _vorschau_text(zeilen, n=6, spalten=8, breite=14):
    out = []
    for z in list(zeilen)[:n]:
        out.append(" | ".join(("" if v is None else (v if isinstance(v, str) else E.als_text(v)))[:breite] for v in list(z)[:spalten]))
    return "\n".join(out)


def datei_inhalt(ctx, pfad, trenner="auto"):
    """Was bietet die Datei an? -> Liste von {typ: csv|blatt|tabelle|name, name, zeilen, spalten, vorschau, text}.
    Wirft E.FormelFehler, wenn sie nicht lesbar ist."""
    if not pfad or not os.path.exists(pfad):
        raise E.FormelFehler("Datei nicht gefunden: %s" % pfad)
    ext = os.path.splitext(pfad)[1].lower()
    if ext in CSV_ENDUNGEN:
        with open(pfad, "rb") as f:
            tab = E.tabelle_aus_text(E.lese_text_bytes(f.read()), trenner or "auto")
        return [{"typ": "csv", "name": "", "zeilen": len(tab.zeilen), "spalten": len(tab.spalten),
                 "vorschau": _vorschau_text(tab.zeilen),
                 "text": "Textdatei (%d Zeilen × %d Spalten)" % (len(tab.zeilen), len(tab.spalten))}]
    d = _datei_oeffnen(ctx, pfad)
    try:
        def eintrag(typ, name, rng, vorsilbe):
            ra = rng.getRangeAddress()
            z, sp = ra.EndRow - ra.StartRow + 1, ra.EndColumn - ra.StartColumn + 1
            sh = d.getSheets().getByIndex(ra.Sheet)
            kopf = sh.getCellRangeByPosition(ra.StartColumn, ra.StartRow, ra.EndColumn, min(ra.EndRow, ra.StartRow + 5))
            return {"typ": typ, "name": name, "zeilen": z, "spalten": sp,
                    "vorschau": _vorschau_text([[(int(v) if isinstance(v, float) and v == int(v) else v) for v in r] for r in kopf.getDataArray()]),
                    "text": "%s: %s (%d × %d)" % (vorsilbe, name, z, sp)}
        res = []
        sheets = d.getSheets()
        for n in sheets.getElementNames():
            sh = sheets.getByName(n)
            cur = sh.createCursor()
            cur.gotoEndOfUsedArea(False)
            ra = cur.getRangeAddress()
            res.append(eintrag("blatt", n, sh.getCellRangeByPosition(0, 0, ra.EndColumn, ra.EndRow), "Blatt"))
        try:
            dbs = d.DatabaseRanges
            for n in dbs.getElementNames():
                if n.startswith("__"):
                    continue
                ra = dbs.getByName(n).getDataArea()
                sh = sheets.getByIndex(ra.Sheet)
                res.append(eintrag("tabelle", n, sh.getCellRangeByPosition(ra.StartColumn, ra.StartRow, ra.EndColumn, ra.EndRow), "Tabelle"))
        except Exception:
            traceback.print_exc()
        try:
            nr = d.NamedRanges
            for n in nr.getElementNames():
                rng = nr.getByName(n).getReferredCells()
                if rng is not None:
                    res.append(eintrag("name", n, rng, "Benannter Bereich"))
        except Exception:
            traceback.print_exc()
        return res
    finally:
        try:
            d.close(True)
        except Exception:
            pass


def loese_pfad(doc, pfad):
    """{Name} im Pfad durch den Wert der benannten Zelle ersetzen (z. B. C:\\Daten\\{Datei})."""
    pfad = (pfad or "").strip().strip('"')
    if "{" not in pfad:
        return pfad
    fn = baue_parameter(doc) if doc is not None else E.hole_parameter
    return E._PAR.sub(lambda m: E.als_text(fn(m.group(1).strip()), "de"), pfad)


ORDNER_SPALTEN = [("name", "Name"), ("endung", "Endung"), ("pfad", "Pfad"), ("groesse", "Größe"),
                  ("geaendert", "Geändert"), ("erstellt", "Erstellt"), ("ordner", "Unterordner")]
ORDNER_STANDARD = ["name", "geaendert", "groesse"]


def ordner_liste(ordner, muster=None, spalten=None, unterordner=False):
    """Dateien eines Ordners (auf Wunsch mit allen Unterordnern) -> Tabelle mit den gewählten Spalten, nach Ordner und Name sortiert."""
    import fnmatch
    import datetime as dt
    if not ordner:
        raise E.FormelFehler("Es ist kein Ordner angegeben")
    if not os.path.isdir(ordner):
        raise E.FormelFehler("Ordner nicht gefunden: %s" % ordner)
    muster_liste = [m.strip().lower() for m in re.split(r"[;,]", muster or "*") if m.strip()] or ["*"]
    gewaehlt = [k for k in (spalten or ORDNER_STANDARD) if k in dict(ORDNER_SPALTEN)] or list(ORDNER_STANDARD)
    gewaehlt = [k for k, _ in ORDNER_SPALTEN if k in gewaehlt]          # feste Reihenfolge
    ordner_liste_ = []                                                  # (voller Ordnerpfad, relativ)
    if unterordner:
        for wurzel, dirs, _dateien in os.walk(ordner):
            dirs[:] = sorted((x for x in dirs if not x.startswith(".")), key=lambda x: x.casefold())
            rel = os.path.relpath(wurzel, ordner)
            ordner_liste_.append((wurzel, "" if rel == "." else rel))
    else:
        ordner_liste_.append((ordner, ""))
    zeilen = []
    for wurzel, rel in ordner_liste_:
        try:
            namen = sorted(os.listdir(wurzel), key=lambda x: x.casefold())
        except OSError:
            continue
        for n in namen:
            voll = os.path.join(wurzel, n)
            if not os.path.isfile(voll) or n.startswith("~$") or n.startswith(".~lock"):
                continue                                               # Unterordner, Office-/LibreOffice-Sperrdateien
            if not any(fnmatch.fnmatch(n.lower(), m) for m in muster_liste):
                continue
            try:
                st = os.stat(voll)
            except OSError:
                continue
            erst = getattr(st, "st_birthtime", None)                   # Mac
            if erst is None and os.name == "nt":
                erst = st.st_ctime                                     # Windows: Erstellungszeit
            werte = {"name": n, "endung": os.path.splitext(n)[1].lstrip(".").lower(), "pfad": voll,
                     "groesse": st.st_size, "geaendert": dt.datetime.fromtimestamp(st.st_mtime).replace(microsecond=0),
                     "erstellt": dt.datetime.fromtimestamp(erst).replace(microsecond=0) if erst else None,
                     "ordner": rel}
            zeilen.append([werte[k] for k in gewaehlt])
    return E.Tabelle([dict(ORDNER_SPALTEN)[k] for k in gewaehlt], zeilen)


def ordner_waehlen(ctx, startpfad=None):
    fp = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FolderPicker", ctx)
    try:
        start = startpfad if startpfad and os.path.isdir(startpfad) else lies_einstellung("ordner_quelle", "")
        if start and os.path.isdir(start):
            fp.setDisplayDirectory(uno.systemPathToFileUrl(start))
    except Exception:
        pass
    if fp.execute() != 1:
        return None
    try:
        return uno.fileUrlToSystemPath(fp.getDirectory())
    except Exception:
        return None


def lies_quelle(ctx, doc, q):
    """Quelle (dict) -> Tabelle. Wirft E.FormelFehler mit verständlicher Meldung."""
    art = q.get("art")
    if art == "blatt":
        if doc is None:
            raise E.FormelFehler("Es ist kein Calc-Dokument geöffnet")
        return lese_blatt(doc, q.get("blatt"), q.get("bereich"))[1]
    if art == "ordner":
        return ordner_liste(loese_pfad(doc, q.get("pfad", "")), q.get("muster"), q.get("spalten"), bool(q.get("unterordner")))
    if art == "datei":
        pfad = q.get("pfad", "") if q.get("roh") else loese_pfad(doc, q.get("pfad", ""))   # roh: Pfad aus der Dateiliste, kein {Name}
        if not pfad:
            raise E.FormelFehler("Es ist keine Datei angegeben")
        if not os.path.exists(pfad):
            raise E.FormelFehler("Datei nicht gefunden: %s" % pfad)
        ext = os.path.splitext(pfad)[1].lower()
        if ext in CSV_ENDUNGEN:
            with open(pfad, "rb") as f:
                text = E.lese_text_bytes(f.read())
            return E.tabelle_aus_text(text, q.get("trenner") or "auto")
        d = _datei_oeffnen(ctx, pfad)
        try:
            ziel_dok = os.path.basename(pfad)
            if q.get("tabelle"):
                dbs = d.DatabaseRanges
                if not dbs.hasByName(q["tabelle"]):
                    raise E.FormelFehler("Die Tabelle „%s“ gibt es in der Datei %s nicht (mehr)" % (q["tabelle"], ziel_dok))
                ra = dbs.getByName(q["tabelle"]).getDataArea()
                sh = d.getSheets().getByIndex(ra.Sheet)
                return tabelle_aus_bereich(d, sh.getCellRangeByPosition(ra.StartColumn, ra.StartRow, ra.EndColumn, ra.EndRow))
            if q.get("bereichsname"):
                nr = d.NamedRanges
                rng = nr.getByName(q["bereichsname"]).getReferredCells() if nr.hasByName(q["bereichsname"]) else None
                if rng is None:
                    raise E.FormelFehler("Den benannten Bereich „%s“ gibt es in der Datei %s nicht (mehr)" % (q["bereichsname"], ziel_dok))
                return tabelle_aus_bereich(d, rng)
            blatt = q.get("blatt")
            if blatt and not d.getSheets().hasByName(blatt):
                raise E.FormelFehler("Das Tabellenblatt „%s“ gibt es in der Datei %s nicht (mehr)" % (blatt, ziel_dok))
            if not blatt:
                blatt = d.getSheets().getByIndex(0).Name
            return lese_blatt(d, blatt, q.get("bereich"))[1]
        finally:
            try:
                d.close(True)
            except Exception:
                pass
    if art == "zwischenablage":
        return tabelle_aus_zwischenablage(ctx, q.get("trenner") or "auto")
    if art == "abfrage":
        return E.hole_tabelle(q.get("name"))
    if art == "liste":
        if q.get("parameter"):
            werte = E.werte_liste(E.hole_parameter(q["parameter"]))
        else:
            werte = [x.strip() for x in str(q.get("werte") or "").splitlines() if x.strip()]
        if not werte:
            raise E.FormelFehler("Die Liste ist leer")
        return E.Tabelle([(q.get("spalte") or "").strip() or "Wert"], [[v] for v in werte])
    raise E.FormelFehler("Keine Quelle gewählt")


def tabelle_aus_zwischenablage(ctx, trenner="auto"):
    try:
        clip = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)
        inhalt = clip.getContents()
        fl = uno.createUnoStruct("com.sun.star.datatransfer.DataFlavor")
        fl.MimeType = "text/plain;charset=utf-16"
        fl.HumanPresentableName = "Unicode-Text"
        fl.DataType = uno.getTypeByName("string")
        text = inhalt.getTransferData(fl)
    except Exception:
        raise E.FormelFehler("In der Zwischenablage liegt kein Text (oder sie ist nicht lesbar)")
    if not isinstance(text, str) or text.strip() == "":
        raise E.FormelFehler("Die Zwischenablage ist leer")
    return E.tabelle_aus_text(text, trenner)


# Beim Anlegen einer Abfrage aus einem Tabellenblatt: Überschriften und Datentypen als zwei normale Schritte
NEUE_TABELLE_SCHRITTE = [{"op": "erste_zeile_als_kopf"}]      # Datentypen werden nicht automatisch erkannt (kostet Zeit, nicht immer genau)


def rechtsbuendig_auffuellen(texte):
    """Zahlen/Datum rechtsbündig darstellen, ohne die Spaltenausrichtung zu ändern (die würde auch die Überschrift
    nach rechts schieben): vorn mit Ziffernleerzeichen (U+2007, so breit wie eine Ziffer) auffüllen."""
    def breite(t):
        b = 0.0
        for ch in t:
            b += 0.5 if ch in ".,:;' " else 1.0
        return b
    if not texte:
        return texte
    mx = max(breite(t) for t in texte)
    return ["\u2007" * int(round(mx - breite(t))) + t for t in texte]


def beschreibe_quelle(q):
    art = q.get("art")
    if art == "blatt":
        s = "Tabellenblatt %s" % (q.get("blatt") or "(aktuelles)")
        return s + (", Bereich %s" % q["bereich"] if q.get("bereich") else "")
    if art == "datei":
        zusatz = (", Tabelle %s" % q["tabelle"] if q.get("tabelle") else ", Bereich %s" % q["bereichsname"] if q.get("bereichsname")
                  else ", Blatt %s" % q["blatt"] if q.get("blatt") else "")
        return "Datei %s%s" % (os.path.basename((q.get("pfad", "")).replace("\\", "/")), zusatz)
    if art == "ordner":
        return "Ordner %s (%s%s)" % (q.get("pfad", ""), q.get("muster") or "*", ", mit Unterordnern" if q.get("unterordner") else "")
    if art == "zwischenablage":
        return "Zwischenablage"
    if art == "abfrage":
        return "Abfrage %s" % q.get("name", "?")
    if art == "liste":
        if q.get("parameter"):
            return "Liste aus Parameter {%s}" % q["parameter"]
        n = len([x for x in str(q.get("werte") or "").splitlines() if x.strip()])
        return "Liste mit %d Wert(en)" % n
    return "(keine Quelle)"


# ---------------------------------------------------------------------------
# Ergebnis schreiben (neues Blatt oder Zielzelle) / Abfragen im Dokument speichern
# ---------------------------------------------------------------------------
class ZielBelegt(E.FormelFehler):
    """Im Zielbereich stehen Daten, die nicht zu dieser Abfrage gehören."""


def gueltiger_blattname(name):
    n = re.sub(r"[\[\]\*\?:/\\]", "_", name or "").strip().strip("'")
    return (n or "Abfrage")[:60]


def spalten_buchstabe(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def adresse_text(c0, r0, c1, r1):
    return "%s%d:%s%d" % (spalten_buchstabe(c0), r0 + 1, spalten_buchstabe(c1), r1 + 1)


def zu_zelle(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dt.datetime):
        return E.datetime_zu_serie(v)
    if isinstance(v, dt.date):
        return E.datetime_zu_serie(v)
    if isinstance(v, dt.time):
        return (v.hour * 3600 + v.minute * 60 + v.second) / 86400.0
    return str(v)


def spaltenart(werte):
    for v in werte:
        if v is None:
            continue
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, dt.datetime):
            return "datumzeit"
        if isinstance(v, dt.date):
            return "datum"
        if isinstance(v, dt.time):
            return "zeit"
        if isinstance(v, E.Prozent):
            return "prozent"
        if isinstance(v, E.Waehrung):
            return "waehrung"
        if isinstance(v, (int, float)):
            return "zahl"
        return "text"
    return "leer"


def _schreibe_ab(doc, sh, tab, c0, r0):
    """Überschriften + Daten ab Zelle (c0, r0) schreiben, Formate setzen. -> (c1, r1) letzte Zelle."""
    nspalten, nzeilen = len(tab.spalten), len(tab.zeilen)
    if nspalten == 0:
        return c0, r0
    kopf = sh.getCellRangeByPosition(c0, r0, c0 + nspalten - 1, r0)
    kopf.setDataArray((tuple(tab.spalten),))
    kopf.CharWeight = 150.0
    if nzeilen:
        body = sh.getCellRangeByPosition(c0, r0 + 1, c0 + nspalten - 1, r0 + nzeilen)
        body.setDataArray(tuple(tuple(zu_zelle(v) for v in z) for z in tab.zeilen))
        nf = doc.getNumberFormats()
        loc = doc.CharLocale
        keys = {"datum": nf.getStandardFormat(2, loc), "datumzeit": nf.getStandardFormat(6, loc),
                "zeit": nf.getStandardFormat(4, loc), "bool": nf.getStandardFormat(1024, loc),
                "waehrung": nf.getStandardFormat(8, loc), "prozent": nf.getStandardFormat(128, loc)}
        for c in range(nspalten):
            werte = [z[c] for z in tab.zeilen]
            art = spaltenart(werte)
            st = anzeige_stellen(werte)
            if st is not None and art in ("zahl", "prozent"):
                try:
                    keys[art] = zahlenformat_stellen(doc, st, art == "prozent")
                except Exception:
                    traceback.print_exc()
            if art in keys:
                sh.getCellRangeByPosition(c0 + c, r0 + 1, c0 + c, r0 + nzeilen).NumberFormat = keys[art]
    return c0 + nspalten - 1, r0 + nzeilen


def anzeige_stellen(werte):
    """Feste Anzeigestellen einer Spalte (Dezimal/ProzentA aus Runden „nur Anzeige“ oder Typ mit Stellen); sonst None."""
    for v in werte:
        if v is None:
            continue
        return getattr(v, "stellen", None) if isinstance(v, (E.Dezimal, E.ProzentA)) else None
    return None


def zahlenformat_stellen(doc, stellen, prozent=False):
    """Calc-Zahlenformat mit fester Stellenzahl (0,00 bzw. 0,00 %) – das Format wird bei Bedarf angelegt."""
    from com.sun.star.lang import Locale
    nf = doc.getNumberFormats()
    en = Locale("en", "US", "")
    n = max(0, min(15, int(stellen)))
    code = ("#,##0" + ("." + "0" * n if n else "")) + ("%" if prozent else "")
    key = nf.queryKey(code, en, False)
    if key == -1:
        key = nf.addNew(code, en)
    return key


# Farben der intelligenten Tabelle: Schlüssel, Anzeigename, Kopf (dunkel), Bänderung (hell)
TABELLEN_FARBEN = [("blau", "Blau", 0x1F4E79, 0xDDEBF7), ("gruen", "Grün", 0x375623, 0xE2EFDA),
                   ("orange", "Orange", 0xC65911, 0xFCE4D6), ("rot", "Rot", 0xA61C1C, 0xFADBD8),
                   ("violett", "Violett", 0x5B2C83, 0xE8DFF0), ("tuerkis", "Türkis", 0x1F6F78, 0xDDF1F3),
                   ("grau", "Grau", 0x404040, 0xEDEDED), ("gold", "Gold", 0x7F6000, 0xFFF2CC)]
TABELLEN_FARBE = {k: (n, kopf, band) for k, n, kopf, band in TABELLEN_FARBEN}
TABELLEN_STANDARD = {"tabelle": True, "baender": True, "farbe": "blau", "reiter": False}
BEREICH_PRAEFIX = "tbl_"


def tabellen_optionen(ziel):
    """Optionen der intelligenten Tabelle mit Standardwerten (Standard: an, Blau, Bänderung an, Reiter aus)."""
    o = dict(TABELLEN_STANDARD)
    for k in o:
        if (ziel or {}).get(k) is not None:
            o[k] = ziel[k]
    if o["farbe"] not in TABELLEN_FARBE:
        o["farbe"] = "blau"
    return o


def bereichsname(name):
    """Name des Datenbankbereichs: tbl_ + Abfragename (Sonderzeichen und Leerzeichen werden zu _)."""
    return BEREICH_PRAEFIX + re.sub(r"[^\w]", "_", name or "")


def entferne_tabellenbereich(doc, ziel):
    """Den gemerkten Datenbankbereich der Abfrage entfernen (der Zellinhalt bleibt)."""
    try:
        n = (ziel or {}).get("bereich")
        if n and doc.DatabaseRanges.hasByName(n):
            doc.DatabaseRanges.removeByName(n)
    except Exception:
        traceback.print_exc()


def _band_stil(doc, schluessel):
    """Zellvorlage für die Bänderung (wird bei Bedarf angelegt bzw. in der Farbe nachgeführt)."""
    name = "OpenQuery_Band_" + schluessel
    stile = doc.getStyleFamilies().getByName("CellStyles")
    if stile.hasByName(name):
        st = stile.getByName(name)
    else:
        st = doc.createInstance("com.sun.star.style.CellStyle")
        stile.insertByName(name, st)
    st.CellBackColor = TABELLEN_FARBE[schluessel][2]
    return name


def formatiere_tabelle(doc, sh, abfragename, ziel, c0, r0, c1, r1, eigenes_blatt):
    """Ausgabebereich (c0,r0)-(c1,r1) wie eine intelligente Tabelle in Excel formatieren: Kopfzeile in der Farbe,
    Bänderung (bedingte Formatierung, bleibt beim Sortieren/Filtern stimmig), Autofilter über alle Spalten und
    benannter Datenbankbereich tbl_<Abfragename>. Reiterfarbe nur auf Wunsch und nur bei eigenem Blatt."""
    opt = tabellen_optionen(ziel)
    _, kopf_farbe, _ = TABELLEN_FARBE[opt["farbe"]]
    try:
        if eigenes_blatt:
            if opt["reiter"]:
                sh.TabColor = kopf_farbe
                ziel["reiter_farbe"] = kopf_farbe
            else:
                if ziel.get("reiter_farbe") is not None and sh.TabColor == ziel["reiter_farbe"]:
                    sh.TabColor = -1        # nur die Farbe zurücknehmen, die diese Abfrage selbst gesetzt hat
                ziel.pop("reiter_farbe", None)
    except Exception:
        traceback.print_exc()
    entferne_tabellenbereich(doc, ziel)
    ziel.pop("bereich", None)
    if not opt["tabelle"] or c1 < c0:
        return
    nzeilen = r1 - r0
    try:
        kopf = sh.getCellRangeByPosition(c0, r0, c1, r0)
        kopf.CellBackColor = kopf_farbe
        kopf.CharColor = 0xFFFFFF
        kopf.CharWeight = 150.0
        kopf.HoriJustify = uno.Enum("com.sun.star.table.CellHoriJustify", "LEFT")       # Überschriften immer links
        if nzeilen and opt["baender"]:
            body = sh.getCellRangeByPosition(c0, r0 + 1, c1, r1)
            stil = _band_stil(doc, opt["farbe"])
            cf = body.ConditionalFormat
            cf.addNew((_pv("Operator", uno.Enum("com.sun.star.sheet.ConditionOperator", "FORMULA")),
                       _pv("Formula1", "MOD(ROW()-%d;2)=1" % (r0 + 1)), _pv("StyleName", stil)))
            body.ConditionalFormat = cf
        dbr = doc.DatabaseRanges
        name = bereichsname(abfragename)
        basis, i = name, 2
        belegt = set()                              # Bereiche anderer gespeicherter Abfragen
        try:
            for n_, t_ in gespeicherte_abfragen(doc).items():
                if n_ != abfragename:
                    b_ = (E.Abfrage.from_json(t_).ziel or {}).get("bereich")
                    if b_:
                        belegt.add(b_)
        except Exception:
            pass
        while dbr.hasByName(name) and name in belegt:      # nie einen fremden Bereich überschreiben
            name = "%s_%d" % (basis, i)
            i += 1
        if dbr.hasByName(name):                     # verwaister Bereich (Abfrage wurde gelöscht): übernehmen
            dbr.removeByName(name)
        adr = sh.getCellRangeByPosition(c0, r0, c1, max(r1, r0 + 1)).getRangeAddress()
        dbr.addNewByName(name, adr)
        db = dbr.getByName(name)
        db.ContainsHeader = True
        db.AutoFilter = True
        ziel["bereich"] = name
    except Exception:
        traceback.print_exc()


def _pv(name, wert):
    p = PropertyValue()
    p.Name, p.Value = name, wert
    return p


def schreibe_tabelle(doc, tab, blattname, ziel=None, abfragename=None, zelle="A1"):
    """Ergebnis in ein (neues oder vorhandenes) Blatt schreiben, ab der Zielzelle (Standard A1); der alte Inhalt
    des Blatts wird ersetzt. Mit ziel/abfragename wird es zusätzlich als intelligente Tabelle formatiert."""
    sheets = doc.getSheets()
    vorhanden = sheets.hasByName(blattname)
    probe = sheets.getByName(blattname) if vorhanden else sheets.getByIndex(0)
    try:
        start = probe.getCellRangeByName((zelle or "A1").strip() or "A1").getRangeAddress()
    except Exception:
        raise E.FormelFehler("Ungültige Zielzelle '%s'" % zelle)
    if vorhanden:
        sh = probe
        sh.clearContents(1023)   # Werte, Text, Formeln, Formate: alles
    else:
        sheets.insertNewByName(blattname, sheets.getCount())
        sh = sheets.getByName(blattname)
    c0, r0 = start.StartColumn, start.StartRow
    c1, r1 = _schreibe_ab(doc, sh, tab, c0, r0)
    if ziel is not None:
        formatiere_tabelle(doc, sh, abfragename or blattname, ziel, c0, r0, c1, r1, True)
    try:
        cols = sh.getColumns()
        for c in range(min(len(tab.spalten), 100)):
            col = cols.getByIndex(c)
            col.OptimalWidth = True
            if ziel is not None and ziel.get("bereich"):
                col.Width = col.Width + 700         # Platz für den Filterpfeil
    except Exception:
        pass
    return sh


def ist_verbindung(abfrage):
    """Reine Verbindungs-Abfrage: schreibt nichts ins Blatt, ist aber in Verbinden/Anfügen/Verweis nutzbar."""
    return (abfrage.ziel or {}).get("art") == "keine"


def zielblatt_name(abfrage):
    z = abfrage.ziel or {}
    if z.get("art") == "keine":
        return ""
    if z.get("art") == "zelle":
        return z.get("blatt") or ""
    return gueltiger_blattname(abfrage.name)


def pruefe_ziel(doc, abfrage):
    """Das Ziel darf nicht auf dem Quellblatt liegen (sonst würde die Quelle überschrieben)."""
    q = abfrage.quelle or {}
    if q.get("art") != "blatt":
        return
    quell = q.get("blatt") or aktives_blatt_name(doc)
    ziel = zielblatt_name(abfrage)
    if quell and ziel == quell:
        if (abfrage.ziel or {}).get("art") == "zelle":
            raise E.FormelFehler("Das Zielblatt '%s' ist zugleich die Quelle. Bitte ein anderes Blatt als "
                                 "Ziel wählen." % ziel)
        raise E.FormelFehler("Das Zielblatt '%s' ist zugleich die Quelle. Bitte einen anderen "
                             "Abfragenamen wählen." % ziel)


def _liegt_in(adr, c0, r0, c1, r1):
    return (adr.StartColumn >= c0 and adr.EndColumn <= c1 and adr.StartRow >= r0 and adr.EndRow <= r1)


def _inhalt_adressen(sh, c0, r0, c1, r1):
    """Adressen der Zellbereiche mit Inhalt (Werte, Text, Formeln) innerhalb des Rechtecks. Die Ergebnisse von
    queryContentCells werden auf das Rechteck beschnitten, weil LibreOffice bei leerem Ergebnis teils Fremdes liefert."""
    res = []
    for a in sh.getCellRangeByPosition(c0, r0, c1, r1).queryContentCells(23).getRangeAddresses():
        if a.Sheet == sh.RangeAddress.Sheet and a.StartColumn >= c0 and a.EndColumn <= c1 and a.StartRow >= r0 and a.EndRow <= r1:
            res.append(a)
    return res


def _bereichs_adresse(doc, name):
    """(Blattname, Blattindex, c0, r0, c1, r1) des Datenbereichs; None, wenn es ihn nicht (mehr) gibt."""
    try:
        if name and doc.DatabaseRanges.hasByName(name):
            ad = doc.DatabaseRanges.getByName(name).getDataArea()
            return (doc.getSheets().getByIndex(ad.Sheet).Name, ad.Sheet, ad.StartColumn, ad.StartRow,
                    ad.EndColumn, ad.EndRow)
    except Exception:
        traceback.print_exc()
    return None


def _fremde_bereiche(doc, eigener_name):
    """Datenbereiche der Tabellen anderer OpenQuery-Abfragen (nur wenn die Abfrage noch gespeichert ist):
    [(name, blattindex, c0, r0, c1, r1)]."""
    res = []
    try:
        dbr = doc.DatabaseRanges
        belegt = set()                  # nur Bereiche, die noch zu einer gespeicherten Abfrage gehören
        for t_ in gespeicherte_abfragen(doc).values():
            try:
                b_ = (E.Abfrage.from_json(t_).ziel or {}).get("bereich")
                if b_:
                    belegt.add(b_)
            except Exception:
                pass
        for n in dbr.getElementNames():
            if n == eigener_name or n not in belegt:
                continue
            ad = dbr.getByName(n).getDataArea()
            res.append((n, ad.Sheet, ad.StartColumn, ad.StartRow, ad.EndColumn, ad.EndRow))
    except Exception:
        traceback.print_exc()
    return res


def _bedingte_formate_entfernen(sh, c0, r0, c1, r1):
    """Bedingte Formate (Bänderung), die ganz im Bereich liegen, entfernen: clearContents räumt sie nicht ab."""
    try:
        cfs = sh.getPropertyValue("ConditionalFormats")
        for cf in cfs.getConditionalFormats():
            ranges = cf.Range.getRangeAddresses()
            if ranges and all(_liegt_in(r, c0, r0, c1, r1) for r in ranges):
                cfs.removeByID(cf.ID)
    except Exception:
        traceback.print_exc()


def _plane_verschiebung(sh, alt, c0, r0, c1, r1, fremde):
    """Wird die Tabelle länger oder kürzer, sollen fremde Daten darunter (in den Spalten der Tabelle) mitwandern und den
    Abstand zur Tabelle behalten. -> (c0, c_max, alte_letzte_zeile, Zeilendifferenz) oder None (nichts zu verschieben)."""
    try:
        if alt is None or alt[0].Name != sh.Name or (alt[1][0], alt[1][1]) != (c0, r0):
            return None
        c1o, r1o = alt[1][2], alt[1][3]
        delta = r1 - r1o
        if delta == 0:
            return None
        cm = max(c1, c1o)
        cur = sh.createCursor()
        cur.gotoEndOfUsedArea(False)
        letzte = cur.getRangeAddress().EndRow
        if letzte <= r1o or not _inhalt_adressen(sh, c0, r1o + 1, cm, letzte):
            return None
        idx = sh.RangeAddress.Sheet
        for _n, si_, fc0, fr0, fc1, fr1 in fremde:        # eine Tabelle, die nur teilweise in den Spalten läge, würde zerrissen
            if si_ == idx and fr0 > r1o and not (fc1 < c0 or fc0 > cm) and (fc0 < c0 or fc1 > cm):
                return None
        return (c0, cm, r1o, delta)
    except Exception:
        traceback.print_exc()
        return None


def _verschiebe_darunter(sh, c0, cm, r1o, delta):
    """Zellen unterhalb der alten Tabelle in den Spalten c0..cm um delta Zeilen nach unten (Tabelle länger) bzw. oben
    (Tabelle kürzer) schieben. Die alte Tabelle ist dann bereits geleert."""
    from com.sun.star.table import CellRangeAddress
    from com.sun.star.sheet.CellInsertMode import DOWN
    from com.sun.star.sheet.CellDeleteMode import UP
    idx = sh.RangeAddress.Sheet
    if delta > 0:
        sh.insertCells(CellRangeAddress(idx, c0, r1o + 1, cm, r1o + delta), DOWN)
    else:
        sh.removeRange(CellRangeAddress(idx, c0, r1o + delta + 1, cm, r1o), UP)


NOTIZ_TEXT = ("Dies ist eine OpenQuery-Tabelle. Änderungen werden überschrieben, "
              "außer in manuell hinzugefügten Spalten.")


def _setze_notiz(doc, sh, c0, r0):
    """Hinweis-Notiz an der linken oberen Zelle der Ausgabetabelle (nicht dauerhaft sichtbar)."""
    try:
        zelle = sh.getCellByPosition(c0, r0)
        ann = zelle.getAnnotation()
        if (ann.getString() or "") != NOTIZ_TEXT:
            sh.getAnnotations().insertNew(zelle.getCellAddress(), NOTIZ_TEXT)
            sh.getCellByPosition(c0, r0).getAnnotation().setIsVisible(False)
    except Exception:
        traceback.print_exc()


def _stand_berechnen(sh, abfrage, c0, r0, c1, r1):
    """Prüfsumme der von OpenQuery geschriebenen Tabelle (ohne manuelle Spalten und Formelspalten, die der Nutzer
    ändern darf). Wird nach dem Schreiben gemerkt; weicht sie später ab, wurde die Tabelle von Hand geändert."""
    daten = sh.getCellRangeByPosition(c0, r0, c1, r1).getDataArray()
    if not daten:
        return ""
    st = _hand_schritt(abfrage)
    aus = set()
    if st is not None:
        aus = {x.strip().casefold() for x in str(st.get("handspalten") or "").splitlines() if x.strip()}
        aus |= {str(n).strip().casefold() for n in (st.get("formeln") or {})}
    kopf = [str(x) for x in daten[0]]
    cols = [i for i, n in enumerate(kopf) if n.strip().casefold() not in aus]
    inhalt = [[z[i] for i in cols] for z in daten]
    return hashlib.md5(json.dumps(inhalt, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def hand_geaendert(doc, abfrage):
    """True, wenn die Ausgabetabelle seit dem letzten Schreiben von Hand geändert wurde (nur wenn ein Stand gemerkt ist)."""
    try:
        ziel = abfrage.ziel or {}
        alt = ziel.get("stand")
        if not alt or ziel.get("art") == "keine":
            return False
        ad = _bereichs_adresse(doc, ziel.get("bereich"))
        if ad is None:
            return False
        sh = doc.getSheets().getByIndex(ad[1])
        return _stand_berechnen(sh, abfrage, ad[2], ad[3], ad[4], ad[5]) != alt
    except Exception:
        traceback.print_exc()
        return False


def schreibe_ergebnis(doc, tab, abfrage, bestaetigt=False):
    """Ergebnis gemäß Ziel der Abfrage schreiben. Merkt sich den beschriebenen Bereich in abfrage.ziel.
    Die Tabelle „folgt“ ihrem Datenbankbereich tbl_<Name>: wurde sie verschoben (Zellen/Zeilen/Spalten eingefügt,
    ausgeschnitten, in ein anderes Blatt), wird dort aktualisiert; nur der Tabellenbereich selbst wird ersetzt.
    Wirft ZielBelegt, wenn dort fremde Daten stehen (außer bestaetigt=True)."""
    pruefe_ziel(doc, abfrage)
    ziel = abfrage.ziel if isinstance(abfrage.ziel, dict) else {"art": "blatt"}
    abfrage.ziel = ziel
    sheets = doc.getSheets()
    if ziel.get("art") == "keine":          # nur Verbindung: nichts ins Blatt schreiben
        entferne_tabellenbereich(doc, ziel)
        ziel.pop("bereich", None)
        return None
    # --- wo steht die Tabelle jetzt? (Datenbereich folgen)
    folge = _bereichs_adresse(doc, ziel.get("bereich"))
    sh = alt = None
    if folge is not None:
        bl_name, bl_idx, c0, r0, ac1, ar1 = folge
        sh = sheets.getByIndex(bl_idx)
        if ziel.get("art") != "zelle":
            erwartet = gueltiger_blattname(abfrage.name)
            try:
                st = sheets.getByName(erwartet).getCellRangeByName(ziel.get("zelle") or "A1").getRangeAddress() \
                    if sheets.hasByName(erwartet) else None
            except Exception:
                st = None
            if not (bl_name == erwartet and st is not None and st.StartColumn == c0 and st.StartRow == r0):
                ziel["art"] = "zelle"            # verschoben: ab jetzt gilt der neue Ort
        if ziel.get("art") == "zelle":
            ziel["blatt"] = bl_name
            ziel["zelle"] = adresse_text(c0, r0, c0, r0).split(":")[0]
        alt = (sh, (c0, r0, ac1, ar1))
    elif ziel.get("art") != "zelle":
        entferne_tabellenbereich(doc, ziel)                # (kein Bereich bekannt) altes Blatt neu schreiben
        sh = schreibe_tabelle(doc, tab, gueltiger_blattname(abfrage.name), ziel, abfrage.name,
                              ziel.get("zelle") or "A1")
        ziel["art"] = "blatt"
        ziel.pop("letzter", None)
        ziel.pop("letzter_blatt", None)
        ziel["spalten"] = list(tab.spalten)
        return sh.Name
    else:
        blatt = ziel.get("blatt")
        if not blatt or not sheets.hasByName(blatt):
            raise E.FormelFehler("Das Zielblatt '%s' gibt es nicht mehr" % (blatt or ""))
        sh = sheets.getByName(blatt)
        try:
            start = sh.getCellRangeByName(ziel.get("zelle") or "A1").getRangeAddress()
        except Exception:
            raise E.FormelFehler("Ungültige Zielzelle '%s'" % ziel.get("zelle"))
        c0, r0 = start.StartColumn, start.StartRow
        if ziel.get("letzter") and ziel.get("letzter_blatt") and sheets.hasByName(ziel["letzter_blatt"]):
            try:
                alt_sh = sheets.getByName(ziel["letzter_blatt"])
                a = alt_sh.getCellRangeByName(ziel["letzter"]).getRangeAddress()
                alt = (alt_sh, (a.StartColumn, a.StartRow, a.EndColumn, a.EndRow))
            except Exception:
                alt = None
    blatt = sh.Name
    c1, r1 = c0 + max(len(tab.spalten), 1) - 1, r0 + len(tab.zeilen)
    fremde = _fremde_bereiche(doc, ziel.get("bereich"))
    verschieben = _plane_verschiebung(sh, alt, c0, r0, c1, r1, fremde)
    # zwei OpenQuery-Tabellen (oder andere benannte Bereiche) dürfen sich nicht berühren
    for n_, si_, fc0, fr0, fc1, fr1 in fremde:
        if verschieben and si_ == sh.RangeAddress.Sheet and fr0 > verschieben[2] and not (fc1 < c0 or fc0 > verschieben[1]):
            continue                              # liegt unterhalb und wandert mit
        if si_ == sh.RangeAddress.Sheet and not (c1 + 1 < fc0 or fc1 + 1 < c0 or r1 + 1 < fr0 or fr1 + 1 < r0):
            raise E.FormelFehler("Die neue Tabelle (%s) würde die Tabelle „%s“ (%s) berühren oder überdecken. "
                                 "Zwischen zwei Tabellen muss mindestens eine Zeile oder Spalte frei bleiben."
                                 % (adresse_text(c0, r0, c1, r1), n_, adresse_text(fc0, fr0, fc1, fr1)))
    # Konflikt: Inhalt im neuen Bereich, der nicht zum alten Ergebnis gehört
    if not bestaetigt:
        pr1 = min(r1, verschieben[2]) if verschieben else r1       # Zeilen unterhalb der alten Tabelle wandern mit
        for adr in _inhalt_adressen(sh, c0, r0, c1, pr1):
            innerhalb = (alt is not None and alt[0].Name == sh.Name and _liegt_in(adr, *alt[1]))
            if not innerhalb:
                raise ZielBelegt("Im Zielbereich %s auf Blatt '%s' stehen schon andere Daten (die Tabelle würde dort "
                                 "hineinwachsen)." % (adresse_text(c0, r0, c1, r1), blatt))
    entferne_tabellenbereich(doc, ziel)
    if alt is not None:
        a = alt[1]
        _bedingte_formate_entfernen(alt[0], *a)
        alt[0].getCellRangeByPosition(a[0], a[1], a[2], a[3]).clearContents(1023)
    if verschieben:
        _verschiebe_darunter(sh, *verschieben)
    c1, r1 = _schreibe_ab(doc, sh, tab, c0, r0)
    st_h = _hand_schritt(abfrage)
    if st_h is not None:
        schreibe_formelspalten(doc, sh, tab, st_h, c0, r0, c1, r1)
        schreibe_spaltenformate(doc, sh, tab, st_h, c0, r0, c1, r1)
    eigenes = ziel.get("art") != "zelle"
    formatiere_tabelle(doc, sh, abfrage.name, ziel, c0, r0, c1, r1, eigenes)
    if eigenes:
        ziel.pop("letzter", None)
        ziel.pop("letzter_blatt", None)
    else:
        ziel["letzter"] = adresse_text(c0, r0, c1, r1)
        ziel["letzter_blatt"] = blatt
    ziel["spalten"] = list(tab.spalten)
    _setze_notiz(doc, sh, c0, r0)
    try:
        ziel["stand"] = _stand_berechnen(sh, abfrage, c0, r0, c1, r1)
    except Exception:
        traceback.print_exc()
        ziel.pop("stand", None)
    return blatt


def gespeicherte_abfragen(doc):
    """-> dict name -> Abfrage-JSON-Text"""
    ergebnis = {}
    try:
        props = doc.getDocumentProperties().getUserDefinedProperties()
        for p in props.getPropertySetInfo().getProperties():
            if p.Name.startswith(PROP_PRAEFIX):
                ergebnis[p.Name[len(PROP_PRAEFIX):]] = props.getPropertyValue(p.Name)
    except Exception:
        traceback.print_exc()
    return ergebnis


def lies_reihenfolge(doc):
    try:
        props = doc.getDocumentProperties().getUserDefinedProperties()
        return [str(n) for n in json.loads(props.getPropertyValue(PROP_REIHENFOLGE))]
    except Exception:
        return []


def speichere_reihenfolge(doc, namen):
    props = doc.getDocumentProperties().getUserDefinedProperties()
    text = json.dumps(list(namen), ensure_ascii=False)
    try:
        props.addProperty(PROP_REIHENFOLGE, 128, text)
    except Exception:
        props.setPropertyValue(PROP_REIHENFOLGE, text)


def geordnete_namen(doc, namen):
    """Namen in der gespeicherten Reihenfolge; unbekannte (neue) alphabetisch dahinter."""
    namen = list(namen)
    rf = [n for n in lies_reihenfolge(doc) if n in namen]
    return rf + sorted(n for n in namen if n not in rf)


_ARBEIT = {"fn": None}      # vom Editor gesetzt: liefert {name: json} der gerade bearbeiteten (evtl. ungespeicherten) Abfragen


def abfragen_texte(doc):
    """Wie gespeicherte_abfragen, aber mit den Arbeitsständen des offenen Editors (für Verweise zwischen Abfragen)."""
    texte = gespeicherte_abfragen(doc) if doc is not None else {}
    try:
        if _ARBEIT["fn"]:
            texte.update(_ARBEIT["fn"]())
    except Exception:
        traceback.print_exc()
    return texte


def speichere_abfrage(doc, abfrage):
    props = doc.getDocumentProperties().getUserDefinedProperties()
    name = PROP_PRAEFIX + abfrage.name
    text = abfrage.to_json()
    try:
        props.addProperty(name, 128, text)
    except Exception:
        props.setPropertyValue(name, text)


def loesche_abfrage(doc, name, bereich_entfernen=False):
    """Abfrage aus der Datei entfernen. Der Datenbankbereich tbl_… bleibt immer stehen (seit 0.6.0);
    „bereich_entfernen“ wird nur noch aus Gründen der Aufrufkompatibilität angenommen."""
    try:
        doc.getDocumentProperties().getUserDefinedProperties().removeProperty(PROP_PRAEFIX + name)
    except Exception:
        pass


def baue_aufloeser(ctx, doc, eigen=None, cache=None):
    """Funktion name -> Tabelle für Verbinden/Anfügen: Ergebnis einer anderen gespeicherten Abfrage dieser Datei.
    Schützt vor Zirkelbezügen (eine Abfrage darf sich nicht selbst, auch nicht über andere, einbinden)."""
    stack = [eigen] if eigen else []
    if cache is None:                 # der Editor gibt einen gemeinsamen Zwischenspeicher mit (Basisabfragen nur einmal rechnen)
        cache = {}

    def hole(name):
        if name in stack:
            raise E.FormelFehler("Zirkelbezug: Die Abfrage '%s' ist schon in Bearbeitung (%s)"
                                 % (name, " → ".join(stack + [name])))
        texte = abfragen_texte(doc)
        if name not in texte:
            raise E.FormelFehler("Die Abfrage '%s' gibt es in dieser Datei nicht (sie muss gespeichert sein)" % name)
        key = (name, texte[name])
        if key in cache:
            return cache[key]
        a = E.Abfrage.from_json(texte[name])
        stack.append(name)
        alt_stand = E.SNAPSHOT.get("fn")
        E.SNAPSHOT["fn"] = lambda a=a: lies_eigenen_stand(doc, a)
        try:
            roh = lies_quelle(ctx, doc, a.quelle)
            tab = E.fuehre_aus(roh, a.schritte)
        except E.StepError as e:
            raise E.FormelFehler("Abfrage '%s': %s" % (name, e))
        finally:
            E.SNAPSHOT["fn"] = alt_stand
            stack.pop()
        cache[key] = tab
        return tab
    return hole


def datei_quelle_aus_schritt(pfad, st):
    """Zielangaben des Schritts „Dateiinhalt einlesen“ -> Quelle (dict) für lies_quelle; der Pfad wird nicht als {Name} gedeutet."""
    q = {"art": "datei", "pfad": pfad, "roh": True, "trenner": st.get("trenner") or "auto"}
    for k in ("blatt", "tabelle", "bereichsname", "bereich"):
        if st.get(k):
            q[k] = st[k]
    return q


def setze_aufloeser(ctx, doc, eigen=None, abfrage=None, cache=None):
    """Auflöser für andere Abfragen, Parameter aus benannten Zellen und eigenen letzten Stand (Handeinträge) setzen."""
    E.AUFLOESER["fn"] = baue_aufloeser(ctx, doc, eigen, cache)
    E.PARAMETER["fn"] = baue_parameter(doc)
    E.DATEI_LESER["fn"] = lambda pfad, st: lies_quelle(ctx, doc, datei_quelle_aus_schritt(pfad, st))
    E.SNAPSHOT["fn"] = (lambda: lies_eigenen_stand(doc, abfrage)) if abfrage is not None else None


# --- Parameter: benannte Zellen -------------------------------------------------------------------------------------
def parameter_bereich(doc, name):
    """Benannte Einzelzelle -> Zellbereich (1×1). Wirft E.FormelFehler mit dem Parameternamen."""
    try:
        nr = doc.NamedRanges
        treffer = None
        if nr.hasByName(name):
            treffer = name
        else:
            for n in nr.getElementNames():
                if n.casefold() == name.casefold():
                    treffer = n
                    break
        if treffer is None:
            raise E.FormelFehler("Parameter '%s': In dieser Datei gibt es weder einen OpenQuery-Parameter noch eine "
                                 "benannte Zelle mit diesem Namen (Zelle: Namen im Namensfeld links über der Tabelle vergeben)" % name)
        ref = nr.getByName(treffer).getReferredCells()
    except E.FormelFehler:
        raise
    except Exception as e:
        raise E.FormelFehler("Parameter '%s': %s" % (name, e))
    if ref is None:
        raise E.FormelFehler("Parameter '%s': Der Name verweist nicht auf eine Zelle" % name)
    ra = ref.getRangeAddress()
    if ra.StartRow != ra.EndRow or ra.StartColumn != ra.EndColumn:
        raise E.FormelFehler("Parameter '%s': Der Name muss genau eine Zelle bezeichnen, nicht einen Bereich" % name)
    return ref


PARAM_PRAEFIX = "AEP:"
PARAM_TYPEN = [("text", "Text"), ("zahl", "Zahl"), ("datum", "Datum"), ("datumzeit", "Datum mit Uhrzeit"),
               ("janein", "Ja/Nein"), ("liste", "Liste (mit ; getrennt)"),
               ("abfrage_liste", "Liste aus einer Abfrage (Spalte)"), ("abfrage_wert", "Wert aus einer Abfrage (erste Zelle)")]
PARAM_HINWEIS = {"text": "Beliebiger Text, z. B. C:\\Daten", "zahl": "Zahl, z. B. 12,5",
                 "datum": "Datum, z. B. 31.01.2026", "datumzeit": "Datum mit Uhrzeit, z. B. 31.01.2026 06:00",
                 "janein": "ja oder nein", "liste": "Werte mit ; getrennt, z. B. Berlin;Potsdam;Cottbus",
                 "abfrage_liste": "Abfragename, optional mit Spalte: Aktive Liegenschaften[Nummer] (sonst erste Spalte)",
                 "abfrage_wert": "Abfragename, optional mit Spalte: Stichtage[Datum] (erste nicht leere Zelle)"}
PARAM_ABFRAGE = ("abfrage_liste", "abfrage_wert")


def teile_abfrage_angabe(text):
    """„Name[Spalte]“ -> (Name, Spalte oder '')."""
    m = re.match(r"^\s*(.*?)\s*\[([^\[\]]+)\]\s*$", str(text or ""))
    return (m.group(1), m.group(2).strip()) if m else (str(text or "").strip(), "")


def abfrage_parameter_wert(typ, angabe, pname):
    """Wert eines Parameters, der aus dem Ergebnis einer anderen Abfrage kommt (Liste mit ; oder erster Wert)."""
    abf, spalte = teile_abfrage_angabe(angabe)
    fn = E.AUFLOESER.get("fn")
    if fn is None:
        raise E.FormelFehler("Parameter '%s': Andere Abfragen sind hier nicht verfügbar" % pname)
    try:
        tab = fn(abf)
    except E.FormelFehler as e:
        raise E.FormelFehler("Parameter '%s': %s" % (pname, e.args[0] if e.args else e))
    if not tab.spalten:
        raise E.FormelFehler("Parameter '%s': Die Abfrage '%s' hat keine Spalten" % (pname, abf))
    if spalte:
        try:
            i = tab.idx(spalte)
        except E.FormelFehler:
            raise E.FormelFehler("Parameter '%s': Die Abfrage '%s' hat keine Spalte '%s' (vorhanden: %s)"
                                 % (pname, abf, spalte, ", ".join(tab.spalten[:8])))
    else:
        i = 0
    werte = [z[i] for z in tab.zeilen if not E.ist_leer(z[i])]
    if not werte:
        raise E.FormelFehler("Parameter '%s': Die Abfrage '%s' liefert in Spalte '%s' keinen Wert" % (pname, abf, tab.spalten[i]))
    if typ == "abfrage_wert":
        return werte[0]
    teile, gesehen = [], set()
    for w in werte:
        t = E.als_text(w).strip()
        if ";" in t:
            raise E.FormelFehler("Parameter '%s': Ein Wert aus Abfrage '%s' enthält ein Semikolon (%s); Listen werden mit ; getrennt"
                                 % (pname, abf, t[:30]))
        if t and t.casefold() not in gesehen:
            gesehen.add(t.casefold())
            teile.append(t)
    return ";".join(teile)


def lies_oq_parameter(doc):
    """-> dict Name -> {typ, wert, beschreibung}: die in dieser Datei gespeicherten OpenQuery-Parameter."""
    out = {}
    if doc is None:
        return out
    try:
        props = doc.getDocumentProperties().getUserDefinedProperties()
        for p in props.getPropertySetInfo().getProperties():
            if p.Name.startswith(PARAM_PRAEFIX):
                try:
                    d = json.loads(props.getPropertyValue(p.Name))
                    out[p.Name[len(PARAM_PRAEFIX):]] = {"typ": d.get("typ", "text"), "wert": d.get("wert", ""),
                                                        "beschreibung": d.get("beschreibung", ""),
                                                        "vorschlag": d.get("vorschlag") or None}
                except Exception:
                    continue
    except Exception:
        traceback.print_exc()
    return out


def speichere_oq_parameter(doc, name, p):
    props = doc.getDocumentProperties().getUserDefinedProperties()
    daten = {"typ": p["typ"], "wert": p["wert"], "beschreibung": p.get("beschreibung", "")}
    if p.get("vorschlag"):
        daten["vorschlag"] = p["vorschlag"]
    text = json.dumps(daten, ensure_ascii=False)
    try:
        props.addProperty(PARAM_PRAEFIX + name, 128, text)
    except Exception:
        props.setPropertyValue(PARAM_PRAEFIX + name, text)


def loesche_oq_parameter(doc, name):
    try:
        doc.getDocumentProperties().getUserDefinedProperties().removeProperty(PARAM_PRAEFIX + name)
    except Exception:
        pass


def parse_param_wert(typ, text):
    """Eingabetext -> (Python-Wert, Text zum Speichern). Wirft ValueError mit verständlicher Meldung."""
    t = str(text or "").strip()
    if t == "":
        raise ValueError("Bitte einen Wert angeben.")
    try:
        if typ == "zahl":
            return E.parse_zahl(t), t
        if typ == "datum":
            return E.parse_datum(t), t
        if typ == "datumzeit":
            return E.parse_datum(t, mit_zeit=True), t
        if typ == "janein":
            v = E.parse_bool(t)
            return v, "ja" if v else "nein"
        if typ in PARAM_ABFRAGE:
            if not teile_abfrage_angabe(t)[0]:
                raise ValueError("Bitte den Namen einer Abfrage angeben.")
            return t, t
        if typ == "liste":
            teile = [x.strip() for x in t.split(";") if x.strip()]
            if not teile:
                raise ValueError("Bitte mindestens einen Wert angeben.")
            return ";".join(teile), ";".join(teile)
    except E.FormelFehler as ex:
        raise ValueError("%s\n(%s)" % (ex, PARAM_HINWEIS.get(typ, "")))
    return t, t


def finde_oq_parameter(doc, name):
    """(gespeicherter Name, Parameter) ohne Rücksicht auf Groß/Kleinschreibung; (None, None) wenn es ihn nicht gibt."""
    ps = lies_oq_parameter(doc)
    if name in ps:
        return name, ps[name]
    for n, p in ps.items():
        if n.casefold() == str(name).strip().casefold():
            return n, p
    return None, None


def zellname_vorhanden(doc, name):
    try:
        return any(n.casefold() == str(name).strip().casefold() for n in doc.NamedRanges.getElementNames())
    except Exception:
        return False


def baue_parameter(doc):
    """{Name} -> Wert. Eine benannte Zelle gleichen Namens hat Vorrang vor einem OpenQuery-Parameter."""
    def hole(name):
        if not zellname_vorhanden(doc, name):
            n, p = finde_oq_parameter(doc, name)
            if p is not None and p["typ"] in PARAM_ABFRAGE:
                return abfrage_parameter_wert(p["typ"], p["wert"], n)
            if p is not None:
                try:
                    return parse_param_wert(p["typ"], p["wert"])[0]
                except ValueError as ex:
                    raise E.FormelFehler("Parameter '%s': %s" % (name, str(ex).split("\n")[0]))
        wert = tabelle_aus_bereich(doc, parameter_bereich(doc, name)).zeilen[0][0]
        if wert is None:
            raise E.FormelFehler("Parameter '%s': Die Zelle ist leer" % name)
        if isinstance(wert, E.FehlerWert):
            raise E.FormelFehler("Parameter '%s': Die Zelle enthält einen Fehler (%s)" % (name, wert))
        return wert
    return hole


def parameter_liste(doc):
    """[(Name, Anzeigewert)] aller Parameter dieser Datei: benannte Einzelzellen und OpenQuery-Parameter."""
    out = []
    try:
        nr = doc.NamedRanges
        for n in sorted(nr.getElementNames(), key=str.casefold):
            try:
                ref = parameter_bereich(doc, n)
                out.append((n, ref.getCellByPosition(0, 0).getString()))
            except Exception:
                continue
    except Exception:
        pass
    zellen = {n.casefold() for n, _ in out}
    for n, p in sorted(lies_oq_parameter(doc).items(), key=lambda kv: kv[0].casefold()):
        if n.casefold() not in zellen:
            out.append((n, "%s   [OpenQuery]" % p["wert"]))
    return sorted(out, key=lambda x: x[0].casefold())


def parameter_namen(doc, nur_janein=False):
    """Namen der Parameter dieser Datei (für Auswahllisten in Schrittdialogen); nur_janein: nur Ja/Nein-fähige."""
    if doc is None:
        return []
    try:
        liste = parameter_liste(doc)
    except Exception:
        return []
    if not nur_janein:
        return [n for n, _ in liste]
    oq = lies_oq_parameter(doc)
    out = []
    for n, w in liste:
        p = oq.get(n)
        if p is not None and not zellname_vorhanden(doc, n):
            if p["typ"] == "janein":
                out.append(n)
        else:
            try:
                E.parse_bool(str(w).split("   [")[0])
                out.append(n)
            except Exception:
                pass
    return out


def parameter_aus_abfrage(doc, abfrage_name):
    """Namen der Parameter, die ihren Wert aus der Abfrage abfrage_name holen."""
    ziel = str(abfrage_name).casefold()
    return sorted((n for n, p in lies_oq_parameter(doc).items()
                   if (p["typ"] in PARAM_ABFRAGE and teile_abfrage_angabe(p["wert"])[0].casefold() == ziel)
                   or ((p.get("vorschlag") or {}).get("art") == "abfrage"
                       and teile_abfrage_angabe(p["vorschlag"].get("wert"))[0].casefold() == ziel)),
                  key=str.casefold)


def parameter_abfrage_umbenennen(doc, alt, neu):
    """Parameter „aus Abfrage“, die auf die Abfrage alt zeigen, auf den neuen Namen umstellen."""
    try:
        for n in parameter_aus_abfrage(doc, alt):
            p = lies_oq_parameter(doc)[n]
            if p["typ"] in PARAM_ABFRAGE and teile_abfrage_angabe(p["wert"])[0].casefold() == str(alt).casefold():
                _, sp = teile_abfrage_angabe(p["wert"])
                p["wert"] = neu + ("[%s]" % sp if sp else "")
            v = p.get("vorschlag") or {}
            if v.get("art") == "abfrage" and teile_abfrage_angabe(v.get("wert"))[0].casefold() == str(alt).casefold():
                _, sp = teile_abfrage_angabe(v["wert"])
                v["wert"] = neu + ("[%s]" % sp if sp else "")
            speichere_oq_parameter(doc, n, p)
    except Exception:
        traceback.print_exc()


def parameter_verwendung(doc, name):
    """Namen der gespeicherten Abfragen, die {name} im Text haben."""
    marke = "{%s}" % name
    bed = []                                       # Schritt-Bedingung, Quelle „Liste“, Filter „Werte aus Parameter“
    for k in ("parameter", "listenparameter"):
        bed += ['"%s": %s' % (k, json.dumps(name)), '"%s": %s' % (k, json.dumps(name, ensure_ascii=False))]
    return sorted(n for n, t in gespeicherte_abfragen(doc).items()
                  if marke.casefold() in t.casefold() or any(b.casefold() in t.casefold() for b in bed))


def pruefe_param_name(doc, name, alt=None):
    """Gültiger neuer Parametername? Wirft ValueError mit Meldung. ``alt`` = bisheriger Name beim Ändern."""
    n = (name or "").strip()
    if not n:
        raise ValueError("Bitte einen Namen angeben.")
    if re.search(r'[{}\[\];"]', n):
        raise ValueError("Der Name darf keine Zeichen aus { } [ ] ; \" enthalten.")
    if zellname_vorhanden(doc, n):
        raise ValueError("In dieser Datei gibt es schon eine benannte Zelle oder einen benannten Bereich „%s“. "
                         "Die Zelle hätte immer Vorrang. Bitte einen anderen Namen wählen (z. B. p_%s)." % (n, n))
    for k in lies_oq_parameter(doc):
        if k.casefold() == n.casefold() and (alt is None or k.casefold() != alt.casefold()):
            raise ValueError("Einen Parameter „%s“ gibt es schon." % k)
    return n


VORSCHLAG_ARTEN = [("keine", "(keine – freie Eingabe)"), ("liste", "Feste Liste (mit ; getrennt)"),
                   ("abfrage", "Werte aus einer Abfrage (Spalte)")]
VORSCHLAG_TYPEN = ("text", "zahl", "datum", "datumzeit")      # nur hier macht eine Auswahlliste Sinn


def vorschlag_werte(ctx, doc, v, pname=""):
    """Vorschlagswerte eines Parameters -> Liste von Texten. Wirft ValueError mit verständlicher Meldung."""
    if not v or v.get("art") not in ("liste", "abfrage"):
        return []
    if v["art"] == "liste":
        teile, gesehen = [], set()
        for x in str(v.get("wert") or "").split(";"):
            x = x.strip()
            if x and x.casefold() not in gesehen:
                gesehen.add(x.casefold())
                teile.append(x)
        return teile
    if not teile_abfrage_angabe(v.get("wert"))[0]:
        raise ValueError("Bitte den Namen einer Abfrage angeben, z. B. Standorte[Name].")
    if teile_abfrage_angabe(v["wert"])[0] not in abfragen_texte(doc):
        raise ValueError("Die Abfrage „%s“ gibt es in dieser Datei nicht (sie muss gespeichert sein)."
                         % teile_abfrage_angabe(v["wert"])[0])
    if E.AUFLOESER.get("fn") is None:
        setze_aufloeser(ctx, doc)
    try:
        return abfrage_parameter_wert("abfrage_liste", v["wert"], pname or "Vorschlag").split(";")
    except E.FormelFehler as ex:
        raise ValueError(str(ex.args[0] if ex.args else ex))


_LETZTER_PARAM_DLG = {}      # nur für Tests: zuletzt geöffneter Dialog „Neuer Parameter“


class ParamForm:
    """Formular für einen Parameter (Name, Typ, Wert, Vorschläge, Beschreibung). Wird im Einzeldialog
    (parameter_bearbeiten) und in der Parameterverwaltung benutzt. Die Elemente heißen in beiden gleich."""

    HOEHE = 148          # Höhe des Formulars in Dialogeinheiten

    def __init__(self, ctx, doc, d, x0, y0, breite, alt=None):
        self.ctx, self.doc, self.d, self.alt = ctx, doc, d, alt
        p0 = lies_oq_parameter(doc).get(alt) if alt else None
        v0 = (p0 or {}).get("vorschlag") or {}
        self.typen = [k for k, _ in PARAM_TYPEN]
        self.varten = [k for k, _ in VORSCHLAG_ARTEN]
        fx, fw = x0 + 64, max(breite - 72, 60)
        self.vorrat = {"werte": [], "fehler": ""}
        self.fx, self.fw, self.y0 = fx, fw, y0
        d.add("FixedText", "l1", x0, y0 + 2, 60, 10, Label="Name:")
        d.add("Edit", "name", fx, y0, fw, 12, Text=alt or "")
        d.add("FixedText", "l2", x0, y0 + 20, 60, 10, Label="Typ:")
        d.add("ListBox", "typ", fx, y0 + 18, fw, 12, Dropdown=True, LineCount=6)
        setze_liste(d.ctrl("typ").getModel(), [t for _, t in PARAM_TYPEN],
                    [self.typen.index(p0["typ"]) if p0 and p0["typ"] in self.typen else 0])
        d.add("FixedText", "l3", x0, y0 + 38, 60, 10, Label="Wert:")
        d.add("Edit", "wert", fx, y0 + 36, fw, 12, Text=(p0 or {}).get("wert", ""))
        d.add("ListBox", "wertwahl", -3000, y0 + 36, fw, 12, Dropdown=True, LineCount=12)   # mit Vorschlagswerten statt „wert“
        d.add("FixedText", "hinweis", fx, y0 + 50, fw, 10, Label="", TextColor=0x606060)
        d.add("FixedText", "l6", x0, y0 + 68, 60, 10, Label="Vorschläge:")
        d.add("ListBox", "vart", fx, y0 + 66, fw, 12, Dropdown=True, LineCount=4)
        setze_liste(d.ctrl("vart").getModel(), [t for _, t in VORSCHLAG_ARTEN],
                    [self.varten.index(v0["art"]) if v0.get("art") in self.varten else 0])
        d.add("FixedText", "l7", x0, y0 + 84, 62, 10, Label="Liste / Abfrage:")
        d.add("Edit", "vtext", fx, y0 + 82, fw - 52, 12, Text=v0.get("wert", ""))
        d.add("Button", "vlade", fx + fw - 48, y0 + 82, 48, 12, Label="Laden")
        d.add("FixedText", "vhinweis", fx, y0 + 96, fw, 10, Label="", TextColor=0x606060)
        d.add("FixedText", "l4", x0, y0 + 114, 60, 10, Label="Beschreibung:")
        d.add("Edit", "besch", fx, y0 + 112, fw, 12, Text=(p0 or {}).get("beschreibung", ""))
        d.add("FixedText", "l5", x0, y0 + 130, breite - 8, 20, MultiLine=True, TextColor=0x606060,
              Label="Benutzung: {Name} in Textfeldern, Formeln und im Dateipfad. Eine benannte Zelle gleichen Namens hätte Vorrang.")
        d.on_select("typ", self.umschalten)
        d.on_select("vart", self.umschalten)
        d.on_select("wertwahl", self.wahl_uebernehmen)
        d.on_click("vlade", self.laden)
        self.umschalten()
        self.stand = self.zustand()

    # -- Zustand ------------------------------------------------------------------------------------------------
    def typ_aktuell(self):
        return self.typen[max(sel_pos(self.d.ctrl("typ")), 0)]

    def vart_aktuell(self):
        return self.varten[max(sel_pos(self.d.ctrl("vart")), 0)]

    def vorschlag_aktuell(self):
        art = self.vart_aktuell()
        if art == "keine" or self.typ_aktuell() not in VORSCHLAG_TYPEN:
            return None
        return {"art": art, "wert": self.d.ctrl("vtext").getText().strip()}

    def wert_text(self):
        """Der gewählte/eingetippte Wert (aus der Auswahlliste, wenn Vorschläge aktiv sind)."""
        if self.vorrat["werte"] and self.vorschlag_aktuell():
            i = sel_pos(self.d.ctrl("wertwahl"))
            if 0 <= i < len(self.vorrat["werte"]):
                return self.vorrat["werte"][i]
        return self.d.ctrl("wert").getText()

    def zustand(self):
        d = self.d
        return (d.ctrl("name").getText().strip(), self.typ_aktuell(), self.wert_text(), d.ctrl("besch").getText().strip(),
                self.vart_aktuell(), d.ctrl("vtext").getText().strip())

    def geaendert(self):
        return self.zustand() != self.stand

    # -- Verhalten ----------------------------------------------------------------------------------------------
    def laden(self, *_):
        """Vorschlagswerte lesen und das Feld „Wert“ zur Auswahlliste machen (oder zurück zur freien Eingabe)."""
        d, vorrat = self.d, self.vorrat
        v = self.vorschlag_aktuell()
        vorrat["werte"], vorrat["fehler"] = [], ""
        if v is not None:
            try:
                vorrat["werte"] = vorschlag_werte(self.ctx, self.doc, v, d.ctrl("name").getText().strip())
                if not vorrat["werte"]:
                    vorrat["fehler"] = "Keine Vorschlagswerte gefunden."
            except ValueError as ex:
                vorrat["fehler"] = str(ex).split("\n")[0]
        aktiv = bool(vorrat["werte"])
        akt = d.ctrl("wert").getText().strip()
        d.platziere("wert", -3000 if aktiv else self.fx, self.y0 + 36, self.fw, 12)
        d.platziere("wertwahl", self.fx if aktiv else -3000, self.y0 + 36, self.fw, 12)
        if aktiv:
            gesucht = [x.casefold() for x in vorrat["werte"]]
            setze_liste(d.ctrl("wertwahl").getModel(), vorrat["werte"],
                        [gesucht.index(akt.casefold())] if akt.casefold() in gesucht else [])
            d.ctrl("vhinweis").getModel().Label = "%d Vorschläge geladen%s" % (
                len(vorrat["werte"]), "" if not akt or akt.casefold() in gesucht
                else "; der bisherige Wert „%s“ steht nicht darin" % akt[:30])
        else:
            d.ctrl("vhinweis").getModel().Label = vorrat["fehler"] if v is not None else ""

    def wahl_uebernehmen(self, *_):
        i = sel_pos(self.d.ctrl("wertwahl"))
        if 0 <= i < len(self.vorrat["werte"]):
            self.d.ctrl("wert").getModel().Text = self.vorrat["werte"][i]

    def umschalten(self, *_):
        d = self.d
        typ = self.typ_aktuell()
        d.ctrl("hinweis").getModel().Label = PARAM_HINWEIS[typ]
        ok_typ = typ in VORSCHLAG_TYPEN
        d.ctrl("vart").getModel().Enabled = ok_typ
        d.ctrl("vtext").getModel().Enabled = ok_typ and self.vart_aktuell() != "keine"
        d.ctrl("vlade").getModel().Enabled = ok_typ and self.vart_aktuell() != "keine"
        self.laden()

    def befuellen(self, alt):
        """Formular mit einem gespeicherten Parameter füllen (alt = None: leeres Formular für einen neuen)."""
        d = self.d
        p0 = lies_oq_parameter(self.doc).get(alt) if alt else None
        v0 = (p0 or {}).get("vorschlag") or {}
        self.alt = alt
        d.ctrl("name").getModel().Text = alt or ""
        d.ctrl("typ").selectItemPos(self.typen.index(p0["typ"]) if p0 and p0["typ"] in self.typen else 0, True)
        d.ctrl("wert").getModel().Text = (p0 or {}).get("wert", "")
        d.ctrl("besch").getModel().Text = (p0 or {}).get("beschreibung", "")
        d.ctrl("vtext").getModel().Text = v0.get("wert", "")
        d.ctrl("vart").selectItemPos(self.varten.index(v0["art"]) if v0.get("art") in self.varten else 0, True)
        self.umschalten()
        self.stand = self.zustand()

    def lesen(self, parent):
        """Prüft das Formular. Gibt (name, parameter) zurück, None bei Abbruch (Meldung wurde gezeigt oder Rückfrage verneint)."""
        ctx, d = self.ctx, self.d
        typ = self.typ_aktuell()
        try:
            n = pruefe_param_name(self.doc, d.ctrl("name").getText(), self.alt)
            v = self.vorschlag_aktuell()
            if v is not None:
                if not v["wert"]:
                    raise ValueError("Bitte die Vorschlagsliste angeben (Werte mit ; getrennt bzw. Abfragename).")
                self.laden()                                        # Liste ist jetzt aktuell
                if self.vorrat["fehler"] and not self.vorrat["werte"]:
                    raise ValueError("Vorschläge: %s" % self.vorrat["fehler"])
            _, text = parse_param_wert(typ, self.wert_text())
            if typ in PARAM_ABFRAGE and teile_abfrage_angabe(text)[0] not in abfragen_texte(self.doc):
                raise ValueError("Die Abfrage „%s“ gibt es in dieser Datei nicht (sie muss gespeichert sein)."
                                 % teile_abfrage_angabe(text)[0])
        except ValueError as ex:
            meldung(ctx, parent, str(ex), "WARNINGBOX")
            return None
        if v is not None and text.casefold() not in [x.casefold() for x in self.vorrat["werte"]]:
            if meldung(ctx, parent, "Der Wert „%s“ steht nicht in der Vorschlagsliste.\n\nTrotzdem speichern?" % text[:40],
                       "QUERYBOX", 3) != 2:
                return None
        neu = {"typ": typ, "wert": text, "beschreibung": d.ctrl("besch").getText().strip()}
        if v is not None:
            neu["vorschlag"] = v
        return n, neu

    def speichern(self, parent):
        """Prüfen und speichern (bei Umbenennung wird der alte Name entfernt). Gibt den Namen zurück oder None."""
        erg = self.lesen(parent)
        if erg is None:
            return None
        n, neu = erg
        if self.alt and self.alt != n:
            loesche_oq_parameter(self.doc, self.alt)
        speichere_oq_parameter(self.doc, n, neu)
        self.alt = n
        self.stand = self.zustand()
        return n


def _auto_ok(d, fn):
    """Testbetrieb: simuliert nach ABFRAGE_AUTOOK Sekunden den Klick auf OK."""
    auto_ok = os.environ.get("ABFRAGE_AUTOOK")
    if auto_ok:
        t_ = threading.Timer(float(auto_ok), _sicher(fn))
        t_.daemon = True
        t_.start()


def parameter_bearbeiten(ctx, doc, parent, alt=None):
    """Dialog Neu/Ändern für einen Parameter. Gibt den gespeicherten Namen zurück oder None."""
    d = Dlg(ctx, "Parameter ändern" if alt else "Neuer Parameter", 280, 188)
    _LETZTER_PARAM_DLG["d"] = d
    form = ParamForm(ctx, doc, d, 8, 8, 272, alt)
    d.add("Button", "ok", 138, 168, 66, 14, Label="OK", DefaultButton=True)
    d.add("Button", "abbr", 208, 168, 64, 14, Label="Abbrechen")
    res = {"name": None}

    def ok():
        n = form.speichern(d.peer())
        if n is not None:
            res["name"] = n
            d.schliessen(1)
    d.on_click("ok", ok)
    d.on_click("abbr", lambda: d.schliessen(0))
    _auto_ok(d, ok)
    d.zeigen(parent)
    d.weg()
    return res["name"]


class ParameterDialog:
    """Parameter verwalten – aufgebaut wie „Parameter verwalten“ in Power Query: links „Neu“ und die Liste der Parameter,
    rechts das Formular zum gewählten Parameter."""

    def __init__(self, ctx, doc, parent=None, wahl=None):
        self.ctx, self.doc, self.parent, self.wahl = ctx, doc, parent, wahl

    def _zeilen(self):
        namen = sorted(lies_oq_parameter(self.doc), key=str.casefold)
        ps = lies_oq_parameter(self.doc)
        typ_t = dict(PARAM_TYPEN)
        return namen, ["%s   [%s]   =   %s%s" % (n, typ_t.get(ps[n]["typ"], ps[n]["typ"]), ps[n]["wert"],
                                                 ("   –   " + ps[n]["beschreibung"]) if ps[n]["beschreibung"] else "") for n in namen]

    def zeigen(self):
        ctx = self.ctx
        d = Dlg(ctx, "Parameter verwalten", 450, 196)
        self.d = d
        self.form = None
        d.add("Button", "neu", 8, 8, 110, 14, Label="Neu")
        d.add("ListBox", "lst", 8, 26, 110, 136)
        d.add("FixedText", "trenn", 124, 8, 1, 154, BackgroundColor=TRENNLINIE)
        self.namen = []
        self._still = False
        form = ParamForm(ctx, self.doc, d, 132, 8, 312, None)
        self.form = form
        d.add("Button", "uebern", 132, 166, 74, 14, Label="Übernehmen", HelpText="Den Parameter mit den Eingaben rechts speichern")
        d.add("Button", "weg", 210, 166, 66, 14, Label="Löschen")
        d.add("Button", "zu", 378, 166, 66, 14, Label="Schließen", DefaultButton=True)
        self.aendern_ = lambda: self.uebernehmen()

        def aktuell():
            i = sel_pos(d.ctrl("lst"))
            return self.namen[i] if 0 <= i < len(self.namen) else None
        self.aktuell = aktuell

        def fuellen(wahl=None):
            self.namen, texte = self._zeilen()
            self._still = True
            try:
                setze_liste(d.ctrl("lst").getModel(), [n for n in self.namen],
                            [self.namen.index(wahl)] if wahl in self.namen else ([0] if texte and wahl is None else []))
            finally:
                self._still = False
            a = aktuell()
            if a is not None or wahl is None:
                form.befuellen(a)
        self.fuellen = fuellen

        def frage_aenderungen():
            """Wurde das Formular geändert? Dann Rückfrage. True = weitermachen."""
            if not form.geaendert() or not form.zustand()[0]:
                return True
            w = meldung(ctx, d.peer(), "Änderungen an „%s“ übernehmen?" % (form.zustand()[0]), "QUERYBOX", 3)
            if w == 2:
                return form.speichern(d.peer()) is not None
            return True

        def gewaehlt(*_):
            if self._still:
                return
            if not frage_aenderungen():
                if form.alt in self.namen:                         # Auswahl zurücksetzen
                    self._still = True
                    try:
                        d.ctrl("lst").selectItemPos(self.namen.index(form.alt), True)
                    finally:
                        self._still = False
                return
            form.befuellen(aktuell())
        d.on_select("lst", gewaehlt)

        def neu():
            if not frage_aenderungen():
                return
            self._still = True
            try:
                setze_liste(d.ctrl("lst").getModel(), self.namen, [])
            finally:
                self._still = False
            form.befuellen(None)
            d.ctrl("name").setFocus()
        self.neu = neu

        def uebernehmen():
            n = form.speichern(d.peer())
            if n is not None:
                fuellen(n)
                form.stand = form.zustand()
        self.uebernehmen = uebernehmen

        def loeschen():
            a = form.alt if form.alt else aktuell()
            if a is None:
                return
            benutzt = parameter_verwendung(self.doc, a)
            text = "Parameter „%s“ löschen?" % a
            if benutzt:
                text += "\n\nEr wird noch verwendet in: %s.\nDiese Abfragen melden danach einen Fehler, bis du den Parameter ersetzt." % ", ".join(benutzt)
            if meldung(ctx, d.peer(), text, "QUERYBOX", 3) == 2:
                loesche_oq_parameter(self.doc, a)
                fuellen()
        self.loeschen = loeschen

        def schliessen():
            if frage_aenderungen():
                d.schliessen(0)
        d.on_click("neu", neu)
        d.on_click("uebern", uebernehmen)
        d.on_click("weg", loeschen)
        d.on_click("zu", schliessen)
        fuellen(self.wahl if self.wahl in lies_oq_parameter(self.doc) else None)
        d.zeigen(self.parent)
        d.weg()


def befehl_parameter(ctx, frame, doc):
    if not ist_calc(doc):
        return
    ParameterDialog(ctx, doc, _parent(frame)).zeigen()


# --- Selbstreferenz: letzter Stand der eigenen Ausgabe ------------------------------------------------------------------
def lies_eigenen_stand(doc, abfrage):
    """Letzter Ausgabestand dieser Abfrage im Blatt als Tabelle (Kopfzeile = Spaltennamen); None, wenn es noch keinen gibt."""
    z = abfrage.ziel or {}
    if z.get("art") == "keine":
        raise E.FormelFehler("Manuelle Spalten behalten braucht eine Ausgabe im Blatt (nicht „Nur Verbindung“)")
    rng = None
    try:
        sheets = doc.getSheets()
        b = z.get("bereich")
        if b and doc.DatabaseRanges.hasByName(b):
            ad = doc.DatabaseRanges.getByName(b).getDataArea()
            rng = sheets.getByIndex(ad.Sheet).getCellRangeByPosition(ad.StartColumn, ad.StartRow, ad.EndColumn, ad.EndRow)
        elif z.get("art") == "zelle":
            if z.get("letzter") and z.get("letzter_blatt") and sheets.hasByName(z["letzter_blatt"]):
                rng = sheets.getByName(z["letzter_blatt"]).getCellRangeByName(z["letzter"])
        else:
            name = gueltiger_blattname(abfrage.name)
            if sheets.hasByName(name):
                sh = sheets.getByName(name)
                cur = sh.createCursor()
                cur.gotoEndOfUsedArea(False)
                ra = cur.getRangeAddress()
                st = sh.getCellRangeByName(z.get("zelle") or "A1").getRangeAddress()
                rng = sh.getCellRangeByPosition(st.StartColumn, st.StartRow, ra.EndColumn, ra.EndRow)
    except Exception:
        traceback.print_exc()
        return None
    if rng is None:
        return None
    t = tabelle_aus_bereich(doc, rng)
    if not t.zeilen:
        return None
    kopf = [E.als_text(c) for c in t.zeilen[0]]
    if not any(kopf):
        return None
    return E.Tabelle(E.eindeutige_namen(kopf), t.zeilen[1:])


def _hand_schritt(abfrage):
    return next((x for x in abfrage.schritte if x.get("op") == "hand_behalten" and x.get("aktiv", True) is not False), None)


def _formel_parser(doc):
    p = doc.createInstance("com.sun.star.sheet.FormulaParser")
    p.CompileEnglish = True
    p.FormulaConvention = uno.getConstantByName("com.sun.star.sheet.AddressConvention.OOO")
    return p


def _formel_um(p, text, von, nach):
    """Formeltext, der in Zelle `von` (Blatt, Spalte, Zeile) steht, so wie er in Zelle `nach` stehen müsste:
    relative Bezüge wandern mit (wie beim Kopieren), absolute ($A$1) bleiben."""
    from com.sun.star.table import CellAddress
    tok = p.parseFormula(text, CellAddress(*von))
    return "=" + p.printFormula(tok, CellAddress(*nach))


def erkenne_formelspalten(doc, sh, c0, r0, c1, r1, kopf, st):
    """Manuelle Spalten, in denen in JEDER Zeile dieselbe (zeilenrelative) Formel steht, sind Formelspalten:
    die Formel wird im Schritt gemerkt und beim Aktualisieren für alle Zeilen neu eingetragen.
    Gemischte Spalten (Formeln und Werte, verschiedene Formeln) bleiben Wertespalten."""
    manuell = {x.strip().casefold() for x in str(st.get("handspalten") or "").splitlines() if x.strip()}
    formeln = dict(st.get("formeln") or {})
    if r1 > r0:
        p = _formel_parser(doc)
        idx = sh.RangeAddress.Sheet
        zeilen = list(range(r0 + 1, r1 + 1))
        if len(zeilen) > 3000:                                    # sehr lange Tabellen: Stichprobe + Anfang/Ende
            schritt = len(zeilen) // 200
            zeilen = sorted(set(zeilen[::schritt] + [zeilen[0], zeilen[-1]]))
        for j, n in enumerate(kopf):
            if n.strip().casefold() not in manuell:
                continue
            col = c0 + j
            alle = [a[0] for a in sh.getCellRangeByPosition(col, r0 + 1, col, r1).getFormulaArray()]
            if not any(t != "" for t in alle):
                continue                                          # ganz leer: bisherigen Stand beibehalten
            if not all(isinstance(t, str) and t.startswith("=") for t in alle):
                formeln.pop(n, None)                              # Werte oder gemischt -> Wertespalte
                continue
            try:
                norm = {_formel_um(p, alle[z - r0 - 1], (idx, col, z), (idx, col, r0 + 1)) for z in zeilen}
            except Exception:
                traceback.print_exc()
                formeln.pop(n, None)
                continue
            if len(norm) == 1:
                formeln[n] = {"f": norm.pop(), "c": col, "r": r0 + 1}
            else:
                formeln.pop(n, None)                              # verschiedene Formeln -> Wertespalte
    if formeln:
        st["formeln"] = formeln
    else:
        st.pop("formeln", None)


_FORMAT_EIGENSCHAFTEN = ("CharColor", "CharFontName", "CharHeight", "CharWeight", "CharUnderline", "CellBackColor")


def lies_spaltenformat(doc, zelle):
    """Zellformat einer manuellen Spalte (Zahlenformat, Schrift, Farben) als dict; nur, was vom Standard-Zellenformat
    abweicht. Leeres dict = Standard."""
    try:
        std = doc.getStyleFamilies().getByName("CellStyles").getByName("Default")
    except Exception:
        std = None
    d = {}
    for pn in _FORMAT_EIGENSCHAFTEN:
        try:
            v = zelle.getPropertyValue(pn)
            if std is None or v != std.getPropertyValue(pn):
                d[pn] = v
        except Exception:
            pass
    try:
        slant = zelle.getPropertyValue("CharPosture").value
        if std is None or slant != std.getPropertyValue("CharPosture").value:
            d["CharPosture"] = slant
    except Exception:
        pass
    try:
        key = zelle.getPropertyValue("NumberFormat")
        if std is None or key != std.getPropertyValue("NumberFormat"):
            f = doc.getNumberFormats().getByKey(key)
            loc = f.Locale
            d["zf"] = f.FormatString
            d["zl"] = [loc.Language, loc.Country, loc.Variant]
    except Exception:
        pass
    return d


def setze_spaltenformat(doc, bereich, d):
    from com.sun.star.lang import Locale
    for pn in _FORMAT_EIGENSCHAFTEN:
        if pn in d:
            try:
                bereich.setPropertyValue(pn, d[pn])
            except Exception:
                pass
    if "CharPosture" in d:
        try:
            bereich.setPropertyValue("CharPosture", uno.Enum("com.sun.star.awt.FontSlant", d["CharPosture"]))
        except Exception:
            pass
    if d.get("zf"):
        try:
            nf = doc.getNumberFormats()
            loc = Locale(*(d.get("zl") or ["de", "DE", ""]))
            key = nf.queryKey(d["zf"], loc, False)
            if key == -1:
                key = nf.addNew(d["zf"], loc)
            bereich.setPropertyValue("NumberFormat", key)
        except Exception:
            traceback.print_exc()


def erkenne_spaltenformate(doc, sh, c0, r0, c1, r1, kopf, st):
    """Zahlenformat, Schrift und Farben der manuellen Spalten (aus der ersten Datenzeile) im Schritt merken, damit sie
    beim Neuschreiben der Tabelle wieder angewendet werden. Spalten ohne besondere Formatierung bleiben ohne Eintrag."""
    manuell = {x.strip().casefold() for x in str(st.get("handspalten") or "").splitlines() if x.strip()}
    formate = dict(st.get("formate") or {})
    if r1 > r0:
        for j, n in enumerate(kopf):
            if n.strip().casefold() not in manuell:
                continue
            d = lies_spaltenformat(doc, sh.getCellByPosition(c0 + j, r0 + 1))
            if d:
                formate[n] = d
            else:
                formate.pop(n, None)
    if formate:
        st["formate"] = formate
    else:
        st.pop("formate", None)


def schreibe_spaltenformate(doc, sh, tab, st, c0, r0, c1, r1):
    """Gemerkte Formate der manuellen Spalten auf alle Datenzeilen der frisch geschriebenen Tabelle anwenden."""
    formate = st.get("formate") or {}
    if not formate or r1 <= r0:
        return
    for name, d in formate.items():
        if name not in tab.spalten:
            continue
        col = c0 + tab.idx(name)
        setze_spaltenformat(doc, sh.getCellRangeByPosition(col, r0 + 1, col, r1), d)


def schreibe_formelspalten(doc, sh, tab, st, c0, r0, c1, r1):
    """Formelspalten für alle Zeilen der frisch geschriebenen Tabelle eintragen (zeilenrelativ angepasst)."""
    formeln = st.get("formeln") or {}
    if not formeln or r1 <= r0:
        return
    from com.sun.star.sheet.FillDirection import TO_BOTTOM
    p = _formel_parser(doc)
    idx = sh.RangeAddress.Sheet
    for name, t in formeln.items():
        if name not in tab.spalten:
            continue
        col = c0 + tab.idx(name)
        try:
            sh.getCellByPosition(col, r0 + 1).setFormula(_formel_um(p, t["f"], (idx, t["c"], t["r"]), (idx, col, r0 + 1)))
            if r1 > r0 + 1:
                sh.getCellRangeByPosition(col, r0 + 1, col, r1).fillAuto(TO_BOTTOM, 1)
        except Exception:
            traceback.print_exc()


def uebernehme_neue_spalten(doc, abfrage):
    """Spalten, die in der Tabelle im Blatt dazugekommen sind, als manuelle Spalten übernehmen: Spalten innerhalb des
    Tabellenbereichs immer, rechts angrenzende nur mit dem Häkchen im Schritt „Manuelle Spalten behalten“.
    Fehlende Überschriften werden zu „SpalteN“ (N = Position in der Tabelle), doppelte zu „Name (2)“ usw.
    Die Überschrift wird sofort im Blatt geändert und der Name im Schritt ergänzt. -> Liste der neuen Namen."""
    z = abfrage.ziel if isinstance(abfrage.ziel, dict) else {}
    if doc is None or z.get("art") == "keine" or not z.get("spalten"):
        return []
    st = next((x for x in abfrage.schritte if x.get("op") == "hand_behalten" and x.get("aktiv", True) is not False), None)
    if st is None:
        return []
    ad = _bereichs_adresse(doc, z.get("bereich"))
    if ad is None:
        return []
    _, idx, c0, r0, c1, r1 = ad
    sh = doc.getSheets().getByIndex(idx)
    db = doc.DatabaseRanges.getByName(z["bereich"])
    if st.get("auto_neu"):
        fremd = [f for f in _fremde_bereiche(doc, z["bereich"]) if f[1] == idx]
        while c1 < 1000:
            c = c1 + 1
            if any(not (c < f[2] or c > f[4] or r1 < f[3] or r0 > f[5]) for f in fremd):
                break                                   # nie in eine andere Tabelle hinein
            if not _inhalt_adressen(sh, c, r0, c, r1):
                break
            c1 = c
        if c1 != ad[4]:
            db.setDataArea(sh.getCellRangeByPosition(c0, r0, c1, r1).getRangeAddress())
    # ganz leere Spalten am rechten Rand zählen nicht zur Tabelle (z. B. zu weit geratener Bereich)
    belegt = [a.EndColumn for a in _inhalt_adressen(sh, c0, r0, c1, r1)]
    c_letzte = max(belegt) if belegt else c0
    if c_letzte < c1:
        c1 = c_letzte
        db.setDataArea(sh.getCellRangeByPosition(c0, r0, c1, r1).getRangeAddress())
    kopf = [E.als_text(v).strip() for v in sh.getCellRangeByPosition(c0, r0, c1, r0).getDataArray()[0]]
    bekannt = {str(n).casefold() for n in z["spalten"]}
    alle = {k.casefold() for k in kopf if k} | bekannt
    gesehen, neu = set(), []
    for j, n in enumerate(kopf):
        low = n.casefold()
        if low and low in bekannt and low not in gesehen:
            gesehen.add(low)                            # bekannte Spalte der Abfrage
            continue
        if n and low not in gesehen and low not in bekannt:
            name = n                                    # neue Spalte mit eigener, noch freier Überschrift
        else:                                           # leer oder doppelt: eindeutigen Namen bilden
            basis = n or "Spalte%d" % (j + 1)
            name, k = basis, 2
            while name.casefold() in alle or name.casefold() in gesehen:
                name = "%s (%d)" % (basis, k)
                k += 1
        alle.add(name.casefold())
        gesehen.add(name.casefold())
        if name != n:
            sh.getCellByPosition(c0 + j, r0).String = name
        kopf[j] = name
        neu.append(name)
    if neu:
        vorhandene = [x.strip() for x in str(st.get("handspalten") or "").splitlines() if x.strip()]
        low = {x.casefold() for x in vorhandene}
        st["handspalten"] = "\n".join(vorhandene + [n for n in neu if n.casefold() not in low])
    try:
        erkenne_formelspalten(doc, sh, c0, r0, c1, r1, kopf, st)
    except Exception:
        traceback.print_exc()
    try:
        erkenne_spaltenformate(doc, sh, c0, r0, c1, r1, kopf, st)
    except Exception:
        traceback.print_exc()
    return neu


def andere_abfragen(doc, eigen=None):
    return sorted(n for n in abfragen_texte(doc) if n != eigen)


_EDITOR_KONTEXT = {"doc": None, "eigen": None}      # vom Editor gesetzt; die Tabellen-Dialoge lesen ihn


class HandGeaendert(E.FormelFehler):
    """Die Ausgabetabelle wurde von Hand geändert; Aktualisieren würde die Änderungen überschreiben."""


def aktualisiere_abfrage(ctx, doc, abfrage, trotzdem=False):
    """Quelle neu lesen, Schritte anwenden, Ziel ersetzen. Gibt die Zeilenzahl zurück.
    trotzdem=False: wurde die Ausgabetabelle von Hand geändert, wird HandGeaendert geworfen (nichts wird überschrieben)."""
    if not trotzdem and hand_geaendert(doc, abfrage):
        raise HandGeaendert("Die Ausgabetabelle wurde seit dem letzten Laden von Hand geändert und deshalb nicht aktualisiert. "
                            "Beim Aktualisieren würden diese Änderungen überschrieben.")
    setze_aufloeser(ctx, doc, abfrage.name, abfrage)
    E.HINWEISE[:] = []
    vorher = abfrage.to_json()
    uebernehme_neue_spalten(doc, abfrage)
    if abfrage.to_json() != vorher:
        speichere_abfrage(doc, abfrage)        # neue manuelle Spalten/Formelspalten gleich festhalten, auch wenn der Lauf scheitert
    roh = lies_quelle(ctx, doc, abfrage.quelle)
    tab = E.fuehre_aus(roh, abfrage.schritte)
    schreibe_ergebnis(doc, tab, abfrage)
    speichere_abfrage(doc, abfrage)        # merkt sich den neuen Ausgabebereich
    return len(tab.zeilen)


# ---------------------------------------------------------------------------
# Dialoge
# ---------------------------------------------------------------------------
def datei_waehlen(ctx, speichern=False, filter_name="Tabellen und Text",
                  muster="*.csv;*.txt;*.tsv;*.xlsx;*.xls;*.ods", vorgabe=None, parent=None, startpfad=None):
    fp = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", ctx)
    fp.initialize((1 if speichern else 0,))
    schluessel = "ordner_speichern" if speichern else "ordner_quelle"
    try:
        ordner = (os.path.dirname(startpfad) if startpfad else "") or lies_einstellung(schluessel, "")
        if ordner and os.path.isdir(ordner):
            fp.setDisplayDirectory(uno.systemPathToFileUrl(ordner))
    except Exception:
        pass
    fp.appendFilter(filter_name, muster)
    fp.appendFilter("Alle Dateien", "*.*")
    fp.setCurrentFilter(filter_name)
    if vorgabe:
        try:
            fp.setDefaultName(vorgabe)
        except Exception:
            pass
    if fp.execute() != 1:
        return None
    files = fp.getSelectedFiles() if hasattr(fp, "getSelectedFiles") else fp.getFiles()
    pfad = uno.fileUrlToSystemPath(files[0]) if files else None
    if pfad:
        schreibe_einstellung(schluessel, os.path.dirname(pfad))          # nächstes Mal dort weitermachen
    return pfad


class QuellenDialog:
    ARTEN = [("blatt", "Tabellenblatt dieses Dokuments"), ("datei", "Datei (CSV, TXT, XLSX, XLS, ODS)"),
             ("ordner", "Ordner (Liste der Dateien)"),
             ("zwischenablage", "Zwischenablage (Text einfügen)"),
             ("abfrage", "Andere Abfrage dieser Datei (auch „Nur Verbindung“)"),
             ("liste", "Liste (Parameter oder eingetippte Werte)")]
    TRENNER = [("auto", "Automatisch erkennen"), (";", "Semikolon ;"), ("\t", "Tabulator"),
               (",", "Komma ,"), ("|", "Senkrechter Strich |")]

    def __init__(self, ctx, doc, quelle=None, parent=None, ausgabe=None, eigen=None, eigen_name=None):
        """ausgabe: {Blattname: Abfragename} der Ausgabeblätter von Abfragen (werden nie vorgewählt);
        eigen: Ausgabeblatt der gerade bearbeiteten Abfrage (wird nicht angeboten);
        eigen_name: Name der gerade bearbeiteten Abfrage (sie selbst wird als Quelle nicht angeboten)."""
        self.eigen_name = eigen_name
        self.ctx, self.doc, self.parent = ctx, doc, parent
        self.q = dict(quelle or {})
        self.ausgabe, self.eigen = dict(ausgabe or {}), eigen
        self.ergebnis = None

    def _blaetter(self):
        """-> (Namen, Anzeigetexte, Vorauswahl) der Tabellenblätter dieses Dokuments."""
        namen, texte = [], []
        try:
            for n in self.doc.getSheets().getElementNames():
                if n == self.eigen:
                    continue
                namen.append(n)
                texte.append(n + ("   (Ausgabe von „%s“)" % self.ausgabe[n] if n in self.ausgabe else ""))
        except Exception:
            pass
        wunsch = self.q.get("blatt")
        if wunsch not in namen:
            wunsch = aktives_blatt_name(self.doc) if self.doc is not None else None
            if wunsch not in namen or wunsch in self.ausgabe:
                frei = [n for n in namen if n not in self.ausgabe]
                wunsch = frei[0] if frei else (namen[0] if namen else None)
        return namen, texte, (namen.index(wunsch) if wunsch in namen else -1)

    def zeigen(self):
        ctx = self.ctx
        d = Dlg(ctx, "Quelle wählen", 300, 192)
        self.d = d
        d.add("FixedText", "l1", 8, 8, 70, 10, Label="Quelle:")
        d.add("ListBox", "art", 80, 6, 212, 12, Dropdown=True, StringItemList=tuple(l for _, l in self.ARTEN),
              LineCount=4)
        d.add("FixedText", "l2", 8, 28, 70, 10, Label="Datei:")
        d.add("Edit", "pfad", 80, 26, 150, 12, Text=self.q.get("pfad", ""))
        d.add("Button", "durch", 234, 26, 58, 12, Label="Suchen…")
        d.add("FixedText", "l3", 8, 46, 70, 10, Label="Trennzeichen (CSV):")
        d.add("ListBox", "trenner", 80, 44, 212, 12, Dropdown=True,
              StringItemList=tuple(l for _, l in self.TRENNER), LineCount=6)
        d.add("FixedText", "l4", 8, 64, 70, 10, Label="Blatt:")
        d.add("Edit", "blatt", -3000, 62, 212, 12, Text=self.q.get("blatt", ""))
        d.add("ListBox", "dateiwahl", -3000, 62, 212, 12, Dropdown=True, LineCount=12)
        d.add("Edit", "vorschau", -3000, 124, 284, 44, MultiLine=True, ReadOnly=True, HScroll=False, VScroll=False)
        d.add("ListBox", "blattwahl", 80, 62, 212, 12, Dropdown=True, LineCount=10)
        blatt_namen, blatt_texte, blatt_vor = self._blaetter()
        setze_liste(d.ctrl("blattwahl").getModel(), blatt_texte, [blatt_vor] if blatt_vor >= 0 else [])
        abf_namen = andere_abfragen(self.doc, self.eigen_name) if self.doc is not None else []
        d.add("ListBox", "abfragewahl", -3000, 62, 212, 12, Dropdown=True, LineCount=10)
        wunsch_abf = self.q.get("name") if self.q.get("name") in abf_namen else None
        setze_liste(d.ctrl("abfragewahl").getModel(), abf_namen,
                    [abf_namen.index(wunsch_abf)] if wunsch_abf else ([0] if abf_namen else []))
        d.add("FixedText", "l5", 8, 82, 70, 10, Label="Bereich, z. B. A1:F500:")
        d.add("Edit", "bereich", 80, 80, 212, 12, Text=self.q.get("bereich", ""))
        d.add("FixedText", "hinweis", 8, 98, 284, 24, MultiLine=True, Label="")
        lp_namen = list(parameter_namen(self.doc)) if self.doc is not None else []
        if self.q.get("parameter") and self.q["parameter"] not in lp_namen:
            lp_namen.append(self.q["parameter"])
        d.add("ListBox", "listewahl", -3000, 62, 212, 12, Dropdown=True, LineCount=10)
        setze_liste(d.ctrl("listewahl").getModel(), ["(Werte unten eintippen)"] + lp_namen,
                    [lp_namen.index(self.q["parameter"]) + 1 if self.q.get("parameter") in lp_namen else 0])
        d.add("Edit", "listespalte", -3000, 80, 212, 12, Text=self.q.get("spalte", "") or "Wert")
        d.add("FixedText", "l6", -3000, 98, 70, 10, Label="Werte (je Zeile):")
        d.add("Edit", "listewerte", -3000, 98, 212, 50, MultiLine=True, VScroll=True,
              Text=str(self.q.get("werte") or ""))
        d.add("Edit", "muster", -3000, 62, 212, 12, Text=self.q.get("muster", "*"))
        gew = self.q.get("spalten") or ORDNER_STANDARD
        for k, (schl, bez) in enumerate(ORDNER_SPALTEN):
            d.add("CheckBox", "sp_" + schl, -3000, 78 + 11 * (k // 4), 52, 10, Label=bez, State=1 if schl in gew else 0)
        d.add("CheckBox", "unter", -3000, 101, 212, 10, Label="Unterordner einbeziehen (alle Ebenen)",
              State=1 if self.q.get("unterordner") else 0)
        d.add("Button", "ok", 150, 174, 70, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", 224, 174, 68, 14, Label="Abbrechen")
        arten = [a for a, _ in self.ARTEN]
        trn = [t for t, _ in self.TRENNER]
        setze_liste(d.ctrl("art").getModel(), [l for _, l in self.ARTEN],
                    [arten.index(self.q.get("art", "blatt")) if self.q.get("art", "blatt") in arten else 0])
        setze_liste(d.ctrl("trenner").getModel(), [l for _, l in self.TRENNER],
                    [trn.index(self.q.get("trenner", "auto")) if self.q.get("trenner", "auto") in trn else 0])

        inhalt = {"pfad": None, "liste": []}

        def datei_lesen(*_):
            """Inhalt der gewählten Datei (Blätter, Tabellen, benannte Bereiche) in die Liste laden."""
            p = d.ctrl("pfad").getText().strip().strip('"')
            trn_ = trn[max(sel_pos(d.ctrl("trenner")), 0)]
            inhalt["pfad"], inhalt["liste"] = (p, trn_), []
            fehler = ""
            try:
                inhalt["liste"] = datei_inhalt(ctx, loese_pfad(self.doc, p), trn_) if p else []
            except Exception as ex:
                fehler = str(ex)
            inhalt["fehler"] = fehler
            lst = inhalt["liste"]
            wunsch = 0
            for k, e in enumerate(lst):
                if (e["typ"] == "tabelle" and e["name"] == self.q.get("tabelle")) \
                        or (e["typ"] == "name" and e["name"] == self.q.get("bereichsname")) \
                        or (e["typ"] == "blatt" and e["name"] == self.q.get("blatt")
                            and not self.q.get("tabelle") and not self.q.get("bereichsname")):
                    wunsch = k
            setze_liste(d.ctrl("dateiwahl").getModel(), [e["text"] for e in lst], [wunsch] if lst else [])
            if fehler:
                d.ctrl("vorschau").getModel().Text = fehler
            datei_gewaehlt()

        def datei_gewaehlt(*_):
            i = sel_pos(d.ctrl("dateiwahl"))
            lst = inhalt["liste"]
            if 0 <= i < len(lst):
                d.ctrl("vorschau").getModel().Text = lst[i]["vorschau"]
            elif not d.ctrl("vorschau").getModel().Text or lst == []:
                if not d.ctrl("vorschau").getModel().Text:
                    d.ctrl("vorschau").getModel().Text = ""
            art = arten[max(sel_pos(d.ctrl("art")), 0)]
            d.ctrl("bereich").getModel().Enabled = art == "blatt" or (
                art == "datei" and 0 <= i < len(lst) and lst[i]["typ"] == "blatt")

        def aktualisiere_hinweis(*_):
            art = arten[max(sel_pos(d.ctrl("art")), 0)]
            hinweis = {"blatt": "Verwendet den benutzten Bereich des angegebenen Tabellenblatts in diesem "
                                "Dokument (leer = das jetzt aktive Blatt; sein Name wird gemerkt).",
                       "ordner": "Listet die Dateien dieses Ordners (auf Wunsch mit Unterordnern). Muster z. B. *.csv oder *.xlsx;*.ods. "
                                 "Für „Dateiinhalt einlesen“ die Spalte „Pfad“ ankreuzen. Die Liste wird bei jeder Aktualisierung neu gelesen.",
                       "datei": "Die Datei wird bei jeder Aktualisierung neu eingelesen. Der Pfad darf {Name} einer benannten Zelle enthalten. Unten stehen ihre Blätter, Tabellen und benannten Bereiche zur Auswahl, darunter eine Vorschau.",
                       "zwischenablage": "Kopieren Sie zuerst die Daten (z. B. aus dem Datenbankprogramm); "
                                         "sie werden jetzt eingelesen. Bei Aktualisierung ist die "
                                         "Zwischenablage nicht mehr verfügbar.",
                       "abfrage": ("Das Ergebnis einer anderen, schon gespeicherten Abfrage dieser Datei wird als "
                                   "Ausgangstabelle verwendet. Das geht auch mit „Nur Verbindung“-Abfragen."
                                   if abf_namen else
                                   "Es gibt noch keine andere gespeicherte Abfrage in dieser Datei. Eine neue "
                                   "Abfrage muss erst mit „Schließen und Laden“ gespeichert sein."),
                       "liste": "Eine einspaltige Tabelle aus den Werten eines Parameters (Liste mit ; oder aus einer Abfrage) "
                                "oder aus den eingetippten Zeilen. Die Werte sind Text; „Datentypen erkennen“ macht Zahlen daraus."}[art]
            d.ctrl("hinweis").getModel().Label = hinweis
            d.ctrl("pfad").getModel().Enabled = art in ("datei", "ordner")
            d.ctrl("trenner").getModel().Enabled = art in ("datei", "zwischenablage")
            d.ctrl("durch").getModel().Enabled = art in ("datei", "ordner")
            ordner = art == "ordner"
            d.ctrl("bereich").getModel().Enabled = art == "blatt"
            d.platziere("bereich", -3000 if ordner or art == "liste" else 80, 80, 212, 12)
            d.ctrl("l5").getModel().Label = "Spalten:" if ordner else "Bereich, z. B. A1:F500:"
            d.ctrl("l2").getModel().Label = "Ordner:" if ordner else "Datei:"
            d.platziere("muster", 80 if ordner else -3000, 62, 212, 12)
            for k, (schl, _) in enumerate(ORDNER_SPALTEN):
                d.platziere("sp_" + schl, (80 + 53 * (k % 4)) if ordner else -3000, 78 + 11 * (k // 4), 52, 10)
            d.platziere("unter", 80 if ordner else -3000, 101, 212, 10)
            liste_ = art == "liste"
            d.platziere("hinweis", 8, 152 if liste_ else 116 if ordner else 98, 284, 20 if liste_ else 22 if ordner else 24)
            d.platziere("listewahl", 80 if liste_ else -3000, 62, 212, 12)
            d.platziere("listespalte", 80 if liste_ else -3000, 80, 212, 12)
            d.platziere("l6", 8 if liste_ else -3000, 98, 70, 10)
            d.platziere("listewerte", 80 if liste_ else -3000, 98, 212, 50)
            d.ctrl("l5").getModel().Label = "Spaltenname:" if liste_ else d.ctrl("l5").getModel().Label
            d.platziere("blattwahl", 80 if art == "blatt" else -3000, 62, 212, 12)      # Blattliste nur bei „Tabellenblatt“
            d.platziere("abfragewahl", 80 if art == "abfrage" else -3000, 62, 212, 12)
            d.platziere("dateiwahl", 80 if art == "datei" else -3000, 62, 212, 12)
            d.platziere("vorschau", 8 if art == "datei" else -3000, 124, 284, 44)
            d.ctrl("l4").getModel().Label = ("Blatt:" if art == "blatt" else "Abfrage:" if art == "abfrage"
                                             else "Parameter:" if liste_ else "Dateimuster:" if ordner else "Inhalt der Datei:")
            if art == "datei":
                if inhalt["pfad"] is None and d.ctrl("pfad").getText().strip():
                    datei_lesen()
                else:
                    datei_gewaehlt()

        d.on_select("art", aktualisiere_hinweis)
        d.on_select("dateiwahl", datei_gewaehlt)
        d.on_select("trenner", lambda *_: datei_lesen() if arten[max(sel_pos(d.ctrl("art")), 0)] == "datei" else None)
        aktualisiere_hinweis()

        def durchsuchen():
            if arten[max(sel_pos(d.ctrl("art")), 0)] == "ordner":
                p = ordner_waehlen(ctx, d.ctrl("pfad").getText().strip().strip('"') or None)
                if p:
                    d.ctrl("pfad").getModel().Text = p
                return
            p = datei_waehlen(ctx, startpfad=d.ctrl("pfad").getText().strip().strip('"') or None)
            if p:
                d.ctrl("pfad").getModel().Text = p
                datei_lesen()

        def ok():
            art = arten[max(sel_pos(d.ctrl("art")), 0)]
            q = {"art": art}
            if art == "abfrage":
                i = sel_pos(d.ctrl("abfragewahl"))
                if not 0 <= i < len(abf_namen):
                    meldung(ctx, d.peer(), "Bitte eine Abfrage wählen (oder zuerst eine andere Abfrage speichern).", "WARNINGBOX")
                    return
                q["name"] = abf_namen[i]
            if art == "liste":
                j = sel_pos(d.ctrl("listewahl"))
                werte = d.ctrl("listewerte").getText()
                if j > 0:
                    q["parameter"] = lp_namen[j - 1]
                elif not [x for x in werte.splitlines() if x.strip()]:
                    meldung(ctx, d.peer(), "Bitte einen Parameter wählen oder Werte eintippen (eine Zeile je Wert).", "WARNINGBOX")
                    return
                else:
                    q["werte"] = "\n".join(x.strip() for x in werte.splitlines() if x.strip())
                q["spalte"] = d.ctrl("listespalte").getText().strip() or "Wert"
                self.ergebnis = q
                d.schliessen(1)
                return
            if art == "ordner":
                p = d.ctrl("pfad").getText().strip().strip('"')
                if not p:
                    meldung(ctx, d.peer(), "Bitte einen Ordner wählen.", "WARNINGBOX")
                    return
                if "{" not in p and not os.path.isdir(p):
                    meldung(ctx, d.peer(), "Der Ordner wurde nicht gefunden.", "WARNINGBOX")
                    return
                q["pfad"] = p
                q["muster"] = d.ctrl("muster").getText().strip() or "*"
                q["spalten"] = [schl for schl, _ in ORDNER_SPALTEN if d.ctrl("sp_" + schl).getModel().State == 1]
                if d.ctrl("unter").getModel().State == 1:
                    q["unterordner"] = True
                if not q["spalten"]:
                    meldung(ctx, d.peer(), "Bitte mindestens eine Spalte wählen.", "WARNINGBOX")
                    return
                if "{" not in p:
                    schreibe_einstellung("ordner_quelle", p)
                self.ergebnis = q
                d.schliessen(1)
                return
            if art == "datei":
                p = d.ctrl("pfad").getText().strip().strip('"')
                if not p:
                    meldung(ctx, d.peer(), "Bitte eine Datei wählen.", "WARNINGBOX")
                    return
                q["pfad"] = p
                if os.path.dirname(p):
                    schreibe_einstellung("ordner_quelle", os.path.dirname(p))
            if art in ("datei", "zwischenablage"):
                q["trenner"] = trn[max(sel_pos(d.ctrl("trenner")), 0)]
            if art == "datei":
                if inhalt["pfad"] is None or inhalt["pfad"][0] != q["pfad"]:
                    datei_lesen()                      # Pfad von Hand eingetippt: Inhalt erst jetzt lesen
                lst = inhalt["liste"]
                i = sel_pos(d.ctrl("dateiwahl"))
                if lst and not 0 <= i < len(lst):
                    i = 0
                if lst:
                    e = lst[i]
                    if e["typ"] == "blatt":
                        q["blatt"] = e["name"]
                        if d.ctrl("bereich").getText().strip():
                            q["bereich"] = d.ctrl("bereich").getText().strip().upper()
                    elif e["typ"] == "tabelle":
                        q["tabelle"] = e["name"]
                    elif e["typ"] == "name":
                        q["bereichsname"] = e["name"]
                else:
                    meldung(ctx, d.peer(), inhalt.get("fehler") or "Die Datei wurde nicht gefunden oder ist nicht lesbar.", "WARNINGBOX")
                    return
            if art == "blatt":
                i = sel_pos(d.ctrl("blattwahl"))
                if 0 <= i < len(blatt_namen):          # Name festhalten, damit Aktualisieren vom aktiven Blatt unabhängig ist
                    q["blatt"] = blatt_namen[i]
                if d.ctrl("bereich").getText().strip():
                    q["bereich"] = d.ctrl("bereich").getText().strip().upper()
            self.ergebnis = q
            d.schliessen(1)

        d.on_click("durch", durchsuchen)
        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        auto_ok = os.environ.get("ABFRAGE_AUTOOK")
        if auto_ok:   # Testbetrieb: simuliert den Klick auf OK
            t_ = threading.Timer(float(auto_ok), _sicher(ok))
            t_.daemon = True
            t_.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


class ZielDialog:
    """Wohin soll das Ergebnis? Neues Blatt, ab einer Zielzelle oder nur als Verbindung; Format als intelligente
    Tabelle; Aktualisieren beim Öffnen."""
    ARTEN = [("blatt", "Neues Blatt mit dem Namen der Abfrage"), ("zelle", "Vorhandenes Blatt, ab Zielzelle"),
             ("keine", "Nur Verbindung (nicht ins Blatt schreiben)")]

    def __init__(self, ctx, doc, abfrage, parent=None):
        self.ctx, self.doc, self.parent = ctx, doc, parent
        self.abfrage = abfrage
        self.ergebnis = None

    def zeigen(self):
        ctx, a = self.ctx, self.abfrage
        ziel = dict(a.ziel or {"art": "blatt"})
        opt = tabellen_optionen(ziel)
        blaetter = list(self.doc.getSheets().getElementNames()) if self.doc is not None else []
        d = Dlg(ctx, "Ausgabe und Aktualisierung", 300, 214)
        d.add("FixedText", "l1", 8, 8, 70, 10, Label="Ergebnis ausgeben in:")
        d.add("ListBox", "art", 80, 6, 212, 12, Dropdown=True, LineCount=4)
        d.add("FixedText", "l2", 8, 28, 70, 10, Label="Blatt:")
        d.add("ListBox", "blatt", 80, 26, 212, 12, Dropdown=True, LineCount=12)
        d.add("FixedText", "l3", 8, 46, 70, 10, Label="Zielzelle (z. B. B3):")
        d.add("Edit", "zelle", 80, 44, 80, 12, Text=ziel.get("zelle", "A1"))
        d.add("FixedText", "linie", 8, 62, 284, 1, BackgroundColor=TRENNLINIE)
        d.add("CheckBox", "tabelle", 8, 68, 284, 12,
              Label="Als intelligente Tabelle formatieren (Kopfzeile, Autofilter, Bereich „%s“)" % bereichsname(a.name),
              State=1 if opt["tabelle"] else 0)
        d.add("FixedText", "l4", 20, 85, 56, 10, Label="Farbe:")
        d.add("ListBox", "farbe", 80, 83, 110, 12, Dropdown=True, LineCount=8)
        d.add("CheckBox", "baender", 20, 99, 272, 12, Label="Bänderung (abwechselnde Zeilenfarbe)",
              State=1 if opt["baender"] else 0)
        d.add("CheckBox", "reiter", 20, 113, 272, 12, Label="Reiter des Blatts in dieser Farbe einfärben",
              State=1 if opt["reiter"] else 0)
        d.add("FixedText", "linie2", 8, 129, 284, 1, BackgroundColor=TRENNLINIE)
        d.add("CheckBox", "auto", 8, 135, 284, 12, Label="Beim Öffnen der Datei automatisch aktualisieren",
              State=1 if a.auto else 0)
        d.add("FixedText", "hinweis", 8, 152, 284, 34, MultiLine=True, Label="")
        d.add("FixedText", "fehler", 8, 184, 284, 14, MultiLine=True, Label="", TextColor=0xB00020)
        d.add("Button", "ok", 150, 196, 70, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", 224, 196, 68, 14, Label="Abbrechen")
        arten = [x for x, _ in self.ARTEN]
        setze_liste(d.ctrl("art").getModel(), [l for _, l in self.ARTEN],
                    [arten.index(ziel.get("art", "blatt")) if ziel.get("art", "blatt") in arten else 0])
        vorgabe_blatt = ziel.get("blatt") if ziel.get("blatt") in blaetter else (blaetter[0] if blaetter else None)
        setze_liste(d.ctrl("blatt").getModel(), blaetter,
                    [blaetter.index(vorgabe_blatt)] if vorgabe_blatt in blaetter else [])
        farb_keys = [k for k, _, _, _ in TABELLEN_FARBEN]
        setze_liste(d.ctrl("farbe").getModel(), [n for _, n, _, _ in TABELLEN_FARBEN], [farb_keys.index(opt["farbe"])])

        def aktualisiere(*_):
            art = arten[max(sel_pos(d.ctrl("art")), 0)]
            tabelle = bool(d.ctrl("tabelle").getModel().State)
            d.ctrl("blatt").getModel().Enabled = art == "zelle"
            d.ctrl("zelle").getModel().Enabled = art in ("blatt", "zelle")      # auch beim neuen Blatt: Startzelle
            schreibt = art != "keine"
            d.ctrl("tabelle").getModel().Enabled = schreibt
            d.ctrl("baender").getModel().Enabled = schreibt and tabelle
            d.ctrl("reiter").getModel().Enabled = art == "blatt"
            d.ctrl("farbe").getModel().Enabled = schreibt and (tabelle or art == "blatt")
            d.ctrl("hinweis").getModel().Label = {
                "blatt": "Das Blatt wird bei jeder Aktualisierung komplett neu geschrieben, die Tabelle beginnt in der "
                         "Zielzelle (Standard A1). Der Blattname ist der Abfragename.",
                "zelle": "Nur der Bereich des letzten Ergebnisses wird bei jeder Aktualisierung ersetzt. "
                         "Stehen im neuen Bereich fremde Daten, wird nachgefragt (beim automatischen "
                         "Aktualisieren stattdessen ein Fehler gemeldet).",
                "keine": "Es wird nichts ins Tabellenblatt geschrieben. Die Abfrage steht nur anderen Abfragen "
                         "(Verbinden, Anfügen, Verweis) zur Verfügung."}[art]
        d.on_select("art", aktualisiere)
        d.on_select("tabelle", aktualisiere)
        aktualisiere()

        def ok():
            art = arten[max(sel_pos(d.ctrl("art")), 0)]
            neu = {"art": art}
            if art == "zelle":
                i = sel_pos(d.ctrl("blatt"))
                if i < 0 or i >= len(blaetter):
                    d.ctrl("fehler").getModel().Label = "Bitte ein Blatt wählen."
                    return
                zelle = d.ctrl("zelle").getText().strip().upper() or "A1"
                try:
                    self.doc.getSheets().getByName(blaetter[i]).getCellRangeByName(zelle).getRangeAddress()
                except Exception:
                    d.ctrl("fehler").getModel().Label = "'%s' ist keine gültige Zelle." % zelle
                    return
                neu.update(blatt=blaetter[i], zelle=zelle)
            elif art == "blatt":
                zelle = d.ctrl("zelle").getText().strip().upper() or "A1"
                try:
                    probe_name = gueltiger_blattname(a.name)
                    probe_blatt = (self.doc.getSheets().getByName(probe_name) if self.doc.getSheets().hasByName(probe_name)
                                   else self.doc.getSheets().getByIndex(0))
                    probe_blatt.getCellRangeByName(zelle).getRangeAddress()
                except Exception:
                    d.ctrl("fehler").getModel().Label = "'%s' ist keine gültige Zelle." % zelle
                    return
                neu["zelle"] = zelle
            for k in ("letzter", "letzter_blatt", "bereich", "reiter_farbe"):      # altes Ergebnis merken, damit es ersetzt wird
                if ziel.get(k):
                    neu[k] = ziel[k]
            neu["tabelle"] = bool(d.ctrl("tabelle").getModel().State)
            neu["baender"] = bool(d.ctrl("baender").getModel().State)
            neu["reiter"] = bool(d.ctrl("reiter").getModel().State) and art == "blatt"
            fi = sel_pos(d.ctrl("farbe"))
            neu["farbe"] = farb_keys[fi] if 0 <= fi < len(farb_keys) else "blau"
            probe = E.Abfrage(a.name, a.quelle, [], neu, False)
            try:
                pruefe_ziel(self.doc, probe)
            except E.FormelFehler as e:
                d.ctrl("fehler").getModel().Label = str(e)
                return
            self.ergebnis = (neu, bool(d.ctrl("auto").getModel().State))
            d.schliessen(1)

        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        auto_ok = os.environ.get("ABFRAGE_AUTOOK")
        if auto_ok:   # Testbetrieb: simuliert den Klick auf OK
            t = threading.Timer(float(auto_ok), _sicher(ok))
            t.daemon = True
            t.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


class _Text(unohelper.Base, XTransferable):
    """Reiner Text für die Zwischenablage."""

    def __init__(self, text):
        self.text = text
        self.flavor = DataFlavor()
        self.flavor.MimeType = "text/plain;charset=utf-16"
        self.flavor.HumanPresentableName = "Unicode-Text"
        self.flavor.DataType = uno.getTypeByName("string")

    def getTransferData(self, flavor):
        return self.text

    def getTransferDataFlavors(self):
        return (self.flavor,)

    def isDataFlavorSupported(self, flavor):
        return "text/plain" in (flavor.MimeType or "")


def in_zwischenablage(ctx, text):
    """Text in die System-Zwischenablage legen. -> True, wenn es geklappt hat."""
    try:
        zw = ctx.ServiceManager.createInstanceWithContext("com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)
        t = _Text(text)
        zw.setContents(t, None)
        return True
    except Exception:
        traceback.print_exc()
        return False


class _Strg(unohelper.Base, XKeyListener):
    """Strg/Cmd+C in einem Raster."""

    def __init__(self, fn):
        self.fn = fn

    def keyPressed(self, ev):
        try:
            if ev.KeyCode == 514 and (ev.Modifiers & 2):       # Key.C, KeyModifier.MOD1 (Strg bzw. Cmd)
                self.fn()
        except Exception:
            traceback.print_exc()

    def keyReleased(self, ev):
        pass

    def disposing(self, ev):
        pass


class _Taste(unohelper.Base, XKeyListener):
    """Reagiert auf die Eingabetaste in einem Eingabefeld (ohne dass der Dialog sie als Standardknopf auswertet)."""

    def __init__(self, fn):
        self.fn = fn

    def keyPressed(self, ev):
        if ev.KeyCode == 1280:          # com.sun.star.awt.Key.RETURN
            self.fn()

    def keyReleased(self, ev):
        pass

    def disposing(self, ev):
        pass


class _Fokus(unohelper.Base, XFocusListener):
    def __init__(self, fn):
        self.fn = fn

    def focusGained(self, ev):
        self.fn()

    def focusLost(self, ev):
        pass

    def disposing(self, ev):
        pass


class BedingtDialog:
    """Bedingte Spalte wie im Power-Query-Dialog: Wenn / Sonst wenn … / Sonst.
    Jede Klausel kann weitere Bedingungen haben (UND/ODER). Werte: fester Text/Zahl, Spalte oder Formel."""
    MAX_ZEILEN = 14
    ART_LABELS = [("text", "Wert"), ("spalte", "Spalte"), ("formel", "Formel")]
    X = {"lbl": 6, "sp": 44, "op": 118, "wa": 200, "wt": 244, "dl": 334, "da": 352, "dw": 396, "plus": 484, "del": 498}
    B = {"lbl": 36, "sp": 70, "op": 78, "wa": 40, "wt": 86, "dl": 16, "da": 40, "dw": 84, "plus": 12, "del": 12}
    ZEILE = 16
    Y0 = 48

    def __init__(self, ctx, op, tab_vor, schritt=None, vorbelegt=None, parent=None):
        self.ctx, self.op, self.tab, self.parent = ctx, op, tab_vor, parent
        self.start = dict(vorbelegt or {})
        if schritt:
            self.start.update(E.normalisiere_schritt(schritt))
        self.ergebnis = None

    # -- Datenmodell: flache Zeilenliste (Klauselkopf "k" / weitere Bedingung "c") ----------
    @staticmethod
    def _leere_bedingung():
        return {"spalte": "", "bedingung": "enthaelt", "wert_art": "text", "wert": ""}

    def _zeilen_aus_schritt(self, s):
        kl, sonst_art, sonst = E.normalisiere_bedingt(s)
        zeilen = []
        for k in kl:
            bed = list(k.get("bedingungen") or [self._leere_bedingung()])
            kopf = dict(bed[0])
            kopf.update(t="k", verk=k.get("verknuepfung", "und"), dann_art=k.get("dann_art", "text"),
                        dann=k.get("dann") or "")
            zeilen.append(kopf)
            for b in bed[1:]:
                z = dict(b)
                z["t"] = "c"
                zeilen.append(z)
        if not zeilen:
            kopf = self._leere_bedingung()
            kopf.update(t="k", verk="und", dann_art="text", dann="")
            zeilen.append(kopf)
        return zeilen[:self.MAX_ZEILEN], sonst_art, sonst or ""

    @staticmethod
    def _klauseln_aus_zeilen(zeilen):
        kl = []
        for z in zeilen:
            b = {"spalte": z["spalte"], "bedingung": z["bedingung"], "wert_art": z["wert_art"], "wert": z["wert"]}
            if z["t"] == "k":
                kl.append({"verknuepfung": z.get("verk", "und"), "bedingungen": [b],
                           "dann_art": z["dann_art"], "dann": z["dann"]})
            elif kl:
                kl[-1]["bedingungen"].append(b)
        return kl

    def zeigen(self):
        ctx, tab = self.ctx, self.tab
        spalten = list(tab.spalten) + ["{%s}" % n_ for n_ in parameter_namen(_EDITOR_KONTEXT.get("doc"))]   # Parameter als Spaltenname wählbar
        felder = E.OPS[self.op]["felder"]
        zeilen, sonst_art, sonst = self._zeilen_aus_schritt(self.start)
        self.zeilen = zeilen
        bed_namen = [v for v, _ in E.BEDINGUNGEN]
        bed_labels = [l for _, l in E.BEDINGUNGEN]
        arten = [v for v, _ in self.ART_LABELS]
        art_labels = [l for _, l in self.ART_LABELS]
        n_max = self.MAX_ZEILEN
        BREITE = 520
        d = Dlg(ctx, "Bedingte Spalte hinzufügen", BREITE, 200)
        self.d = d
        self.letztes_feld = None
        X, B = self.X, self.B

        d.add("FixedText", "t_neu", 6, 8, 90, 10, Label="Neuer Spaltenname")
        d.add("Edit", "neu", 6, 20, 150, 12, Text=str(self.start.get("neu") or "Bedingte Spalte"))
        for lab, x in (("Spaltenname", X["sp"]), ("Operator", X["op"]), ("Wert", X["wa"]), ("Ausgabe", X["da"])):
            d.add("FixedText", "h_" + lab, x, 36, 60, 10, Label=lab)

        def dropdown(name, x, y, w, items, zeilen_anzeige=12):
            d.add("ListBox", name, x, y, w, 12, Dropdown=True, LineCount=zeilen_anzeige)
            setze_liste(d.ctrl(name).getModel(), items, [0])

        def fokus_merker(name):
            fk = _Fokus(lambda: setattr(self, "letztes_feld", name))
            d.refs.append(fk)
            d.ctrl(name).addFocusListener(fk)

        for i in range(n_max):
            y = self.Y0 + i * self.ZEILE
            d.add("FixedText", "r%d_lbl" % i, X["lbl"], y + 2, B["lbl"], 10, Label="")
            dropdown("r%d_und" % i, X["lbl"], y, B["lbl"], ["UND", "ODER"])
            dropdown("r%d_sp" % i, X["sp"], y, B["sp"], ["(Spalte)"] + spalten)
            dropdown("r%d_op" % i, X["op"], y, B["op"], bed_labels)
            dropdown("r%d_wa" % i, X["wa"], y, B["wa"], art_labels)
            d.add("Edit", "r%d_wt" % i, X["wt"], y, B["wt"], 12)
            dropdown("r%d_ws" % i, X["wt"], y, B["wt"], ["(Spalte)"] + spalten)
            d.add("FixedText", "r%d_dl" % i, X["dl"], y + 2, B["dl"], 10, Label="Dann")
            dropdown("r%d_da" % i, X["da"], y, B["da"], art_labels)
            d.add("Edit", "r%d_dt" % i, X["dw"], y, B["dw"], 12)
            dropdown("r%d_ds" % i, X["dw"], y, B["dw"], ["(Spalte)"] + spalten)
            d.add("Button", "r%d_plus" % i, X["plus"], y, B["plus"], 12, Label="+")
            d.add("Button", "r%d_del" % i, X["del"], y, B["del"], 12, Label="✕")
            fokus_merker("r%d_wt" % i)
            fokus_merker("r%d_dt" % i)

        # unterer Teil (Position wird je nach Zeilenzahl gesetzt)
        d.add("Button", "klausel", 6, 0, 90, 12, Label="Klausel hinzufügen")
        d.add("FixedText", "t_sonst", 6, 0, 30, 10, Label="Sonst")
        dropdown("sa", X["da"], 0, B["da"], art_labels)
        d.add("Edit", "st", X["dw"], 0, B["dw"], 12)
        dropdown("ss", X["dw"], 0, B["dw"], ["(Spalte)"] + spalten)
        d.add("FixedText", "t_ins", 6, 0, 150, 10, Label="Spalte in Formelfeld einfügen:")
        dropdown("ins", 150, 0, 110, ["(Spalte wählen)"] + spalten, 14)
        d.add("FixedText", "t_ort", 270, 0, 130, 10, Label="Format fester Zahlen/Daten:")
        dropdown("ort", 400, 0, 112, [l for _, l in E.ORTE], 4)
        d.add("Button", "btnParam", 6, 0, 150, 12, Label="Parameter einfügen…")
        d.add("FixedText", "fehler", 6, 0, BREITE - 12, 24, MultiLine=True, Label="", TextColor=0xB00020)
        d.add("Button", "ok", BREITE - 150, 0, 70, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", BREITE - 76, 0, 68, 14, Label="Abbrechen")
        for nm in ("st",):
            fokus_merker(nm)
        orte = [v for v, _ in E.ORTE]
        setze_liste(d.ctrl("ort").getModel(), [l for _, l in E.ORTE],
                    [orte.index(self.start.get("ort", "de")) if self.start.get("ort", "de") in orte else 0])

        def sp_index(name):
            return spalten.index(name) + 1 if name in spalten else 0

        def setze_sichtbar(name, sichtbar, aktiv=True):
            m = d.model.getByName(name)
            m.EnableVisible = bool(sichtbar)
            m.Enabled = bool(aktiv)

        def wert_felder(prefix, art, wert, aktiv=True):
            """Edit oder Spaltenauswahl je nach Art sichtbar machen und füllen."""
            ist_spalte = art == "spalte"
            setze_sichtbar(prefix + "t", not ist_spalte, aktiv)
            setze_sichtbar(prefix + "s", ist_spalte, aktiv)
            if ist_spalte:
                setze_liste(d.ctrl(prefix + "s").getModel(), ["(Spalte)"] + spalten, [sp_index(wert)])
            else:
                d.ctrl(prefix + "t").getModel().Text = "" if wert is None else str(wert)

        def zeichne():
            n = len(self.zeilen)
            for i in range(n_max):
                aktiv = i < n
                for k in ("lbl", "und", "sp", "op", "wa", "wt", "ws", "dl", "da", "dt", "ds", "plus", "del"):
                    setze_sichtbar("r%d_%s" % (i, k), False)
                if not aktiv:
                    continue
                z = self.zeilen[i]
                kopf = z["t"] == "k"
                erste_weitere = (not kopf) and i > 0 and self.zeilen[i - 1]["t"] == "k"
                klausel_nr = sum(1 for q in self.zeilen[:i + 1] if q["t"] == "k")
                if kopf:
                    d.ctrl("r%d_lbl" % i).getModel().Label = "Wenn" if klausel_nr == 1 else "Sonst wenn"
                    setze_sichtbar("r%d_lbl" % i, True)
                elif erste_weitere:
                    setze_sichtbar("r%d_und" % i, True)
                    kz = max((j for j in range(i) if self.zeilen[j]["t"] == "k"))
                    setze_liste(d.ctrl("r%d_und" % i).getModel(), ["UND", "ODER"],
                                [1 if self.zeilen[kz].get("verk") == "oder" else 0])
                else:
                    kz = max((j for j in range(i) if self.zeilen[j]["t"] == "k"))
                    d.ctrl("r%d_lbl" % i).getModel().Label = "ODER" if self.zeilen[kz].get("verk") == "oder" else "UND"
                    setze_sichtbar("r%d_lbl" % i, True)
                setze_liste(d.ctrl("r%d_sp" % i).getModel(), ["(Spalte)"] + spalten, [sp_index(z["spalte"])])
                setze_sichtbar("r%d_sp" % i, True)
                setze_liste(d.ctrl("r%d_op" % i).getModel(), bed_labels,
                            [bed_namen.index(z["bedingung"]) if z["bedingung"] in bed_namen else 0])
                setze_sichtbar("r%d_op" % i, True)
                ohne_wert = z["bedingung"] in E.OHNE_WERT
                setze_liste(d.ctrl("r%d_wa" % i).getModel(), art_labels,
                            [arten.index(z["wert_art"]) if z["wert_art"] in arten else 0])
                setze_sichtbar("r%d_wa" % i, True, not ohne_wert)
                wert_felder("r%d_w" % i, z["wert_art"], z["wert"], not ohne_wert)
                if kopf:
                    setze_sichtbar("r%d_dl" % i, True)
                    setze_liste(d.ctrl("r%d_da" % i).getModel(), art_labels,
                                [arten.index(z["dann_art"]) if z["dann_art"] in arten else 0])
                    setze_sichtbar("r%d_da" % i, True)
                    wert_felder("r%d_d" % i, z["dann_art"], z["dann"])
                    setze_sichtbar("r%d_plus" % i, len(self.zeilen) < n_max)
                setze_sichtbar("r%d_del" % i, n > 1)
            # unterer Teil
            y = self.Y0 + n * self.ZEILE + 4
            d.platziere("klausel", 6, y, 90, 12)
            d.model.getByName("klausel").Enabled = n < n_max
            y += 20
            d.platziere("t_sonst", 6, y + 2, 30, 10)
            d.platziere("sa", X["da"], y, B["da"], 12)
            d.platziere("st", X["dw"], y, B["dw"], 12)
            d.platziere("ss", X["dw"], y, B["dw"], 12)
            setze_liste(d.ctrl("sa").getModel(), art_labels, [arten.index(sonst_zustand["art"])])
            wert_felder("s", sonst_zustand["art"], sonst_zustand["wert"])
            y += 20
            d.platziere("t_ins", 6, y + 2, 140, 10)
            d.platziere("ins", 150, y, 110, 12)
            d.platziere("t_ort", 270, y + 2, 128, 10)
            d.platziere("ort", 400, y, 112, 12)
            y += 18
            d.platziere("btnParam", 6, y, 150, 12)
            y += 18
            d.platziere("fehler", 6, y, BREITE - 12, 24)
            y += 28
            d.platziere("ok", BREITE - 150, y, 70, 14)
            d.platziere("abbr", BREITE - 76, y, 68, 14)
            d.model.Height = y + 20

        sonst_zustand = {"art": sonst_art if sonst_art in arten else "text", "wert": sonst}

        def lies():
            """Eingaben aus den Steuerelementen in die Zeilenliste übernehmen."""
            for i, z in enumerate(self.zeilen):
                si = sel_pos(d.ctrl("r%d_sp" % i))
                z["spalte"] = spalten[si - 1] if si > 0 else ""
                z["bedingung"] = bed_namen[max(sel_pos(d.ctrl("r%d_op" % i)), 0)]
                z["wert_art"] = arten[max(sel_pos(d.ctrl("r%d_wa" % i)), 0)]
                z["wert"] = self._wert_lesen(d, "r%d_w" % i, z["wert_art"], spalten)
                if z["t"] == "k":
                    z["dann_art"] = arten[max(sel_pos(d.ctrl("r%d_da" % i)), 0)]
                    z["dann"] = self._wert_lesen(d, "r%d_d" % i, z["dann_art"], spalten)
                else:
                    if i > 0 and self.zeilen[i - 1]["t"] == "k":
                        kz = i - 1
                        self.zeilen[kz]["verk"] = "oder" if sel_pos(d.ctrl("r%d_und" % i)) == 1 else "und"
            sonst_zustand["art"] = arten[max(sel_pos(d.ctrl("sa")), 0)]
            sonst_zustand["wert"] = self._wert_lesen(d, "s", sonst_zustand["art"], spalten)

        self._lies = lies

        def neue_klausel():
            lies()
            if len(self.zeilen) >= n_max:
                return
            k = self._leere_bedingung()
            k.update(t="k", verk="und", dann_art="text", dann="")
            self.zeilen.append(k)
            zeichne()

        def plus(i):
            lies()
            if len(self.zeilen) >= n_max:
                return
            ende = i + 1
            while ende < len(self.zeilen) and self.zeilen[ende]["t"] == "c":
                ende += 1
            self.zeilen.insert(ende, dict(self._leere_bedingung(), t="c"))
            zeichne()

        def loeschen(i):
            lies()
            z = self.zeilen[i]
            if len(self.zeilen) <= 1:
                return
            if z["t"] == "k":     # Klausel mit ihren weiteren Bedingungen entfernen
                ende = i + 1
                while ende < len(self.zeilen) and self.zeilen[ende]["t"] == "c":
                    ende += 1
                if ende - i >= len(self.zeilen):
                    return
                del self.zeilen[i:ende]
            else:
                del self.zeilen[i]
            zeichne()

        def aenderung(*_):
            lies()
            zeichne()

        self._aktionen = {"klausel": neue_klausel, "plus": plus, "loeschen": loeschen}   # für Tests
        d.on_click("klausel", neue_klausel, None)
        for i in range(n_max):
            d.on_click("r%d_plus" % i, (lambda k: lambda: plus(k))(i))
            d.on_click("r%d_del" % i, (lambda k: lambda: loeschen(k))(i))
            for nm in ("wa", "da", "op"):
                d.on_select("r%d_%s" % (i, nm), aenderung)
            d.on_select("r%d_und" % i, aenderung)
        d.on_select("sa", aenderung)

        def einfuegen(e):
            i = sel_pos(d.ctrl("ins"))
            if i <= 0:
                return
            name = self.letztes_feld
            setze_liste(d.ctrl("ins").getModel(), ["(Spalte wählen)"] + spalten, [0])
            if not name:
                d.ctrl("fehler").getModel().Label = "Bitte zuerst in das Formelfeld klicken, in das die Spalte soll."
                return
            # nur in Felder der Art „Formel“ einfügen
            if name == "st":
                art = sonst_zustand["art"] if False else arten[max(sel_pos(d.ctrl("sa")), 0)]
            else:
                zi = int(name[1:name.index("_")])
                art = arten[max(sel_pos(d.ctrl("r%d_%s" % (zi, "wa" if name.endswith("wt") else "da"))), 0)]
            if art != "formel":
                d.ctrl("fehler").getModel().Label = "Das angeklickte Feld ist keine Formel (Art „Formel“ wählen)."
                return
            d.ctrl("fehler").getModel().Label = ""
            c = d.ctrl(name)
            c.insertText(c.getSelection(), "[%s]" % spalten[i - 1])
            c.setFocus()
        d.on_select("ins", einfuegen)

        def parameter_einfuegen():
            name = self.letztes_feld
            if not name:
                d.ctrl("fehler").getModel().Label = "Bitte zuerst in das Wert-Feld klicken, in das der Parameter soll."
                return
            doc_ = _EDITOR_KONTEXT.get("doc")
            liste = parameter_liste(doc_) if doc_ is not None else []
            if not liste:
                meldung(ctx, d.fenster if hasattr(d, "fenster") else self.parent,
                        "In dieser Datei gibt es noch keinen Parameter.\n\nLege einen in OpenQuery an (Knopf „Parameter…“ "
                        "oder Menü OpenQuery ▸ Parameter …).")
                return
            i = waehle_aus_liste(ctx, "Parameter", "Parameter wählen (wird als {Name} eingefügt):",
                                 ["%s   =   %s" % (n_, w_) for n_, w_ in liste], self.parent)
            if i is None:
                return
            d.ctrl("fehler").getModel().Label = ""
            c = d.ctrl(name)
            c.insertText(c.getSelection(), "{%s}" % liste[i][0])
            c.setFocus()
        d.on_click("btnParam", parameter_einfuegen)
        self._parameter_einfuegen = parameter_einfuegen     # für Tests

        def sammeln():
            lies()
            s = {"op": self.op, "neu": d.ctrl("neu").getText().strip(),
                 "klauseln": self._klauseln_aus_zeilen(self.zeilen),
                 "sonst_art": sonst_zustand["art"], "sonst": sonst_zustand["wert"],
                 "ort": orte[max(sel_pos(d.ctrl("ort")), 0)]}
            if self.start.get("aktiv") is False:
                s["aktiv"] = False
            return s

        def ok():
            try:
                s = sammeln()
                if not s["neu"]:
                    raise E.FormelFehler("Bitte einen Namen für die neue Spalte angeben")
                E.wende_schritt(tab, s)
            except E.StepError as e:
                d.ctrl("fehler").getModel().Label = e.meldung
                return
            except Exception as e:
                d.ctrl("fehler").getModel().Label = str(e)
                return
            self.ergebnis = s
            d.schliessen(1)

        self._sammeln = sammeln
        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        zeichne()
        auto = os.environ.get("ABFRAGE_AUTOOK")
        if auto:
            t = threading.Timer(float(auto), _sicher(ok))
            t.daemon = True
            t.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis

    @staticmethod
    def _wert_lesen(d, prefix, art, spalten):
        if art == "spalte":
            i = sel_pos(d.ctrl(prefix + "s"))
            return spalten[i - 1] if i > 0 else ""
        return d.ctrl(prefix + "t").getText()


class VerbindenDialog:
    """Tabellen verbinden (Merge/Join): zweite Tabelle = andere Abfrage, mehrere Schlüsselpaare, Verknüpfungsart."""
    MAX_SCHLUESSEL = 5
    KEINE = "(keine)"

    def __init__(self, ctx, op, tab_vor, schritt=None, vorbelegt=None, parent=None):
        self.ctx, self.op, self.tab, self.parent = ctx, op, tab_vor, parent
        self.start = dict(vorbelegt or {})
        if schritt:
            self.start.update(schritt)
        self.ergebnis = None

    def _spalten_rechts(self, name):
        try:
            return list(E.hole_tabelle(name).spalten), ""
        except E.FormelFehler as e:
            return [], str(e)

    def zeigen(self):
        ctx = self.ctx
        doc, eigen = _EDITOR_KONTEXT["doc"], _EDITOR_KONTEXT["eigen"]
        namen = andere_abfragen(doc, eigen) if doc is not None else []
        if not namen:
            meldung(ctx, self.parent, "Es gibt keine andere gespeicherte Abfrage in dieser Datei. "
                    "Bitte die zweite Tabelle zuerst als eigene Abfrage anlegen und speichern.", "WARNINGBOX")
            return None
        links = [self.KEINE] + list(self.tab.spalten)
        join_keys = [k for k, _ in E.JOIN_ARTEN]
        d = Dlg(ctx, "Abfragen zusammenführen", 360, 262)
        self.d = d
        d.add("FixedText", "t_abf", 8, 8, 200, 10, Label="Zweite Tabelle (andere Abfrage):")
        d.add("ListBox", "abf", 8, 20, 344, 12, Dropdown=True, LineCount=10)
        start_abf = self.start.get("abfrage") if self.start.get("abfrage") in namen else namen[0]
        setze_liste(d.ctrl("abf").getModel(), namen, [namen.index(start_abf)])
        d.add("FixedText", "t_key", 8, 38, 344, 10, Label="Schlüsselspalten:  Spalte der ersten Tabelle  =  Spalte der zweiten Tabelle")
        paare = list(self.start.get("schluessel") or [])
        for i in range(self.MAX_SCHLUESSEL):
            y = 50 + i * 15
            d.add("ListBox", "kl%d" % i, 8, y, 160, 12, Dropdown=True, LineCount=12)
            d.add("FixedText", "ks%d" % i, 172, y + 2, 8, 10, Label="=")
            d.add("ListBox", "kr%d" % i, 184, y, 168, 12, Dropdown=True, LineCount=12)
            p = paare[i] if i < len(paare) else {}
            setze_liste(d.ctrl("kl%d" % i).getModel(), links,
                        [links.index(p["links"]) if p.get("links") in links else 0])
        y = 50 + self.MAX_SCHLUESSEL * 15 + 4
        d.add("FixedText", "t_join", 8, y, 200, 10, Label="Verknüpfungsart:")
        d.add("ListBox", "join", 8, y + 12, 344, 12, Dropdown=True, LineCount=7)
        setze_liste(d.ctrl("join").getModel(), [l for _, l in E.JOIN_ARTEN],
                    [join_keys.index(self.start.get("join", "links")) if self.start.get("join", "links") in join_keys else 0])
        y += 30
        d.add("FixedText", "t_sp", 8, y, 210, 10, Label="Spalten aus der zweiten Tabelle (keine Auswahl = alle):")
        d.add("ListBox", "sp", 8, y + 12, 210, 62, MultiSelection=True)
        d.add("FixedText", "t_pre", 226, y, 126, 10, Label="Präfix für diese Spalten:")
        d.add("Edit", "pre", 226, y + 12, 126, 12, Text=str(self.start.get("praefix") or ""))
        d.add("FixedText", "fehler", 226, y + 30, 126, 40, MultiLine=True, Label="", TextColor=0xB00020)
        yb = y + 82
        d.add("Button", "ok", 224, yb, 62, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", 290, yb, 62, 14, Label="Abbrechen")
        d.model.Height = yb + 22

        def fuelle_rechts(erste_mal=False):
            name = namen[sel_pos(d.ctrl("abf"))] if sel_pos(d.ctrl("abf")) >= 0 else namen[0]
            rcols, fehler = self._spalten_rechts(name)
            d.ctrl("fehler").getModel().Label = fehler
            items = [self.KEINE] + rcols
            for i in range(self.MAX_SCHLUESSEL):
                m = d.ctrl("kr%d" % i).getModel()
                alt = None
                if erste_mal:
                    p = paare[i] if i < len(paare) else {}
                    alt = p.get("rechts")
                else:
                    k = sel_pos(d.ctrl("kr%d" % i))
                    alt = m.StringItemList[k] if 0 <= k < len(m.StringItemList) else None
                setze_liste(m, items, [items.index(alt) if alt in items else 0])
            auswahl = []
            if erste_mal:
                auswahl = [rcols.index(c) for c in (self.start.get("spalten_rechts") or []) if c in rcols]
            m = d.ctrl("sp").getModel()
            m.StringItemList = tuple(rcols)
            m.SelectedItems = uno.Any("[]short", tuple(auswahl))
        fuelle_rechts(True)
        d.on_select("abf", lambda e: fuelle_rechts(False), None)

        def ok():
            name = namen[max(sel_pos(d.ctrl("abf")), 0)]
            rcols, _ = self._spalten_rechts(name)
            schluessel = []
            for i in range(self.MAX_SCHLUESSEL):
                a = sel_pos(d.ctrl("kl%d" % i))
                b = sel_pos(d.ctrl("kr%d" % i))
                if a > 0 and b > 0:
                    schluessel.append({"links": links[a], "rechts": rcols[b - 1]})
                elif (a > 0) != (b > 0):
                    meldung(ctx, d.peer(), "Schlüsselpaar %d: Bitte links und rechts eine Spalte wählen." % (i + 1), "WARNINGBOX")
                    return
            s = {"op": self.op, "abfrage": name, "schluessel": schluessel,
                 "join": join_keys[max(sel_pos(d.ctrl("join")), 0)],
                 "spalten_rechts": [rcols[i] for i in sel_multi(d.ctrl("sp")) if i < len(rcols)],
                 "praefix": d.ctrl("pre").getText()}
            try:
                E.wende_schritt(self.tab, s)
            except E.StepError as e:
                meldung(ctx, d.peer(), e.meldung, "WARNINGBOX")
                return
            self.ergebnis = s
            d.schliessen(1)
        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        auto = os.environ.get("ABFRAGE_AUTOOK")
        if auto:
            t = threading.Timer(float(auto), _sicher(ok))
            t.daemon = True
            t.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


class AnfuegenDialog:
    """Tabellen anfügen (Append/Union): eine oder mehrere andere Abfragen unter die aktuelle Tabelle setzen."""

    def __init__(self, ctx, op, tab_vor, schritt=None, vorbelegt=None, parent=None):
        self.ctx, self.op, self.tab, self.parent = ctx, op, tab_vor, parent
        self.start = dict(vorbelegt or {})
        if schritt:
            self.start.update(schritt)
        self.ergebnis = None

    def zeigen(self):
        ctx = self.ctx
        doc, eigen = _EDITOR_KONTEXT["doc"], _EDITOR_KONTEXT["eigen"]
        namen = andere_abfragen(doc, eigen) if doc is not None else []
        if not namen:
            meldung(ctx, self.parent, "Es gibt keine andere gespeicherte Abfrage in dieser Datei. "
                    "Bitte die anzufügende Tabelle zuerst als eigene Abfrage anlegen und speichern.", "WARNINGBOX")
            return None
        keys = [k for k, _ in E.AUSRICHTUNG]
        alle_sp = list(self.tab.spalten)              # Spalten aller beteiligten Tabellen (für „Nur diese Spalten“)
        for n_ in namen:
            try:
                for c_ in E.hole_tabelle(n_).spalten:
                    if c_ not in alle_sp:
                        alle_sp.append(c_)
            except Exception:
                pass
        d = Dlg(ctx, "Anfügen", 300, 330)
        self.d = d
        d.add("FixedText", "t_q", 8, 8, 284, 10, Label="Tabellen (andere Abfragen), die angefügt werden (Mehrfachauswahl):")
        d.add("ListBox", "q", 8, 20, 284, 70, MultiSelection=True)
        gew = [namen.index(n) for n in (self.start.get("abfragen") or []) if n in namen]
        setze_liste(d.ctrl("q").getModel(), namen, gew)
        d.add("FixedText", "t_a", 8, 98, 284, 10, Label="Spalten zuordnen:")
        d.add("ListBox", "a", 8, 110, 284, 12, Dropdown=True, LineCount=3)
        setze_liste(d.ctrl("a").getModel(), [l for _, l in E.AUSRICHTUNG],
                    [keys.index(self.start.get("ausrichtung", "name")) if self.start.get("ausrichtung", "name") in keys else 0])
        d.add("FixedText", "t_h", 8, 128, 140, 20, Label="Herkunftsspalte (Name, leer = keine):", MultiLine=True)
        d.add("Edit", "h", 8, 150, 140, 12, Text=str(self.start.get("herkunft") or ""))
        d.add("FixedText", "t_e", 152, 128, 140, 20, Label="Herkunftswert der aktuellen Tabelle:", MultiLine=True)
        d.add("Edit", "e", 152, 150, 140, 12, Text=str(self.start.get("herkunft_eigen") or eigen or ""))
        d.add("FixedText", "t_z", 8, 166, 284, 20, MultiLine=True,
              Label="Abweichende Spaltennamen zuordnen (je Zeile: Spalte der angefügten Tabelle = Spalte der aktuellen Tabelle):")
        d.add("Edit", "z", 8, 188, 284, 34, MultiLine=True, VScroll=True, Text=str(self.start.get("zuordnung") or ""))
        d.add("FixedText", "t_n", 8, 226, 284, 10, Label="Nur diese Spalten der angefügten Tabellen übernehmen (keine Auswahl = alle):")
        d.add("ListBox", "n", 8, 238, 284, 62, MultiSelection=True)
        setze_liste(d.ctrl("n").getModel(), alle_sp,
                    [alle_sp.index(c) for c in (self.start.get("nur_spalten") or []) if c in alle_sp])
        d.add("Button", "ok", 164, 308, 62, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", 230, 308, 62, 14, Label="Abbrechen")
        d.model.Height = 330

        def ok():
            s = {"op": self.op, "abfragen": [namen[i] for i in sel_multi(d.ctrl("q")) if i < len(namen)],
                 "ausrichtung": keys[max(sel_pos(d.ctrl("a")), 0)],
                 "herkunft": d.ctrl("h").getText().strip(), "herkunft_eigen": d.ctrl("e").getText(),
                 "zuordnung": d.ctrl("z").getText(),
                 "nur_spalten": [alle_sp[i] for i in sel_multi(d.ctrl("n")) if i < len(alle_sp)]}
            try:
                E.wende_schritt(self.tab, s)
            except E.StepError as e:
                meldung(ctx, d.peer(), e.meldung, "WARNINGBOX")
                return
            self.ergebnis = s
            d.schliessen(1)
        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        auto = os.environ.get("ABFRAGE_AUTOOK")
        if auto:
            t = threading.Timer(float(auto), _sicher(ok))
            t.daemon = True
            t.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


_LETZTER_BED_DLG = {}


def bedingung_bearbeiten(ctx, doc, parent, bestehend=None):
    """Dialog „Schritt nur ausführen, wenn …“. -> dict {parameter, vergleich, wert}, {} = Bedingung entfernen, None = abbrechen."""
    namen = parameter_namen(doc)
    if not namen:
        meldung(ctx, parent, "In dieser Datei gibt es noch keinen Parameter.\n\nLege zuerst einen an (Knopf „Parameter…“ oben "
                "oder Menü OpenQuery ▸ Parameter …) oder gib einer Zelle einen Namen.")
        return None
    b = dict(bestehend or {})
    d = Dlg(ctx, "Schritt nur ausführen, wenn …", 280, 108)
    d.add("FixedText", "l1", 8, 10, 70, 10, Label="Parameter:")
    d.add("ListBox", "par", 80, 8, 192, 12, Dropdown=True, LineCount=12)
    setze_liste(d.ctrl("par").getModel(), namen, [namen.index(b["parameter"]) if b.get("parameter") in namen else 0])
    d.add("FixedText", "l2", 8, 28, 70, 10, Label="Vergleich:")
    d.add("ListBox", "vgl", 80, 26, 192, 12, Dropdown=True, LineCount=8)
    vw = [v for v, _ in E.BED_VERGLEICHE]
    setze_liste(d.ctrl("vgl").getModel(), [l for _, l in E.BED_VERGLEICHE], [vw.index(b["vergleich"]) if b.get("vergleich") in vw else 0])
    d.add("FixedText", "l3", 8, 46, 70, 10, Label="Wert:")
    d.add("Edit", "wert", 80, 44, 192, 12, Text=str(b.get("wert", "")))
    d.add("FixedText", "hinweis", 8, 62, 264, 22, MultiLine=True,
          Label="Ist die Bedingung nicht erfüllt, wird der Schritt übersprungen (wie ausgeschaltet). Datum so wie im Parameter, z. B. 31.12.2025.")
    d.add("Button", "weg", 8, 90, 90, 14, Label="Bedingung entfernen")
    d.add("Button", "ok", 150, 90, 58, 14, Label="OK", DefaultButton=True)
    d.add("Button", "abbr", 212, 90, 60, 14, Label="Abbrechen")
    res = {"v": None}
    _LETZTER_BED_DLG["d"] = d

    def ok():
        res["v"] = {"parameter": namen[max(sel_pos(d.ctrl("par")), 0)], "vergleich": vw[max(sel_pos(d.ctrl("vgl")), 0)],
                    "wert": d.ctrl("wert").getText().strip()}
        d.schliessen(1)
    d.on_click("ok", ok)
    d.on_click("weg", lambda: (res.update(v={}), d.schliessen(1)))
    d.on_click("abbr", lambda: d.schliessen(0))
    auto = os.environ.get("ABFRAGE_AUTOOK")
    if auto:
        t = threading.Timer(float(auto), _sicher(ok))
        t.daemon = True
        t.start()
    d.zeigen(parent)
    d.weg()
    return res["v"]


class DateiLesenDialog:
    """Schritt „Dateiinhalt einlesen“: Spalte mit dem Dateipfad, erste Datei oder alle untereinander,
    Navigator (Blatt/Tabelle/benannter Bereich) an Hand der Datei der ersten Zeile."""

    def __init__(self, ctx, op, tab_vor, schritt=None, vorbelegt=None, parent=None):
        self.ctx, self.op, self.tab, self.parent = ctx, op, tab_vor, parent
        self.start = dict(vorbelegt or {})
        if schritt:
            self.start.update(schritt)
        self.ergebnis = None

    def zeigen(self):
        ctx, tab = self.ctx, self.tab
        spalten = list(tab.spalten)
        wunsch = self.start.get("pfadspalte") or "Pfad"
        if wunsch not in spalten:
            kand = [c for c in spalten if c.casefold() == "pfad"]
            wunsch = kand[0] if kand else None
        if wunsch is None:
            meldung(ctx, self.parent, "In der Tabelle gibt es keine Spalte mit dem Dateipfad. Bitte in der Ordner-Quelle "
                    "(Schritt 01 doppelklicken) die Spalte „Pfad“ ankreuzen.", "WARNINGBOX")
            return None
        modi = [m for m, _ in E.DATEI_MODI]
        trn = [t for t, _ in QuellenDialog.TRENNER]
        d = Dlg(ctx, "Dateiinhalt einlesen", 300, 254)
        self.d = d
        d.add("FixedText", "l1", 8, 8, 110, 10, Label="Spalte mit dem Dateipfad:")
        d.add("ListBox", "pc", 120, 6, 172, 12, Dropdown=True, LineCount=8)
        setze_liste(d.ctrl("pc").getModel(), spalten, [spalten.index(wunsch)])
        d.add("FixedText", "l2", 8, 26, 110, 10, Label="Welche Dateien:")
        d.add("ListBox", "modus", 120, 24, 172, 12, Dropdown=True, LineCount=3)
        setze_liste(d.ctrl("modus").getModel(), [l for _, l in E.DATEI_MODI],
                    [modi.index(self.start.get("modus", "erste")) if self.start.get("modus", "erste") in modi else 0])
        d.add("FixedText", "l3", 8, 44, 110, 10, Label="Herkunftsspalte (leer = keine):")
        d.add("Edit", "herk", 120, 42, 172, 12, Text=str(self.start.get("herkunft", "Quelle.Datei") or ""))
        d.add("FixedText", "l4", 8, 62, 110, 10, Label="Trennzeichen (CSV):")
        d.add("ListBox", "trn", 120, 60, 172, 12, Dropdown=True, LineCount=6)
        setze_liste(d.ctrl("trn").getModel(), [l for _, l in QuellenDialog.TRENNER],
                    [trn.index(self.start.get("trenner", "auto")) if self.start.get("trenner", "auto") in trn else 0])
        d.add("FixedText", "l5", 8, 80, 110, 10, Label="Beispieldatei (erste Zeile):")
        d.add("Edit", "bsp", 120, 78, 172, 12, ReadOnly=True, Text="")
        d.add("FixedText", "l6", 8, 98, 110, 10, Label="Inhalt der Datei:")
        d.add("ListBox", "dw", 120, 96, 172, 12, Dropdown=True, LineCount=12)
        d.add("FixedText", "l7", 8, 116, 110, 10, Label="Bereich, z. B. A1:F500:")
        d.add("Edit", "ber", 120, 114, 172, 12, Text=str(self.start.get("bereich") or ""))
        d.add("Edit", "vor", 8, 132, 284, 62, MultiLine=True, ReadOnly=True, HScroll=False, VScroll=False)
        d.add("FixedText", "hinweis", 8, 198, 284, 30, MultiLine=True,
              Label="Blatt, Tabelle oder Bereich gelten für jede Datei. Bei „Alle Dateien“ muss jede Datei gleich aufgebaut sein; "
                    "sonst bricht die Abfrage mit dem Namen der Datei ab.")
        d.add("Button", "ok", 164, 236, 62, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", 230, 236, 62, 14, Label="Abbrechen")

        inhalt = {"pfad": None, "liste": [], "fehler": ""}

        def beispiel():
            i = sel_pos(d.ctrl("pc"))
            col = spalten[i] if 0 <= i < len(spalten) else wunsch
            k = spalten.index(col)
            for z in tab.zeilen:
                if not E.ist_leer(z[k]):
                    return str(z[k]).strip()
            return ""

        def lesen(*_):
            p = beispiel()
            d.ctrl("bsp").getModel().Text = p
            t_ = trn[max(sel_pos(d.ctrl("trn")), 0)]
            inhalt["liste"], inhalt["fehler"], inhalt["pfad"] = [], "", p
            try:
                if not p:
                    raise E.FormelFehler("Die Dateiliste ist leer: Es gibt keine Beispieldatei")
                inhalt["liste"] = datei_inhalt(ctx, p, t_)
            except Exception as ex:
                inhalt["fehler"] = str(ex)
            lst = inhalt["liste"]
            w = 0
            for k, e in enumerate(lst):
                if (e["typ"] == "tabelle" and e["name"] == self.start.get("tabelle")) \
                        or (e["typ"] == "name" and e["name"] == self.start.get("bereichsname")) \
                        or (e["typ"] == "blatt" and e["name"] == self.start.get("blatt")
                            and not self.start.get("tabelle") and not self.start.get("bereichsname")):
                    w = k
            setze_liste(d.ctrl("dw").getModel(), [e["text"] for e in lst], [w] if lst else [])
            if inhalt["fehler"]:
                d.ctrl("vor").getModel().Text = inhalt["fehler"]
            gewaehlt()

        def gewaehlt(*_):
            i, lst = sel_pos(d.ctrl("dw")), inhalt["liste"]
            if 0 <= i < len(lst):
                d.ctrl("vor").getModel().Text = lst[i]["vorschau"]
            d.ctrl("ber").getModel().Enabled = 0 <= i < len(lst) and lst[i]["typ"] == "blatt"

        d.on_select("dw", gewaehlt)
        d.on_select("pc", lesen)
        d.on_select("trn", lesen)
        lesen()

        def ok():
            lst = inhalt["liste"]
            i = sel_pos(d.ctrl("dw"))
            if not lst:
                meldung(ctx, d.peer(), inhalt["fehler"] or "Die Beispieldatei ist nicht lesbar.", "WARNINGBOX")
                return
            e = lst[i if 0 <= i < len(lst) else 0]
            st = {"op": self.op, "pfadspalte": spalten[max(sel_pos(d.ctrl("pc")), 0)],
                  "modus": modi[max(sel_pos(d.ctrl("modus")), 0)], "herkunft": d.ctrl("herk").getText().strip(),
                  "trenner": trn[max(sel_pos(d.ctrl("trn")), 0)]}
            if e["typ"] == "blatt":
                st["blatt"] = e["name"]
                if d.ctrl("ber").getText().strip():
                    st["bereich"] = d.ctrl("ber").getText().strip().upper()
            elif e["typ"] == "tabelle":
                st["tabelle"] = e["name"]
            elif e["typ"] == "name":
                st["bereichsname"] = e["name"]
            try:
                E.wende_schritt(tab, st)
            except E.StepError as ex:
                meldung(ctx, d.peer(), ex.meldung, "WARNINGBOX")
                return
            self.ergebnis = st
            d.schliessen(1)
        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        auto = os.environ.get("ABFRAGE_AUTOOK")
        if auto:
            t = threading.Timer(float(auto), _sicher(ok))
            t.daemon = True
            t.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


class SchrittDialog:
    """Erzeugt den Eingabedialog für einen Schritt generisch aus den Felddefinitionen der Engine."""
    BREITE_LABEL, BREITE_FELD = 125, 215
    BREITE_PANEL = 140
    OPERATOREN = ["+", "-", "*", "/", "^", "&", "(", ")", ";", "=", "<>", "<", ">"]

    def __init__(self, ctx, op, tab_vor, schritt=None, vorbelegt=None, parent=None):
        self.ctx, self.op, self.tab, self.parent = ctx, op, tab_vor, parent
        self.def_ = E.OPS[op]
        self.start = dict(vorbelegt or {})
        if schritt:
            self.start.update(schritt)
        self.ergebnis = None

    LISTE_MIN, LISTE_MAX = 62, 150
    FKT_BAND = 0                 # Höhe des Streifens mit den Funktionslisten (nur Dialoge mit Formelfeld)
    _kuerzen = 0                 # Dialogeinheiten, um die Listen kürzer werden (Dialog wäre sonst höher als der Bildschirm)

    KURZ_MAX = 4            # Auswahlen mit höchstens so vielen Einträgen zeigen die ganze Liste statt eines Dropdowns

    def _als_liste(self, f):
        """Ganze Liste sichtbar? Ja bei ausdrücklichem Wunsch oder bei kurzer Auswahl – aber nur, solange es keine Parameter
        gibt (im Dropdown lassen sich zusätzlich {Parameter} wählen)."""
        if f.get("als_liste"):
            return True
        try:
            if f["art"] != "wahl" or len(f["wahl"]) > self.KURZ_MAX:
                return False
            return not parameter_namen(_EDITOR_KONTEXT.get("doc"))
        except Exception:
            return False

    def _hoehe(self, f):
        art = f["art"]
        if art == "spalten":                 # Spaltenliste: so lang, wie es bei der Spaltenzahl sinnvoll ist
            h = int(max(self.LISTE_MIN, min(self.LISTE_MAX, len(self.tab.spalten) * 8.6 + 6))) - self._kuerzen
            h = max(h, 40)
        elif art == "liste":
            h = max(80 - self._kuerzen, 40)
        elif art == "formel":
            h = 70
        elif art == "wahl" and self._als_liste(f):
            h = len(f["wahl"]) * 9 + 6
        elif art == "textblock":
            h = 40 if self.op == "hand_behalten" else 62
        elif art == "aggregation":
            h = f.get("zeilen", 3) * 15 - 3 + 12          # + Kopfzeile
        else:
            h = 12
        if len(f["label"]) > 34 and h < 20:
            h = 20        # langes Etikett braucht zwei Zeilen
        return h

    def zeigen(self):
        ctx, tab = self.ctx, self.tab
        felder = self.def_["felder"]
        if self.op == "tabellen_verbinden":
            return VerbindenDialog(ctx, self.op, tab, None, self.start, self.parent).zeigen()
        if self.op == "tabellen_anfuegen":
            return AnfuegenDialog(ctx, self.op, tab, None, self.start, self.parent).zeigen()
        if self.op == "datei_einlesen":
            return DateiLesenDialog(ctx, self.op, tab, None, self.start, self.parent).zeigen()
        if any(f["art"] == "klauseln" for f in felder):
            self._inst = BedingtDialog(ctx, self.op, tab, None, self.start, self.parent)
            return self._inst.zeigen()
        if not felder:
            return None                           # Schritt ohne Eingaben: es gibt nichts zu ändern
        spalten = list(tab.spalten)
        laengste = max(len(f["label"]) for f in felder)
        if laengste <= 30:                        # kurze Etiketten: Feld rückt näher an die Beschriftung
            self.BREITE_LABEL = int(min(125, max(55, laengste * 5 + 8)))
        w = self.BREITE_LABEL + self.BREITE_FELD + 24
        hat_formel = any(f["art"] == "formel" for f in felder)
        self.FKT_BAND = 80 if hat_formel else 0
        panel_x = w                       # rechts: Spalten- und Funktionsliste wie in Power Query
        if hat_formel:
            w += self.BREITE_PANEL + 8
        try:                                      # nie höher als der Bildschirm (grob 2 Pixel je Dialogeinheit)
            max_du = int(toolkit(ctx).getWorkArea().Height / 2.0) - 40
        except Exception:
            max_du = 9999
        self._kuerzen = 0
        for _runde in range(2):
            y = 8
            pos = {}
            for f in felder:
                h = self._hoehe(f)
                if f.get("block_vor"):
                    y += 9                            # mehr Abstand vor einem neuen Block
                pos[f["name"]] = (y, h)
                y += h + 5
                if f["art"] == "formel":
                    y += self.FKT_BAND                # Funktionslisten über die ganze Breite unter der Formel
            hoehe = y + 52
            if hoehe <= max_du or _runde:
                break
            n_listen = sum(1 for f in felder if f["art"] in ("spalten", "liste")) or 1
            self._kuerzen = int((hoehe - max_du) / n_listen) + 1
        d = Dlg(ctx, self.def_["titel"], w, hoehe)
        self.d = d
        lx, fx = 8, 8 + self.BREITE_LABEL + 4
        kontroll = {}
        agg_namen = {}
        doc_ = _EDITOR_KONTEXT.get("doc")
        pn = ["{%s}" % n_ for n_ in parameter_namen(doc_)]            # Parameter als wählbare Einträge: {Name}
        pn_jn = ["{%s}" % n_ for n_ in parameter_namen(doc_, True)]
        spalten_pn = spalten + pn
        ja_dd = set()
        fehlend = {}                                   # Feldname -> Spaltennamen, die es hier nicht mehr gibt (nur „Manuelle Spalten“)
        lp_namen = {}                                  # Feldname -> wählbare Parameternamen (Art „listenparam“)
        for f in felder:
            fy, fh = pos[f["name"]]
            d.add("FixedText", "lbl_" + f["name"], lx, fy + 1, self.BREITE_LABEL, 10 if fh == 12 else 20,
                  Label=f["label"], MultiLine=True)
            n = "f_" + f["name"]
            wert = self.start.get(f["name"], f.get("standard"))
            art = f["art"]
            if art == "spalte":
                items = (["(keine)"] if f.get("optional") else []) + spalten_pn
                d.add("ListBox", n, fx, fy, self.BREITE_FELD, 12, Dropdown=True, LineCount=12)
                sel = 0
                if wert in spalten_pn:
                    sel = spalten_pn.index(wert) + (1 if f.get("optional") else 0)
                setze_liste(d.ctrl(n).getModel(), items, [sel])
            elif art == "spalten":
                d.add("ListBox", n, fx, fy, self.BREITE_FELD, fh, MultiSelection=True, Border=2)
                gewaehlt = [spalten_pn.index(s) for s in (wert or []) if s in spalten_pn]
                items_sp = list(spalten_pn)
                if self.op == "hand_behalten":
                    # Schlüsselspalte, die es an dieser Stelle nicht mehr gibt (Überschrift in einem früheren Schritt oder in
                    # der Quelle geändert): sichtbar mit Hinweis behalten statt stillschweigend zu verlieren
                    fehlend[f["name"]] = [x for x in (wert or []) if x not in spalten_pn]
                    for k_, x in enumerate(fehlend[f["name"]]):
                        items_sp.append("⚠ %s  (fehlt hier)" % x)
                        gewaehlt.append(len(spalten_pn) + k_)
                setze_liste(d.ctrl(n).getModel(), items_sp, gewaehlt)
            elif art == "wahl":
                labels = [l for _, l in f["wahl"]]
                werte = [v for v, _ in f["wahl"]]
                if self._als_liste(f):      # ganze Liste sichtbar statt Dropdown
                    d.add("ListBox", n, fx, fy, self.BREITE_FELD, fh)
                else:
                    d.add("ListBox", n, fx, fy, self.BREITE_FELD, 12, Dropdown=True, LineCount=10)
                    labels, werte = labels + pn, werte + pn
                setze_liste(d.ctrl(n).getModel(), labels, [werte.index(wert) if wert in werte else 0])
            elif art == "ja_nein" and pn_jn:        # mit Ja/Nein-Parameter: Auswahl Ja / Nein / {Parameter}
                d.add("ListBox", n, fx, fy, self.BREITE_FELD, 12, Dropdown=True, LineCount=10)
                eintraege = ["Ja", "Nein"] + pn_jn
                setze_liste(d.ctrl(n).getModel(), eintraege,
                            [pn_jn.index(wert) + 2 if wert in pn_jn else (0 if wert else 1)])
                ja_dd.add(f["name"])
            elif art == "ja_nein":
                d.add("CheckBox", n, fx, fy, self.BREITE_FELD, 12, Label="", State=1 if wert else 0)
            elif art == "formel":
                d.add("Edit", n, fx, fy, self.BREITE_FELD, 38, MultiLine=True, VScroll=True,
                      Text=str(wert or ""), AutoVScroll=True)
                bw = self.BREITE_FELD // len(self.OPERATOREN)
                for k, op_ in enumerate(self.OPERATOREN):
                    d.add("Button", "op%d" % k, fx + k * bw, fy + 41, bw, 12, Label=op_)
                d.add("Button", "btnRunden", fx, fy + 56, 160, 12, Label="Auswahl/Formel mit RUNDEN umschließen, Stellen:")
                d.add("Edit", "stellen", fx + 165, fy + 56, 28, 12, Text="2")
            elif art == "listenparam":
                namen_lp = list(parameter_namen(doc_))
                if wert and wert not in namen_lp:
                    namen_lp.append(wert)              # Parameter inzwischen gelöscht: Name bleibt sichtbar (Ausführen meldet den Fehler)
                lp_namen[f["name"]] = namen_lp
                d.add("ListBox", n, fx, fy, self.BREITE_FELD, 12, Dropdown=True, LineCount=10)
                setze_liste(d.ctrl(n).getModel(), ["(Werte unten ankreuzen)"] + namen_lp,
                            [namen_lp.index(wert) + 1 if wert in namen_lp else 0])
            elif art == "liste":
                d.add("Edit", "such", fx + 62, fy, self.BREITE_FELD - 62, 12)      # Filter: enthält …
                d.add("FixedText", "lbl_such", fx, fy + 2, 60, 10, Label="Suche (enthält):")
                d.add("ListBox", n, fx, fy + 15, self.BREITE_FELD, fh - 15, MultiSelection=True)
            elif art == "textblock":
                text = "" if wert is None else str(wert)
                if text == "" and f.get("vorbelegung") == "spaltenliste":
                    text = "\n".join("%s = %s" % (s, s) for s in spalten)
                d.add("Edit", n, fx, fy, self.BREITE_FELD, fh, MultiLine=True, VScroll=True, Text=text)
            elif art == "aggregation":
                zeilen = f.get("zeilen", 3)
                vorhanden = list(wert or [])
                namen = []
                bs, bf, bn = 80, 70, self.BREITE_FELD - 80 - 70 - 10
                fn_labels = ["(keine)"] + [l for _, l in E.AGG_FN]
                fn_werte = [v for v, _ in E.AGG_FN]
                for tx_, bx_, bw_ in (("Spalte", fx, bs), ("Funktion", fx + bs + 5, bf), ("Neuer Name", fx + bs + bf + 10, bn)):
                    d.add("FixedText", "kopf_%s_%s" % (f["name"], tx_), bx_, fy, bw_, 10, Label=tx_)
                for i in range(zeilen):
                    a = vorhanden[i] if i < len(vorhanden) else {}
                    zy = fy + 12 + i * 15
                    nm_sp, nm_fn, nm_nm = "agg%d_sp" % i, "agg%d_fn" % i, "agg%d_nm" % i
                    d.add("ListBox", nm_sp, fx, zy, bs, 12, Dropdown=True, LineCount=12)
                    setze_liste(d.ctrl(nm_sp).getModel(), ["(Spalte)"] + spalten,
                                [spalten.index(a["spalte"]) + 1 if a.get("spalte") in spalten else 0])
                    d.add("ListBox", nm_fn, fx + bs + 5, zy, bf, 12, Dropdown=True, LineCount=10)
                    setze_liste(d.ctrl(nm_fn).getModel(), fn_labels,
                                [fn_werte.index(a["fn"]) + 1 if a.get("fn") in fn_werte else 0])
                    d.add("Edit", nm_nm, fx + bs + bf + 10, zy, bn, 12, Text=a.get("name", ""))
                    namen.append((nm_sp, nm_fn, nm_nm))
                agg_namen[f["name"]] = namen
            else:   # text, zahl
                d.add("Edit", n, fx, fy, self.BREITE_FELD, 12, Text="" if wert is None else str(wert))
            kontroll[f["name"]] = art

        d.add("FixedText", "fehler", 8, y, w - 16, 26, MultiLine=True, Label="", TextColor=0xB00020)
        if any(fehlend.values()):
            d.ctrl("fehler").getModel().Label = (
                "Die mit ⚠ markierte Spalte gibt es an dieser Stelle nicht mehr (Überschrift in der Quelle oder in einem "
                "früheren Schritt geändert?). Bitte die richtige Spalte wählen und die ⚠-Zeile abwählen.")
        d.add("Button", "ok", w - 150, hoehe - 20, 70, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", w - 76, hoehe - 20, 68, 14, Label="Abbrechen")

        # Parameter: benannte Zelle als {Name} in ein Textfeld / die Formel einfügen
        param_felder = [f["name"] for f in felder if f["art"] in ("text", "formel", "textblock", "zahl")]
        if param_felder:
            d.add("Button", "btnParam", 8, hoehe - 20, 110, 14, Label="{ } Parameter…")
            merker = {"feld": "f_" + param_felder[0]}
            for fn_ in param_felder:
                fk = _Fokus((lambda nm: lambda: merker.update(feld=nm))("f_" + fn_))
                d.refs.append(fk)
                d.ctrl("f_" + fn_).addFocusListener(fk)

            def parameter_einfuegen():
                doc_ = _EDITOR_KONTEXT.get("doc")
                liste = parameter_liste(doc_) if doc_ is not None else []
                if not liste:
                    meldung(ctx, self.parent, "In dieser Datei gibt es noch keinen Parameter.\n\n"
                            "Entweder legst du in OpenQuery einen an (Knopf „Parameter…“ oben oder Menü OpenQuery ▸ "
                            "Parameter …), oder du gibst einer Zelle einen Namen: Zelle markieren, im Namensfeld links "
                            "über der Tabelle einen Namen eintippen (z. B. Startdatum) und Enter drücken.")
                    return
                i = waehle_aus_liste(ctx, "Parameter", "Parameter wählen (wird als {Name} eingefügt):",
                                     ["%s   =   %s" % (n_, w_) for n_, w_ in liste], self.parent)
                if i is None:
                    return
                c_ = d.ctrl(merker["feld"])
                c_.insertText(c_.getSelection(), "{%s}" % liste[i][0])
                c_.setFocus()
            d.on_click("btnParam", parameter_einfuegen)
            self._parameter_einfuegen = parameter_einfuegen     # für Tests

        # Werteliste (Mehrfachauswahl) aufbauen / bei Spaltenwechsel neu füllen
        liste_felder = [f for f in felder if f["art"] == "liste"]
        auswahl_merker = {"werte": list(self.start.get("werte") or [])}

        def spalte_aktuell():
            if "spalte" not in kontroll:
                return None
            c = d.ctrl("f_spalte")
            i = sel_pos(c)
            off = 1 if any(f["name"] == "spalte" and f.get("optional") for f in felder) else 0
            return spalten[i - off] if 0 <= i - off < len(spalten) else None

        alle_werte = []      # alle Werte der Spalte; auswahl_merker["werte"] = gewählte (auch die gerade ausgeblendeten)

        def anzeige_werte():
            such = d.ctrl("such").getText().strip().casefold() if "such" in [x for x in d.model.getElementNames()] else ""
            return [v for v in alle_werte if such in str(v).casefold()] if such else list(alle_werte)

        def liste_fuellen(*_):
            if not liste_felder:
                return
            sp = spalte_aktuell()
            n = "f_" + liste_felder[0]["name"]
            alle_werte[:] = E.eindeutige_werte(tab, sp) if sp else []
            gezeigt = anzeige_werte()
            self._liste_werte = gezeigt
            anzeige = ["(leer)" if v == "" else v for v in gezeigt]
            sel = [i for i, v in enumerate(gezeigt) if v in auswahl_merker["werte"]]
            setze_liste(d.ctrl(n).getModel(), anzeige, sel)

        if liste_felder:
            def merke(*_):
                """Auswahl der sichtbaren Werte in die Gesamtauswahl übernehmen (ausgeblendete bleiben erhalten)."""
                n = "f_" + liste_felder[0]["name"]
                idx = set(sel_multi(d.ctrl(n)))
                gew = [v for v in auswahl_merker["werte"] if v not in self._liste_werte]
                gew += [v for i, v in enumerate(self._liste_werte) if i in idx]
                auswahl_merker["werte"] = gew

            class _Such(unohelper.Base, XTextListener):
                def textChanged(self_, ev):
                    _sicher(lambda: (merke(), liste_fuellen()))()

                def disposing(self_, ev):
                    pass
            such_l = _Such()
            d.refs.append(such_l)
            d.ctrl("such").addTextListener(such_l)
            d.on_select("f_" + liste_felder[0]["name"], merke)
            d.on_select("f_spalte", lambda e: (merke(), auswahl_merker.update(werte=[]), liste_fuellen()))
            liste_fuellen()
            lp_felder = [f for f in felder if f["art"] == "listenparam"]
            if lp_felder:
                lpn = "f_" + lp_felder[0]["name"]

                def lp_umschalten(*_):
                    """Mit gewähltem Listenparameter ist das Ankreuzen der Werte abgeschaltet."""
                    an = sel_pos(d.ctrl(lpn)) <= 0
                    d.ctrl("such").getModel().Enabled = an
                    d.ctrl("f_" + liste_felder[0]["name"]).getModel().Enabled = an
                d.on_select(lpn, lp_umschalten)
                lp_umschalten()
                self._lp_umschalten = lp_umschalten

        # Einfügehilfen für Formeln
        if "formel" in kontroll.values():
            fname = [f["name"] for f in felder if f["art"] == "formel"][0]

            ed = d.ctrl("f_" + fname)

            def text_einfuegen(text):
                ed.insertText(ed.getSelection(), text)
                ed.setFocus()

            def liste_einfuegen(listname, fmt):
                c = d.ctrl(listname)
                i = sel_pos(c)
                if i < 0:
                    return
                roh_ = c.getModel().StringItemList[i]
                setze_liste(c.getModel(), c.getModel().StringItemList, [])   # Auswahl löschen -> erneuter Klick möglich
                if roh_.startswith(KATEGORIE_MARKE):                          # Kategorieüberschrift: nichts einfügen
                    return
                text = fmt(roh_)
                sel_text = ed.getSelectedText()
                if sel_text and listname != "ins_sp" and "(" in text:         # Markierung wird zum ersten Argument der Funktion
                    kopf_, rest_ = text.split("(", 1)
                    args_ = rest_.rstrip(")").split("; ")
                    args_[0] = sel_text
                    text = "%s(%s)" % (kopf_, "; ".join(args_))
                text_einfuegen(text)

            # rechts: Spalten (Doppelklick fügt ein); darunter über die ganze Breite die Funktionen, je Rubrik eine Liste
            px, pw = panel_x + 4, self.BREITE_PANEL
            fy_f, fh_f = pos[fname]
            d.add("FixedText", "lbl_ins_sp", px, 8, pw, 10, Label="Spalten (Doppelklick fügt [Name] ein)")
            d.add("ListBox", "ins_sp", px, 20, pw, fy_f + 68 - 20, Border=2)
            setze_liste(d.ctrl("ins_sp").getModel(), spalten, [])
            yb = fy_f + fh_f + 4
            d.add("FixedText", "lbl_ins_fn", 8, yb, w - 16, 10,
                  Label="Funktionen (Doppelklick fügt ein; markierter Text im Formelfeld wird eingeschlossen)")
            n_k = len(FUNKTIONS_KATEGORIEN)
            bk = (w - 16 - (n_k - 1) * 4) // n_k
            fn_listen = []
            for k_, (kat, fl) in enumerate(FUNKTIONS_KATEGORIEN):
                ln_ = "ins_fn%d" % k_
                kx = 8 + k_ * (bk + 4)
                d.add("FixedText", "lbl_" + ln_, kx, yb + 11, bk, 9, Label=kat, FontWeight=150.0)
                d.add("ListBox", ln_, kx, yb + 21, bk, self.FKT_BAND - 24, Border=2)
                setze_liste(d.ctrl(ln_).getModel(), sorted(fl, key=lambda t: t.casefold()), [])
                fn_listen.append(ln_)
            for ln_, fm_ in [("ins_sp", lambda t: "[%s]" % t)] + [(l_, lambda t: t) for l_ in fn_listen]:     # Einfachklick wählt, Doppelklick fügt ein
                dk = _Maus(_sicher(lambda ev, ln_=ln_, fm_=fm_: liste_einfuegen(ln_, fm_) if getattr(ev, "ClickCount", 1) >= 2 else None))
                d.refs.append(dk)
                d.ctrl(ln_).addMouseListener(dk)
            for k, op_ in enumerate(self.OPERATOREN):
                d.on_click("op%d" % k, (lambda o: lambda: text_einfuegen(
                    o if o in ("(", ")") else (o + " " if o == ";" else " %s " % o)))(op_))

            def runden():
                try:
                    n = int(d.ctrl("stellen").getText().strip() or "0")
                except ValueError:
                    n = 2
                sel = ed.getSelectedText()
                if sel:
                    ed.insertText(ed.getSelection(), "RUNDEN(%s; %d)" % (sel, n))
                else:
                    ed.setText("RUNDEN(%s; %d)" % (ed.getText(), n))
                ed.setFocus()
            d.on_click("btnRunden", runden)
            self._runden, self._text_einfuegen = runden, text_einfuegen   # für Tests
            self._liste_einfuegen = liste_einfuegen

        # Felder je nach Auswahl ein-/ausblenden (Angabe zeige=(Feld, Werte[, "nicht"]) in der Felddefinition)
        def sichtbar(f):
            z = f.get("zeige")
            if not z:
                return True
            cf = next((g for g in felder if g["name"] == z[0]), None)
            if cf is None or cf["art"] != "wahl" or ("f_" + z[0]) not in [x for x in d.model.getElementNames()]:
                return True
            werte_ = [v for v, _ in cf["wahl"]]
            j = max(sel_pos(d.ctrl("f_" + z[0])), 0)
            if j >= len(werte_):
                return True                      # ein {Parameter} ist gewählt: Felder bleiben sichtbar
            ist = werte_[j] in z[1]
            return (not ist) if len(z) > 2 and z[2] == "nicht" else ist

        def layout(*_):
            yy = 8
            for f in felder:
                if not sichtbar(f):
                    for nm in ("lbl_" + f["name"], "f_" + f["name"]):
                        d.modell(nm).EnableVisible = False
                    continue
                fy_, fh_ = yy + (9 if f.get("block_vor") else 0), self._hoehe(f)
                d.modell("lbl_" + f["name"]).PositionY = fy_ + 1
                d.modell("f_" + f["name"]).PositionY = fy_
                for nm in ("lbl_" + f["name"], "f_" + f["name"]):
                    d.modell(nm).EnableVisible = True
                yy = fy_ + fh_ + 5 + (self.FKT_BAND if f["art"] == "formel" else 0)
            d.modell("fehler").PositionY = yy
            h_neu = yy + 52
            for nm in ("ok", "abbr", "btnParam"):
                if nm in [x for x in d.model.getElementNames()]:
                    d.modell(nm).PositionY = h_neu - 20
            d.model.Height = h_neu
            self._hoehe_dialog = h_neu

        dyn = [f for f in felder if f.get("zeige")]
        if dyn and not any(f["art"] in ("formel", "liste", "aggregation") for f in felder):
            for nm in sorted({f["zeige"][0] for f in dyn}):
                d.on_select("f_" + nm, layout)
            layout()
            self._layout = layout                 # für Tests

        def sammeln():
            s = {"op": self.op}
            for f in felder:
                n, art = "f_" + f["name"], f["art"]
                if f.get("zeige") and not sichtbar(f):
                    continue                     # ausgeblendetes Feld: gehört nicht zum Schritt
                if art == "aggregation":
                    zeilen = []
                    for nm_sp, nm_fn, nm_nm in agg_namen[f["name"]]:
                        fi = sel_pos(d.ctrl(nm_fn)) - 1
                        if fi < 0:
                            continue
                        si = sel_pos(d.ctrl(nm_sp)) - 1
                        zeilen.append({"spalte": spalten[si] if si >= 0 else "", "fn": E.AGG_FN[fi][0],
                                       "name": d.ctrl(nm_nm).getText().strip()})
                    s[f["name"]] = zeilen
                    continue
                c = d.ctrl(n)
                if art == "spalte":
                    i = sel_pos(c)
                    if f.get("optional"):
                        s[f["name"]] = spalten_pn[i - 1] if i > 0 else ""
                    else:
                        s[f["name"]] = spalten_pn[i] if i >= 0 else ""
                elif art == "spalten":
                    alle_sp = spalten_pn + fehlend.get(f["name"], [])
                    s[f["name"]] = [alle_sp[i] for i in sel_multi(c) if i < len(alle_sp)]
                elif art == "listenparam":
                    j = sel_pos(c)
                    if j > 0:
                        s[f["name"]] = lp_namen[f["name"]][j - 1]
                elif art == "wahl":
                    j = max(sel_pos(c), 0)
                    s[f["name"]] = f["wahl"][j][0] if j < len(f["wahl"]) else pn[j - len(f["wahl"])]
                elif art == "ja_nein" and f["name"] in ja_dd:
                    j = max(sel_pos(c), 0)
                    s[f["name"]] = (j == 0) if j < 2 else pn_jn[j - 2]
                elif art == "ja_nein":
                    s[f["name"]] = bool(c.getModel().State)
                elif art == "zahl":
                    t = c.getText().strip()
                    if t == "":
                        s[f["name"]] = f.get("standard", 0)
                    elif "{" in t and "}" in t:
                        s[f["name"]] = t              # {Parameter}: wird beim Ausführen aufgelöst
                    else:
                        try:
                            s[f["name"]] = int(float(t.replace(",", ".")))
                        except ValueError:
                            raise E.FormelFehler("'%s' muss eine ganze Zahl sein" % f["label"])
                elif art == "liste":
                    merke()
                    s[f["name"]] = [v for v in alle_werte if v in auswahl_merker["werte"]]
                else:
                    s[f["name"]] = c.getText()
            if self.start.get("aktiv") is False:      # ein ausgeschalteter Schritt bleibt ausgeschaltet
                s["aktiv"] = False
            return s

        def ok():
            try:
                s = sammeln()
                E.wende_schritt(tab, s)
            except E.StepError as e:
                d.ctrl("fehler").getModel().Label = e.meldung
                return
            except Exception as e:
                d.ctrl("fehler").getModel().Label = str(e)
                return
            self.ergebnis = s
            d.schliessen(1)

        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        auto = os.environ.get("ABFRAGE_AUTOOK")
        if auto:   # Testbetrieb: simuliert den Klick auf OK
            t = threading.Timer(float(auto), _sicher(ok))
            t.daemon = True
            t.start()
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


def frage_text(ctx, titel, text, vorgabe="", parent=None):
    """Kleiner Dialog mit einem Eingabefeld. -> Text oder None bei Abbruch."""
    d = Dlg(ctx, titel, 240, 70)
    d.add("FixedText", "l", 8, 8, 224, 10, Label=text)
    d.add("Edit", "t", 8, 22, 224, 14, Text=vorgabe or "")
    d.add("Button", "ok", 100, 48, 62, 14, Label="OK", DefaultButton=True)
    d.add("Button", "abbr", 166, 48, 66, 14, Label="Abbrechen")
    res = {"t": None}

    def ok():
        res["t"] = d.ctrl("t").getText()
        d.schliessen(1)
    d.on_click("ok", ok)
    d.on_click("abbr", lambda: d.schliessen(0))
    auto = os.environ.get("ABFRAGE_FRAGETEXT")      # Testbetrieb: Eingabe simulieren
    if auto is not None:
        def tippe():
            d.ctrl("t").getModel().Text = auto
            ok()
        t = threading.Timer(1.0, _sicher(tippe))
        t.daemon = True
        t.start()
    d.zeigen(parent)
    d.weg()
    return res["t"]


class EigenschaftenDialog:
    """Name und Beschreibung einer Abfrage."""

    def __init__(self, ctx, abfrage, name_pruefen, parent=None):
        self.ctx, self.a, self.pruefen, self.parent = ctx, abfrage, name_pruefen, parent
        self.ergebnis = None

    def zeigen(self):
        d = Dlg(self.ctx, "Eigenschaften der Abfrage", 260, 130)
        d.add("FixedText", "l1", 8, 8, 60, 10, Label="Name:")
        d.add("Edit", "name", 70, 6, 182, 12, Text=self.a.name)
        d.add("FixedText", "l2", 8, 26, 60, 10, Label="Beschreibung:")
        lang = len(self.a.beschreibung or "") > 150 or (self.a.beschreibung or "").count("\n") >= 3
        d.add("Edit", "beschr", 70, 24, 182, 50, Text=self.a.beschreibung, MultiLine=True, VScroll=lang,
              Border=1)             # Rahmen wie die anderen Felder; der Rollbalken erscheint nur bei langem Text
        d.add("FixedText", "info", 8, 80, 244, 24, MultiLine=True,
              Label="Quelle: %s\nSchritte: %d" % (beschreibe_quelle(self.a.quelle), len(self.a.schritte)),
              TextColor=0x555555)
        d.add("Button", "ok", 120, 110, 62, 14, Label="OK", DefaultButton=True)
        d.add("Button", "abbr", 186, 110, 66, 14, Label="Abbrechen")

        def ok():
            name = d.ctrl("name").getText().strip()
            fehler = self.pruefen(name)
            if fehler:
                meldung(self.ctx, d.peer(), fehler, "WARNINGBOX")
                return
            self.ergebnis = (name, d.ctrl("beschr").getText())
            d.schliessen(1)
        d.on_click("ok", ok)
        d.on_click("abbr", lambda: d.schliessen(0))
        d.zeigen(self.parent)
        d.weg()
        return self.ergebnis


def start_anpassen_dialog(ctx, parent, aktuell):
    """Auswahl und Reihenfolge der Knöpfe im Start-Reiter. aktuell: Liste von Kennungen ("|" = Trennlinie).
    Rückgabe: neue Liste oder None."""
    d = Dlg(ctx, "Start-Reiter anpassen", 330, 200)
    d.add("FixedText", "l1", 8, 6, 120, 10, Label="Verfügbare Knöpfe")
    d.add("FixedText", "l2", 190, 6, 130, 10, Label="Im Start-Reiter (in dieser Reihenfolge)")
    d.add("ListBox", "frei", 8, 18, 130, 150, Border=1)
    d.add("ListBox", "im", 190, 18, 132, 150, Border=1)
    d.add("Button", "hin", 142, 40, 44, 14, Label="Hinzu ▸", HelpText="Gewählten Knopf in den Start-Reiter übernehmen")
    d.add("Button", "weg", 142, 58, 44, 14, Label="◂ Weg", HelpText="Gewählten Knopf aus dem Start-Reiter nehmen")
    d.add("Button", "hoch", 142, 82, 44, 14, Label="▲", HelpText="Nach oben")
    d.add("Button", "runter", 142, 100, 44, 14, Label="▼", HelpText="Nach unten")
    d.add("Button", "trenn", 142, 124, 44, 14, Label="| Lücke", HelpText="Lücke (Trennung) hinter dem gewählten Knopf einfügen")
    d.add("Button", "stand", 8, 176, 80, 14, Label="Zurücksetzen", HelpText="Die ursprüngliche Anordnung wiederherstellen")
    d.add("Button", "ok", 192, 176, 62, 14, Label="OK", DefaultButton=True)
    d.add("Button", "abbr", 258, 176, 64, 14, Label="Abbrechen")
    liste = [i for i in aktuell if i == "|" or i in ALLE_EINTRAEGE]
    res = {"liste": None}

    def text(i):
        return "──────" if i == "|" else ALLE_EINTRAEGE[i][1].replace("\n", " ").replace(" ▾", " ▾")

    def frei_ids():
        drin = set(liste)
        return sorted([i for i in ALLE_EINTRAEGE if i not in drin], key=lambda i: text(i).casefold())

    def zeige(frei_sel=None, im_sel=None):
        fr = frei_ids()
        setze_liste(d.ctrl("frei").getModel(), [text(i) for i in fr], [frei_sel] if frei_sel is not None and fr else [])
        setze_liste(d.ctrl("im").getModel(), [text(i) for i in liste], [im_sel] if im_sel is not None and liste else [])
        d._fr = fr

    def hin():
        i = sel_pos(d.ctrl("frei"))
        if i < 0:
            return
        j = sel_pos(d.ctrl("im"))
        pos = j + 1 if j >= 0 else len(liste)
        liste.insert(pos, d._fr[i])
        zeige(min(i, max(len(d._fr) - 2, 0)), pos)

    def weg():
        j = sel_pos(d.ctrl("im"))
        if j < 0:
            return
        del liste[j]
        zeige(None, min(j, len(liste) - 1) if liste else None)

    def bewege(delta):
        j = sel_pos(d.ctrl("im"))
        if j < 0 or not (0 <= j + delta < len(liste)):
            return
        liste[j], liste[j + delta] = liste[j + delta], liste[j]
        zeige(None, j + delta)

    def trenn():
        j = sel_pos(d.ctrl("im"))
        liste.insert(j + 1 if j >= 0 else len(liste), "|")
        zeige(None, j + 1 if j >= 0 else len(liste) - 1)

    def stand():
        liste[:] = list(START_STANDARD)
        zeige()

    def ok():
        res["liste"] = list(liste)
        d.schliessen(1)
    zeige()
    for n, f in (("hin", hin), ("weg", weg), ("hoch", lambda: bewege(-1)), ("runter", lambda: bewege(1)),
                 ("trenn", trenn), ("stand", stand), ("ok", ok), ("abbr", lambda: d.schliessen(0))):
        d.on_click(n, f)
    d.zeigen(parent)
    d.weg()
    return res["liste"]


def waehle_aus_liste(ctx, titel, text, items, parent=None):
    d = Dlg(ctx, titel, 240, 130)
    d.add("FixedText", "l", 8, 8, 224, 10, Label=text)
    d.add("ListBox", "lst", 8, 20, 224, 84)
    setze_liste(d.ctrl("lst").getModel(), items, [0] if items else [])
    d.add("Button", "ok", 100, 110, 62, 14, Label="OK", DefaultButton=True)
    d.add("Button", "abbr", 166, 110, 66, 14, Label="Abbrechen")
    res = {"i": None}

    def ok():
        i = sel_pos(d.ctrl("lst"))
        if i >= 0:
            res["i"] = i
            d.schliessen(1)
    d.on_click("ok", ok)
    d.on_click("abbr", lambda: d.schliessen(0))
    d.zeigen(parent)
    d.weg()
    return res["i"]


def symbol_url(name):
    """file-URL eines Leisten-Symbols (icons/<name>.png im Paket); leer, wenn es fehlt."""
    try:
        pfad = os.path.join(_hier, "icons", name + ".png")
        return uno.systemPathToFileUrl(pfad) if os.path.exists(pfad) else ""
    except Exception:
        return ""


# Leiste im Kopf: Reiter -> Knöpfe (id, Beschriftung, Symbol, Aktion, Hilfetext); None = Lücke.
# Aktion: ("fn", Methode) | ("op", Schritt) | ("menu", [(Text, Schritt), …]) | ("tgl", Häkchen)
LEISTE = [
    ("Start", [
        ("laden", "Schließen\nund Laden", "laden_schliessen", ("fn", "laden"), "Schließen und Laden: Abfragen ins Tabellenblatt schreiben und den Editor schließen"),
        ("ladenin", "Laden in …", "laden_schliessen_in", ("fn", "laden_in"), "Schließen und Laden in …: Ausgabe wählen (neues Blatt, bestehendes Blatt, Zelle, nur Verbindung)"),
        None,
        ("u_rueck", "Rückgängig", "rueckgaengig", ("fn", "rueckgaengig"), "Letzte Änderung an der Abfrage rückgängig machen"),
        ("u_wied", "Wiederholen", "wiederholen", ("fn", "wiederholen"), "Rückgängig gemachte Änderung wiederholen"),
        None,
        ("aktual", "Aktualisieren", "aktualisieren", ("fn", "vorschau_aktualisieren"), "Quelle dieser Abfrage neu einlesen und die Vorschau aktualisieren"),
        ("aktalle", "Alle aktualisieren", "alle_aktualisieren", ("fn", "alle_vorschau_aktualisieren"), "Die Quellen aller Abfragen neu einlesen"),
        ("insblatt", "Ins Blatt schreiben", "ins_blatt", ("fn", "ins_blatt_schreiben"), "Diese Abfrage ins Tabellenblatt schreiben; der Editor bleibt offen"),
        ("dok", "Speichern", "speichern", ("fn", "dokument_speichern"), "Dokument speichern"),
        ("param", "Parameter", "parameter", ("fn", "parameter_verwalten"), "Parameter verwalten"),
        None,
        ("spwahl", "Spalten wählen", "spalten_waehlen", ("op", "spalten_behalten"), "Nur die gewählten Spalten behalten"),
        ("spentf", "Spalte entfernen", "spalten_entfernen", ("op", "spalten_entfernen"), "Spalten entfernen"),
        ("zbeh", "Zeilen behalten ▾", "zeilen_behalten", ("menu", [
            ("Obere Zeilen beibehalten", "zeilen_behalten_oben"), ("Untere Zeilen beibehalten", "zeilen_behalten_unten"),
            ("Zeilenbereich beibehalten", "zeilen_bereich"), ("Doppelte Werte beibehalten", "duplikate_behalten"),
            ("Fehler beibehalten", "fehler_zeilen_behalten")]), "Zeilen behalten …"),
        ("zentf", "Zeilen entfernen ▾", "zeilen_entfernen", ("menu", [
            ("Obere Zeilen entfernen", "zeilen_entfernen_oben"), ("Untere Zeilen entfernen", "zeilen_entfernen_unten"),
            ("Alternative Zeilen entfernen", "jede_nte_zeile"), ("Leere Zeilen entfernen", "leere_zeilen_entfernen"),
            ("Doppelte Werte entfernen", "duplikate_entfernen"), ("Fehler entfernen", "fehler_zeilen_entfernen")]),
         "Zeilen entfernen …"),
        ("sort", "Sortieren ▾", "sortieren", ("menu", [("Zeilen sortieren …", "sortieren"), ("Zeilen umkehren", "zeilen_umkehren")]),
         "Zeilen sortieren oder umkehren"),
        ("filt", "Filtern ▾", "filtern", ("menu", [
            ("Zeilen filtern …", "filtern"), ("Nach Einzelwerten filtern …", "filtern_werte")]), "Zeilen filtern"),
        ("kopf", "Überschrift ▾", "ueberschrift", ("menu", [
            ("Erste Zeile als Überschriften verwenden", "erste_zeile_als_kopf"),
            ("Überschriften als erste Zeile", "kopf_als_erste_zeile")]), "Überschriften festlegen"),
        ("grp", "Gruppieren", "gruppieren", ("op", "gruppieren"), "Gruppieren und aggregieren"),
    ]),
    ("Transformieren", [
        ("typ", "Datentyp", "datentyp", ("op", "typ_aendern"), "Datentyp ändern"),
        ("erk", "Typen erkennen", "typen_erkennen", ("op", "typen_erkennen"), "Datentypen automatisch erkennen"),
        ("ers", "Ersetzen ▾", "ersetzen", ("menu", [
            ("Werte ersetzen …", "ersetzen"), ("Leere Werte ersetzen …", "leere_ersetzen"),
            ("Fehlerwerte ersetzen …", "fehler_ersetzen")]), "Werte ersetzen"),
        ("fuell", "Ausfüllen ▾", "ausfuellen", ("menu", [
            ("Nach unten ausfüllen", "fuellen_unten"), ("Nach oben ausfüllen", "fuellen_oben")]), "Leere Zellen ausfüllen"),
        ("txt", "Text ▾", "text", ("menu", [
            ("Text umformatieren …", "text_umwandeln"), ("Text extrahieren …", "text_extrahieren"),
            ("Präfix/Suffix hinzufügen …", "praefix_suffix")]), "Text bearbeiten"),
        ("teil", "Spalte teilen", "teilen", ("op", "spalte_teilen"), "Spalte teilen"),
        ("rund", "Runden", "runden", ("op", "runden"), "Zahlen runden"),
        ("rech", "Rechnen ▾", "rechnen", ("menu", [("Rechnen …", "rechnen"), ("Zahleneigenschaft …", "zahleneigenschaft")]),
         "Standardoperationen"),
        ("umb", "Spalten umbenennen ▾", "umbenennen", ("menu", [("Spalte umbenennen …", "spalte_umbenennen"),
                                                    ("Mehrere Spalten umbenennen …", "spalten_umbenennen")]), "Spalten umbenennen"),
        ("spord", "Spalten anordnen ▾", "spalten_ordnen", ("menu", [("Spalten verschieben …", "spalten_verschieben"),
            ("Spaltenreihenfolge umkehren", "spaltenreihenfolge_umkehren"), ("Spalten sortieren …", "spalten_sortieren")]),
         "Spalten anordnen"),
        ("trans", "Transponieren", "transponieren", ("op", "transponieren"), "Tabelle transponieren"),
        ("entp", "Entpivotieren", "entpivotieren", ("op", "entpivotieren"), "Spalten entpivotieren"),
        ("piv", "Pivotieren", "pivotieren", ("op", "pivotieren"), "Spalte pivotieren"),
    ]),
    ("Spalte hinzufügen", [
        ("bdef", "Benutzerdef.\nSpalte", "benutzerdefiniert", ("op", "benutzerdefinierte_spalte"), "Spalte per Formel"),
        ("bed", "Bedingte Spalte", "bedingt", ("op", "bedingte_spalte"), "Spalte mit Wenn/Sonst-Regeln"),
        ("idx", "Indexspalte", "index", ("op", "indexspalte"), "Indexspalte (Zähler)"),
        ("dup", "Spalte\nduplizieren", "duplizieren", ("op", "spalte_duplizieren"), "Spalte duplizieren"),
        ("zus", "Spalten verbinden", "zusammenfuehren", ("op", "spalten_zusammenfuehren"), "Spalten zu einer verbinden"),
        ("man", "Manuelle Spalte", "manuell", ("op", "hand_behalten"), "Manuell hinzugefügte Spalten behalten"),
    ]),
    ("Kombinieren", [
        ("verb", "Abfragen zusammenführen", "verbinden", ("op", "tabellen_verbinden"), "Abfragen zusammenführen (Merge)"),
        ("anf", "Abfragen anfügen", "anfuegen", ("op", "tabellen_anfuegen"), "Abfragen untereinander anfügen"),
        ("datei", "Dateien einlesen", "datei", ("op", "datei_einlesen"), "Dateiinhalt einlesen"),
        ("verw", "Abfrage-Verweis", "verweis", ("fn", "verweis_erstellen"), "Neue Abfrage als Verweis auf diese"),
    ]),
    ("Ansicht", [
        ("gitter", "Gitternetz", "gitter", ("tgl", "chkGitter"), "Gitternetz statt Bänderung"),
        ("det", "Zeilendetails", "details", ("tgl", "chkDetails"), "Zeilendetails unter der Tabelle"),
        ("brt", "Spaltenbreite", "breite", ("fn", "breite_aktuelle"), "Breite der markierten Spalte optimieren"),
        ("brta", "Alle Breiten", "breite_alle", ("fn", "alle_breiten_optimieren"), "Alle Spalten optimal breit"),
        ("abfl", "Abfrageliste", "abfragen_liste", ("tgl", "chkAbfr"), "Abfrageliste ein-/ausblenden"),
        ("schl", "Schrittliste", "schritte_liste", ("tgl", "chkSchr"), "Schrittliste ein-/ausblenden"),
        ("suche", "Schritt suchen", "suche", ("fn", "schritt_suchen"), "Schritt per Suche finden"),
        ("maxi", "Maximieren", "maximieren", ("fn", "maximieren"), "Editor-Fenster maximieren bzw. wieder verkleinern"),
    ]),
    ("Extras", [
        ("upd", "Updates", "updates", ("fn", "updates_suchen"), "Auf neue Version bei GitHub prüfen"),
        ("startanp", "Start\nanpassen", "start_anpassen", ("fn", "start_anpassen"), "Wählen, welche Knöpfe der Start-Reiter zeigt, und ihre Reihenfolge"),
        ("rkl", "Rechtsklick", "eigenschaften", ("fn", "rechtsklick_umschalten"), "Rechtsklick für Menüs ein-/ausschalten (dann öffnet der Doppelklick die Bearbeitung)"),
        ("symb", "Symbole\nstatt Text", "symbole", ("fn", "knopfart_umschalten"), "Die Knöpfe unter den Listen als Symbole oder als Text zeigen"),
        ("protok", "Absturz-\nprotokoll", "protokoll", ("fn", "absturzprotokoll_umschalten"), "Absturzprotokoll ein-/ausschalten (legt nur nach Nachfrage eine Datei an)"),
    ]),
]

# Befehle der Abfrage- und der Schrittliste (früher eigene Reiter): Menüs im Start-Reiter, Symbolknöpfe statt der
# grauen Knöpfe unter den Listen (Extras ▸ Symbole statt Text)
ABFRAGE_KNOEPFE = [
        ("a_neu", "Neue Abfrage", "abfrage_neu", ("abf", "neu"), "Neue Abfrage anlegen"),
        ("a_par", "Neuer Parameter", "parameter", ("abf", "neuer_parameter"), "Neuen Parameter anlegen"),
        None,
        ("a_oef", "Abfrage öffnen", "oeffnen", ("abf", "oeffnen"), "Abfrage aus einer Datei in dieses Dokument übernehmen"),
        ("a_spe", "Abfrage speichern", "exportieren", ("abf", "speichern"), "Gewählte Abfrage in einer Datei speichern"),
        None,
        ("a_dup", "Abfrage duplizieren", "duplizieren", ("abf", "dupliziere"), "Abfrage duplizieren"),
        ("a_ver", "Abfrage-Verweis", "verweis", ("abf", "verweis"), "Neue Abfrage als Verweis auf diese"),
        ("a_umb", "Abfrage umbenennen", "umbenennen", ("abf", "umbenennen"), "Abfrage umbenennen"),
        ("a_eig", "Abfrage-Eigenschaften", "eigenschaften", ("abf", "eigenschaften"), "Name und Beschreibung der Abfrage"),
        ("a_aus", "Abfrage-Ausgabe", "ausgabe", ("abf", "ausgabe"), "Wohin diese Abfrage ihr Ergebnis schreibt"),
        ("a_hoc", "Abfrage nach oben", "hoch", ("abf", "hoch"), "Abfrage in der Liste nach oben"),
        ("a_run", "Abfrage nach unten", "runter", ("abf", "runter"), "Abfrage in der Liste nach unten"),
        ("a_los", "Abfrage löschen", "loeschen", ("abf", "loeschen"), "Gewählte Abfrage löschen"),
        ("a_end", "Abfragen bis zum Ende löschen", "bis_ende", ("abf", "bis_ende"), "Gewählte und alle folgenden Abfragen löschen (Parameter bleiben)"),
        ("a_aut", "Autom. speichern", "autospeichern", ("tgl", "chkAuto"), "Dokument nach jedem Schritt speichern"),
]
SCHRITT_KNOEPFE = [
        ("s_hin", "Schritt hinzufügen ▾", "schritt_hinzu", ("sch", "hinzu"), "Menü aller Schritte"),
        ("s_suc", "Schritt suchen", "suche", ("fn", "schritt_suchen"), "Schritt per Suche finden"),
        None,
        ("s_aen", "Schritt ändern", "aendern", ("sch", "aendern"), "Gewählten Schritt ändern"),
        ("s_umb", "Schritt umbenennen", "umbenennen", ("sch", "umbenennen"), "Schritt umbenennen"),
        ("s_dup", "Schritt duplizieren", "duplizieren", ("sch", "dupliziere"), "Schritt duplizieren"),
        ("s_ein", "Schritt Ein/Aus", "ein_aus", ("sch", "ein_aus"), "Schritt vorübergehend ausschalten"),
        ("s_bed", "Schritt-Bedingung", "bedingung_schritt", ("sch", "bedingung"), "Schritt nur unter einer Bedingung ausführen"),
        None,
        ("s_vor", "Einfügen vor", "einfuegen_vor", ("sch", "einvor"), "Schritt vor dem gewählten einfügen"),
        ("s_nac", "Einfügen nach", "einfuegen_nach", ("sch", "einnach"), "Schritt nach dem gewählten einfügen"),
        ("s_hoc", "Schritt nach oben", "hoch", ("sch", "hoch"), "Schritt nach oben"),
        ("s_run", "Schritt nach unten", "runter", ("sch", "runter"), "Schritt nach unten"),
        ("s_los", "Schritt löschen", "loeschen", ("sch", "loeschen"), "Gewählten Schritt löschen"),
        ("s_end", "Bis zum Ende löschen", "bis_ende", ("sch", "bis_ende"), "Diesen und alle folgenden Schritte löschen"),
]
def _menue_aus(knoepfe, ohne=()):
    """Menüeinträge (Text, Aktion) aus einer Knopfliste; None = Trennlinie."""
    ergebnis = []
    for e_ in knoepfe:
        if e_ is None:
            if ergebnis and ergebnis[-1] != (None, None):
                ergebnis.append((None, None))
        elif e_[0] not in ohne:
            ergebnis.append((e_[1].replace(" ▾", "").replace("\n", " "), e_[3]))
    while ergebnis and ergebnis[-1] == (None, None):
        ergebnis.pop()
    return ergebnis


ABF_MENUE_E = ("a_menu", "Abfrage ▾", "abfragen_liste", ("menu", _menue_aus(ABFRAGE_KNOEPFE)), "Alle Befehle für Abfragen")
SCH_MENUE_E = ("s_menu", "Schritt ▾", "schritte_liste", ("menu", _menue_aus(SCHRITT_KNOEPFE, ("s_hin", "s_suc"))),
               "Alle Befehle für den gewählten Schritt")
_s_ = LEISTE[0][1]
_i_ = [i for i, e_ in enumerate(_s_) if e_ and e_[0] == "param"][0] + 1
_a_neu = [e_ for e_ in ABFRAGE_KNOEPFE if e_ and e_[0] == "a_neu"][0]
_s_hin = [e_ for e_ in SCHRITT_KNOEPFE if e_ and e_[0] == "s_hin"][0]
_s_[_i_:_i_] = [None, _a_neu, ABF_MENUE_E, None, _s_hin, SCH_MENUE_E]
START_STANDARD = [e_[0] if e_ else "|" for e_ in _s_]

ALLE_EINTRAEGE = {}                           # Kennung -> Eintrag: alles, was sich im Start-Reiter anordnen lässt
for _liste_ in [e_ for _t_, e_ in LEISTE] + [ABFRAGE_KNOEPFE, SCHRITT_KNOEPFE]:
    for _e_ in _liste_:
        if _e_ is not None:
            ALLE_EINTRAEGE.setdefault(_e_[0], _e_)


def start_eintraege():
    """Einträge des Start-Reiters: die gespeicherte Auswahl des Nutzers (Extras ▸ Start anpassen) oder die Vorgabe."""
    ids = lies_einstellung("start_leiste", None)
    if not isinstance(ids, list) or not ids:
        ids = START_STANDARD
    ergebnis = []
    for i_ in ids:
        if i_ == "|":
            if ergebnis and ergebnis[-1] is not None:
                ergebnis.append(None)
        elif i_ in ALLE_EINTRAEGE:
            ergebnis.append(ALLE_EINTRAEGE[i_])
    return ergebnis or [ALLE_EINTRAEGE[i_] if i_ != "|" else None for i_ in START_STANDARD]


def text_von(op):
    return str(op[1])


MEHR = ("u_mehr", "Mehr ▾", "mehr", ("fn", "leiste_mehr"), "Weitere Befehle dieses Reiters (passen nicht ins Fenster)")
FEST = []        # (früher: rechts im Band immer sichtbar; Rückgängig/Wiederholen stehen jetzt ganz links im Start-Reiter)
KOPF_FARBE, KOPF_TEXT = 0xF4F5F7, 0x222222
ICON_B, ICON_H = 27, 26                       # Symbolrahmen (20 % größer als in 0.9.1)
_LETZTER_TAB = [0]     # zuletzt benutzter Reiter (bleibt über das Öffnen hinaus)

_ZULETZT_OPS = []     # zuletzt gewählte Schritte (neueste zuerst)


def merke_operation(op):
    if op in _ZULETZT_OPS:
        _ZULETZT_OPS.remove(op)
    _ZULETZT_OPS.insert(0, op)
    del _ZULETZT_OPS[6:]


def suche_operation(ctx, parent=None):
    """Suchdialog für Schritte: tippen filtert die Liste (Titel und Gruppe); ohne Eingabe stehen die zuletzt
    verwendeten oben. Doppelklick oder Enter wählt. -> op oder None."""
    alle = []
    for gruppe in E.GRUPPEN:
        for op, dd in E.ops_der_gruppe(gruppe):
            alle.append((op, dd["titel"], gruppe))
    d = Dlg(ctx, "Schritt suchen", 240, 150)
    d.add("FixedText", "l", 8, 8, 224, 10, Label="Was möchten Sie tun? Suchbegriff eingeben:")
    d.add("Edit", "t", 8, 20, 224, 14)
    d.add("ListBox", "lst", 8, 38, 224, 86)
    d.add("Button", "ok", 100, 130, 62, 14, Label="OK", DefaultButton=True)
    d.add("Button", "abbr", 166, 130, 66, 14, Label="Abbrechen")
    sicht = []
    res = {"op": None}

    def fuellen(*_):
        q = d.ctrl("t").getText().strip().casefold()
        if q:
            treffer = [a for a in alle if all(w in (a[1] + " " + a[2]).casefold() for w in q.split())]
        else:
            rang = {op: k for k, op in enumerate(_ZULETZT_OPS)}
            zl = sorted([a for a in alle if a[0] in rang], key=lambda a: rang[a[0]])
            treffer = zl + [a for a in alle if a[0] not in rang]
        sicht[:] = treffer
        texte = [("★ " if (not q and a[0] in _ZULETZT_OPS) else "") + "%s   (%s)" % (a[1], a[2]) for a in treffer]
        setze_liste(d.ctrl("lst").getModel(), texte, [0] if texte else [])

    class _Such(unohelper.Base, XTextListener):
        def textChanged(self_, ev):
            _sicher(fuellen)()

        def disposing(self_, ev):
            pass
    sl = _Such()
    d.refs.append(sl)
    d.ctrl("t").addTextListener(sl)

    def ok():
        i = sel_pos(d.ctrl("lst"))
        if 0 <= i < len(sicht):
            res["op"] = sicht[i][0]
            d.schliessen(1)
    d.on_click("ok", ok)
    d.on_click("abbr", lambda: d.schliessen(0))
    fuellen()
    auto = os.environ.get("ABFRAGE_SUCHE")      # Testbetrieb: Suchbegriff simulieren
    if auto is not None:
        def tippe():
            d.ctrl("t").getModel().Text = auto
            fuellen()
            ok()
        t = threading.Timer(1.0, _sicher(tippe))
        t.daemon = True
        t.start()
    d.zeigen(parent)
    d.weg()
    if res["op"]:
        merke_operation(res["op"])
    return res["op"]


# ---------------------------------------------------------------------------
# Hauptdialog
# ---------------------------------------------------------------------------
RECHTSBUENDIG = ("ganz", "dezimal", "waehrung", "prozent", "datum", "datumzeit", "zeit")
TYP_SYMBOLE = {"text": "ABC", "ganz": "123", "dezimal": "1,2", "waehrung": "€", "prozent": "%",
               "datum": "Dat", "datumzeit": "Dat+Zeit", "zeit": "Zeit", "bool": "J/N", "leer": "-"}
SYMBOL_ZU_TYP = {"text": "text", "ganz": "ganzzahl", "dezimal": "dezimal", "waehrung": "waehrung",
                 "prozent": "prozent", "datum": "datum", "datumzeit": "datumzeit", "zeit": "zeit", "bool": "bool"}


def typ_art(werte):
    """Typart einer Spalte: text/ganz/dezimal/waehrung/prozent/datum/datumzeit/zeit/bool/leer oder 'mix'."""
    gesehen = set()
    for v in werte[:2000]:
        if v is not None:
            a = spaltenart([v])
            if a == "zahl":
                a = "ganz" if isinstance(v, int) else "dezimal"
            gesehen.add(a)
    if not gesehen:
        return "leer"
    if gesehen == {"ganz", "dezimal"}:
        return "dezimal"
    return gesehen.pop() if len(gesehen) == 1 else "mix"


def typ_kuerzel(werte):
    a = typ_art(werte)
    return "Mix" if a == "mix" else TYP_SYMBOLE[a]


def _eindeutig(liste):
    gesehen, aus = set(), []
    for x in liste:
        if x not in gesehen:
            gesehen.add(x)
            aus.append(x)
    return aus


class Editor:
    MIN_BREITE, MIN_HOEHE = 520, 280

    def __init__(self, ctx, frame, doc, abfrage=None):
        self.ctx, self.frame, self.doc = ctx, frame, doc
        self.smgr = ctx.ServiceManager
        self.abfrage = abfrage or E.Abfrage("Abfrage1", {}, [])
        self.alter_name = None          # Name, unter dem die Abfrage schon im Dokument liegt
        try:
            if doc is not None and self.abfrage.name in gespeicherte_abfragen(doc):
                self.alter_name = self.abfrage.name
        except Exception:
            pass
        self.roh = None
        self._cache_q, self._cache_t, self._cache_basis = {}, {}, {}      # temporärer Zwischenspeicher (nur solange der Editor offen ist)
        self.arbeit = []                # Arbeitsstand aller Abfragen der Datei (Liste links)
        self.aktuell = 0
        self._entfernt = []             # im Editor gelöschte, bisher gespeicherte Abfragen
        self._erste_sp = 0
        self.abfragen_an = self.schritte_an = True
        self.alle_an = True                         # beim Schließen und Laden alle Abfragen aktualisieren
        self._max, self._vor_max = False, None      # Fenster maximiert?
        self.breite_a, self.breite_s = 98, 150      # Breite der Abfragen- und der Schrittliste (ziehbar)
        self.gitter, self.details_an = False, True
        self._dunkel, self._feld = False, 0xFFFFFF
        self._detail_zeile = 0
        self._breiten_ignorieren = False
        self._drag = None
        self._spdrag = None
        self._leer = True
        self._rect = (0, 0, 100, 100)
        self._scroll = {}
        self._arten = {}
        self._fehler = {}               # Spaltenname -> Anzahl Fehler (⚠ im Spaltenkopf)
        self._kontext_setzen()
        self.sel_spalte = None          # per Klick markierte Spalte
        self.betroffen = []             # Spalten, die der gewählte Schritt betrifft/neu anlegt
        self.angezeigt = None
        self.fehler_schritt = None
        self.ergebnis_ok = False
        self.verlauf, self.wiederholen_liste = [], []
        self.vorschau_limit = VORSCHAU_STUFEN[VORSCHAU_STANDARD][1]
        self.breiten = {}               # Spaltenname -> Breite (vom Nutzer gezogen), bleibt erhalten
        self._grid_namen = []
        self.nummern_breite = 20
        self._busy = False
        self._letzte_extra = 0
        self._cm_args = None
        self._diag_n = 0
        self._t0 = time.time()
        self._menue_offen = False
        self._letzter_rechtsklick = 0.0
        self._diag_pfad = os.path.join(os.path.expanduser("~"), "OpenQuery-Diagnose.txt")
        if not os.path.exists(self._diag_pfad):
            self._diag_pfad = None
        self._geo = None
        self._kz = None
        self._sichtbar = False
        self._im_layout = False
        self.parent = None
        try:
            self.parent = frame.getContainerWindow()
        except Exception:
            pass

    # -- Abfragenliste (links) -----------------------------------------------------
    def _eintrag(self, a, alt, orig):
        return {"a": a, "alt": alt, "orig": orig, "verlauf": [], "wdh": [], "sel": None}

    def _arbeit_aufbauen(self):
        """Alle gespeicherten Abfragen der Datei als Arbeitsstand; die geöffnete ist das Objekt self.abfrage."""
        texte = gespeicherte_abfragen(self.doc) if self.doc is not None else {}
        self.arbeit = []
        aktuell = None
        for name in geordnete_namen(self.doc, texte) if self.doc is not None else []:
            if name == self.alter_name:
                e = self._eintrag(self.abfrage, name, texte[name])
                aktuell = len(self.arbeit)
            else:
                try:
                    e = self._eintrag(E.Abfrage.from_json(texte[name]), name, texte[name])
                except Exception:
                    continue
            self.arbeit.append(e)
        if aktuell is None:
            self.arbeit.append(self._eintrag(self.abfrage, None, None))
            aktuell = len(self.arbeit) - 1
        self.aktuell = aktuell
        _ARBEIT["fn"] = lambda: {e["a"].name: e["a"].to_json() for e in self.arbeit}

    @staticmethod
    def _listenname(a):
        """Anzeigename in der Abfragenliste; reine Verbindungen sind mit ↔ gekennzeichnet."""
        return ("↔ " + a.name) if ist_verbindung(a) else a.name

    def _param_namen(self):
        """Parameter dieser Datei, alphabetisch (stehen unter den Abfragen in derselben Liste)."""
        try:
            return sorted(lies_oq_parameter(self.doc), key=str.casefold) if self.doc is not None else []
        except Exception:
            return []

    def _abfr_items(self):
        """Einträge der linken Liste: erst die Abfragen, dann die Parameter als {Name} (so schreibt man sie in Schritten)."""
        return [self._listenname(e["a"]) for e in self.arbeit] + ["{%s}" % n for n in self._param_namen()]

    def _param_an(self, z):
        """Name des Parameters in Listenzeile z (oder None, wenn dort eine Abfrage steht)."""
        namen = self._param_namen()
        i = z - len(self.arbeit)
        return namen[i] if 0 <= i < len(namen) else None

    def abfragen_liste_neu(self):
        self.lstA.setze(self._abfr_items(), self.aktuell)
        self._autospeichern_planen()

    def _eintrag_ablegen(self):
        if not self.arbeit:
            return
        e = self.arbeit[self.aktuell]
        e["alt"], e["verlauf"], e["wdh"] = self.alter_name, self.verlauf, self.wiederholen_liste
        e["sel"] = self.lstS.pos()
        e["breiten"] = self.breiten

    def _wechsle_zu(self, idx):
        if idx == self.aktuell or not (0 <= idx < len(self.arbeit)):
            return
        self._eintrag_ablegen()
        self.aktuell = idx
        self._eintrag_laden()

    def _eintrag_laden(self):
        e = self.arbeit[self.aktuell]
        self.abfrage, self.alter_name = e["a"], e["alt"]
        self.verlauf, self.wiederholen_liste = e["verlauf"], e["wdh"]
        self.breiten = e.get("breiten", {})
        self.sel_spalte = None
        self.fehler_schritt = None
        self.d.ctrl("txtName").getModel().Text = self.abfrage.name
        self._kontext_setzen()
        self.roh = None
        try:
            uebernehme_neue_spalten(self.doc, self.abfrage)         # im Blatt dazugekommene Handspalten
        except Exception:
            traceback.print_exc()
        if self.abfrage.quelle:
            self.quelle_laden()
        if self._abfr_items() != self.lstA.items:
            self.abfragen_liste_neu()
        else:
            self.lstA.waehle(self.aktuell)             # nur die Auswahl ändern, die Liste nicht neu aufbauen
        self.liste_neu(e.get("sel"))
        self.zeige()
        self.knoepfe_aktualisieren()

    _param_ansicht = None

    def _abfrage_gewaehlt(self, ev=None):
        pos = self.lstA.pos()
        if pos >= len(self.arbeit):
            pn = self._param_an(pos)            # ein Parameter ist markiert: seine Werte in der Tabellenfläche zeigen
            if pn is not None:
                self._spaeter(lambda: self.parameter_anzeigen(pn))
            return                              # die geöffnete Abfrage bleibt, wie sie ist
        if self._param_ansicht is not None and pos == self.aktuell:
            self._param_ansicht = None          # zurück von der Parameteransicht zur geöffneten Abfrage
            self._spaeter(self.zeige)
            return
        self._param_ansicht = None
        self._spaeter(lambda: self._wechsle_zu(self.lstA.pos()))

    def parameter_anzeigen(self, pn):
        """Klick auf einen Parameter: alle Parameter als Tabelle (Parameter, Wert, Typ, Verwendet in, Beschreibung); der
        angeklickte ist markiert, seine Einzelheiten stehen in den Zeilendetails und sein Wert lässt sich dort ändern."""
        alle = lies_oq_parameter(self.doc)
        if pn not in alle:
            return
        typ_t = dict(PARAM_TYPEN)
        namen = sorted(alle, key=str.casefold)
        zeilen = []
        for n in namen:
            p = alle[n]
            zeilen.append([n, p.get("wert", ""), typ_t.get(p.get("typ"), str(p.get("typ"))),
                           ", ".join(parameter_verwendung(self.doc, n)), p.get("beschreibung", "")])
        tab = E.Tabelle(["Parameter", "Wert", "Typ", "Verwendet in", "Beschreibung"], zeilen)
        self._param_zeilen = namen
        self._param_ansicht = pn
        self.angezeigt = tab
        self._detail_zeile = namen.index(pn)
        self.fuelle_grid(tab)
        self._detail_zeile = namen.index(pn)
        self.zeige_details(namen.index(pn))
        try:
            self.d.ctrl("grid").selectRow(namen.index(pn))
        except Exception:
            pass
        d = self.d
        d.ctrl("lblInfo").getModel().Label = "Parameter – Zeile anklicken; Wert unten ändern; Doppelklick ändert alle Eigenschaften. Klick auf eine Abfrage zeigt wieder die Tabelle."
        for n_ in ("lblZeilen", "lblMarkiert", "lblQual"):
            d.ctrl(n_).getModel().Label = ""
        d.ctrl("lblZeilen").getModel().Label = "%d Parameter" % len(namen)

    def _param_aus_zeile(self, zeile):
        namen = getattr(self, "_param_zeilen", [])
        return namen[zeile] if 0 <= zeile < len(namen) else None

    def _param_steuer_platzieren(self):
        """Wertfeld und Knopf für den Parameter über den Zeilendetails: nur in der Parameteransicht."""
        d = self.d
        geo = getattr(self, "_detail_geo", None)
        try:
            if self._param_ansicht is not None and geo and self.details_an:
                x0, y, RW = geo
                p = lies_oq_parameter(self.doc).get(self._param_ansicht, {})
                lbl = d.ctrl("lblDetail").getModel()
                lbl.Label = "Parameter {%s} – Wert:" % self._param_ansicht
                wl = min(int(self._textbreite(lbl.Label) * 1.15) + 6, max(RW // 2, 60))
                d.platziere("lblDetail", x0, y + 1, wl, 10)
                d.platziere("txtParamWert", x0 + wl + 2, y - 1, max(RW - wl - 64, 40), 13)
                d.platziere("btnParamWert", x0 + RW - 58, y - 1, 56, 13)
                d.platziere("btnDetailZu", -3000, -3000, 14, 10)
                tm = d.ctrl("txtParamWert").getModel()
                if getattr(self, "_param_text_fuer", None) != self._param_ansicht:
                    tm.Text = str(p.get("wert", ""))
                    self._param_text_fuer = self._param_ansicht
                return
        except Exception:
            traceback.print_exc()
        self._param_text_fuer = None
        for n in ("txtParamWert", "btnParamWert"):
            try:
                d.platziere(n, -3000, -3000, 10, 10)
            except Exception:
                pass
        if geo and self.details_an and self._param_ansicht is None:
            x0, y, RW = geo
            d.platziere("btnDetailZu", x0 + RW - 14, y, 14, 10)

    def _param_wert_speichern(self):
        pn = self._param_ansicht
        if pn is None:
            return
        p = lies_oq_parameter(self.doc).get(pn)
        if p is None:
            return
        text = self.d.ctrl("txtParamWert").getModel().Text
        try:
            if p.get("typ") == "zahl" and text.strip():
                float(text.strip().replace(",", "."))
            elif p.get("typ") == "janein" and text.strip():
                E.parse_bool(text.strip())
        except Exception:
            self.meld("Der Wert passt nicht zum Typ des Parameters (%s)." % dict(PARAM_TYPEN).get(p.get("typ"), p.get("typ")))
            return
        if zellname_vorhanden(self.doc, pn):
            self.meld("Es gibt eine benannte Zelle „%s“; sie hat Vorrang. Den Wert dort in der Tabelle ändern." % pn)
            return
        p["wert"] = text
        speichere_oq_parameter(self.doc, pn, p)
        self.cache_leeren()
        self._param_text_fuer = None
        self.parameter_anzeigen(pn)

    def _abfrage_tipp(self, z):
        pn = self._param_an(z)
        if pn is not None:
            p = lies_oq_parameter(self.doc).get(pn, {})
            typ_t = dict(PARAM_TYPEN)
            return "\n".join(x for x in ("Parameter {%s}" % pn, "Typ: " + typ_t.get(p.get("typ"), str(p.get("typ"))),
                                           "Wert: %s" % p.get("wert", ""), p.get("beschreibung", ""),
                                           ("Rechtsklick oder Doppelklick: Menü" if rechtsklick_aktiv() else "Doppelklick: Menü")) if x)
        a = self.arbeit[z]["a"] if 0 <= z < len(self.arbeit) else None
        if a is None:
            return ""
        return "\n".join(x for x in (a.name, a.beschreibung, "Nur Verbindung (nicht im Blatt)" if ist_verbindung(a) else "",
                                      "Quelle: " + beschreibe_quelle(a.quelle), "%d Schritte" % len(a.schritte)) if x)

    def _schritt_tipp(self, z):
        if z == 0:
            return "Quelle\n" + beschreibe_quelle(self.abfrage.quelle)
        if 1 <= z <= len(self.abfrage.schritte):
            st = self.abfrage.schritte[z - 1]
            name = (st.get("name") or "").strip()
            return "\n".join(x for x in (name, E.beschreibe(st)) if x)
        return ""

    def _freier_name(self, basis):
        belegt = {e["a"].name.casefold() for e in self.arbeit} | {n.casefold() for n in gespeicherte_abfragen(self.doc)} \
            if self.doc is not None else {e["a"].name.casefold() for e in self.arbeit}
        if basis.casefold() not in belegt:
            return basis
        i = 2
        while "%s (%d)" % (basis, i) in belegt or ("%s (%d)" % (basis, i)).casefold() in belegt:
            i += 1
        return "%s (%d)" % (basis, i)

    def _neue_in_liste(self, a, nach_aktuell=True):
        self._eintrag_ablegen()
        pos = self.aktuell + 1 if nach_aktuell else len(self.arbeit)
        self.arbeit.insert(pos, self._eintrag(a, None, None))
        self.aktuell = pos
        self._eintrag_laden()

    def neue_abfrage(self):
        i = 1
        while True:
            name = "Abfrage%d" % i
            if name.casefold() not in {e["a"].name.casefold() for e in self.arbeit} \
                    and not (self.doc is not None and self.doc.getSheets().hasByName(name)):
                break
            i += 1
        self._neue_in_liste(E.Abfrage(name, {}, []), nach_aktuell=False)
        self._spaeter(self.quelle_waehlen)               # sofort die Quelle wählen lassen (Abbrechen: Abfrage bleibt leer)

    def _auto_geaendert(self, ev=None):
        an = bool(self.d.ctrl("chkAuto").getModel().State)
        if an != self.autospeichern_an():
            schreibe_einstellung("auto_speichern", an, fragen=True)
            self._diag("Automatisch speichern: %s" % an)
            if an:
                self._autospeichern_planen()

    def autospeichern_an(self):
        return bool(lies_einstellung("auto_speichern", False))

    def autospeichern_umschalten(self):
        an = not self.autospeichern_an()
        schreibe_einstellung("auto_speichern", an, fragen=True)
        self._diag("Automatisch speichern: %s" % an)
        if an:
            self._autospeichern_planen()

    def _autospeichern_planen(self):
        """Nach jeder Änderung (entprellt, erst nach dem laufenden Ereignis) Abfragen und Datei sichern."""
        if not self.autospeichern_an() or self.doc is None or getattr(self, "_auto_geplant", False):
            return
        self._auto_geplant = True
        self._spaeter(self._autospeichern)

    def _abfragen_sichern(self):
        """Alle Abfragen des Editors (auch die ungeschriebenen) und ihre Reihenfolge als Dokumentwerte sichern.
        Die Blätter werden dabei nicht neu geschrieben."""
        doc = self.doc
        gesichert = getattr(self, "_auto_namen", {})
        for e in self.arbeit:
            a = e["a"]
            alt = gesichert.get(id(a))
            if alt and alt != a.name and alt != e.get("alt"):
                loesche_abfrage(doc, alt)            # umbenannt: Zwischenstand unter dem alten Namen entfernen
            speichere_abfrage(doc, a)
            gesichert[id(a)] = a.name
        self._auto_namen = gesichert
        speichere_reihenfolge(doc, [e["a"].name for e in self.arbeit])

    def _autospeichern(self):
        self._auto_geplant = False
        if not self.autospeichern_an() or self.doc is None:
            return
        try:
            self._abfragen_sichern()
            doc = self.doc
            if doc.hasLocation() and not doc.isReadonly():
                doc.store()
                self._diag("Automatisch gespeichert (%d Abfragen)" % len(self.arbeit))
            elif not getattr(self, "_auto_hinweis", False):
                self._auto_hinweis = True
                self.meld("Automatisches Speichern: Die Datei hat noch keinen Speicherort. Bitte einmal "
                          "mit Datei ▸ Speichern unter … sichern, danach wird nach jedem Schritt gespeichert.")
        except Exception:
            traceback.print_exc()

    def parameter_verwalten(self, wahl=None):
        ParameterDialog(self.ctx, self.doc, self.d.peer(), wahl).zeigen()
        self.cache_leeren()
        self.abfragen_liste_neu()

    def neuer_parameter(self):
        """Knopf „Neuer Parameter“ unter den Abfragen."""
        if self.doc is None:
            return
        n = parameter_bearbeiten(self.ctx, self.doc, self.d.peer())
        self.abfragen_liste_neu()
        if n is not None:
            try:
                self.lstA.waehle(len(self.arbeit) + self._param_namen().index(n))
            except Exception:
                pass

    def parameter_bearbeiten_(self, name):
        n = parameter_bearbeiten(self.ctx, self.doc, self.d.peer(), name)
        self.abfragen_liste_neu()
        if n is not None:
            try:
                self.lstA.waehle(len(self.arbeit) + self._param_namen().index(n))
            except Exception:
                pass

    def _param_nach_bearbeiten(self, pn):
        self.cache_leeren()
        self._param_text_fuer = None
        alle = lies_oq_parameter(self.doc)
        if self._param_ansicht is not None:
            ziel = pn if pn in alle else (sorted(alle, key=str.casefold)[0] if alle else None)
            if ziel is not None:
                self.parameter_anzeigen(ziel)

    def parameter_loeschen(self, name):
        benutzt = parameter_verwendung(self.doc, name)
        text = "Parameter „%s“ löschen?" % name
        if benutzt:
            text += "\n\nEr wird noch verwendet in: %s.\nDiese Abfragen melden danach einen Fehler, bis du den Parameter ersetzt." % ", ".join(benutzt)
        if self.meld(text, "QUERYBOX", 3) == 2:
            loesche_oq_parameter(self.doc, name)
            self.abfragen_liste_neu()

    def dokument_speichern(self):
        """Knopf „Dokument speichern“: Stand aller Abfragen sichern und die ganze Datei speichern."""
        self._spaeter(self._dokument_speichern)

    def _dokument_speichern(self):
        doc = self.doc
        if doc is None:
            return
        try:
            self._abfragen_sichern()
            if not doc.hasLocation():
                self.meld("Die Datei hat noch keinen Speicherort. Bitte einmal im Calc-Fenster mit "
                          "Datei ▸ Speichern unter … sichern. Danach speichert dieser Knopf die Datei.")
                return
            if doc.isReadonly():
                self.meld("Die Datei ist schreibgeschützt und kann nicht gespeichert werden.")
                return
            doc.store()
            self._diag("Dokument gespeichert (%d Abfragen)" % len(self.arbeit))
            self.d.ctrl("lblZeilen").getModel().Label = "Dokument gespeichert"
        except Exception as e:
            traceback.print_exc()
            self.meld("Das Dokument konnte nicht gespeichert werden: %s" % e)

    ABFRAGE_BEFEHLE = [("Neue Abfrage", "neu"), ("Neuer Parameter …", "neuer_parameter"),     # Reihenfolge wie die Knöpfe
                       ("Abfrage öffnen …", "oeffnen"), ("Abfrage speichern …", "speichern"),
                       ("Abfrage aktualisieren", "aktualisieren"), ("Abfrage löschen", "loeschen"), ("Abfragen bis zum Ende löschen", "bis_ende"), ("Abfrage umbenennen …", "umbenennen"),
                       ("Abfrage duplizieren", "dupliziere"), ("Abfrage-Verweis", "verweis"), ("Eigenschaften …", "eigenschaften"),
                       ("▲ Abfrage nach oben", "hoch"), ("▼ Abfrage nach unten", "runter"), ("Ausgabe …", "ausgabe")]

    def abfrage_befehl(self, name):
        i = self.lstA.pos()
        pn = self._param_an(i) if i >= 0 else None
        if pn is not None:                                   # in der Liste ist ein Parameter markiert
            if name == "loeschen":
                return self.parameter_loeschen(pn)
            if name in ("umbenennen", "eigenschaften"):
                return self.parameter_bearbeiten_(pn)
            if name == "bis_ende":
                return self.abfragen_bis_ende_loeschen()
            if name in ("aktualisieren", "dupliziere", "verweis", "hoch", "runter", "ausgabe"):
                if name == "ausgabe" or name == "aktualisieren":
                    pass                                     # gelten für die geöffnete Abfrage
                else:
                    self.meld("Das geht nur für Abfragen, nicht für Parameter. Parameter lassen sich ändern oder löschen.", "INFOBOX")
                    return
        elif i >= 0 and i != self.aktuell:
            self._wechsle_zu(i)
        {"neu": self.neue_abfrage, "neuer_parameter": self.neuer_parameter, "aktualisieren": self.vorschau_aktualisieren,
         "loeschen": self.abfrage_loeschen, "bis_ende": self.abfragen_bis_ende_loeschen, "umbenennen": self.abfrage_umbenennen,
         "dupliziere": self.abfrage_duplizieren, "verweis": self.abfrage_verweis,
         "hoch": lambda: self.abfrage_verschieben(-1), "runter": lambda: self.abfrage_verschieben(1),
         "eigenschaften": self.abfrage_eigenschaften, "ausgabe": self.ziel_waehlen,
         "oeffnen": self.abfrage_oeffnen, "speichern": self.abfrage_speichern}[name]()

    PARAMETER_BEFEHLE = [("Bearbeiten …", "bearbeiten"), ("Löschen", "loeschen"), ("Neuer Parameter …", "neu"),
                         ("Parameter verwalten …", "verwalten")]

    def zeige_parameter_menue(self, x, y, pname):
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        ids = {}
        for n, (text, name) in enumerate(self.PARAMETER_BEFEHLE, 1):
            pm.insertItem(n, text, 0, -1)
            ids[n] = name
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
        self._pm = pm
        wahl = self._menue_ausfuehren(pm, r)
        if wahl in ids:
            fn = {"bearbeiten": lambda: self.parameter_bearbeiten_(pname), "loeschen": lambda: self.parameter_loeschen(pname),
                  "neu": self.neuer_parameter, "verwalten": lambda: self.parameter_verwalten(pname)}[ids[wahl]]
            self._nach_menue("Parameter:" + ids[wahl], fn)

    def zeige_abfragen_menue(self, x, y):
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        ids = {}
        for n, (text, name) in enumerate(self.ABFRAGE_BEFEHLE, 1):
            pm.insertItem(n, text, 0, -1)
            ids[n] = name
        pm.insertSeparator(len(ids))
        pm.insertItem(500, "Automatisch speichern (nach jedem Schritt)", 0, len(ids) + 1)
        pm.checkItem(500, self.autospeichern_an())
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
        self._pm = pm
        wahl = self._menue_ausfuehren(pm, r)
        if wahl == 500:
            def umschalten():
                self.autospeichern_umschalten()
                try:
                    self.d.ctrl("chkAuto").getModel().State = 1 if self.autospeichern_an() else 0
                except Exception:
                    pass
            self._nach_menue("Abfrage:autospeichern", umschalten)
        elif wahl in ids:
            self._nach_menue("Abfrage:" + ids[wahl], lambda n=ids[wahl]: self.abfrage_befehl(n))

    def abfragen_maus(self, ev):
        """Abfragenliste (beim Loslassen): nur Linksklicks. Einfachklick wählt (macht die Liste selbst),
        Doppelklick öffnet das Menü – erst nach dem Mausereignis. Rechtsklicks werden ignoriert."""
        if not menue_geste(ev):
            return
        if not self._rechtsklick_zulassen():
            return
        ps = self.d.ctrl("lstAbfragen").getPosSize()
        x, y, z = ps.X + ev.X, ps.Y + ev.Y, self.lstA.zeile_bei(ev.X, ev.Y)
        pn = self._param_an(z) if z >= 0 else None
        if pn is not None:                                  # Parameterzeile: eigenes Menü
            self._spaeter(lambda: self.zeige_parameter_menue(x, y, pn))
            return
        if not 0 <= z < len(self.arbeit):
            return

        def menue():
            try:
                if z != self.aktuell:
                    self._wechsle_zu(z)
                self._spaeter(lambda: self.zeige_abfragen_menue(x, y))
            except Exception:
                traceback.print_exc()
        self._spaeter(menue)

    def _name_pruefen(self, name):
        """-> Fehlertext oder None."""
        name = name.strip()
        if not name:
            return "Der Name darf nicht leer sein."
        for k, e in enumerate(self.arbeit):
            if k != self.aktuell and e["a"].name.casefold() == name.casefold():
                return "Es gibt schon eine Abfrage namens „%s“." % e["a"].name
        return None

    def _abfrage_neuer_name(self, neu):
        alt = self.abfrage.name
        if neu == alt:
            return
        self.merke()
        for k, e in enumerate(self.arbeit):
            E.abfragename_in_verweisen(e["a"], alt, neu)          # Verweise anderer Abfragen (und eigene) folgen
        parameter_abfrage_umbenennen(self.doc, alt, neu)          # Parameter „aus Abfrage“ folgen
        self.abfrage.name = neu
        self.d.ctrl("txtName").getModel().Text = neu
        self._kontext_setzen()
        self.abfragen_liste_neu()
        self.liste_neu(self.lstS.pos())

    def _name_uebernehmen(self):
        """Eingabetaste im Namensfeld: neuen Namen in die Arbeitsliste übernehmen (nichts wird ins Blatt geschrieben)."""
        neu = self.d.ctrl("txtName").getText().strip()
        if neu == self.abfrage.name:
            return
        fehler = self._name_pruefen(neu)
        if fehler:
            self.d.ctrl("txtName").getModel().Text = self.abfrage.name
            self.meld(fehler)
            return
        self._abfrage_neuer_name(neu)

    def abfrage_umbenennen(self):
        neu = frage_text(self.ctx, "Abfrage umbenennen", "Neuer Name der Abfrage:", self.abfrage.name, self.d.peer())
        if neu is None:
            return
        fehler = self._name_pruefen(neu)
        if fehler:
            self.meld(fehler)
            return
        self._abfrage_neuer_name(neu.strip())

    def abfrage_duplizieren(self):
        a = E.Abfrage.from_json(self.abfrage.to_json())
        a.name = self._freier_name(self.abfrage.name)
        a.ziel, a.auto = {"art": "keine" if ist_verbindung(a) else "blatt"}, False     # Kopie bekommt ein eigenes Ausgabeblatt
        self._neue_in_liste(a)

    def abfrage_verweis(self):
        a = E.Abfrage(self._freier_name(self.abfrage.name), {"art": "abfrage", "name": self.abfrage.name}, [])
        self._neue_in_liste(a)

    def abfrage_verschieben(self, richtung):
        j = self.aktuell + richtung
        if not (0 <= j < len(self.arbeit)):
            return
        self._eintrag_ablegen()
        self.arbeit[self.aktuell], self.arbeit[j] = self.arbeit[j], self.arbeit[self.aktuell]
        self.aktuell = j
        self.abfragen_liste_neu()

    def _abhaengige_abfragen(self, name):
        """Alle Abfragen dieser Sitzung, die (auch über andere) von der Abfrage name abhängen."""
        gefunden = []
        offen = [name]
        while offen:
            n = offen.pop()
            for e in self.arbeit:
                if e["a"].name not in gefunden and e["a"].name != name and n in E.abfrage_verweist_auf(e["a"]):
                    gefunden.append(e["a"].name)
                    offen.append(e["a"].name)
        return gefunden

    def abfragen_bis_ende_loeschen(self):
        """Die markierte Abfrage und alle dahinter löschen (Parameter bleiben)."""
        self.abfrage_loeschen(bis_ende=True)

    def abfrage_loeschen(self, bis_ende=False):
        a = self.abfrage
        folg = [e["a"].name for e in self.arbeit[self.aktuell + 1:]] if bis_ende else []
        abh = []                                  # abhängige Abfragen, die NICHT ohnehin gelöscht werden
        for n_ in [a.name] + folg:
            for x in self._abhaengige_abfragen(n_):
                if x not in abh and x != a.name and x not in folg:
                    abh.append(x)
        betroffen = [a.name] + folg + abh
        par = sorted({p for n in betroffen for p in parameter_aus_abfrage(self.doc, n)}, key=str.casefold)
        blaetter = []
        try:
            for n in betroffen:
                e = next((x for x in self.arbeit if x["a"].name == n), None)
                z = (e["a"].ziel or {}) if e else {}
                bn = zielblatt_name(e["a"]) if e and z.get("art") not in ("keine", "zelle") else ""
                if bn and self.doc.getSheets().hasByName(bn):
                    blaetter.append(bn)
        except Exception:
            blaetter = []
        self._diag("Abfrage löschen: Frage")
        wahl = loesch_dialog(self.ctx, self.d.peer(), a.name, abh, par, blaetter, folg if bis_ende else None)
        if not wahl:
            self._diag("Abfrage löschen: abgebrochen")
            return
        if (abh and not wahl["abh"]) or (par and not wahl["par"]):
            text = "Abfrage „%s“ kann nicht gelöscht werden, solange davon abhängige Teile bleiben." % a.name
            if abh and not wahl["abh"]:
                text += "\n\nDiese Abfragen hängen von ihr ab: %s" % ", ".join(abh)
            if par and not wahl["par"]:
                text += "\n\nDiese Parameter holen ihren Wert aus ihr: %s" % ", ".join(par)
            text += "\n\nÄndere sie zuerst oder lösche sie mit."
            meldung(self.ctx, self.d.peer(), text, "ERRORBOX", 1)
            return
        self._diag("Abfrage löschen: bestätigt")
        zu_loeschen = [self.arbeit[self.aktuell]] + [e for e in self.arbeit if e["a"].name in abh or e["a"].name in folg]
        loesch_blatt = list(blaetter) if wahl["blatt"] else []
        alt_aktuell = self.alter_name
        sichern = dict(par=par if wahl["par"] else [])

        def loeschen():
            """Erst nach dem Ende des Klick-/Dialogereignisses (der Neuaufbau mitten darin stürzte am Mac ab)."""
            an = getattr(self, "_auto_namen", {})
            index = None
            for eintrag in zu_loeschen:
                try:
                    k = next(i for i, e in enumerate(self.arbeit) if e is eintrag)
                except StopIteration:
                    continue
                if eintrag is zu_loeschen[0]:
                    index = k
                alt = alt_aktuell if eintrag is zu_loeschen[0] else eintrag.get("alt")
                namen = {alt, eintrag["a"].name, an.get(id(eintrag["a"]))} - {None, ""}
                del self.arbeit[k]
                rest = {e["a"].name for e in self.arbeit} | {an.get(id(e["a"])) for e in self.arbeit}
                for n in namen - rest:
                    loesche_abfrage(self.doc, n, True)
                    if n in self._entfernt:
                        self._entfernt.remove(n)
                an.pop(id(eintrag["a"]), None)
            for pn in sichern["par"]:
                try:
                    loesche_oq_parameter(self.doc, pn)
                except Exception:
                    traceback.print_exc()
            for bn in loesch_blatt:
                try:
                    sheets = self.doc.getSheets()
                    benutzt = any((e["a"].quelle or {}).get("art") == "blatt" and (e["a"].quelle or {}).get("blatt") == bn
                                  for e in self.arbeit)
                    if sheets.hasByName(bn) and sheets.getCount() > 1 and not benutzt:
                        sheets.removeByName(bn)
                    else:
                        self._diag("Blatt %s bleibt (einziges Blatt oder wird als Quelle benutzt)" % bn)
                except Exception:
                    traceback.print_exc()
            try:
                speichere_reihenfolge(self.doc, [e["a"].name for e in self.arbeit])
            except Exception:
                pass
            if index is None:
                index = 0
            if not self.arbeit:
                self.arbeit.append(self._eintrag(E.Abfrage(self._freier_name("Abfrage1"), {}, []), None, None))
                index = 0
            self.aktuell = min(index, len(self.arbeit) - 1)
            self._diag("Abfrage löschen: Eintrag laden")
            try:
                self._eintrag_laden()
            except Exception:
                traceback.print_exc()
                absturzlog("FEHLER in Abfrage löschen: " + traceback.format_exc().strip().splitlines()[-1])
            self._diag("Abfrage löschen: fertig")
        self._spaeter(loeschen)

    def abfrage_eigenschaften(self):
        res = EigenschaftenDialog(self.ctx, self.abfrage, self._name_pruefen, self.d.peer()).zeigen()
        if not res:
            return
        name, beschr = res
        if beschr != self.abfrage.beschreibung:
            self.merke()
            self.abfrage.beschreibung = beschr
        self._abfrage_neuer_name(name)

    def _andere_speichern(self):
        """Beim Laden: geänderte/neue/gelöschte andere Abfragen sichern und (samt abhängiger) aktualisieren.
        -> Liste von Fehlertexten."""
        fehler = []
        doc = self.doc
        geaendert = {self.abfrage.name}
        self.arbeit = [e for k, e in enumerate(self.arbeit) if k == self.aktuell or e["a"].quelle]   # leere neue Abfragen verwerfen
        self.aktuell = next(k for k, e in enumerate(self.arbeit) if e["a"] is self.abfrage)
        for k, e in enumerate(self.arbeit):
            a = e["a"]
            if k != self.aktuell and (e["orig"] is None or a.to_json() != e["orig"] or e["alt"] != a.name):
                geaendert.add(a.name)
        wachs = True
        while wachs:                                  # Abfragen, die auf geänderte verweisen, ebenfalls aktualisieren
            wachs = False
            for e in self.arbeit:
                if e["a"].name not in geaendert and any(n in geaendert for n in E.abfrage_verweist_auf(e["a"])):
                    geaendert.add(e["a"].name)
                    wachs = True
        for k, e in enumerate(self.arbeit):
            a = e["a"]
            if k == self.aktuell or a.name not in geaendert:
                continue
            try:
                if e["alt"] and e["alt"] != a.name:
                    loesche_abfrage(doc, e["alt"])
                    alt_blatt, neu_blatt = gueltiger_blattname(e["alt"]), gueltiger_blattname(a.name)
                    sheets = doc.getSheets()
                    if (a.ziel or {}).get("art") != "zelle" and sheets.hasByName(alt_blatt) and not sheets.hasByName(neu_blatt):
                        sheets.getByName(alt_blatt).Name = neu_blatt
                speichere_abfrage(doc, a)
                e["alt"], e["orig"] = a.name, a.to_json()
            except Exception as ex:
                fehler.append("%s: %s" % (a.name, ex))
        for k, e in enumerate(self.arbeit):             # erst alles gesichert, dann aktualisiert (gegenseitige Verweise)
            a = e["a"]
            if k == self.aktuell or a.name not in geaendert:
                continue
            try:
                aktualisiere_abfrage(self.ctx, doc, a)
            except Exception as ex:
                fehler.append("%s: %s" % (a.name, ex))
        namen = {e["a"].name for e in self.arbeit}
        for n in self._entfernt:
            if n not in namen:
                loesche_abfrage(doc, n, True)
        speichere_reihenfolge(doc, [e["a"].name for e in self.arbeit])
        if getattr(self, "alle_an", False):            # auch alle übrigen Abfragen der Datei aktualisieren
            try:
                erledigt = {self.abfrage.name} | {e["a"].name for k, e in enumerate(self.arbeit) if e["a"].name in geaendert}
                in_liste = {e["a"].name for e in self.arbeit}
                for n in sorted(gespeicherte_abfragen(doc)):
                    if n in erledigt or n not in in_liste:
                        continue
                    try:
                        aktualisiere_abfrage(self.ctx, doc, E.Abfrage.from_json(gespeicherte_abfragen(doc)[n]))
                    except Exception as ex:
                        fehler.append("%s: %s" % (n, ex))
            except Exception:
                traceback.print_exc()
        return fehler

    # -- Ansicht: Farben, Gitternetz, Zeilendetails, Teiler -------------------------------
    def _farben(self):
        """Kopf- und Zellfarben passend zu hellem/dunklem Fenster."""
        dunkel, feld = bool(getattr(self.d, "dunkel", False)), 0xFFFFFF
        if dunkel:
            feld = Dlg.DUNKEL_FELD
        self._dunkel, self._feld = dunkel, feld
        if dunkel:                                   # fest gesetzte dunkle Textfarben vertragen sich nicht mit dem dunklen Grund
            for n_, c_ in (("lblLeer", 0xD6D2CB), ("lblMarkiert", 0x9CC8F5), ("lblCopy", 0xB9B4AC),
                           ("lblQual", 0xFF9A9A), ("lblFehler", 0xFF9A9A)):
                try:
                    self.d.model.getByName(n_).TextColor = c_
                except Exception:
                    pass
        for n in ("gridA", "gridB", "gridDetail"):
            try:
                gm = self.d.model.getByName(n)
                gm.HeaderBackgroundColor = Dlg.DUNKEL_KOPF if dunkel else 0xD9D9D9
                gm.HeaderTextColor = Dlg.DUNKEL_TEXT if dunkel else 0x000000
            except Exception:
                pass
        self._gitter_anwenden()

    def _band_farbe(self):
        """Zweite Zeilenfarbe der Bänderung: das Feld leicht abgesetzt (hell: dunkler, dunkel: heller)."""
        f = int(self._feld) & 0xFFFFFF
        r, g, b = (f >> 16) & 255, (f >> 8) & 255, f & 255
        if self._dunkel:                                   # dunkel: Feld etwas heller (warmes Grau)
            return Dlg.DUNKEL_BAND
        else:                                              # hell: zartes Blau (Rot/Grün etwas weg, Blau bleibt)
            r, g, b = (max(0, min(255, c - d)) for c, d in zip((r, g, b), (22, 12, 0)))
        return (r << 16) | (g << 8) | b

    def _gitter_anwenden(self):
        """Gitternetz an: Linien, einfarbige Zeilen. Gitternetz aus: Bänderung (Zeilen abwechselnd) ohne Linien.
        Listen (Abfragen, Schritte) haben nie Bänderung und nie Linien."""
        band = (self._feld, self._band_farbe())
        for n in ("deckAbfragen", "deckSchritte"):
            try:
                self.d.model.getByName(n).BackgroundColor = self._feld
            except Exception:
                pass
        for n in ("gridA", "gridB", "gridDetail", "lstAbfragen", "lstSchritte"):
            try:
                gm = self.d.model.getByName(n)
                if n in ("lstAbfragen", "lstSchritte"):
                    gm.UseGridLines = False
                    gm.RowBackgroundColors = (self._feld,)
                elif self.gitter or n == "gridDetail":
                    gm.UseGridLines = True
                    gm.GridLineColor = TRENNLINIE
                    gm.RowBackgroundColors = (self._feld,)
                else:
                    gm.UseGridLines = False
                    gm.RowBackgroundColors = band
            except Exception:
                traceback.print_exc()
        self._neu_zeichnen()

    def _gitter_geaendert(self, ev=None):
        self.gitter = bool(self.d.ctrl("chkGitter").getModel().State)
        self._gitter_anwenden()
        self.zeige()                  # Raster neu aufbauen, damit Linien/Zeilenfarben überall neu gezeichnet werden
        self._ansicht_speichern()

    def _details_umschalten(self, an):
        self.details_an = bool(an)
        self.d.ctrl("chkDetails").getModel().State = 1 if an else 0
        self.layout(self.d.model.Width, self.d.model.Height)
        if an:
            self.zeige_details()
        self._ansicht_speichern()

    def _listen_sichtbar_geaendert(self, ev=None):
        ab = bool(self.d.ctrl("chkAbfr").getModel().State)
        sc = bool(self.d.ctrl("chkSchr").getModel().State)
        if (ab, sc) != (self.abfragen_an, self.schritte_an):
            self.abfragen_an, self.schritte_an = ab, sc
            self.layout(self.d.model.Width, self.d.model.Height)
            self._ansicht_speichern()

    def _breite_aendern(self, welche, delta):
        """Pfeilknöpfe: Abfragenliste (a) oder Schrittliste (s) schmaler/breiter."""
        if welche == "a":
            self.breite_a = int(max(60, min(300, self.breite_a + delta)))
        else:
            self.breite_s = int(max(60, min(300, self.breite_s + delta)))
        self.layout(self.d.model.Width, self.d.model.Height)
        self._ansicht_speichern()

    def _alle_geaendert(self, ev=None):
        self.alle_an = bool(self.d.ctrl("chkAlle").getModel().State)
        self._ansicht_speichern()

    def maximieren(self):
        """Fenster auf die ganze Arbeitsfläche setzen und wieder zurück (eigener Knopf, weil die Titelleiste je nach
        System keine Maximieren-Schaltfläche hat)."""
        try:
            dlg = self.d.dlg
            if not self._max:
                self._vor_max = dlg.getPosSize()
                wa = toolkit(self.ctx).getWorkArea()
                dlg.setPosSize(wa.X, wa.Y, wa.Width, wa.Height, 15)
            else:
                v = self._vor_max
                if v is not None:
                    dlg.setPosSize(v.X, v.Y, v.Width, v.Height, 15)
            self._max = not self._max
            self.d.ctrl("btnMax").getModel().Label = "Verkleinern" if self._max else "Maximieren"
            self.layout(self.d.model.Width, self.d.model.Height)
            self.d.bei_groesse(0, 0)
        except Exception:
            traceback.print_exc()

    def _details_geaendert(self, ev=None):
        an = bool(self.d.ctrl("chkDetails").getModel().State)
        if an != self.details_an:
            self._details_umschalten(an)

    def zeige_details(self, zeile=None):
        """Ganzer Datensatz der angeklickten Zeile, untereinander (Spalte | Wert), wie die Tabellenzeilendetails in Power Query."""
        if not self.details_an:
            return
        try:
            t = self.angezeigt
            if zeile is not None:
                self._detail_zeile = zeile
            z = self._detail_zeile
            smgr = self.smgr
            gm = self.d.model.getByName("gridDetail")
            if getattr(self, "_detail_cm", None) is None:           # Spaltenmodell nur EINMAL anlegen: wird es bei jedem
                cm = smgr.createInstance("com.sun.star.awt.grid.DefaultGridColumnModel")   # Klick ersetzt, trifft das
                for fl, br in ((0, 75), (1, 100)):                  # Betriebssystem (Bedienungshilfen) auf tote Spalten
                    c = cm.createColumn()
                    c.Flexibility = fl
                    c.ColumnWidth = br
                    cm.addColumn(c)
                cm.getColumns()[0].HorizontalAlign = uno.Enum("com.sun.star.style.HorizontalAlignment", "LEFT")
                gm.ColumnModel = cm
                gm.GridDataModel = smgr.createInstance("com.sun.star.awt.grid.DefaultGridDataModel")
                self._detail_cm = cm
            dm = gm.GridDataModel                                   # Zeilen werden nur ausgetauscht, nicht das Modell
            try:
                dm.removeAllRows()
            except Exception:
                pass
            titel = "Tabellenzeilendetails"
            if t is not None and t.zeilen:
                z = max(0, min(z, len(t.zeilen) - 1))
                self._detail_zeile = z
                zeile_w = t.zeilen[z]
                namen = t.spalten[:MAX_SPALTEN_VORSCHAU]
                dm.addRows(tuple(str(i) for i in range(len(namen))),
                           tuple((n, E.als_text(zeile_w[i])) for i, n in enumerate(namen)))
                titel += " – Zeile %d" % (z + 1)
            self.d.ctrl("lblDetail").getModel().Label = titel
            self._param_steuer_platzieren()
            self._scroll.pop("gridDetail", None)
            gm.VScroll = gm.HScroll = False
            self._scroll_anpassen()
            self._scroll_spaeter()
        except Exception:
            traceback.print_exc()

    def _ansicht_speichern(self):
        """Breiten der Listen und Anzeigeoptionen in der Datei merken."""
        try:
            if self.doc is None:
                return
            props = self.doc.getDocumentProperties().getUserDefinedProperties()
            text = json.dumps({"a": int(self.breite_a), "s": int(self.breite_s), "gitter": self.gitter,
                               "details": self.details_an, "ab": self.abfragen_an, "sc": self.schritte_an,
                               "al": self.alle_an})
            try:
                props.addProperty(PROP_ANSICHT, 128, text)
            except Exception:
                props.setPropertyValue(PROP_ANSICHT, text)
        except Exception:
            pass

    def _ansicht_laden(self):
        try:
            props = self.doc.getDocumentProperties().getUserDefinedProperties()
            z = json.loads(props.getPropertyValue(PROP_ANSICHT))
            self.breite_a = max(60, min(300, int(z.get("a", self.breite_a))))
            self.breite_s = max(60, min(300, int(z.get("s", self.breite_s))))
            self.gitter = bool(z.get("gitter", False))
            self.details_an = bool(z.get("details", True))
            self.abfragen_an = bool(z.get("ab", True))
            self.schritte_an = bool(z.get("sc", True))
            self.alle_an = bool(z.get("al", True))
        except Exception:
            pass
        try:
            self.d.ctrl("chkGitter").getModel().State = 1 if self.gitter else 0
            self.d.ctrl("chkDetails").getModel().State = 1 if self.details_an else 0
            self.d.ctrl("chkAbfr").getModel().State = 1 if self.abfragen_an else 0
            self.d.ctrl("chkSchr").getModel().State = 1 if self.schritte_an else 0
            self.d.ctrl("chkAlle").getModel().State = 1 if self.alle_an else 0
        except Exception:
            pass

    def _diag(self, text, ev=None, quelle=None):
        """Diagnose für Mausereignisse: schreibt nur, wenn im Benutzerordner die Datei OpenQuery-Diagnose.txt existiert."""
        if self._diag_pfad is None:
            return
        try:
            if ev is not None:
                try:
                    qn = quelle.getModel().Name if quelle is not None else ""
                except Exception:
                    qn = "Dialog" if quelle is not None else ""
                text += " [Quelle=%s X=%s Y=%s Tasten=%s Klicks=%s Popup=%s]" % (
                    qn, getattr(ev, "X", "?"), getattr(ev, "Y", "?"), getattr(ev, "Buttons", "?"),
                    getattr(ev, "ClickCount", "?"), getattr(ev, "PopupTrigger", "?"))
            with open(self._diag_pfad, "a", encoding="utf-8") as f:
                f.write("%.2f %s\n" % (time.time() - self._t0, text))
        except Exception:
            pass

    def _abs_x(self, ev, quelle=None):
        """Waagrechte Pixelposition der Maus im Dialog. quelle: das Element, bei dem der Listener hängt
        (der Dialog selbst liefert schon Dialogkoordinaten, ein Element nur seine eigenen)."""
        try:
            if quelle is None or quelle is self.d.dlg:
                return ev.X
            return quelle.getPosSize().X + ev.X
        except Exception:
            return ev.X

    def _teiler_start(self, k, ev, quelle=None):
        self._diag("Teiler %d gedrückt" % k, ev, quelle)
        try:
            self._drag = {"k": k, "abs": self._abs_x(ev, quelle), "w": self.breite_a if k == 1 else self.breite_s}
        except Exception:
            self._drag = None

    def _dlg_gedrueckt(self, ev):
        """Druck auf den Dialog selbst (nicht auf ein Element): liegt er auf einem Teiler, beginnt das Ziehen.
        Fängt den Fall ab, dass die schmalen Teilerflächen selbst keine Mausereignisse bekommen."""
        self._diag("Dialog gedrückt", ev, self.d.dlg)
        if self._drag is not None or getattr(ev, "Buttons", 1) != 1:
            return
        for k in (1, 2):
            try:
                ps = self.d.ctrl("sp%dl" % k).getPosSize()
                if ps.X - 5 <= ev.X <= ps.X + ps.Width + 5 and ps.Y <= ev.Y <= ps.Y + ps.Height:
                    self._teiler_start(k, ev, self.d.dlg)
                    return
            except Exception:
                pass

    def _ziehen_ende(self, ev=None):
        if self._drag is None and self._spdrag is None:
            return
        spalte = self._spdrag is not None
        self._diag("Ziehen beendet (%s)" % ("Spalte" if spalte else "Teiler"), ev)
        self._drag = self._spdrag = None
        if spalte:
            self._breiten_ignorieren = False
            self.breiten_merken()
        self._ansicht_speichern()

    def _teiler_bewegt(self, ev, quelle=None):
        """Mausbewegung irgendwo im Dialog: bei gegriffenem Teiler/Spaltenrand und gehaltener Taste die Breite nachführen."""
        dr, sd = self._drag, self._spdrag
        if not dr and not sd:
            return
        if not (getattr(ev, "Buttons", 0) & 1):            # Taste losgelassen
            self._ziehen_ende()
            return
        x = self._abs_x(ev, quelle)
        self._diag_n += 1
        if self._diag_n % 5 == 1:
            self._diag("Ziehen bewegt, x=%s" % x, ev, quelle)
        gp = self.d.ctrl("grid").getPosSize().Width
        f = max(gp / max(self.d.modell("grid").Width, 1), 0.5)       # Pixel je Dialogeinheit
        if sd:
            try:
                w = int(max(20, min(250, sd["w"] + (x - sd["abs"]) / f)))
                cols = self.d.ctrl("grid").getModel().ColumnModel.getColumns()
                cols[sd["col"]].ColumnWidth = w
                self.breiten[sd["name"]] = w
            except Exception:
                traceback.print_exc()
            return
        delta = (x - dr["abs"]) / f
        if dr["k"] == 1:
            self.breite_a = int(max(60, min(300, dr["w"] + delta)))
        else:
            self.breite_s = int(max(60, min(300, dr["w"] - delta)))
        self.layout(self.d.model.Width, self.d.model.Height)

    # -- Hilfen ------------------------------------------------------------
    def meld(self, text, art="WARNINGBOX", knoepfe=1):
        try:
            p = self.d.peer()
        except Exception:
            p = self.parent
        return meldung(self.ctx, p, text, art, knoepfe)

    def tabelle_bis(self, bis):
        """Tabelle nach den ersten `bis` Schritten (Fehler -> StepError)."""
        try:
            schluessel = (id(self.roh), json.dumps(self.abfrage.schritte[:bis], sort_keys=True, default=str))
        except Exception:
            return E.fuehre_aus(self.roh, self.abfrage.schritte, bis)
        if schluessel in self._cache_t:
            return self._cache_t[schluessel][1]
        tab = E.fuehre_aus(self.roh, self.abfrage.schritte, bis)
        if len(self._cache_t) > 40:
            self._cache_t.pop(next(iter(self._cache_t)))
        self._cache_t[schluessel] = (self.roh, tab)         # roh mit festhalten, damit id(roh) nicht wiederverwendet wird
        return tab

    # -- Aufbau --------------------------------------------------------------
    def bauen(self):
        d = Dlg(self.ctx, TITEL + " – Abfrage bearbeiten", 650, 330, groesse_aenderbar=True)
        d.esc_sperren = True       # Escape soll den Editor nicht schließen
        d.warm = False             # Hauptfenster bleibt flach in Systemfarben; die Dialoge davor sind warmgrau
        self.d = d
        z = d.add
        for k_, (tname, eintraege) in enumerate(LEISTE):               # Reiter und flache Symbole im Kopfband
            z("FixedText", "tab%d" % k_, -3000, 2, 60, 11, Label=tname, Align=1, NoLabel=True, HelpText=tname,
              )
        z("FixedText", "tabLinie", -3000, 13, 40, 2, BackgroundColor=0x3B82C4)
        for n_ in ("tabBasisL", "tabBasisR"):                          # dünne Linie unter den Reitern (um den blauen Balken herum)
            z("FixedText", n_, -3000, 14, 10, 1, BackgroundColor=TRENNLINIE)
        for e_ in list(ALLE_EINTRAEGE.values()) + [MEHR]:
            if True:
                kid, label, symbol, aktion, tipp = e_
                url = symbol_url(symbol)
                if url:
                    z("ImageControl", "tbi_" + kid, -3000, 19, ICON_B, ICON_H, ImageURL=url, Border=2, BorderColor=0xD3D7DD,
                      BackgroundColor=0xFFFFFF, ScaleImage=True, ScaleMode=1, HelpText=tipp)
                else:
                    z("FixedText", "tbi_" + kid, -3000, 19, ICON_B, ICON_H, Label="•", Align=1, HelpText=tipp)
                z("FixedText", "tbt_" + kid, -3000, 47, 58, 24, Label=label, Align=1, MultiLine=True, NoLabel=True,
                  FontHeight=8.4, HelpText=tipp)
        z("Button", "btnUndo", -3000, 12, 52, 14, Label="Rückgängig")          # unsichtbar: Zustand für Tests/Verlauf
        z("Button", "btnRedo", -3000, 12, 60, 14, Label="Wiederholen")
        # unter den Abfragen
        z("Button", "btnNeuerParam", 5, 245, 100, 12, Label="Neuer Parameter", HelpText="Neuen Parameter anlegen")
        z("Button", "btnOeffnen", 5, 245, 48, 12, Label="Öffnen…", HelpText="Abfrage aus einer Datei öffnen (in diese Datei übernehmen)")
        z("Button", "btnSpeichern", 55, 245, 48, 12, Label="Speichern…", HelpText="Die gewählte Abfrage in einer Datei speichern")
        # unter den Schritten
        z("Button", "btnZiel", 5, 245, 150, 12, Label="Ausgabe …", HelpText="Wohin diese Abfrage ihr Ergebnis schreibt")
        for n in ("linieOben", "linieUnten"):                 # waagrechte Trennlinien: unter dem Menüband / über dem Fuß
            z("FixedText", n, 5, 38, 100, 1, BackgroundColor=TRENNLINIE)

        z("FixedText", "lblAbfragen", 5, 60, 100, 10, Label="Abfragen")
        z("FixedText", "lblSchritte", 5, 60, 150, 10, Label="Angewendete Schritte")
        for k in (1, 2):      # senkrechte Trennlinie (1) mit schmalen Griffflächen links/rechts (ziehbar)
            z("FixedText", "sp%da" % k, 5, 58, 2, 10)
            z("FixedText", "sp%dl" % k, 5, 58, 1, 10, BackgroundColor=TRENNLINIE)
            z("FixedText", "sp%db" % k, 5, 58, 2, 10)
        z("Grid", "lstSchritte", 8, 72, 144, 184, Border=0)
        z("Grid", "lstAbfragen", 8, 72, 100, 184, Border=0)
        # Abdeckfelder über der leeren Restfläche der Listen: ein Klick dorthin trifft nicht das Raster
        # (LibreOffice-Raster greifen dort auf nicht vorhandene Zeilen zu)
        z("FixedText", "deckAbfragen", -3000, 0, 10, 10, Label="")
        z("FixedText", "deckSchritte", -3000, 0, 10, 10, Label="")
        z("Button", "btnNeueAbfrage", 5, 230, 100, 12, Label="Neue Abfrage")
        for n_, t_ in (("btnAbfAktual", "Neu laden"), ("btnAbfLoeschen", "Löschen"), ("btnAbfUmben", "Umbenennen"),
                       ("btnAbfDupl", "Duplizieren"), ("btnAbfVerweis", "Verweis"), ("btnAbfEigen", "Eigensch."),
                       ("btnAbfHoch", "▲"), ("btnAbfRunter", "▼")):
            z("Button", n_, 5, 245, 48, 12, Label=t_)
        z("CheckBox", "chkAuto", 5, 245, 100, 10, Label="Autom. speichern")
        z("FixedText", "deckLinks", -3000, 0, 10, 10, Label="")      # deckt den Rest unter den Knöpfen ab
        z("Button", "btnHinzu", 5, 230, 150, 12, Label="Schritt hinzufügen ▾")
        for n_, sym_, tip_ in (("btnUndoK", "rueckgaengig", "Rückgängig"), ("btnRedoK", "wiederholen", "Wiederholen")):
            z("Button", n_, -3000, 230, 14, 12, ImageURL=symbol_url(sym_ + "_k"), ImagePosition=12,
              HelpText=tip_ + " (nur Schritte, Quelle und Ausgabe-Einstellungen der Abfrage)")
        z("Button", "btnUmben", 5, 245, 48, 12, Label="Umbenennen…")
        z("Button", "btnHoch", 5, 230, 73, 12, Label="▲", HelpText="Schritt nach oben")
        z("Button", "btnRunter", 82, 230, 73, 12, Label="▼", HelpText="Schritt nach unten")
        z("Button", "btnAendern", 5, 245, 48, 12, Label="Ändern…")
        z("Button", "btnLoeschen", 55, 245, 48, 12, Label="Löschen")
        z("Button", "btnAktiv", 105, 245, 50, 12, Label="Ein/Aus")
        z("Button", "btnDupl", 5, 260, 150, 12, Label="Duplizieren")
        z("Button", "btnBisEnde", 5, 260, 150, 12, Label="Bis Ende löschen", HelpText="Diesen und alle folgenden Schritte löschen")

        z("FixedText", "lblInfo", 160, 44, 250, 11, Label="", Align=0)
        z("FixedText", "lblVor", 415, 24, 40, 10, Label="Vorschau:")
        z("ListBox", "lstVor", 450, 22, 85, 12, Dropdown=True, LineCount=6)
        for gn in ("gridA", "gridB"):          # zwei Raster im Wechsel: das frisch befüllte wird gezeigt, das alte geparkt
            z("Grid", gn, 160, 72, 375, 190, ShowRowHeader=False, ShowColumnHeader=True, Border=2,
              BorderColor=TRENNLINIE, VScroll=False, HScroll=False)
        d.alias["grid"] = "gridA"
        z("FixedText", "lblLeer", 160, 72, 375, 190, MultiLine=True, Align=1, TextColor=0x777777,
          Label="Noch keine Daten.\n\nBitte oben mit „Quelle…“ eine Quelle wählen.")
        z("FixedText", "lblDetail", 160, 230, 150, 10, Label="Tabellenzeilendetails")
        z("Button", "btnDetailZu", 520, 230, 14, 10, Label="×")
        z("Edit", "txtParamWert", -3000, 230, 100, 13, Text="", Border=1, HelpText="Wert des Parameters – ändern und „Übernehmen“ (oder Enter)")
        z("Button", "btnParamWert", -3000, 230, 56, 13, Label="Übernehmen", HelpText="Wert des Parameters speichern")
        z("Grid", "gridDetail", 160, 240, 375, 60, ShowRowHeader=False, ShowColumnHeader=False, Border=2,
          BorderColor=TRENNLINIE, VScroll=False, HScroll=False)
        z("CheckBox", "chkGitter", 160, 230, 60, 10, Label="Gitternetz")
        z("CheckBox", "chkDetails", 220, 230, 70, 10, Label="Zeilendetails", State=1)
        z("CheckBox", "chkAbfr", 220, 230, 60, 10, Label="Abfragen", State=1, HelpText="Abfrageliste anzeigen")
        z("CheckBox", "chkSchr", 280, 230, 60, 10, Label="Schritte", State=1, HelpText="Schrittliste anzeigen")
        z("CheckBox", "chkAlle", 5, 243, 150, 10, Label="Beim Schließen alle aktualisieren", State=1,
          HelpText="Beim „Schließen und Laden“ werden alle Abfragen dieser Datei neu geschrieben, nicht nur die bearbeiteten (und ihre abhängigen).")
        z("Button", "btnMax", 250, 290, 80, 14, Label="Maximieren",
          HelpText="Fenster auf die ganze Arbeitsfläche vergrößern bzw. wieder verkleinern")
        for n_, t_, h_ in (("btnAbfSchmal", "><", "Liste schmaler"), ("btnAbfBreit", "<>", "Liste breiter"),
                           ("btnSchrSchmal", "><", "Liste schmaler"), ("btnSchrBreit", "<>", "Liste breiter")):
            z("Button", n_, -3000, 0, 16, 10, Label=t_, HelpText=h_)
        for n_ in ("btnArtAbf", "btnArtSchr"):          # Umschalter: Knöpfe unter den Listen als Symbole oder als Text
            z("Button", n_, -3000, 0, 14, 10, ImageURL=symbol_url("symbole_k"), ImagePosition=12,
              HelpText="Knöpfe unter der Liste als Symbole oder als Text zeigen")
        z("FixedText", "deckRechts", -3000, 0, 10, 10, Label="")
        z("FixedText", "deckTabelle", -3000, 0, 10, 10, Label="")        # deckt die leere Fläche unter den Tabellenzeilen ab
        z("FixedText", "deckDetail", -3000, 0, 10, 10, Label="")
        z("FixedText", "deckTabelleR", -3000, 0, 10, 10, Label="")       # deckt den freien Bereich rechts der Spalten ab
        z("FixedText", "lblMarkiert", 160, 60, 187, 11, Label="", Align=0)
        z("FixedText", "lblQual", 350, 60, 185, 11, Label="", Align=0, TextColor=0xB00020)
        z("FixedText", "lblZeilen", 160, 230, 120, 10, Label="", Align=2)
        z("FixedText", "lblFehler", 160, 243, 375, 20, MultiLine=True, Label="", TextColor=0xB00020)

        z("Edit", "txtName", 65, 44, 110, 13, Text=self.abfrage.name,
          HelpText="Name der Abfrage – ändern und Enter drücken")
        z("Button", "btnLadenIn", 200, 290, 125, 14, Label="Schließen und Laden in …",
          HelpText="Wie „Schließen und Laden“, fragt aber vorher nach der Ausgabe (neues Blatt, bestehendes Blatt, nur Verbindung)")
        z("Button", "btnLaden", 325, 290, 125, 14, Label="Schließen und Laden")
        z("FixedText", "lblCopy", 5, 300, 130, 10, Label="© 2026 joaswerk", TextColor=0x707070)
        z("Button", "btnAbbr", 454, 290, 81, 14, Label="Abbrechen")
        for gn in ("gridA", "gridB"):
            try:    # Rasterköpfe fett (wirkt nicht in jeder LibreOffice-Version); Farben je nach hell/dunkel in _farben()
                gm_ = d.model.getByName(gn)
                fd_ = gm_.FontDescriptor
                fd_.Weight = 150.0
                gm_.FontDescriptor = fd_
            except Exception:
                traceback.print_exc()
        for n in ("lblAbfragen", "lblSchritte", "lblMarkiert"):      # Beschriftungen fett
            try:
                m = d.model.getByName(n)
                fd = m.FontDescriptor
                fd.Weight = 150.0
                m.FontDescriptor = fd
            except Exception:
                traceback.print_exc()
        try:
            d.model.getByName("lblMarkiert").TextColor = 0x1F4E79
            d.model.getByName("lblLeer").VerticalAlign = uno.Enum("com.sun.star.style.VerticalAlignment", "MIDDLE")
        except Exception:
            pass
        self._farben()
        setze_liste(d.ctrl("lstVor").getModel(), [l for l, _ in VORSCHAU_STUFEN], [VORSCHAU_STANDARD])

        d.on_click("btnZiel", self.ziel_waehlen, self.meld)
        d.on_click("btnHinzu", self.menue_hinzufuegen, self.meld)
        d.on_click("btnUmben", self.umbenennen, self.meld)
        d.on_click("btnOeffnen", self.abfrage_oeffnen, self.meld)
        d.on_click("btnSpeichern", self.abfrage_speichern, self.meld)
        for k_, (tname, eintraege) in enumerate(LEISTE):
            lz = _Zeiger(_sicher(lambda k=k_: self._spaeter(lambda: self.leiste_reiter(k)), self.meld), d.modell("tab%d" % k_))
            d.refs.append(lz)
            d.ctrl("tab%d" % k_).addMouseListener(lz)
        for e_ in list(ALLE_EINTRAEGE.values()) + [MEHR]:
            if True:
                lz = _Zeiger(_sicher(lambda e=e_: self._spaeter(lambda: self.leiste_klick(e)), self.meld),
                             d.modell("tbt_" + e_[0]))
                d.refs.append(lz)
                d.ctrl("tbi_" + e_[0]).addMouseListener(lz)
                d.ctrl("tbt_" + e_[0]).addMouseListener(lz)
        d.on_click("btnUndoK", lambda: self._spaeter(self.rueckgaengig), self.meld)
        d.on_click("btnRedoK", lambda: self._spaeter(self.wiederholen), self.meld)
        d.on_click("btnHoch", lambda: self.verschiebe(-1), self.meld)
        d.on_click("btnRunter", lambda: self.verschiebe(1), self.meld)
        d.on_click("btnAendern", self.aendern, self.meld)
        d.on_click("btnLoeschen", lambda: self._spaeter(self.loeschen), self.meld)
        d.on_click("btnBisEnde", lambda: self._spaeter(self.loeschen_bis_ende), self.meld)
        d.on_click("btnAktiv", self.ein_aus, self.meld)
        d.on_click("btnDupl", self.dupliziere, self.meld)
        self.lstS = Liste(d, "lstSchritte", _sicher(self._schritt_gewaehlt, self.meld), self._schritt_tipp)
        self.lstA = Liste(d, "lstAbfragen", _sicher(self._abfrage_gewaehlt, self.meld), self._abfrage_tipp)
        self.lstS.nach = self.lstA.nach = self._liste_geaendert
        self.lstA.vorab = lambda n: self._listen_platzieren(na=n)
        self.lstS.vorab = lambda n: self._listen_platzieren(ns=n)
        schritt_maus = _Maus(_sicher(self.schritt_maus, self.meld), beim_loslassen=True)
        d.refs.append(schritt_maus)
        d.ctrl("lstSchritte").addMouseListener(schritt_maus)
        abfr_maus = _Maus(_sicher(self.abfragen_maus, self.meld), beim_loslassen=True)
        d.refs.append(abfr_maus)
        d.ctrl("lstAbfragen").addMouseListener(abfr_maus)
        d.on_click("btnNeueAbfrage", self.neue_abfrage, self.meld)
        for n_, b_ in (("btnAbfAktual", "aktualisieren"), ("btnAbfLoeschen", "loeschen"), ("btnAbfUmben", "umbenennen"),
                       ("btnAbfDupl", "dupliziere"), ("btnAbfVerweis", "verweis"), ("btnAbfEigen", "eigenschaften"),
                       ("btnAbfHoch", "hoch"), ("btnAbfRunter", "runter")):
            d.on_click(n_, lambda b=b_: self._spaeter(lambda: self.abfrage_befehl(b)), self.meld)
        d.on_select("chkAuto", self._auto_geaendert, self.meld)
        d.on_click("btnLaden", self.laden, self.meld)
        d.on_click("btnLadenIn", self.laden_in, self.meld)
        d.on_click("btnNeuerParam", self.neuer_parameter, self.meld)
        d.on_click("btnAbbr", lambda: d.schliessen(0))
        d.on_click("btnDetailZu", lambda: self._details_umschalten(False), self.meld)
        d.on_click("btnParamWert", lambda: self._spaeter(self._param_wert_speichern), self.meld)
        d.on_select("chkGitter", self._gitter_geaendert, self.meld)
        d.on_select("chkDetails", self._details_geaendert, self.meld)
        d.on_select("chkAbfr", self._listen_sichtbar_geaendert, self.meld)
        d.on_select("chkSchr", self._listen_sichtbar_geaendert, self.meld)
        d.on_select("chkAlle", self._alle_geaendert, self.meld)
        d.on_click("btnMax", self.maximieren, self.meld)
        d.on_click("btnArtAbf", lambda: self._spaeter(self.knopfart_umschalten), self.meld)
        d.on_click("btnArtSchr", lambda: self._spaeter(self.knopfart_umschalten), self.meld)
        d.on_click("btnAbfSchmal", lambda: self._breite_aendern("a", -12), self.meld)
        d.on_click("btnAbfBreit", lambda: self._breite_aendern("a", 12), self.meld)
        d.on_click("btnSchrSchmal", lambda: self._breite_aendern("s", -12), self.meld)
        d.on_click("btnSchrBreit", lambda: self._breite_aendern("s", 12), self.meld)
        for k in (1, 2):
            for suffix in ("a", "l", "b"):
                qc = d.ctrl("sp%d%s" % (k, suffix))
                pr = _Maus(_sicher(lambda ev, k=k, qc=qc: self._teiler_start(k, ev, qc), self.meld))
                lo = _Maus(_sicher(self._ziehen_ende, self.meld), beim_loslassen=True)
                d.refs += [pr, lo]
                d.ctrl("sp%d%s" % (k, suffix)).addMouseListener(pr)
                d.ctrl("sp%d%s" % (k, suffix)).addMouseListener(lo)
        # Ziehen: ein gedrücktes Textfeld bekommt keine Bewegungsereignisse (kein Mauseinfang) – deshalb verfolgen alle
        # Elemente die Bewegung; solange der Teiler "gegriffen" ist und die Taste gehalten wird, wird die Breite nachgeführt.
        for n in ("dlg", "gridA", "gridB", "gridDetail", "lstAbfragen", "lstSchritte", "lblAbfragen", "lblSchritte", "lblInfo",
                  "lblDetail", "lblZeilen", "lblMarkiert", "lblQual", "lblFehler", "lblLeer", "linieOben", "linieUnten"):
            try:
                c = d.dlg if n == "dlg" else d.ctrl(n)
                fb = _sicher(lambda ev, c=c: self._teiler_bewegt(ev, c), self.meld)
                bw = _MausBew(fb, fb)
                lo = _Maus(_sicher(self._ziehen_ende, self.meld), beim_loslassen=True)
                d.refs += [bw, lo]
                c.addMouseMotionListener(bw)
                c.addMouseListener(lo)
                if n == "dlg":
                    dp_ = _Maus(_sicher(self._dlg_gedrueckt, self.meld))
                    d.refs.append(dp_)
                    c.addMouseListener(dp_)
            except Exception:
                traceback.print_exc()
        for k in (1, 2):
            for suffix in ("a", "l", "b"):
                qc = d.ctrl("sp%d%s" % (k, suffix))
                fb = _sicher(lambda ev, qc=qc: self._teiler_bewegt(ev, qc), self.meld)
                bw = _MausBew(fb, fb)
                d.refs.append(bw)
                qc.addMouseMotionListener(bw)
        d.on_select("lstVor", self.vorschau_gewaehlt, self.meld)
        tk = _Taste(_sicher(self._name_uebernehmen, self.meld))
        d.refs.append(tk)
        d.ctrl("txtName").addKeyListener(tk)
        for gn in ("gridA", "gridB"):
            maus = _Maus(_sicher(lambda ev, gn=gn: self.grid_maus(ev, gn), self.meld))
            d.refs.append(maus)
            d.ctrl(gn).addMouseListener(maus)
        for gn in ("gridA", "gridB"):                      # Hover über dem Spaltenkopf: voller Name
            bw = _MausBew(_sicher(lambda ev, gn=gn: self._kopf_tipp(ev, gn), self.meld))
            d.refs.append(bw)
            d.ctrl(gn).addMouseMotionListener(bw)
        strg = _Strg(_sicher(self.kopiere_auswahl, self.meld))
        d.refs.append(strg)
        for gn in ("gridA", "gridB", "gridDetail"):
            d.ctrl(gn).addKeyListener(strg)
        dmaus = _Maus(_sicher(self.detail_maus, self.meld))
        d.refs.append(dmaus)
        d.ctrl("gridDetail").addMouseListener(dmaus)
        d.bei_groesse = lambda w, h: self.layout(*self._fenster_logik(w, h))
        d.nach_peer = self._farben
        fenster = _Fenster(_sicher(self.fenster_groesse, self.meld))
        d.refs.append(fenster)
        d.dlg.addWindowListener(fenster)
        self.layout(650, 330)
        self.knoepfe_aktualisieren()

    # -- Layout (Größe ändern) ---------------------------------------------------
    VT_Y, LBL_Y, LIST_Y, BAND = 76, 97, 109, 75           # senkrechte Linien ab, Beschriftungen, Listen/Tabelle, Reiter und Symbolleiste

    SB_PX = 17

    @staticmethod
    def _zeilen_geometrie(g):
        """(Kopfhöhe, Zeilenhöhe) in Pixeln durch Abtasten der Treffer-Abfrage; unabhängig von der Rollposition."""
        erste_y, r0, zeile = None, None, None
        for y in range(0, 160):
            r = g.getRowAtPoint(3, y)
            if r < 0:
                continue
            if erste_y is None:
                erste_y, r0 = y, r
            elif r == r0 + 1:
                zeile = y - erste_y
                break
        if erste_y is None or not zeile:
            return None
        return erste_y, zeile

    ZEILE_DU = 10.3          # Schätzwert der Listenzeilenhöhe in Dialogeinheiten, bis gemessen werden kann

    def _px_je_du(self, name):
        """Pixel je Dialogeinheit senkrecht (waagrecht ist der Wert anders)."""
        ps = self.d.ctrl(name).getPosSize()
        return ps.Height / max(self.d.modell(name).Height, 1)

    def _scroll_fuer(self, name, mit_h):
        """Rollbalken nur zeigen, wenn es etwas zu rollen gibt (gemessen in Pixeln; ohne Messung Schätzung)."""
        if not self._sichtbar:
            return                  # vor dem Anzeigen liefert das Raster keine verlässlichen Maße
        g = self.d.ctrl(name)
        gm = g.getModel()
        ps = g.getPosSize()
        if ps.X < -1000 or ps.Width < 20 or ps.Height < 20:
            return
        f = ps.Width / max(gm.Width, 1)
        n = gm.GridDataModel.RowCount
        geo = self._zeilen_geometrie(g) if n >= 2 else None
        if n >= 2 and geo is None:
            if name == "grid":      # der Streifen rechts braucht keine Zeilenmessung
                self._deckung_rechts(gm, ps, bool(self._scroll.get(self.d.alias.get(name, name), (False, False))[0]), False)
            return                  # noch keine Messung möglich: Zustand lassen, später erneut prüfen
        kopf, zh = geo if geo else ((22 if gm.ShowColumnHeader else 0), self.ZEILE_DU * ps.Height / max(gm.Height, 1))
        noetig_v = (kopf + n * zh) if n else 0
        noetig_h = 0
        if mit_h:
            noetig_h = sum(c.ColumnWidth for c in gm.ColumnModel.getColumns()) * f
        sb, rahmen = self.SB_PX, 2
        hoch, breit = ps.Height - rahmen, ps.Width - rahmen
        v = noetig_v > hoch + (9 if name in ("lstAbfragen", "lstSchritte") else 3)       # Listen sind passend hoch gebaut: kleine Messfehler ergeben keinen Rollbalken
        h = mit_h and noetig_h > breit - (sb if v else 0) + 3
        if h and not v and noetig_v > hoch - sb + 3:
            v = True
        self._deckung(name, gm, ps, kopf, n, zh, v, h)
        key = self.d.alias.get(name, name)
        if self._scroll.get(key) != (v, h):
            self._scroll[key] = (v, h)
            gm.VScroll = v
            gm.HScroll = h
            self.d.auffrischen(name)        # Rollbalken sicher neu zeichnen

    def _letzte_spalte_ausgleichen(self, gm, frei_du, h, cols_du):
        """Die letzte Spalte füllt die Breite des Rasters. Calc tut das über „Flexibility“ nicht überall (am Mac nicht
        verlässlich), deshalb wird die Breite hier ausdrücklich nachgeführt: freie Fläche -> letzte Spalte breiter,
        Überlauf (Fenster wurde schmaler) -> wieder schmaler, nie unter die ursprüngliche Breite. True = Modell neu gebaut."""
        args = getattr(self, "_cm_args", None)
        if not args or cols_du <= 0:
            return False
        extra = self._letzte_extra
        if not h and frei_du >= 4:
            neu = extra + int(frei_du)
        elif h and extra > 0 and frei_du < -1:
            neu = max(0, extra + int(frei_du))
        else:
            return False
        if neu == extra:
            return False
        self._letzte_extra = neu
        gm.ColumnModel = self._spaltenmodell(*args)
        return True

    def _deckung_rechts(self, gm, ps, v, h):
        """Freien Bereich rechts der Spalten abdecken. Hängt nur an den Spaltenbreiten, nicht an der Zeilenmessung."""
        try:
            cols_du = sum(c.ColumnWidth for c in gm.ColumnModel.getColumns())
            frei_du = gm.Width - cols_du - 3 - (self.SB_PX / (ps.Width / max(gm.Width, 1)) if v else 0)
            if self._letzte_spalte_ausgleichen(gm, frei_du, h, cols_du):
                return self._deckung_rechts(gm, ps, v, h)           # nach dem Umbau mit den neuen Breiten prüfen
            if h or frei_du < 4 or cols_du <= 0:
                self.d.platziere("deckTabelleR", -3000, -3000, 10, 10)
            else:
                pxh = ps.Height / max(gm.Height, 1)
                self.d.platziere("deckTabelleR", gm.PositionX + cols_du + 1, gm.PositionY + 1, frei_du,
                                 max(gm.Height - 2 - (self.SB_PX / pxh if h else 0), 1))
        except Exception:
            pass

    def _deckung(self, name, gm, ps, kopf, n, zh, v, h):
        """Leere Fläche unter den letzten Zeilen eines Rasters mit einem Feld abdecken (ein Rechtsklick dort traf sonst
        das nackte Raster)."""
        deck = {"grid": "deckTabelle", "gridDetail": "deckDetail"}.get(name)
        if deck is None:
            return
        if name == "grid":
            self._deckung_rechts(gm, ps, v, h)
        try:
            pxdu = ps.Height / max(gm.Height, 1)
            frei_px = ps.Height - 2 - (kopf + n * zh) - (self.SB_PX if h else 0)
            if frei_px < 12 or v:
                self.d.platziere(deck, -3000, -3000, 10, 10)
                return
            oben = gm.PositionY + (kopf + n * zh + 2) / pxdu
            hoehe = frei_px / pxdu - 2
            self.d.platziere(deck, gm.PositionX + 1, oben, gm.Width - 2, hoehe)
        except Exception:
            pass

    def _scroll_anpassen(self):
        for name, mit_h in (("grid", True), ("gridDetail", False), ("lstAbfragen", False), ("lstSchritte", False)):
            try:
                self._scroll_fuer(name, mit_h)
            except Exception:
                pass

    def _scroll_spaeter(self):
        """Nach dem Anzeigen noch einmal prüfen (erst dann liefert das Raster verlässliche Maße)."""
        self._spaeter(lambda: (self._scroll_anpassen(), self._spaeter(self._scroll_anpassen)))

    def _zeilenhoehe(self):
        """Zeilenhöhe der Listen in Dialogeinheiten: gemessen, sonst die Schätzung."""
        for name, liste in (("lstSchritte", self.lstS), ("lstAbfragen", self.lstA)):
            try:
                if len(liste.items) < 2:
                    continue
                g = self.d.ctrl(name)
                ps = g.getPosSize()
                if ps.X < -1000 or ps.Width < 20 or ps.Height < 40:
                    continue
                geo = self._zeilen_geometrie(g)
                if geo:
                    zh = geo[1] / max(self._px_je_du(name), 0.5)
                    if 6 <= zh <= 18:
                        self.ZEILE_DU = zh
                        break
            except Exception:
                pass
        return self.ZEILE_DU

    def _knopfreihen(self, reihen, x0, y0, breite, hk, abst):
        """Knopfreihen (Namen mit Gewichten) nebeneinander in jede Reihe; gibt das y unter der letzten Reihe zurück."""
        y = y0
        for reihe in reihen:
            gesamt = sum(g for _, g in reihe)
            frei = breite - 3 * (len(reihe) - 1)
            ws = [int(frei * g / gesamt) for _, g in reihe]
            ws[-1] = frei - sum(ws[:-1])
            x = x0
            for (n, _), w in zip(reihe, ws):
                if n is None:
                    x += w + 3
                    continue
                self.d.platziere(n, x, y, w, hk)
                if n == "btnBisEnde":
                    if not self.symbole_an():
                        self.d.modell(n).Label = "Bis Ende löschen" if w >= 56 else "Bis Ende"
                x += w + 3
            y += hk + abst
        return y

    def _listen_platzieren(self, na=None, ns=None):
        """Listen und die Knöpfe darunter: die Knöpfe stehen direkt unter dem letzten Eintrag, bei vollen Listen
        unten über der Fußlinie. Reicht die Breite nicht für zwei Knöpfe nebeneinander, stehen sie untereinander;
        reicht auch die Höhe nicht, entfallen die Knöpfe (Bedienung dann per Doppelklick und Menü)."""
        g = getattr(self, "_geo", None)
        if not g:
            return
        d = self.d
        zh = self._zeilenhoehe()
        yf, LY, LA, LW, xs = g["yf"], g["LY"], g["LA"], g["LW"], g["xs"]
        hk, abst, pfeil = (22 if self.symbole_an() else 12), 2, 13     # Knopfhöhe (Symbolmodus: Platz für 33-px-Symbole), Abstand, Reihe der Breitenpfeile unten
        na = len(self.lstA.items) if na is None else na
        ns = len(self.lstS.items) if ns is None else ns
        ende = yf - 3 - pfeil                            # untere Grenze für Knöpfe
        mind = LY + 3 * zh + 9                           # mindestens drei Listenzeilen sichtbar
        zeile = hk + abst
        # --- linke Knöpfe: zwei Spalten / untereinander / entfallen
        l_namen = [("btnAbfAktual", "btnAbfLoeschen"), ("btnAbfUmben", "btnAbfDupl"),
                   ("btnAbfVerweis", "btnAbfEigen"), ("btnAbfHoch", "btnAbfRunter")]
        if LA >= 94 and mind + 7 * zeile + 10 <= ende:
            modus_l, l_reihen = "zwei", [[("btnNeuerParam", 1)], [("btnOeffnen", 1), ("btnSpeichern", 1)]] \
                + [[(n, 1) for n in r] for r in l_namen]
        elif mind + 12 * zeile + 10 <= ende:
            modus_l, l_reihen = "eins", [[("btnNeuerParam", 1)], [("btnOeffnen", 1)], [("btnSpeichern", 1)]] \
                + [[(n, 1)] for r in l_namen for n in r]
        else:
            modus_l, l_reihen = "aus", []
        links_h = (1 + len(l_reihen)) * zeile + 10
        # --- rechte Knöpfe: drei / zwei / eine Spalte / entfallen
        if LW >= 150:
            modus_r = "drei"
            r_reihen = [[("btnUndoK", 9), ("btnRedoK", 9), (None, 82)],
                        [("btnHinzu", 1)],
                        [("btnAendern", 31), ("btnUmben", 38), ("btnLoeschen", 31)],
                        [("btnAktiv", 27), ("btnDupl", 33), ("btnBisEnde", 40)],
                        [("btnZiel", 1)],
                        [("btnHoch", 1), ("btnRunter", 1)]]          # Pfeile ganz unten, wie bei den Abfragen
        elif LW >= 94:
            modus_r = "zwei"
            r_reihen = [[("btnUndoK", 1), ("btnRedoK", 1)], [("btnHinzu", 1)], [("btnAendern", 1), ("btnUmben", 1)],
                        [("btnLoeschen", 1), ("btnBisEnde", 1)], [("btnAktiv", 1), ("btnDupl", 1)], [("btnZiel", 1)],
                        [("btnHoch", 1), ("btnRunter", 1)]]
        else:
            modus_r = "eins"
            r_reihen = [[("btnUndoK", 1), ("btnRedoK", 1)]] + [[(n, 1)] for n in ("btnHinzu", "btnAendern", "btnUmben", "btnLoeschen",
                                           "btnBisEnde", "btnAktiv", "btnDupl", "btnZiel", "btnHoch", "btnRunter")]
        if mind + len(r_reihen) * zeile - abst > ende:
            modus_r, r_reihen = "aus", []
        rechts_h = len(r_reihen) * zeile - abst if r_reihen else 0
        ya = min(LY + na * zh + 9, ende - links_h)
        ys = min(LY + ns * zh + 9, ende - rechts_h)
        ya, ys = max(ya, LY + zh + 9), max(ys, LY + zh + 9)
        d.neu_platziere("lstAbfragen", 5, LY, LA, ya - 2 - LY)
        d.neu_platziere("lstSchritte", xs, LY, LW, ys - 2 - LY)
        for deck, x_, w_, n_, y_ in (("deckAbfragen", 5, LA, na, ya), ("deckSchritte", xs, LW, ns, ys)):
            oben = LY + n_ * zh + 2
            hoehe = (y_ - 2) - oben
            if hoehe >= 2:
                d.platziere(deck, x_, oben, w_, hoehe)
            else:
                d.platziere(deck, -3000, 0, 10, 10)
        # links
        d.platziere("btnNeueAbfrage", 5, ya, LA, hk)
        for r in l_namen:
            for n in r:
                d.platziere(n, -3000, -3000, 10, 10)
        for n in ("btnNeuerParam", "btnOeffnen", "btnSpeichern"):
            d.platziere(n, -3000, -3000, 10, 10)
        yy = self._knopfreihen(l_reihen, 5, ya + zeile, LA, hk, abst)
        d.platziere("chkAuto", 5, yy, LA, 10)
        yy += 10 + 2
        if ende - yy >= 2:
            d.platziere("deckLinks", 5, yy, LA, ende - yy)
        else:
            d.platziere("deckLinks", -3000, 0, 10, 10)
        # rechts
        for n in ("btnUndoK", "btnRedoK", "btnHinzu", "btnHoch", "btnRunter", "btnAendern", "btnUmben", "btnLoeschen",
                  "btnBisEnde", "btnAktiv", "btnDupl", "btnZiel"):
            d.platziere(n, -3000, -3000, 10, 10)
        yr = self._knopfreihen(r_reihen, xs, ys, LW, hk, abst)
        if r_reihen:
            yr = yr - abst + 2
        else:
            yr = ys
        if ende - yr >= 2:                        # Rest unter den Schritt-Knöpfen abdecken
            d.platziere("deckRechts", xs, yr, LW, ende - yr)
        else:
            d.platziere("deckRechts", -3000, 0, 10, 10)
        self._versteckte_parken()
        for liste in (self.lstA, self.lstS):             # Markierung erneuern (geht beim Verschieben des Rasters verloren)
            try:
                liste.markierung_erneuern()
            except Exception:
                pass

    _LINKS = ("lblAbfragen", "lstAbfragen", "deckAbfragen", "btnNeueAbfrage", "btnNeuerParam", "btnOeffnen", "btnSpeichern", "btnAbfAktual", "btnAbfLoeschen", "btnAbfUmben",
              "btnAbfDupl", "btnAbfVerweis", "btnAbfEigen", "btnAbfHoch", "btnAbfRunter", "chkAuto", "deckLinks",
              "btnAbfSchmal", "btnAbfBreit", "btnArtAbf", "sp1a", "sp1l", "sp1b")
    _RECHTS = ("lblSchritte", "lstSchritte", "deckSchritte", "deckRechts", "txtName", "btnUndo", "btnRedo", "btnUndoK", "btnRedoK", "btnHinzu",
               "btnHoch", "btnRunter", "btnAendern", "btnUmben", "btnLoeschen", "btnAktiv", "btnDupl", "btnBisEnde", "btnZiel",
               "btnSchrSchmal", "btnSchrBreit", "btnArtSchr", "sp2a", "sp2l", "sp2b")

    def _versteckte_parken(self):
        """Ausgeblendete Listen samt Knöpfen aus dem Fenster parken."""
        for an, namen in ((self.abfragen_an, self._LINKS), (self.schritte_an, self._RECHTS)):
            if an:
                continue
            for n in namen:
                try:
                    self.d.platziere(n, -3000, -3000, 10, 10)
                except Exception:
                    pass

    def _markiert_platzieren(self):
        """Spaltenname (links, fett) und direkt dahinter die Fehler-/Leerangabe über der Wertetabelle."""
        try:
            x0, RW, iw = self._mk_geo
            text = self.d.ctrl("lblMarkiert").getModel().Label or ""
            wm = min(int(self._textbreite(text) * 1.2) + 6, max(RW - iw - 40, 40)) if text else 0
            self.d.platziere("lblMarkiert", x0, self.LBL_Y, max(wm, 1), 11)
            self.d.platziere("lblQual", x0 + wm + 2, self.LBL_Y, max(RW - iw - wm - 4, 1), 11)
        except Exception:
            pass

    def _kopfzeile(self):
        """Schrittbeschreibung: volle Breite, solange keine Spalte markiert ist; sonst links neben dem Spaltennamen."""
        try:
            x0, RW = self._kz
            markiert = bool(self.d.ctrl("lblMarkiert").getModel().Label)
            pass                                                           # Schrittbezeichnung steht unter der Tabelle
        except Exception:
            pass

    def _liste_geaendert(self):
        self._listen_platzieren()
        self._scroll_anpassen()
        self._scroll_spaeter()
        if self._sichtbar:            # nach der Auswahl-/Größenänderung noch einmal sauber neu zeichnen lassen
            self._spaeter(lambda: [self.d.auffrischen(n) for n in ("lstAbfragen", "lstSchritte")])

    def _teiler(self, k, x, hoehe):
        d = self.d
        d.platziere("sp%da" % k, x, self.VT_Y, 2, hoehe)
        d.platziere("sp%dl" % k, x + 2, self.VT_Y, 1, hoehe)
        d.platziere("sp%db" % k, x + 3, self.VT_Y, 2, hoehe)

    def _grid_platzieren(self):
        """Das gezeigte Raster an seinen Platz, das andere geparkt; bei leerer Abfrage nur der Hinweis."""
        d = self.d
        x, y, w, h = self._rect
        for n in ("gridA", "gridB"):
            if n == d.alias["grid"] and not self._leer:
                m = d.modell(n)
                if m.Width != max(int(w), 1) or m.Height != max(int(h), 1):
                    d.platziere(n, -3000, y, w, h)       # Größe geändert: erst weg, dann zurück -> vollständig neu gezeichnet
                d.platziere(n, x, y, w, h)
            else:
                d.platziere(n, -3000, -3000, w, h)
        if self._leer:
            d.platziere("deckTabelle", -3000, -3000, 10, 10)
            d.platziere("deckTabelleR", -3000, -3000, 10, 10)
            d.platziere("lblLeer", x, y, w, h)
        else:
            d.platziere("lblLeer", -3000, -3000, w, h)

    def layout(self, W, H):
        """Alle Elemente anhand der Dialoggröße (in Dialogeinheiten) platzieren."""
        if self._im_layout:
            return
        self._im_layout = True
        try:
            W, H = max(int(W), self.MIN_BREITE), max(int(H), self.MIN_HOEHE)
            d = self.d
            LA = int(self.breite_a) if self.abfragen_an else 0
            LW = int(self.breite_s) if self.schritte_an else 0
            ueber = 190 - (W - LA - LW - 30)       # die Tabelle soll mindestens ca. 190 breit bleiben: Listen vorübergehend schmaler
            if ueber > 0:
                k_ = min(ueber, max(LW - 70, 0)); LW -= k_; ueber -= k_
                k_ = min(ueber, max(LA - 70, 0)); LA -= k_
            xs = W - LW - 5                        # Schrittspalte rechts
            sp1 = 5 + LA + 1                       # Teiler zwischen Abfragen und Tabelle
            sp2 = xs - 6                           # Teiler zwischen Tabelle und Schritten
            x0 = sp1 + 6
            RW = sp2 - 1 - x0                      # Tabelle in der Mitte
            BAND, LY = self.BAND, self.LIST_Y
            yf = H - 46                            # Fußlinie; darunter nur Angaben und Laden/Abbrechen
            gh = yf - 5 - LY                       # Höhe von Tabelle und Listen
            ginfo = 12                             # Zeile mit der Schrittbezeichnung direkt unter Tabelle/Details
            # Menüband (Platz für ein späteres Menü; die Knöpfe stehen vorerst darin)
            self._leiste_xs = W - 5
            self._leiste_undo_x = None             # Band nutzt die ganze Breite (Rückgängig/Wiederholen stehen im Start-Reiter)
            self.leiste_platzieren()
            d.platziere("linieOben", 5, BAND, W - 10, 1)
            d.platziere("linieUnten", 5, yf, W - 10, 1)
            # Namensfeld (wie das Namensfeld in Excel) über der Schrittliste
            d.platziere("txtName", xs, 81, LW, 14)
            # Beschriftungszeile: Schrittbeschreibung links, Name der markierten Spalte und Fehler/Leer in der Mitte
            # Spaltenname (rechtsbündig) und Fehler/Leer (linksbündig) treffen sich in der Mitte; die Schrittbeschreibung steht rechts
            iw = min(130, max(RW // 3, 60))                           # rechts oben: „n Zeilen × m Spalten“
            xm = x0 + (RW - iw) // 2 - 2
            self._kz = (x0, RW)
            self._mk_geo = (x0, RW, iw)
            self._markiert_platzieren()
            d.platziere("lblZeilen", x0 + RW - iw, self.LBL_Y, iw, 11)
            self._kopfzeile()
            d.platziere("lblAbfragen", 5, self.LBL_Y, max(LA - 28, 1), 10)
            d.platziere("lblSchritte", xs, self.LBL_Y, max(LW - 28, 1), 10)
            for (nl, nr), xl_, xr_ in ((("btnAbfSchmal", "btnAbfBreit"), 5 + 2, 5 + 20),           # Abfragen: linksbündig
                                       (("btnSchrSchmal", "btnSchrBreit"), xs + LW - 38, xs + LW - 18)):   # Schritte: rechtsbündig
                d.platziere(nl, xl_, yf - 12, 16, 10)         # unten über der waagrechten Linie; Position unabhängig von der Breite
                d.platziere(nr, xr_, yf - 12, 16, 10)
            d.platziere("btnArtAbf", 5 + LA - 16, yf - 12, 14, 10)          # Abfragen: Umschalter rechtsbündig
            d.platziere("btnArtSchr", xs + 2, yf - 12, 14, 10)            # Schritte: Umschalter linksbündig
            vh = yf - self.VT_Y
            self._teiler(1, sp1, vh)
            self._teiler(2, sp2, vh)
            self._geo = {"yf": yf, "LY": LY, "LA": LA, "LW": LW, "xs": xs}
            self._listen_platzieren()
            self._versteckte_parken()
            gm_ = gh - ginfo                       # Tabelle + Details ohne die Zeile darunter
            dh = max(70, int(gm_ * 0.36)) if self.details_an else 0
            gt = gm_ - (dh + 14 if dh else 0)
            d.platziere("lblInfo", x0, LY + gm_ + 1, RW, 11)
            self._rect = (x0, LY, RW, gt)
            self._grid_platzieren()
            if not dh:
                for n in ("lblDetail", "btnDetailZu", "gridDetail", "deckDetail", "txtParamWert", "btnParamWert"):
                    d.platziere(n, -3000, -3000, 10, 10)        # ausgeblendet: außerhalb des Fensters parken
            if dh:
                d.platziere("lblDetail", x0, LY + gt + 3, RW - 20, 10)
                d.platziere("btnDetailZu", x0 + RW - 14, LY + gt + 2, 14, 10)
                d.platziere("gridDetail", x0, LY + gt + 14, RW, dh)
                self._detail_geo = (x0, LY + gt + 2, RW)
            else:
                self._detail_geo = None
            self._param_steuer_platzieren()
            # Fuß: Angaben und Laden/Abbrechen
            yb = yf + 5
            d.platziere("chkAlle", 5, yb, 150, 10)
            d.platziere("chkGitter", 158, yb, 46, 10)
            d.platziere("chkDetails", 206, yb, 62, 10)
            d.platziere("lblVor", 272, yb, 34, 10)
            d.platziere("lstVor", 306, yb - 2, 62, 14)
            d.platziere("chkAbfr", 372, yb, 56, 10)
            d.platziere("chkSchr", 430, yb, 56, 10)
            d.platziere("lblFehler", 5, yb + 14, max(W - 5 - 398, 60), 20)
            d.platziere("btnMax", W - 394, H - 20, 70, 14)
            d.platziere("btnLadenIn", W - 320, H - 20, 128, 14)
            d.platziere("btnLaden", W - 188, H - 20, 108, 14)
            d.platziere("btnAbbr", W - 76, H - 20, 71, 14)
            d.platziere("lblCopy", 5, H - 14, 130, 10)
            self.groesse = (W, H)
            try:
                self.beschreibung_zeigen()                      # Kürzung der Schrittzeile hängt von der Breite ab
            except Exception:
                pass
        finally:
            self._im_layout = False
        self._scroll_anpassen()
        self._scroll_spaeter()

    def _fenster_logik(self, w=0, h=0):
        """Fenstergröße in Dialogeinheiten. Aus der Pixelgröße umgerechnet und mit der Modellgröße verglichen; es gilt
        der kleinere Wert, damit rechts/unten nie etwas abgeschnitten wird (am Mac stimmte eines von beiden nicht)."""
        mw, mh = self.d.model.Width, self.d.model.Height
        try:
            if w and h:
                sz = self.d.peer().convertSizeToLogic(Size(int(w), int(h)), MASSEINHEIT_APPFONT)
                if sz.Width > 100 and sz.Height > 100:
                    diag_global("Editor Layout: Fenster %dx%d px = %dx%d DE, Modell %dx%d DE" % (w, h, sz.Width, sz.Height, mw, mh))
                    return min(mw, sz.Width), min(mh, sz.Height)
        except Exception:
            pass
        return mw, mh

    def fenster_groesse(self, ev):
        """Fenster wurde in der Größe geändert (ev in Pixeln) -> in Dialogeinheiten umrechnen."""
        W = H = None
        try:
            sz = self.d.peer().convertSizeToLogic(Size(ev.Width, ev.Height), MASSEINHEIT_APPFONT)
            W, H = sz.Width, sz.Height
        except Exception:
            try:
                W, H = self.d.model.Width, self.d.model.Height
            except Exception:
                return
        self.layout(W, H)

    # -- Anzeige -----------------------------------------------------------
    @staticmethod
    def fehler_klartext(e):
        """Verständliche Fehlermeldung mit Hinweis, was zu tun ist."""
        m = str(getattr(e, "meldung", e))
        low = m.lower()
        if isinstance(getattr(e, "__cause__", None), KeyError) or "keyerror" in low or "spalte" in low and (
                "nicht" in low or "gibt es" in low or "fehlt" in low):
            hinweis = "Eine Spalte, die dieser Schritt braucht, gibt es an dieser Stelle nicht (mehr). " \
                      "Wurde sie vorher umbenannt, gelöscht oder fehlt in der Quelle? Spalte im Schritt neu wählen."
        elif "division" in low or "zero" in low:
            hinweis = "Es wurde durch 0 geteilt. Mit WENN(...) kann man diesen Fall abfangen."
        elif "could not convert" in low or "umwandeln" in low or "invalid literal" in low:
            hinweis = "Ein Wert hat nicht das erwartete Format. Datentyp oder Gebietsschema (z. B. Komma/Punkt) prüfen."
        else:
            hinweis = ""
        return m + ("\n" + hinweis if hinweis else "")

    def schritt_texte(self):
        texte = ["01. Quelle: " + beschreibe_quelle(self.abfrage.quelle)]
        for k, st in enumerate(self.abfrage.schritte):
            warn = "⚠ " if self.fehler_schritt == k else ""
            aus = "⏸ (aus) " if st.get("aktiv") is False else ""
            titel = (st.get("name") or "").strip() or E.beschreibe(st)
            texte.append("%02d. %s%s%s" % (k + 2, warn, aus, titel))
        return texte

    def beschreibung_zeigen(self):
        """Automatische Beschreibung des markierten Schritts unter der Liste (auch wenn er einen eigenen Namen hat)."""
        try:
            i = self.lstS.pos()
            if i < 1:
                voll = "Quelle: " + beschreibe_quelle(self.abfrage.quelle) if i == 0 else ""
            else:
                voll = E.beschreibe(self.abfrage.schritte[i - 1])
            if i >= 0:        # unter der Tabelle: vollständig; nur wenn der Platz nicht reicht, am Ende gekürzt (Hover: voll)
                text = "Schritt %d: %s" % (i + 1, voll.replace("\n", " "))
                frei = (self._kz[1] if self._kz else 300) - 6
                if self._textbreite(text) > frei:
                    while len(text) > 8 and self._textbreite(text + "…") > frei:
                        text = text[:-1]
                    text = text.rstrip() + "…"
                self.d.ctrl("lblInfo").getModel().Label = text
                self.d.ctrl("lblInfo").getModel().HelpText = "Schritt %d: %s" % (i + 1, voll)
        except Exception:
            pass

    def liste_neu(self, auswahl=None):
        texte = self.schritt_texte()
        if auswahl is None:
            auswahl = len(texte) - 1
        auswahl = max(0, min(auswahl, len(texte) - 1))
        self.lstS.setze(texte, auswahl)
        self.beschreibung_zeigen()

    def gewaehlter_schritt(self):
        """Anzahl der Schritte, bis zu denen die Vorschau gerechnet wird (0 = nur Quelle)."""
        i = self.lstS.pos()
        n = len(self.abfrage.schritte)
        return n if i < 0 else min(i, n)

    def _markierte(self, bis, tab):
        """Spalten, die der angezeigte Schritt betrifft oder neu angelegt hat."""
        if bis < 1 or self.fehler_schritt is not None:
            return []
        s = self.abfrage.schritte[bis - 1]
        if s.get("aktiv") is False or s.get("op") not in E.OPS:
            return []
        namen = []
        for f in E.OPS[s["op"]]["felder"]:
            v = s.get(f["name"])
            if f["art"] == "spalte" and v:
                namen.append(v)
            elif f["art"] == "spalten":
                namen += list(v or [])
        for k in ("neu", "attribut_name", "wert_name"):
            if s.get(k):
                namen.append(s[k])
        try:       # neu entstandene Spalten (Gruppieren, Pivot, Teilen, Umbenennen …)
            vor = {c for c in self.tabelle_bis(bis - 1).spalten}
            namen += [c for c in tab.spalten if c not in vor]
        except E.StepError:
            pass
        gueltig = []
        for n in namen:
            try:
                gueltig.append(tab.spalten[tab.idx(n)])
            except E.FormelFehler:
                continue
        return _eindeutig(gueltig)

    def marker(self, name):
        if name == self.sel_spalte:
            return MARKER_GEKLICKT
        return ""

    def markierung_text(self):
        if self.sel_spalte and self.angezeigt is not None and self.sel_spalte in self.angezeigt.spalten:
            if self.sel_spalte.strip().casefold() in self._manuelle_namen():
                return "%s %s  (manuelle Spalte)" % (self.MANUELL_SYMBOL, self.sel_spalte)
            return self.sel_spalte
        return ""

    def zeige(self):
        if self._busy:
            return
        self._busy = True
        try:
            self._zeige()
        finally:
            self._busy = False

    def _markierung_sichern(self):
        """Die angezeigte Abfrage muss in der Liste links markiert sein (z. B. nach einem Parameter-Doppelklick)."""
        try:
            if self.arbeit and 0 <= self.aktuell < len(self.arbeit) and self.lstA.pos() != self.aktuell:
                if self._abfr_items() != self.lstA.items:
                    self.abfragen_liste_neu()
                else:
                    self.lstA.waehle(self.aktuell)
        except Exception:
            traceback.print_exc()

    def _zeige(self):
        d = self.d
        self._markierung_sichern()
        self.breiten_merken()
        if self.roh is None:
            self.angezeigt = None
            self.betroffen = []
            self._param_ansicht = None
            d.ctrl("lblLeer").getModel().Label = "Noch keine Daten.\n\nBitte oben mit „Quelle…“ eine Quelle wählen."
            self.leer_zeigen()
            d.ctrl("lblInfo").getModel().Label = "Noch keine Daten – bitte zuerst eine Quelle wählen."
            d.ctrl("lblZeilen").getModel().Label = ""
            d.ctrl("lblMarkiert").getModel().Label = ""
            d.ctrl("lblQual").getModel().Label = ""
            self._kopfzeile()
            return
        bis = self.gewaehlter_schritt()
        fehlertext = ""
        self.fehler_schritt = None
        try:
            tab = self.tabelle_bis(bis)
        except E.StepError as e:
            self.fehler_schritt = e.index
            fehlertext = "Fehler in %s – Anzeige bis zum letzten fehlerfreien Schritt." % self.fehler_klartext(e)
            try:
                tab = self.tabelle_bis(e.index)
            except E.StepError:
                tab = self.roh
            self.liste_neu(bis)
        self.angezeigt = tab
        self.betroffen = self._markierte(bis, tab)
        d.ctrl("lblFehler").getModel().Label = fehlertext
        self.fuelle_grid(tab)
        info = "%d Zeilen × %d Spalten" % (len(tab.zeilen), len(tab.spalten))
        hilfe = info
        if len(tab.zeilen) > self.vorschau_limit:
            info = "Vorschau %d von %d Zeilen × %d Sp." % (self.vorschau_limit, len(tab.zeilen), len(tab.spalten))
            hilfe = "Die Vorschau zeigt nur die ersten %d Zeilen; geladen werden alle %d Zeilen × %d Spalten." % (
                self.vorschau_limit, len(tab.zeilen), len(tab.spalten))
        self.beschreibung_zeigen()
        d.ctrl("lblZeilen").getModel().Label = info
        d.ctrl("lblZeilen").getModel().HelpText = hilfe
        d.ctrl("lblMarkiert").getModel().Label = self.markierung_text()
        self._markiert_platzieren()
        self.qualitaet_zeigen()

    # -- Raster ------------------------------------------------------------------
    def breiten_merken(self):
        """Vom Nutzer gezogene Spaltenbreiten festhalten, damit sie nach dem Neuaufbau erhalten bleiben."""
        if self._breiten_ignorieren:          # Breiten wurden gerade gesetzt: Raster-Stand nicht zurücklesen
            self._breiten_ignorieren = False
            return
        try:
            cm = self.d.ctrl("grid").getModel().ColumnModel
            if cm is None:
                return
            for name, c in list(zip(self._grid_namen, cm.getColumns()[1:]))[:-1]:     # die letzte Spalte ist gestreckt: nicht merken
                self.breiten[name] = c.ColumnWidth
        except Exception:
            pass

    MANUELL_SYMBOL = "✎"

    def _manuelle_namen(self):
        """Namen der manuellen Spalten (Schritt „Manuelle Spalten behalten“) dieser Abfrage, kleingeschrieben."""
        namen = set()
        try:
            for st in self.abfrage.schritte:
                if st.get("op") == "hand_behalten" and st.get("aktiv") is not False:
                    namen |= {x.strip().casefold() for x in str(st.get("handspalten") or "").splitlines() if x.strip()}
        except Exception:
            pass
        return namen

    def _titel(self, name, kuerzel):
        n = self._fehler.get(name, 0)
        man = (self.MANUELL_SYMBOL + " ") if name.strip().casefold() in self._manuelle_namen() else ""
        m = self.marker(name)
        # Platz für die Pfeile ist immer reserviert (Geviert-Leerzeichen), damit die Kopfzeile beim Markieren nicht springt
        links, rechts = (m, MARKER_RECHTS) if m else (MARKER_LEER, MARKER_LEER_R)
        return "%s%s%s | %s%s%s" % (links, ("⚠%d | " % n) if n else "", kuerzel, man, name, rechts)

    BREITE_MIN, BREITE_MAX = 30, 100        # Dialogeinheiten; 100 ≈ 5 cm

    @staticmethod
    def _textbreite(text):
        """Grobe Breite eines Textes in Dialogeinheiten (ohne Schriftmetrik, daher nur Näherung)."""
        b = 0.0
        for ch in str(text):
            b += 1.8 if ch == " " else 4.6 if ch.isupper() or ch in "mwMW@%" else 3.5 if ch.isdigit() else 3.3
        return b

    def optimale_breite(self, name, k, zeilen, kuerzel):
        inhalt = max([self._textbreite(E.als_text(z[k])) for z in zeilen] or [0])
        kopf = self._textbreite(self._titel(name, kuerzel)) + 8
        return int(max(self.BREITE_MIN, min(self.BREITE_MAX, max(inhalt, kopf) + 12)))

    def _spaltenmodell(self, spalten, breiten):
        """Neues Spaltenmodell mit den aktuellen Köpfen (nur ein neu zugewiesenes Modell wird sofort neu gezeichnet)."""
        self._cm_args = (spalten, breiten)
        cm = self.smgr.createInstance("com.sun.star.awt.grid.DefaultGridColumnModel")
        c0 = cm.createColumn()          # Spalte 0: Zeilennummern (eigener Zeilenkopf stürzt am Mac ab)
        c0.Title = "Nr."
        c0.ColumnWidth = self.nummern_breite
        c0.Flexibility = 0
        cm.addColumn(c0)
        for k_, name in enumerate(spalten):
            c = cm.createColumn()
            c.Title = self._titel(name, self._kuerzel.get(name, "-"))
            c.ColumnWidth = breiten[name] + (self._letzte_extra if k_ == len(spalten) - 1 else 0)
            # Mac: keine Flexibilität (dort schrumpfte die letzte Spalte auf wenige Pixel); die Breite wird ausdrücklich
            # nachgeführt (_letzte_spalte_ausgleichen). Sonst füllt die letzte Spalte den Rest der Breite.
            c.Flexibility = 0 if (os.environ.get("OQ_FLEX0") or sys.platform == "darwin") else (1 if k_ == len(spalten) - 1 else 0)
            try:
                c.MinWidth = int(breiten[name])        # keine Spalte darf unter ihre Breite schrumpfen
            except Exception:
                pass
            if k_ == len(spalten) - 1:
                c.MaxWidth = 0
            if k_ != len(spalten) - 1:         # die letzte Spalte muss "resizeable" bleiben, sonst streckt Calc sie nicht
                try:
                    c.Resizeable = False       # kein Ziehen mit der Maus (seit 0.7.0); Breite über Menü oder Doppelklick auf den Trenner
                except Exception:
                    pass
            c.HorizontalAlign = uno.Enum("com.sun.star.style.HorizontalAlignment", "LEFT")      # Köpfe immer links
            cm.addColumn(c)
        return cm

    def _kontext_setzen(self):
        """Aktueller Abfragename und Auflöser für Verbinden/Anfügen (andere Abfragen dieser Datei)."""
        try:
            eigen = self.abfrage.name
            _EDITOR_KONTEXT["doc"], _EDITOR_KONTEXT["eigen"] = self.doc, eigen
            if self.doc is not None:
                setze_aufloeser(self.ctx, self.doc, eigen, self.abfrage, self._cache_basis)
        except Exception:
            traceback.print_exc()

    def cache_leeren(self):
        """Zwischenspeicher verwerfen: die nächste Anzeige liest Quellen und Basisabfragen neu."""
        self._cache_q.clear()
        self._cache_t.clear()
        self._cache_basis.clear()

    def _rechtsklick_zulassen(self):
        """Am Mac meldet ein Rechtsklick zwei Ereignisse (Taste 2 und Popup). Nur das erste öffnet ein Menü,
        und nie zwei Menüs übereinander."""
        jetzt = time.time()
        if self._menue_offen or jetzt - self._letzter_rechtsklick < 0.8:
            self._diag("Rechtsklick verworfen (Doppelereignis oder Menü offen)")
            return False
        self._letzter_rechtsklick = jetzt
        return True

    def _menue_ausfuehren(self, pm, r):
        """pm.execute mit Schutz gegen verschachtelte Menüs."""
        self._menue_offen = True
        try:
            wahl = pm.execute(self.d.peer(), r, 0)
            fx = _KLICK.get("fenster")
            if wahl and fx is not None:           # Dialoge nach einem Menübefehl erscheinen beim Menü, nicht beim früheren Klick
                _KLICK["pos"] = (fx[0] + int(r.X) + 20, fx[1] + KOPFZEILE_PX + int(r.Y) + 30)
            return wahl
        finally:
            self._menue_offen = False
            self._letzter_rechtsklick = time.time()

    def _nach_menue(self, name, fn):
        """Menübefehl erst ausführen, wenn das Menü ganz geschlossen ist (nicht mitten im Menü-Ereignis)."""
        self._diag("Menü gewählt: %s" % (name,))

        def lauf():
            self._diag("Befehl startet: %s" % (name,))
            try:
                fn()
                self._markierung_sichern()
                self._diag("Befehl fertig: %s" % (name,))
            except Exception:
                traceback.print_exc()
                self._diag("Befehl Fehler: %s" % (name,))
        self._spaeter(lauf)

    def _spaeter(self, fn):
        """fn nach dem laufenden Ereignis ausführen (vermeidet Neuaufbau mitten im Klick-Ereignis)."""
        try:
            svc = self.smgr.createInstance("com.sun.star.awt.AsyncCallback")
            cb = _Rueckruf(fn, self.d.rueckrufe)
            cb.dienst = svc                 # den Dienst bis zum Lauf des Rückrufs am Leben halten
            self.d.rueckrufe.append(cb)
            svc.addCallback(cb, None)
        except Exception:
            traceback.print_exc()
            fn()

    def _schritt_gewaehlt(self, ev=None):
        self.beschreibung_zeigen()
        self._spaeter(self.zeige)

    def _ansicht_merken(self):
        """Erste sichtbare Spalte des Rasters (0 = Nummernspalte), um die horizontale Ansicht zu halten."""
        try:
            return max(self.d.ctrl("grid").getColumnAtPoint(3, 8), 0)
        except Exception:
            return 0

    def _ansicht_wiederherstellen(self, erste_spalte, gleiche_spalten, n_spalten, n_zeilen):
        """Nach dem Neuaufbau vertikal an den Anfang; horizontal nur halten, wenn die Spalten gleich geblieben sind.
        Zweistufig (erst ganz nach rechts, dann zur Zielspalte), damit das Ergebnis unabhängig davon ist, ob goToCell
        die Zelle nur sichtbar macht (Linux) oder an den Rand setzt (Mac)."""
        if n_spalten < 1 or n_zeilen < 1:
            return
        try:
            g = self.d.ctrl("grid")
            if gleiche_spalten and 0 < erste_spalte < n_spalten:
                g.goToCell(n_spalten - 1, 0)
            g.goToCell(erste_spalte if gleiche_spalten and 0 < erste_spalte < n_spalten else 0, 0)
            g.deselectAllRows()
        except Exception:
            pass                                    # Raster noch nicht sichtbar: Ansicht bleibt wie sie ist

    def _neu_zeichnen(self):
        """Raster zum Neuzeichnen zwingen (Kopfzeile kurz aus-/einblenden, die Scrollposition bleibt)."""
        try:
            gm = self.d.ctrl("grid").getModel()
            gm.ShowColumnHeader = False
            gm.ShowColumnHeader = True
        except Exception:
            pass
        try:       # zusätzlich: erzwungenes Neuzeichnen (Größe um 1 Pixel anstoßen, Fenster als ungültig melden, kurz scrollen)
            g = self.d.ctrl("grid")
            gm_ = g.getModel()
            gm_.Enabled = False           # Aus-/Einschalten zeichnet das ganze Raster neu (auch leere Flächen unter den Zeilen)
            gm_.Enabled = True
            ps = g.getPosSize()
            g.setPosSize(0, 0, 0, ps.Height - 1, 8)
            g.setPosSize(0, 0, 0, ps.Height, 8)
            try:
                g.getPeer().invalidate(1 | 8)        # CHILDREN | UPDATE
            except Exception:
                pass
            n = g.getModel().GridDataModel.RowCount
            sp = len(self._grid_namen) + 1
            self._ansicht_wiederherstellen(self._erste_sp, True, sp, n)       # Größenänderung setzt die Spalte zurück
            if n > 1 and len(self._grid_namen):
                c = max(g.getColumnAtPoint(3, 8), 0)
                g.goToCell(c, min(n - 1, 30))
                g.goToCell(c, 0)
        except Exception:
            pass

    def qualitaet_zeigen(self):
        """Fehler- und Leer-Anzahl der angeklickten Spalte über der Tabelle."""
        self._kopfzeile()
        lbl = self.d.ctrl("lblQual").getModel()
        t = self.angezeigt
        if not self.sel_spalte or t is None or self.sel_spalte not in t.spalten:
            lbl.Label = ""
            return
        k = t.idx(self.sel_spalte)
        fehler, leer = E.spalten_qualitaet([z[k] for z in t.zeilen])
        lbl.Label = "Fehler: %d  ·  Leer: %d" % (fehler, leer)
        lbl.TextColor = (0xFF9A9A if fehler else 0xD6D2CB) if self._dunkel else (0xB00020 if fehler else 0x555555)

    def fuelle_grid(self, tab):
        """Tabelle anzeigen. Es gibt zwei Raster im Wechsel: das frisch befüllte wird an den Platz gesetzt, das alte
        geparkt. So wird immer vollständig neu gezeichnet (kein Altbestand unter kürzeren Tabellen)."""
        d = self.d
        spalten = tab.spalten[:MAX_SPALTEN_VORSCHAU]
        zeilen = tab.zeilen[:self.vorschau_limit]
        self._kuerzel = {}
        self._fehler = {}
        for k, name in enumerate(spalten):       # Fehler je Spalte (alle Zeilen), Anzeige als ⚠ n im Kopf
            n_fehler = E.spalten_qualitaet([z[k] for z in tab.zeilen])[0] if tab.zeilen else 0
            if n_fehler:
                self._fehler[name] = n_fehler
        breiten = {}
        for k, name in enumerate(spalten):
            art = typ_art([z[k] for z in zeilen[:2000]]) if zeilen else "leer"
            kuerzel = "-" if not zeilen else ("Mix" if art == "mix" else TYP_SYMBOLE[art])
            self._kuerzel[name] = kuerzel
            self._arten[name] = art
            if name in self.breiten:
                breiten[name] = self.breiten[name]
            else:
                breiten[name] = self.optimale_breite(name, k, zeilen[:200], kuerzel)
        self._letzte_extra = 0
        cm = self._spaltenmodell(spalten, breiten)
        self.nummern_breite = int(12 + 4.5 * len(str(max(len(zeilen), 1))))     # auch bei vielen Zeilen lesbar
        cm.getColumns()[0].ColumnWidth = self.nummern_breite
        daten = self.smgr.createInstance("com.sun.star.awt.grid.DefaultGridDataModel")
        if zeilen:
            kopf = tuple(str(i + 1) for i in range(len(zeilen)))
            spalten_texte = []
            for k, name in enumerate(spalten):
                texte = [E.als_text(z[k]) for z in zeilen]
                spalten_texte.append(texte)
            werte = tuple((str(i + 1),) + tuple(sp[i] for sp in spalten_texte) for i in range(len(zeilen)))
            daten.addRows(kopf, werte)
        erste = self._ansicht_merken()
        gleiche = list(spalten) == list(self._grid_namen)
        try:
            d.ctrl("grid").deselectAllRows()
        except Exception:
            pass
        neu = "gridB" if d.alias["grid"] == "gridA" else "gridA"
        gm = d.model.getByName(neu)
        gm.ColumnModel = cm
        gm.GridDataModel = daten
        d.alias["grid"] = neu                    # ab jetzt ist das frisch befüllte Raster "grid"
        self._scroll.pop(neu, None)
        gm.VScroll = gm.HScroll = False
        self._leer = False
        self._grid_platzieren()
        self._grid_namen = list(spalten)
        self._erste_sp = erste if gleiche and 0 < erste < len(spalten) + 1 else 0
        self._gitter_anwenden_nur(neu)
        self._scroll_anpassen()
        self._ansicht_wiederherstellen(erste, gleiche, len(spalten) + 1, len(zeilen))
        self.zeige_details()
        self._scroll_spaeter()

    def _gitter_anwenden_nur(self, name):
        """Linien/Bänderung für ein Raster setzen, ohne Neuzeichnen-Tricks (das Raster wurde gerade frisch gesetzt)."""
        try:
            gm = self.d.model.getByName(name)
            if self.gitter:
                gm.UseGridLines = True
                gm.GridLineColor = TRENNLINIE
                gm.RowBackgroundColors = (self._feld,)
            else:
                gm.UseGridLines = False
                gm.RowBackgroundColors = (self._feld, self._band_farbe())
        except Exception:
            traceback.print_exc()

    def leer_zeigen(self):
        """Abfrage ohne Quelle: statt eines leeren Rasters nur ein Hinweis."""
        self._leer = True
        self._grid_namen = []
        self._grid_platzieren()
        try:        # das geparkte Raster nicht mit Altdaten stehen lassen (Bedienungshilfen/Zeilenzugriff)
            gm = self.d.modell("grid")
            gm.GridDataModel = self.smgr.createInstance("com.sun.star.awt.grid.DefaultGridDataModel")
        except Exception:
            pass
        self.zeige_details()

    def titel_aktualisieren(self):
        """Spaltenköpfe (Markierung) neu beschriften. Titel direkt ändern und die Kopfzeile kurz aus-/einblenden:
        so wird neu gezeichnet, ohne dass das Raster zur ersten Spalte zurückspringt."""
        try:
            gm = self.d.ctrl("grid").getModel()
            spalten = list(gm.ColumnModel.getColumns())
            breiten = [c.ColumnWidth for c in spalten]          # Breiten festhalten: das Markierungszeichen ändert sie nicht
            for name, c in zip(self._grid_namen, spalten[1:]):
                c.Title = self._titel(name, self._kuerzel.get(name, "-"))
            for c, b in zip(spalten, breiten):
                c.ColumnWidth = b
            gm.ShowColumnHeader = False
            gm.ShowColumnHeader = True
        except Exception:
            traceback.print_exc()
        self.d.ctrl("lblMarkiert").getModel().Label = self.markierung_text()
        self._markiert_platzieren()
        self.qualitaet_zeigen()

    def vorschau_gewaehlt(self, ev=None):
        i = sel_pos(self.d.ctrl("lstVor"))
        if 0 <= i < len(VORSCHAU_STUFEN):
            self.vorschau_limit = VORSCHAU_STUFEN[i][1]
            self.zeige()

    # -- Rückgängig / Wiederholen --------------------------------------------------
    def _zustand(self):
        a = self.abfrage
        return json.dumps({"quelle": a.quelle, "schritte": a.schritte, "ziel": a.ziel, "auto": a.auto},
                          sort_keys=True, ensure_ascii=False)

    def merke(self):
        """Vor jeder Änderung den aktuellen Zustand für „Zurück“ festhalten."""
        z = self._zustand()
        if not self.verlauf or self.verlauf[-1] != z:
            self.verlauf.append(z)
            del self.verlauf[:-200]
        self.wiederholen_liste = []
        self.knoepfe_aktualisieren()
        self._autospeichern_planen()

    def _setze_zustand(self, text, auswahl=None):
        z = json.loads(text)
        quelle_alt = self.abfrage.quelle
        self.abfrage.quelle, self.abfrage.schritte = z["quelle"], z["schritte"]
        self.abfrage.ziel, self.abfrage.auto = z["ziel"], z["auto"]
        if self.abfrage.quelle != quelle_alt:
            self.quelle_laden()
        self.fehler_schritt = None
        self.liste_neu(auswahl)
        self.zeige()
        self.knoepfe_aktualisieren()
        self._autospeichern_planen()

    def rueckgaengig(self):
        if not self.verlauf:
            return
        self.wiederholen_liste.append(self._zustand())
        self._setze_zustand(self.verlauf.pop())

    def wiederholen(self):
        if not self.wiederholen_liste:
            return
        self.verlauf.append(self._zustand())
        self._setze_zustand(self.wiederholen_liste.pop())

    def knoepfe_aktualisieren(self):
        try:
            self.d.ctrl("btnUndo").getModel().Enabled = True          # immer gleich aussehen (nichts zu tun = keine Wirkung)
            self.d.ctrl("btnRedo").getModel().Enabled = True
        except Exception:
            pass

    # -- Quelle ------------------------------------------------------------
    def quelle_laden(self, neu=False):
        """Quelle lesen. Ohne neu=True kommt sie aus dem Zwischenspeicher, wenn sie in diesem Editor schon gelesen wurde."""
        try:
            try:
                schluessel = json.dumps(self.abfrage.quelle, sort_keys=True, default=str)
            except Exception:
                schluessel = None
            if not neu and schluessel is not None and schluessel in self._cache_q:
                self.roh = self._cache_q[schluessel]
                return True
            self.roh = lies_quelle(self.ctx, self.doc, self.abfrage.quelle)
            if schluessel is not None:
                self._cache_q[schluessel] = self.roh
            return True
        except E.FormelFehler as e:
            self.roh = None
            self.meld(str(e))
        except Exception as e:
            self.roh = None
            traceback.print_exc()
            self.meld("Die Quelle konnte nicht gelesen werden: %s" % e)
        return False

    def quelle_waehlen(self):
        ausgabe = {}
        for e in self.arbeit:
            try:
                if zielblatt_name(e["a"]):
                    ausgabe[zielblatt_name(e["a"])] = e["a"].name
            except Exception:
                pass
        try:
            eigen = zielblatt_name(self.abfrage)
        except Exception:
            eigen = None
        q = QuellenDialog(self.ctx, self.doc, self.abfrage.quelle, self.d.peer(), ausgabe, eigen, self.abfrage.name).zeigen()
        if q:
            self.merke()
            self.abfrage.quelle = q
            if q.get("art") == "blatt" and not self.abfrage.schritte:      # Tabelle: Überschriften und Typen übernehmen
                self.abfrage.schritte = [dict(s_) for s_ in NEUE_TABELLE_SCHRITTE]
            if self.quelle_laden():
                self._typ_hinweis()
            self.liste_neu()
            self.zeige()

    def _typ_hinweis(self):
        """Nach dem Laden einer Quelle: Spalten, die nur Text enthalten, anbieten zur Typerkennung."""
        try:
            if any(st.get("op") in ("typen_erkennen", "typ_aendern") for st in self.abfrage.schritte):
                return
            t = self.roh
            n = 0
            if t is not None and t.zeilen:
                for k in range(len(t.spalten)):
                    if all(isinstance(z[k], str) or z[k] is None for z in t.zeilen[:500]) and \
                            any(isinstance(z[k], str) and z[k].strip() for z in t.zeilen[:500]):
                        n += 1
            if n and self.meld("%d Spalte%s ohne Datentyp (alles Text).\n\nDatentypen automatisch erkennen "
                               "(Zahlen, Datum …)?" % (n, "n" if n != 1 else ""), "QUERYBOX", 3) == 2:
                self.abfrage.schritte.append({"op": "typen_erkennen", "spalten": [], "ort": "de"})
        except Exception:
            traceback.print_exc()

    def ziel_waehlen(self):
        """Ausgabe der geöffneten Abfrage wählen. Gibt True zurück, wenn gewählt wurde."""
        res = ZielDialog(self.ctx, self.doc, self.abfrage, self.d.peer()).zeigen()
        if res:
            self.merke()
            self.abfrage.ziel, self.abfrage.auto = res
            self.abfragen_liste_neu()
            self.zeige()
            return True
        return False

    def laden_in(self):
        """„Schließen und Laden in …“: erst die Ausgabe wählen (wie in Power Query), dann laden."""
        if self.roh is None:
            self.meld("Bitte zuerst eine Quelle wählen.")
            return
        if self.ziel_waehlen():
            self._spaeter(self.laden)

    # -- Schritte ------------------------------------------------------------
    def tabelle_vor_einfuegen(self):
        bis = self.gewaehlter_schritt()
        try:
            return bis, self.tabelle_bis(bis)
        except E.StepError as e:
            return e.index, self.tabelle_bis(e.index)

    def neuer_schritt(self, op, vorbelegt=None, direkt=False, modus="nach"):
        """Neuen Schritt einfügen: modus 'nach' = hinter dem gewählten Schritt, 'vor' = davor."""
        if self.roh is None:
            self.meld("Bitte zuerst eine Quelle wählen.")
            return
        merke_operation(op)
        self._kontext_setzen()
        pos, tab = self.tabelle_vor_einfuegen()
        if modus == "vor":
            i = self.lstS.pos()
            if i >= 1:
                pos = i - 1
                try:
                    tab = self.tabelle_bis(pos)
                except E.StepError as e:
                    self.meld(str(e))
                    return
        if not E.OPS[op]["felder"]:
            direkt = True                       # nichts einzugeben: sofort ausführen, ohne OK-Dialog
        if direkt:
            s = dict(vorbelegt or {}, op=op)
            try:
                E.wende_schritt(tab, s)
            except E.StepError as e:
                self.meld(e.meldung)
                return
        else:
            s = SchrittDialog(self.ctx, op, tab, None, vorbelegt, self.d.peer()).zeigen()
            if not s:
                return
        if not self._spaltenwarnung(tab, s):
            return
        self.merke()
        self.abfrage.schritte.insert(pos, s)
        self._umbenennung_weitergeben(pos, None, s, tab)
        self.fehler_schritt = None
        self.liste_neu(pos + 1)
        self.zeige()

    SPALTEN_WARNUNG = 50

    def _spaltenwarnung(self, tab, s):
        """Erzeugt ein Schritt sehr viele Spalten (z. B. Transponieren vieler Zeilen), vorher warnen. True = weitermachen."""
        try:
            if s.get("op") not in ("transponieren", "pivotieren"):
                return True
            nach = E.wende_schritt(tab, s)
            n = len(nach.spalten)
            if n <= self.SPALTEN_WARNUNG:
                return True
            return self.meld("Dieser Schritt erzeugt %d Spalten.\n\nDas ist sehr viel: Die Vorschau zeigt nur die ersten 150, "
                             "Calc schreibt aber alle ins Tabellenblatt (und ist dabei langsam; ab %d Spalten gibt es "
                             "Grenzen).\n\nTrotzdem übernehmen?" % (n, 16384), "QUERYBOX", 3) == 2
        except E.StepError:
            return True              # den Fehler meldet der normale Ablauf
        except Exception:
            traceback.print_exc()
            return True

    def _umbenennung_weitergeben(self, k, alt, neu, tab_vor):
        """Schritt k ist ein neuer/geänderter Umbenennen-Schritt: die neuen Namen in den Folgeschritten übernehmen."""
        try:
            if k + 1 >= len(self.abfrage.schritte):
                return
            if neu.get("op") in E.SPALTEN_NAMEN_OPS:           # neue Spaltennamen nach Position (Überschriften hoch-/herabstufen)
                nach = E.wende_schritt(tab_vor, neu)
                if alt is not None or len(nach.spalten) != len(tab_vor.spalten):
                    return
                self._zweiphasig(k + 1, [(a, n) for a, n in zip(tab_vor.spalten, nach.spalten) if a != n])
                return
            if neu.get("op") not in ("spalte_umbenennen", "spalten_umbenennen"):
                return
            nach = E.wende_schritt(tab_vor, neu)
            if alt is None:                                   # neu eingefügt: alter Name -> neuer Name
                paare = E.umbenennungen_von(neu)
            else:                                             # geändert: bisheriger neuer Name -> geänderter neuer Name
                bisher = dict(E.umbenennungen_von(alt))
                paare = [(bisher[q], n) for q, n in E.umbenennungen_von(neu) if q in bisher and bisher[q] != n]
            for a, n in paare:
                E.folge_schritte_anpassen(self.abfrage.schritte, k + 1, a, n, nach)
        except Exception:
            traceback.print_exc()

    def _zweiphasig(self, start, paare):
        """Mehrere Umbenennungen gleichzeitig in schritte[start:] (über Platzhalter, damit sich Namen nicht überschreiben)."""
        for i, (a, _) in enumerate(paare):
            E.folge_schritte_anpassen(self.abfrage.schritte, start, a, "\x01%d" % i)
        for i, (_, n) in enumerate(paare):
            E.folge_schritte_anpassen(self.abfrage.schritte, start, "\x01%d" % i, n)

    def _namen_umstellen(self, k, st, start, rueckwaerts):
        """Schritt st (Position k) ändert Spaltennamen (Umbenennen/Überschriften). Die Folgeschritte ab `start` werden
        auf die neuen Namen umgestellt, bzw. mit rueckwaerts=True auf die alten zurück (Schritt gelöscht/pausiert)."""
        try:
            op = st.get("op")
            if op not in E.SPALTEN_NAMEN_OPS and op not in ("spalte_umbenennen", "spalten_umbenennen"):
                return
            tab = self.tabelle_bis(k)
            nach = E.wende_schritt(tab, st)
            if op in E.SPALTEN_NAMEN_OPS:
                if len(nach.spalten) != len(tab.spalten):
                    return
                paare = [(a, n) for a, n in zip(tab.spalten, nach.spalten) if a != n]
                if rueckwaerts:
                    paare = [(n, a) for a, n in paare]
                self._zweiphasig(start, paare)
                return
            paare = [(a, n) for a, n in E.umbenennungen_von(st) if a != n]
            if rueckwaerts:
                paare = [(n, a) for a, n in paare]
            for a, n in paare:
                E.folge_schritte_anpassen(self.abfrage.schritte, start, a, n, tab if rueckwaerts else nach)
        except Exception:
            traceback.print_exc()

    def aendern(self):
        i = self.lstS.pos()
        if i < 1:
            if i == 0:
                self.quelle_waehlen()
            return
        k = i - 1
        s = self.abfrage.schritte[k]
        try:
            tab = self.tabelle_bis(k)
        except E.StepError as e:
            self.meld(str(e))
            return
        self._kontext_setzen()
        neu = SchrittDialog(self.ctx, s["op"], tab, s, None, self.d.peer()).zeigen()
        if neu and not self._spaltenwarnung(tab, neu):
            return
        if neu:
            self.merke()
            if s.get("nur_wenn") and "nur_wenn" not in neu:
                neu["nur_wenn"] = s["nur_wenn"]            # die Bedingung bleibt beim Ändern erhalten
            self.abfrage.schritte[k] = neu
            self._umbenennung_weitergeben(k, s, neu, tab)
            self.liste_neu(i)
            self.zeige()

    def loeschen(self):
        i = self.lstS.pos()
        if i < 1:
            return
        self.merke()
        st = self.abfrage.schritte[i - 1]
        del self.abfrage.schritte[i - 1]
        if st.get("aktiv") is not False:
            self._namen_umstellen(i - 1, st, i - 1, True)      # Folgeschritte bekommen die alten Spaltennamen zurück
        self.fehler_schritt = None
        self.liste_neu(i - 1)
        self.zeige()

    def verschiebe(self, richtung):
        i = self.lstS.pos()
        k = i - 1
        j = k + richtung
        n = len(self.abfrage.schritte)
        if k < 0 or j < 0 or j >= n:
            return
        self.merke()
        s = self.abfrage.schritte
        try:                      # Umbenennen-Schritt über/unter einem Nachbarn: dessen Spaltenbezüge mit umstellen
            for wand, nachbar in ((s[k], s[j]),):
                if wand.get("aktiv") is False or nachbar.get("aktiv") is False:
                    continue
                if wand.get("op") in ("spalte_umbenennen", "spalten_umbenennen"):
                    paare = [(a, n) for a, n in E.umbenennungen_von(wand) if a != n]
                elif wand.get("op") in E.SPALTEN_NAMEN_OPS:
                    vor = self.tabelle_bis(min(k, j))
                    nach_ = E.wende_schritt(vor, wand)
                    paare = [(a, n) for a, n in zip(vor.spalten, nach_.spalten) if a != n] \
                        if len(nach_.spalten) == len(vor.spalten) else []
                else:
                    continue
                for a, n in paare:
                    if richtung < 0:        # Umbenennung rückt nach oben: der Nachbar sieht jetzt den NEUEN Namen
                        E.ersetze_spaltenname_im_schritt(nachbar, a, n)
                    else:                   # rückt nach unten: der Nachbar sieht wieder den ALTEN Namen
                        E.ersetze_spaltenname_im_schritt(nachbar, n, a)
        except Exception:
            traceback.print_exc()
        s[k], s[j] = s[j], s[k]
        self.fehler_schritt = None
        self.liste_neu(j + 1)
        self.zeige()

    def ein_aus(self):
        """Gewählten Schritt aus- oder einschalten, ohne ihn zu löschen."""
        i = self.lstS.pos()
        if i < 1:
            return
        self.merke()
        s = self.abfrage.schritte[i - 1]
        if s.get("aktiv") is False:
            s.pop("aktiv", None)
            self._namen_umstellen(i - 1, s, i, False)          # eingeschaltet: Folgeschritte auf die neuen Namen
        else:
            s["aktiv"] = False
            s2 = dict(s)
            s2.pop("aktiv", None)
            self._namen_umstellen(i - 1, s2, i, True)          # pausiert: Folgeschritte auf die alten Namen zurück
        self.fehler_schritt = None
        self.liste_neu(i)
        self.zeige()

    def bedingung(self):
        """Schritt nur ausführen, wenn ein Parameter eine Bedingung erfüllt."""
        i = self.lstS.pos()
        if i < 1:
            return
        s = self.abfrage.schritte[i - 1]
        res = bedingung_bearbeiten(self.ctx, self.doc, self.d.peer(), s.get("nur_wenn"))
        if res is None:
            return
        self.merke()
        if res:
            s["nur_wenn"] = res
        else:
            s.pop("nur_wenn", None)
        self.fehler_schritt = None
        self.liste_neu(i)
        self.zeige()

    def dupliziere(self):
        """Gewählten Schritt kopieren; die Kopie steht direkt dahinter."""
        i = self.lstS.pos()
        if i < 1:
            return
        self.merke()
        self.abfrage.schritte.insert(i, json.loads(json.dumps(self.abfrage.schritte[i - 1])))
        self.fehler_schritt = None
        self.liste_neu(i + 1)
        self.zeige()

    # -- Menüs ---------------------------------------------------------------
    SCHRITT_BEFEHLE = [("▲ Schritt nach oben", "hoch"), ("▼ Schritt nach unten", "runter"), ("Ändern …", "aendern"),     # wie die Knöpfe
                       ("Schritt umbenennen …", "umbenennen"), ("Schritt löschen", "loeschen"), ("Schritt Ein/Aus", "ein_aus"),
                       ("Schritt duplizieren", "dupliziere"), ("Bis zum Ende löschen", "bis_ende"), ("Bedingung …", "bedingung")]

    def baue_schritt_menue(self):
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        ids = {}
        n = 1
        for modus, text in (("vor", "Schritt einfügen vor …"), ("nach", "Schritt einfügen nach …")):
            pm.insertItem(n, text, 0, -1)          # ganz oben; öffnet dasselbe Menü wie der Button „Schritt hinzufügen“
            ids[n] = ("menue", modus)
            n += 1
        pm.insertSeparator(-1)
        for text, name in self.SCHRITT_BEFEHLE:
            pm.insertItem(n, text, 0, -1)
            ids[n] = name
            n += 1
        return pm, ids

    def schritt_befehl(self, name):
        if isinstance(name, tuple) and len(name) == 3:            # ("einfuegen", modus, op): direkt einfügen
            _, modus, op = name
            self.neuer_schritt(op, None, False, modus)
            return
        if isinstance(name, tuple):
            _, modus = name
            x, y = getattr(self, "_menue_pos", (0, 0))
            self._spaeter(lambda: self.zeige_menue(x, y, self.sel_spalte, modus))     # zweites Menü erst nach dem ersten
            return
        {"hoch": lambda: self.verschiebe(-1), "runter": lambda: self.verschiebe(1), "aendern": self.aendern,
         "dupliziere": self.dupliziere, "ein_aus": self.ein_aus, "loeschen": self.loeschen,
         "umbenennen": self.umbenennen, "bis_ende": self.loeschen_bis_ende, "bedingung": self.bedingung}[name]()

    def umbenennen(self):
        i = self.lstS.pos()
        if i < 1:
            return
        st = self.abfrage.schritte[i - 1]
        neu = frage_text(self.ctx, "Schritt umbenennen",
                         "Name des Schritts (leer = automatische Beschreibung):",
                         st.get("name") or E.beschreibe(st), self.d.peer())
        if neu is None:
            return
        self.merke()
        if neu.strip():
            st["name"] = neu.strip()
        else:
            st.pop("name", None)
        self.liste_neu(i)

    def loeschen_bis_ende(self):
        i = self.lstS.pos()
        if i < 1:
            return
        anzahl = len(self.abfrage.schritte) - (i - 1)
        self._diag("Bis zum Ende löschen: Frage")
        if meldung(self.ctx, self.d.peer(), "Schritt %d und alle folgenden löschen (%d Schritte)?" % (i + 1, anzahl),
                   "QUERYBOX", 3) != 2:
            self._diag("Bis zum Ende löschen: abgebrochen")
            return
        self._diag("Bis zum Ende löschen: bestätigt")

        def ausfuehren():
            """Erst nach dem Ende des Bestätigungsdialogs (der Neuaufbau mitten darin beendete Calc am Mac)."""
            self.merke()
            del self.abfrage.schritte[i - 1:]
            self.fehler_schritt = None
            self._diag("Bis zum Ende löschen: Liste neu")
            self.liste_neu(i - 1)
            self._diag("Bis zum Ende löschen: Anzeige")
            self.zeige()
            self._diag("Bis zum Ende löschen: fertig")
        self._spaeter(ausfuehren)

    def zeige_schritt_menue(self, x, y):
        if self.lstS.pos() < 1:
            return          # Quelle (Eintrag 1) hat keine Schrittbefehle
        pm, ids = self.baue_schritt_menue()
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
        self._pm = pm
        self._menue_pos = (x, y)
        wahl = self._menue_ausfuehren(pm, r)
        if wahl in ids:
            self._nach_menue("Schritt:%s" % (ids[wahl],), lambda w=ids[wahl]: self.schritt_befehl(w))

    def schritt_maus(self, ev):
        """Schrittliste (beim Loslassen): nur Linksklicks. Einfachklick wählt aus, Doppelklick öffnet das Menü
        (auf der Quelle: den Quellendialog). Ist der Rechtsklick eingeschaltet, öffnet er das Menü und der Doppelklick die
        Bearbeitung. Alles erst nach dem Mausereignis."""
        self._diag("Schrittliste Maus", ev)
        geste = menue_geste(ev)
        if not geste:
            return
        z = self.lstS.zeile_bei(ev.X, ev.Y)
        if not 0 <= z < len(self.lstS.items):
            return
        if not self._rechtsklick_zulassen():
            return
        ps = self.d.ctrl("lstSchritte").getPosSize()
        x, y = ps.X + ev.X, ps.Y + ev.Y
        auf_nr = geste == "doppel" and ev.X < NR_BREITE_PX             # Doppelklick auf die Schrittnummer: Bearbeitungsdialog

        def menue():
            try:
                if z != self.lstS.pos():
                    self.lstS.waehle(z)
                    self.beschreibung_zeigen()
                    self.zeige()
                if z == 0 or auf_nr or (geste == "doppel" and rechtsklick_aktiv()):
                    self._spaeter(self.aendern)          # Rechtsklick ein: Rechtsklick = Menü, Doppelklick = Bearbeiten
                else:
                    self._spaeter(lambda: self.zeige_schritt_menue(x, y))
            except Exception:
                traceback.print_exc()
        self._spaeter(menue)

    def baue_menue(self, spalte=None):
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        ids = {}
        n = 1
        pm.insertItem(700, "🔍 Schritt suchen …", 0, -1)
        ids[700] = ("__suche", spalte, False)
        pm.insertSeparator(-1)
        if spalte:
            schnell = [("Aufsteigend sortieren", "sortieren", {"spalte1": spalte, "richtung1": "auf"}, True),
                       ("Absteigend sortieren", "sortieren", {"spalte1": spalte, "richtung1": "ab"}, True),
                       ("Nach Einzelwerten filtern …", "filtern_werte", {"spalte": spalte}, False),
                       ("Textfilter / Zahlenfilter …", "filtern", {"spalte": spalte}, False),
                       ("Spalte entfernen", "spalten_entfernen", {"spalten": [spalte]}, True),
                       ("Spalte umbenennen …", "spalte_umbenennen", {"spalte": spalte}, False),
                       ("Datentyp ändern …", "typ_aendern", {"spalten": [spalte]}, False),
                       ("Werte ersetzen …", "ersetzen", {"spalten": [spalte]}, False),
                       ("Text extrahieren …", "text_extrahieren", {"spalte": spalte}, False),
                       ("Spalte teilen …", "spalte_teilen", {"spalte": spalte}, False)]
            for text, op, vor, direkt in schnell:
                pm.insertItem(n, text, 0, -1)
                ids[n] = (op, vor, direkt)
                n += 1
            sub_f = self.smgr.createInstance("com.sun.star.awt.PopupMenu")    # wie in Power Query: Ausfüllen ▸ Unten/Oben
            for text, op in (("Nach unten", "fuellen_unten"), ("Nach oben", "fuellen_oben")):
                sub_f.insertItem(n, text, 0, -1)
                ids[n] = (op, {"spalten": [spalte]}, True)
                n += 1
            pm.insertItem(900, "Ausfüllen", 0, -1)
            pm.setPopupMenu(900, sub_f)
            pm.insertSeparator(-1)
            pm.insertItem(n, "Spaltenbreite optimieren", 0, -1)
            ids[n] = ("__breite_opt", spalte, False)
            n += 1
            pm.insertItem(n, "Spaltenbreite …", 0, -1)
            ids[n] = ("__breite", spalte, False)
            n += 1
            pm.insertItem(n, "Alle Spalten optimal breit", 0, -1)
            ids[n] = ("__alle_breit", spalte, False)
            n += 1
            pm.insertItem(n, "Einheitliche Breite für alle Spalten …", 0, -1)
            ids[n] = ("__einheit", spalte, False)
            n += 1
            pm.insertSeparator(-1)
        for gruppe in E.GRUPPEN:
            ops = E.ops_der_gruppe(gruppe)
            if not ops:
                continue
            sub = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
            for op, dd in ops:
                sub.insertItem(n, dd["titel"], 0, -1)
                vor = {}
                if spalte:
                    for f in dd["felder"]:
                        if f["art"] == "spalte" and f["name"] in ("spalte", "spalte1"):
                            vor[f["name"]] = spalte
                            break
                        if f["art"] == "spalten":
                            vor[f["name"]] = [spalte]
                            break
                ids[n] = (op, vor, False)
                n += 1
            gid = 1000 + E.GRUPPEN.index(gruppe)
            pm.insertItem(gid, gruppe, 0, -1)
            pm.setPopupMenu(gid, sub)
        return pm, ids

    def zeige_menue(self, x, y, spalte=None, modus="nach", kopie=None):
        pm, ids = self.baue_menue(spalte)
        if kopie is not None:                      # Rechtsklick auf eine Zelle: Kopierbefehle ganz oben
            z, nm = kopie
            pos = 0
            for i, (text, art) in enumerate((("Zelle kopieren", "zelle"), ("Zeile kopieren", "zeile"),
                                              ("Spalte kopieren", "spalte"))):
                if art != "zeile" and not nm:
                    continue
                pm.insertItem(800 + i, text, 0, pos)
                ids[800 + i] = ("__kopie", (art, z, nm), False)
                pos += 1
            pm.insertSeparator(pos)
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
        self._pm = pm   # (Testzugriff: erlaubt endExecute von außen)
        wahl = self._menue_ausfuehren(pm, r)
        if wahl in ids:
            op, vor, direkt = ids[wahl]
            if op == "__suche":
                self._nach_menue("Schritt suchen", lambda: self.suche_schritt(vor, modus))
            elif op == "__kopie":
                art, z, nm = vor
                self.kopiere(art, z, nm)
            elif op == "__breite_opt":
                self._nach_menue("Spalte:Breite optimieren", lambda: self.breite_optimieren(vor))
            elif op == "__breite":
                self._nach_menue("Spalte:Breite", lambda: self.spaltenbreite_eingeben(vor))
            elif op == "__einheit":
                self._nach_menue("Spalte:einheitliche Breite", self.einheitliche_breite)
            elif op == "__alle_breit":
                self._nach_menue("Spalte:alle Breiten", self.alle_breiten_optimieren)
            else:
                self._nach_menue("Spalte:%s" % op, lambda: self.neuer_schritt(op, vor, direkt, modus))

    # -- Leiste (Reiter + Symbolknöpfe) -------------------------------------------------
    _tab_alt = -1

    def leiste_platzieren(self):
        """Hellgrauer Kopf, Reiter und die Symbole des aktiven Reiters setzen; alles andere parken."""
        d = self.d
        xe = getattr(self, "_leiste_xs", 640)                  # rechte Kante des Bands
        xu = getattr(self, "_leiste_undo_x", None)             # Schrittspalte sichtbar: Rückgängig/Wiederholen darüber
        aktiv = _LETZTER_TAB[0] if 0 <= _LETZTER_TAB[0] < len(LEISTE) else 0
        x = 5
        for k, (tname, eintraege) in enumerate(LEISTE):
            w = 14 + int(len(tname) * 4.4)
            d.platziere("tab%d" % k, x, 2, w, 11)
            d.modell("tab%d" % k).FontWeight = 150.0 if k == aktiv else 100.0
            if k == aktiv:
                d.platziere("tabLinie", x + 2, 13, w - 4, 2)
                d.platziere("tabBasisL", 0, 14, x + 2, 1)
                d.platziere("tabBasisR", x + w - 2, 14, max(1, xe + 5 - (x + w - 2)), 1)
            x += w
        BW, LUECKE = 48, 4
        geaendert = set()
        geparkt = self.__dict__.setdefault("_leiste_geparkt", set())

        def setze(e_, x_):
            if x_ is None:
                if e_[0] in geparkt:
                    return                       # liegt schon außerhalb: nichts zu tun (spart viele Aufrufe)
                d.platziere("tbi_" + e_[0], -3000, 19, ICON_B, ICON_H)
                d.platziere("tbt_" + e_[0], -3000, 47, BW, 24)
                geparkt.add(e_[0])
            else:
                geparkt.discard(e_[0])
                if d.platziere("tbi_" + e_[0], x_ + (BW - ICON_B) // 2, 19, ICON_B, ICON_H):
                    geaendert.add("tbi_" + e_[0])
                if d.platziere("tbt_" + e_[0], x_, 47, BW, 24):
                    geaendert.add("tbt_" + e_[0])
        if xu is not None:
            xf = xu
            grenze = xu - 6
        else:
            xf = xe - len(FEST) * (BW)
            grenze = xf - 6
        for e_ in FEST:
            setze(e_, xf)
            xf += BW
        eintr = start_eintraege() if aktiv == 0 else LEISTE[aktiv][1]
        aktive_ids = {e_[0] for e_ in eintr if e_ is not None}
        for kid_, e_ in ALLE_EINTRAEGE.items():          # alles, was nicht zum aktiven Reiter gehört, parken
            if kid_ not in aktive_ids:
                setze(e_, None)
        platz = grenze - 5

        def breite(liste):
            return sum(LUECKE if e_ is None else BW for e_ in liste)
        ueber = []
        if breite(eintr) > platz:
            platz -= BW
            x_ = 0
            n_ = 0
            for e_ in eintr:
                w_ = LUECKE if e_ is None else BW
                if x_ + w_ > platz:
                    break
                x_ += w_
                n_ += 1
            ueber = [e_ for e_ in eintr[n_:] if e_ is not None]
            eintr_sichtbar = eintr[:n_]
        else:
            eintr_sichtbar = eintr
        x = 5
        for e_ in eintr_sichtbar:
            if e_ is None:
                x += LUECKE
                continue
            setze(e_, x)
            x += BW
        for e_ in ueber:
            setze(e_, None)
        self._ueberlauf = ueber
        setze(MEHR, x if ueber else None)
        # nur was sich bewegt hat, neu zeichnen (sonst bleiben Symbole je nach Zeitpunkt unsichtbar)
        for n_ in geaendert:
            d.auffrischen(n_)
        for k in range(len(LEISTE)):
            if k == aktiv or self._tab_alt != aktiv:
                d.auffrischen("tab%d" % k)
        self._tab_alt = aktiv
        d.auffrischen("tabLinie")
        d.auffrischen("tabBasisL")
        d.auffrischen("tabBasisR")

    def leiste_mehr(self):
        """Befehle, die nicht mehr in die Leiste passen, als Menü."""
        ueber = getattr(self, "_ueberlauf", [])
        if not ueber:
            return
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        for i, e_ in enumerate(ueber, 1):
            pm.insertItem(i, e_[1].replace("\n", " "), 0, -1)
        b = self.d.ctrl("tbt_" + MEHR[0]).getPosSize()
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(b.X), int(b.Y + b.Height), 0, 0
        self._pm = pm
        wahl = self._menue_ausfuehren(pm, r)
        if 1 <= wahl <= len(ueber):
            e_ = ueber[wahl - 1]
            pos = (int(b.X), int(b.Y + b.Height))
            self._spaeter(lambda: self.leiste_klick(e_, pos))

    def updates_suchen(self):
        update_pruefen(self.ctx, self.d.peer(), still=False)

    def start_anpassen(self):
        aktuell = lies_einstellung("start_leiste", None)
        if not isinstance(aktuell, list) or not aktuell:
            aktuell = START_STANDARD
        neu = start_anpassen_dialog(self.ctx, self.d.peer(), aktuell)
        if neu is None:
            return
        schreibe_einstellung("start_leiste", neu, fragen=True)
        self.leiste_platzieren()

    def knopfart_umschalten(self):
        neu = not self.symbole_an()
        schreibe_einstellung("knoepfe_symbole", neu, fragen=True)
        self.knopfart_anwenden()

    _KNOPF_SYMBOL = {"btnNeueAbfrage": "abfrage_neu", "btnNeuerParam": "parameter", "btnOeffnen": "oeffnen",
                     "btnSpeichern": "exportieren", "btnAbfAktual": "aktualisieren", "btnAbfLoeschen": "loeschen",
                     "btnAbfUmben": "umbenennen", "btnAbfDupl": "duplizieren", "btnAbfVerweis": "verweis",
                     "btnAbfEigen": "eigenschaften", "btnAbfHoch": "hoch", "btnAbfRunter": "runter",
                     "btnHoch": "hoch", "btnRunter": "runter", "btnAendern": "aendern", "btnUmben": "umbenennen",
                     "btnLoeschen": "loeschen", "btnAktiv": "ein_aus", "btnDupl": "duplizieren",
                     "btnBisEnde": "bis_ende", "btnZiel": "ausgabe", "btnHinzu": "schritt_hinzu"}

    def knopfart_anwenden(self):
        """Knöpfe unter den Listen als Symbole (Beschriftung als Hilfetext) oder als Text zeigen."""
        sym = self.symbole_an()
        orig = self.__dict__.setdefault("_knopf_orig", {})
        for n, icon in self._KNOPF_SYMBOL.items():
            try:
                m = self.d.modell(n)
                if n not in orig:
                    orig[n] = (m.Label, m.HelpText or "")
                label, tipp = orig[n]
                url = (symbol_url(icon + "_g") or symbol_url(icon + "_k")) if sym else ""
                if sym and url:
                    m.Label = ""
                    m.ImageURL = url
                    m.ImagePosition = 12
                    m.HelpText = tipp or label
                else:
                    m.ImageURL = ""
                    m.Label = label
                    m.HelpText = tipp
            except Exception:
                traceback.print_exc()
        self.layout(self.d.model.Width, self.d.model.Height)

    def symbole_an(self):
        return bool(lies_einstellung("knoepfe_symbole", False))

    def absturzprotokoll_umschalten(self):
        if _ABSTURZ_AN[0]:
            _ABSTURZ_AN[0] = False
            meldung(self.ctx, self.d.peer(), "Das Absturzprotokoll ist ausgeschaltet. Die Datei bleibt liegen:\n%s\n"
                    "Du kannst sie löschen, wenn du sie nicht mehr brauchst." % _ABSTURZLOG)
            return
        if meldung(self.ctx, self.d.peer(),
                   "Das Absturzprotokoll schreibt bei jedem Klick eine Zeile in die Datei:\n%s\n\n"
                   "Es hilft bei der Suche nach Abstürzen. Soll die Datei angelegt werden?" % _ABSTURZLOG,
                   "QUERYBOX", 3) == 2:
            _ABSTURZ_AN[0] = True

    def rechtsklick_umschalten(self):
        neu = not rechtsklick_aktiv()
        schreibe_einstellung("rechtsklick", neu, fragen=True)
        meldung(self.ctx, self.d.peer(), "Rechtsklick öffnet die Menüs jetzt %s. Der Doppelklick funktioniert in beiden Fällen." %
                ("(an)" if neu else "nicht (aus)"))

    def _update_still(self):
        if update_automatisch_faellig():
            update_pruefen(self.ctx, self.d.peer(), still=True)

    def leiste_reiter(self, k):
        _LETZTER_TAB[0] = k
        self.leiste_platzieren()

    def leiste_klick(self, e, pos=None):
        kid, label, symbol, aktion, tipp = e
        art, ziel = aktion
        if art == "fn":
            return getattr(self, ziel)()
        if art == "tgl":
            m = self.d.ctrl(ziel).getModel()
            m.State = 0 if m.State else 1                 # setState/Modell löst den Listener nicht aus → Handler selbst rufen
            h = {"chkGitter": self._gitter_geaendert, "chkDetails": self._details_geaendert,
                 "chkAbfr": self._listen_sichtbar_geaendert, "chkSchr": self._listen_sichtbar_geaendert,
                 "chkAuto": self._auto_geaendert}.get(ziel)
            if h:
                h()
            return
        if art == "abf":
            return self._nach_menue("Abfrage:%s" % ziel, lambda: self.abfrage_befehl(ziel))
        if pos is None:
            b = self.d.ctrl("tbt_" + kid).getPosSize()
            pos = (int(b.X), int(b.Y + b.Height))
        if art == "sch":
            self._menue_pos = pos
            if ziel == "hinzu":
                return self.zeige_menue(pos[0], pos[1], self.sel_spalte)
            if ziel in ("einvor", "einnach"):
                return self.schritt_befehl(("menue", "vor" if ziel == "einvor" else "nach"))
            return self._nach_menue("Schritt:%s" % ziel, lambda: self.schritt_befehl(ziel))
        if art == "op":
            return self._nach_menue("Leiste:%s" % ziel, lambda: self.leiste_schritt(ziel))
        if art == "menu":
            pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
            ids = {}
            for i, (text, op) in enumerate(ziel, 1):
                if text is None:
                    pm.insertSeparator(-1)
                    continue
                pm.insertItem(i, text, 0, -1)
                ids[i] = op
            r = Rectangle()
            r.X, r.Y, r.Width, r.Height = pos[0], pos[1], 0, 0
            self._pm = pm
            wahl = self._menue_ausfuehren(pm, r)
            if wahl in ids:
                op = ids[wahl]
                if isinstance(op, tuple):                       # Befehl der Abfrage-/Schrittliste (Art, Ziel)
                    self._nach_menue("Leiste:%s" % (op,), lambda: self.leiste_klick(
                        ("m_" + str(op[1]), text_von(op), "", op, ""), pos))
                else:
                    self._nach_menue("Leiste:%s" % op, lambda: self.leiste_schritt(op))

    def leiste_schritt(self, op):
        spalte = self.sel_spalte
        vor = self._vorbelegung(op, spalte)
        return self.neuer_schritt(op, vor, False, "nach")

    def _vorbelegung(self, op, spalte):
        vor = {}
        if spalte and op in E.OPS:
            for f in E.OPS[op]["felder"]:
                if f["art"] == "spalte" and f["name"] in ("spalte", "spalte1"):
                    vor[f["name"]] = spalte
                    break
                if f["art"] == "spalten":
                    vor[f["name"]] = [spalte]
                    break
        return vor

    def breite_aktuelle(self):
        if self.sel_spalte:
            self.breite_optimieren(self.sel_spalte)
        else:
            self.alle_breiten_optimieren()

    def schritt_suchen(self):
        self._nach_menue("Schritt suchen", lambda: self.suche_schritt(self.sel_spalte, "nach"))

    def verweis_erstellen(self):
        self._spaeter(lambda: self.abfrage_befehl("verweis"))

    def suche_schritt(self, spalte, modus="nach"):
        """Schritt per Suchdialog wählen und wie aus dem Menü hinzufügen."""
        op = suche_operation(self.ctx, self.d.peer())
        if not op:
            return False
        vor = {}
        if spalte:
            for f in E.OPS[op]["felder"]:
                if f["art"] == "spalte" and f["name"] in ("spalte", "spalte1"):
                    vor[f["name"]] = spalte
                    break
                if f["art"] == "spalten":
                    vor[f["name"]] = [spalte]
                    break
        return self.neuer_schritt(op, vor, False, modus)

    def menue_hinzufuegen(self):
        b = self.d.ctrl("btnHinzu").getPosSize()
        self.zeige_menue(b.X, b.Y, self.sel_spalte)

    def baue_tabellenmenue(self):
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        ids = {}
        n = 1

        def eintrag(text, aktion):
            nonlocal n
            pm.insertItem(n, text, 0, -1)
            ids[n] = aktion
            n += 1
            return n - 1

        def trenner():
            pm.insertSeparator(-1)

        eintrag("🔍 Schritt suchen …", ("suche",))
        eintrag("Vorschaudaten kopieren", ("kopieren",))
        trenner()
        eintrag("Erste Zeile als Überschriften verwenden", ("schritt", "erste_zeile_als_kopf", None, True))
        eintrag("Benutzerdefinierte Spalte hinzufügen", ("schritt", "benutzerdefinierte_spalte", None, False))
        eintrag("Bedingte Spalte hinzufügen", ("schritt", "bedingte_spalte", None, False))

        index_id = n
        pm.insertItem(index_id, "Indexspalte", 0, -1)
        index_menu = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        for text, start in (("Ab 0", 0), ("Ab 1", 1)):
            item_id = n + 1
            index_menu.insertItem(item_id, text, 0, -1)
            ids[item_id] = ("schritt", "indexspalte", {"neu": "Index", "start": start, "schritt": 1}, True)
            n += 1
        item_id = n + 1
        index_menu.insertItem(item_id, "Benutzerdefiniert…", 0, -1)
        ids[item_id] = ("schritt", "indexspalte", None, False)
        n += 1
        pm.setPopupMenu(index_id, index_menu)
        n += 1
        trenner()
        eintrag("Spalten auswählen", ("schritt", "spalten_behalten", None, False))
        trenner()
        eintrag("Obere Zeilen beibehalten", ("schritt", "zeilen_behalten_oben", None, False))
        eintrag("Untere Zeilen beibehalten", ("schritt", "zeilen_behalten_unten", None, False))
        eintrag("Zeilenbereich beibehalten", ("schritt", "zeilen_bereich", {"aktion": "behalten"}, False))
        trenner()
        eintrag("Doppelte Werte beibehalten", ("schritt", "duplikate_behalten", None, False))
        eintrag("Fehler beibehalten", ("schritt", "fehler_zeilen_behalten", None, False))
        trenner()
        eintrag("Obere Zeilen entfernen", ("schritt", "zeilen_entfernen_oben", None, False))
        eintrag("Untere Zeilen entfernen", ("schritt", "zeilen_entfernen_unten", None, False))
        eintrag("Alternative Zeilen entfernen", ("schritt", "jede_nte_zeile", {"aktion": "entfernen"}, False))
        trenner()
        eintrag("Doppelte Werte entfernen", ("schritt", "duplikate_entfernen", None, False))
        eintrag("Fehler entfernen", ("schritt", "fehler_zeilen_entfernen", None, False))
        trenner()
        eintrag("Abfragen zusammenführen", ("schritt", "tabellen_verbinden", None, False))
        eintrag("Abfragen anfügen", ("schritt", "tabellen_anfuegen", None, False))
        trenner()
        eintrag("Alle Spalten optimal breit", ("breite_alle",))
        eintrag("Einheitliche Breite für alle Spalten …", ("breite_einheit",))
        return pm, ids

    def zeige_tabellenmenue(self, x, y):
        pm, ids = self.baue_tabellenmenue()
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
        self._pm = pm
        wahl = self._menue_ausfuehren(pm, r)
        aktion = ids.get(wahl)
        if not aktion:
            return
        if aktion[0] == "suche":
            self._nach_menue("Schritt suchen", lambda: self.suche_schritt(None, "nach"))
            return
        if aktion[0] == "kopieren":
            self._nach_menue("Vorschaudaten kopieren", self.kopiere_vorschau)
            return
        if aktion[0] == "breite_alle":
            self._nach_menue("Tabelle:alle Breiten", self.alle_breiten_optimieren)
            return
        if aktion[0] == "breite_einheit":
            self._nach_menue("Tabelle:einheitliche Breite", self.einheitliche_breite)
            return
        _, op, vorbelegt, direkt = aktion
        self._nach_menue("Tabelle:%s" % op,
                         lambda: self.neuer_schritt(op, vorbelegt, direkt))

    def menue_hinzufuegen(self):
        b = self.d.ctrl("btnHinzu").getPosSize()
        self.zeige_menue(b.X, b.Y, self.sel_spalte)

    def kopiere_vorschau(self):
        t = self.angezeigt
        if t is None:
            return False
        spalten = t.spalten[:MAX_SPALTEN_VORSCHAU]
        zeilen = t.zeilen[:self.vorschau_limit]
        text = "\t".join(spalten)
        if zeilen:
            text += "\n" + "\n".join("\t".join(E.als_text(v) for v in z[:len(spalten)]) for z in zeilen)
        ok = in_zwischenablage(self.ctx, text)
        self._diag("Vorschau kopiert: %d Zeilen, %d Spalten, ok=%s" % (len(zeilen), len(spalten), ok))
        return ok

    def spalte_markieren(self, name):
        self.sel_spalte = name
        self.titel_aktualisieren()

    def _zeilenkopf_px(self):
        """Es gibt keinen eingebauten Zeilenkopf mehr (Nummernspalte ist eine normale Spalte)."""
        return 0

    def _spalte_links(self, g, x, y, col):
        """Linker Rand der Spalte col (Pixel im Raster) per Bisektion über die Treffer-Abfrage."""
        lo, hi = max(self._zeilenkopf_px(), x - 700), x
        while lo < hi:
            mitte = (lo + hi) // 2
            if g.getColumnAtPoint(mitte, y) == col:
                hi = mitte
            else:
                lo = mitte + 1
        return lo

    def grid_maus(self, ev, quelle=None):
        """Tabelle: nur Linksklicks, nichts davon verändert etwas im Ereignis selbst (alles über _spaeter).
        Kopf: Einfachklick markiert die Spalte, Doppelklick öffnet das Spaltenmenü, Doppelklick auf den Trenner
        = optimale Breite. Zelle: Einfachklick zeigt die Details, Doppelklick das Kopiermenü.
        Oben links (Nummernkopf): Tabellenmenü. Rechtsklicks werden ignoriert."""
        geste = menue_geste(ev)
        if not geste and (bool(ev.PopupTrigger) or getattr(ev, "Buttons", 1) != 1):
            return
        if quelle is not None and self.d.alias.get("grid") != quelle:
            self._diag("Veraltetes Rasterereignis verworfen: %s" % quelle, ev)
            return
        g = self.d.ctrl(quelle or "grid")
        try:
            if g.getPosSize().X < -1000:
                self._diag("Ereignis aus geparktem Raster verworfen", ev, g)
                return
            col = g.getColumnAtPoint(ev.X, ev.Y)
            zeile = g.getRowAtPoint(ev.X, ev.Y)
            modell = g.getModel()
            n_zeilen = modell.GridDataModel.RowCount
            n_spalten = len(modell.ColumnModel.getColumns())
        except Exception as ex:
            self._diag("Rasterereignis ohne Zugriff aufs Raster verworfen: %s" % ex)
            return
        if col >= n_spalten or zeile >= min(n_zeilen, len(self.angezeigt.zeilen) if self.angezeigt else 0):
            self._diag("Rasterereignis mit veraltetem Zeilen-/Spaltenindex verworfen", ev, g)
            return
        try:                                          # Klick in die Laufleiste: weder Auswahl noch Menü
            v_, h_ = self._scroll.get(quelle or self.d.alias.get("grid"), (False, False))
            ps_ = g.getPosSize()
            if (v_ and ev.X > ps_.Width - self.SB_PX - 1) or (h_ and ev.Y > ps_.Height - self.SB_PX - 1):
                self._diag("Klick in die Laufleiste verworfen", ev, g)
                return
        except Exception:
            pass
        self._diag("Raster gedrückt", ev, g)
        if self._param_ansicht is not None:             # Parameteransicht: Zeile wählen, Doppelklick = Parameter ändern
            pn_ = self._param_aus_zeile(zeile) if zeile >= 0 else None
            if pn_ is not None:
                if geste:
                    self._spaeter(lambda: (self.parameter_bearbeiten_(pn_), self._param_nach_bearbeiten(pn_)))
                else:
                    self._spaeter(lambda: self.parameter_anzeigen(pn_))
            return
        doppel = bool(geste)
        rechts = geste == "rechts"
        name = self._grid_namen[col - 1] if (self.angezeigt is not None and 1 <= col <= len(self._grid_namen)) else None
        ps = g.getPosSize()
        x, y = ps.X + ev.X, ps.Y + ev.Y

        if zeile == -1:
            if col <= 0:                                # oben links: Tabellenmenü (wie in Power Query)
                if (not doppel or rechts) and self.roh is not None and self._rechtsklick_zulassen():
                    self._spaeter(lambda: self.zeige_tabellenmenue(x, y))
                return
            try:                                        # Spaltentrenner? (4 mm = ca. 15 Pixel links und rechts)
                l_, r_ = g.getColumnAtPoint(ev.X - TRENNER_PX, ev.Y), g.getColumnAtPoint(ev.X + TRENNER_PX, ev.Y)
            except Exception:
                l_ = r_ = col
            if l_ != r_:
                if doppel and not rechts and 1 <= l_ <= len(self._grid_namen):
                    nm = self._grid_namen[l_ - 1]
                    self._diag("Doppelklick auf Spaltentrenner: %s" % nm)
                    self._spaeter(lambda: self.breite_optimieren(nm))
                return
            if not name:
                return
            if doppel:
                if self._rechtsklick_zulassen() and self.roh is not None:
                    try:
                        offset = ev.X - self._spalte_links(g, ev.X, ev.Y, col)
                    except Exception:
                        offset = 999

                    def kopf_menue():
                        self.sel_spalte = name
                        if offset < TYP_SYMBOL_PX and not rechts:            # Doppelklick auf das Typsymbol: Datentyp-Menü
                            self.typ_menue(name, x, y)
                        else:
                            self.zeige_menue(x, y, name)
                    self._spaeter(kopf_menue)
            else:
                self._spaeter(lambda: self.spalte_markieren(name))
            return

        # Zelle
        self._letzte_zelle = (zeile, name)
        self._kopier_quelle = "tabelle"
        if doppel:
            if name and self.roh is not None and self._rechtsklick_zulassen():
                kopie = (zeile, name)

                def zell_menue():
                    self.sel_spalte = name
                    self.zeige_menue(x, y, name, kopie=kopie)
                self._spaeter(zell_menue)
            return

        def zelle_gewaehlt():
            self.zeige_details(zeile)
            if name:
                self.spalte_markieren(name)
        self._spaeter(zelle_gewaehlt)

    def _kopf_tipp(self, ev, quelle):
        """Hover-Text am Spaltenkopf: voller Spaltenname (nur beim Wechsel der Spalte, sonst nichts tun)."""
        if self.d.alias.get("grid") != quelle or self.angezeigt is None:
            return
        try:
            g = self.d.ctrl(quelle)
            col = g.getColumnAtPoint(ev.X, ev.Y)
            zeile = g.getRowAtPoint(ev.X, ev.Y)
        except Exception:                                   # z. B. noch kein Fenster: still ignorieren
            return
        schluessel = (col, zeile == -1)
        if schluessel == getattr(self, "_tipp_kopf", None):
            return
        self._tipp_kopf = schluessel
        text = ""
        if zeile == -1 and 1 <= col <= len(self._grid_namen):
            text = self._grid_namen[col - 1]
        self.d.model.getByName(quelle).HelpText = text

    def _zelltext(self, z, name):
        t = self.angezeigt
        return E.als_text(t.zeilen[z][t.idx(name)])

    def kopiere(self, art, z, name):
        """Zelle, Zeile (Tabulator-getrennt) oder Spalte (mit Überschrift) der Vorschau in die Zwischenablage."""
        t = self.angezeigt
        if t is None or not t.zeilen:
            return False
        z = max(0, min(z, len(t.zeilen) - 1))
        if art == "zelle" and name in t.spalten:
            text = self._zelltext(z, name)
        elif art == "spalte" and name in t.spalten:
            k = t.idx(name)
            text = "\n".join([name] + [E.als_text(r[k]) for r in t.zeilen])
        else:
            text = "\t".join(E.als_text(v) for v in t.zeilen[z])
        ok = in_zwischenablage(self.ctx, text)
        self._diag("Kopiert (%s): %d Zeichen, ok=%s" % (art, len(text), ok))
        return ok

    def kopiere_auswahl(self):
        """Strg/Cmd+C: zuletzt angeklickte Zelle der Tabelle bzw. Wert in den Zeilendetails."""
        if getattr(self, "_kopier_quelle", "tabelle") == "detail":
            self.kopiere_detail("wert", getattr(self, "_detail_sel", 0))
        elif getattr(self, "_letzte_zelle", None):
            z, nm = self._letzte_zelle
            self.kopiere("zelle" if nm else "zeile", z, nm)

    def kopiere_detail(self, art, i):
        t = self.angezeigt
        if t is None or not t.zeilen:
            return False
        zeile = t.zeilen[max(0, min(self._detail_zeile, len(t.zeilen) - 1))]
        namen = t.spalten[:MAX_SPALTEN_VORSCHAU]
        if not 0 <= i < len(namen):
            return False
        if art == "wert":
            text = E.als_text(zeile[i])
        elif art == "paar":
            text = "%s\t%s" % (namen[i], E.als_text(zeile[i]))
        else:
            text = "\n".join("%s\t%s" % (n, E.als_text(zeile[k])) for k, n in enumerate(namen))
        return in_zwischenablage(self.ctx, text)

    def detail_maus(self, ev):
        """Zeilendetails: Einfachklick merkt die Zeile (für Strg/Cmd+C), Doppelklick öffnet das Kopiermenü.
        Rechtsklick wie Doppelklick (außer am Mac, einstellbar)."""
        if not menue_geste(ev) and (bool(ev.PopupTrigger) or getattr(ev, "Buttons", 1) != 1):
            return
        g = self.d.ctrl("gridDetail")
        try:
            i = g.getRowAtPoint(ev.X, ev.Y)
            n = g.getModel().GridDataModel.RowCount
        except Exception:
            traceback.print_exc()
            return
        if not 0 <= i < n:
            return
        self._detail_sel = i
        self._kopier_quelle = "detail"
        if not menue_geste(ev) or not self._rechtsklick_zulassen():
            return
        ps = g.getPosSize()
        x, y = ps.X + ev.X, ps.Y + ev.Y

        def menue():
            pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
            ids = {1: "wert", 2: "paar", 3: "alle"}
            for n_, text in ((1, "Wert kopieren"), (2, "Name und Wert kopieren"), (3, "Ganzen Datensatz kopieren")):
                pm.insertItem(n_, text, 0, -1)
            r = Rectangle()
            r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
            self._pm = pm
            wahl = self._menue_ausfuehren(pm, r)
            if wahl in ids:
                self._nach_menue("Detail:" + ids[wahl], lambda: self.kopiere_detail(ids[wahl], i))
        self._spaeter(menue)

    def spaltenbreite_eingeben(self, name):
        """Breite einer Spalte als Zahl (Dialogeinheiten, 100 ≈ 5 cm) – Ersatz, falls das Ziehen mit der Maus nicht geht."""
        akt = int(self.breiten.get(name, 60))
        txt = frage_text(self.ctx, "Spaltenbreite", "Breite von „%s“ (30 bis 250, 100 ≈ 5 cm):" % name, str(akt), self.d.peer())
        if txt is None:
            return
        try:
            w = max(20, min(250, int(float(txt.replace(",", ".")))))
        except ValueError:
            self.meld("Bitte eine Zahl eingeben.")
            return
        self.breiten[name] = w
        self._breiten_ignorieren = True
        self.zeige()

    def einheitliche_breite(self):
        """Eine gemeinsame Breite für alle Spalten (außer der Nummerierung)."""
        if self.angezeigt is None or not self._grid_namen:
            return
        werte = sorted(int(self.breiten.get(n, 60)) for n in self._grid_namen)
        txt = frage_text(self.ctx, "Einheitliche Spaltenbreite",
                         "Breite für alle Spalten (30 bis 250, 100 ≈ 5 cm):", str(werte[len(werte) // 2]), self.d.peer())
        if txt is None:
            return
        try:
            w = max(20, min(250, int(float(txt.replace(",", ".")))))
        except ValueError:
            self.meld("Bitte eine Zahl eingeben.")
            return
        for n in self._grid_namen:
            self.breiten[n] = w
        self._breiten_ignorieren = True
        self.zeige()

    def alle_breiten_optimieren(self):
        self.breiten.clear()
        self._breiten_ignorieren = True
        self.zeige()

    def breite_optimieren(self, name):
        """Breite einer Spalte an den Inhalt anpassen (höchstens ca. 5 cm)."""
        if self.angezeigt is None or name not in self._grid_namen:
            return
        k = self.angezeigt.idx(name)
        zeilen = self.angezeigt.zeilen[:self.vorschau_limit]
        self.breiten[name] = self.optimale_breite(name, k, zeilen, self._kuerzel.get(name, "-"))
        self._breiten_ignorieren = True          # Raster komplett neu aufbauen (Änderung einzelner Spalten wird am Mac nicht gezeichnet)
        self.zeige()

    def typ_menue(self, name, x, y):
        """Datentyp einer Spalte wählen: Menü mit allen Typen (aktueller Typ mit Haken), Auswahl ändert sofort."""
        if self.angezeigt is None or name not in self.angezeigt.spalten:
            return
        k = self.angezeigt.idx(name)
        art = typ_art([z[k] for z in self.angezeigt.zeilen[:2000]])
        aktuell = SYMBOL_ZU_TYP.get(art)
        pm = self.smgr.createInstance("com.sun.star.awt.PopupMenu")
        ids = {}
        for n, (schluessel, titel) in enumerate(E.TYPEN, 1):
            pm.insertItem(n, titel, 0, -1)
            ids[n] = schluessel
            if schluessel == aktuell:
                pm.checkItem(n, True)
        r = Rectangle()
        r.X, r.Y, r.Width, r.Height = int(x), int(y), 0, 0
        self._pm = pm
        wahl = self._menue_ausfuehren(pm, r)
        if wahl in ids:
            self._nach_menue("Typ:%s" % ids[wahl], lambda t=ids[wahl]: self.neuer_schritt(
                "typ_aendern", {"spalten": [name], "typ": t, "ort": "de", "bei_fehler": "fehler"}, True))

    # -- Abfrage-Dateien -------------------------------------------------------
    def abfrage_speichern(self):
        """Die geöffnete Abfrage als Datei sichern (zum Weitergeben oder für eine andere Calc-Datei)."""
        self.merke()
        self.abfrage.name = self.d.ctrl("txtName").getText().strip() or "Abfrage1"
        p = datei_waehlen(self.ctx, True, "Abfrage-Dateien", "*.abfrage.json;*.json",
                          self.abfrage.name + ".abfrage.json")
        if not p:
            return
        if not p.lower().endswith(".json"):
            p += ".abfrage.json"
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.abfrage.to_json())
        self.d.ctrl("lblZeilen").getModel().Label = "Abfrage gespeichert"
        self.d.ctrl("lblZeilen").getModel().HelpText = os.path.basename(p)

    def abfrage_oeffnen(self):
        """Abfrage aus einer Datei als neue Abfrage in diese Datei übernehmen (bestehende Abfragen bleiben unberührt)."""
        p = datei_waehlen(self.ctx, False, "Abfrage-Dateien", "*.abfrage.json;*.json")
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                a = E.Abfrage.from_json(f.read())
        except Exception as e:
            self.meld("Die Datei ist keine gültige Abfrage: %s" % e)
            return
        a.ziel = a.ziel if (a.ziel or {}).get("art") != "zelle" else {"art": "blatt"}   # Ziel gehört zur Datei
        a.name = self._freier_name(a.name or "Abfrage1")
        self._neue_in_liste(a, nach_aktuell=False)
        fehlt = [n for n in sorted(set(re.findall(r"\{([^{}]+)\}", a.to_json()))) if n not in self._param_namen()
                 and n not in a.name]
        hinweis = ""
        if fehlt and self.doc is not None:
            hinweis = "\n\nHinweis: Die Abfrage nennt Parameter, die es in dieser Datei nicht gibt: %s." % ", ".join(
                "{%s}" % n for n in fehlt[:6])
        self.meld("Abfrage „%s“ übernommen.%s" % (a.name, hinweis), "INFOBOX")

    # -- Laden ---------------------------------------------------------------
    def vorschau_aktualisieren(self):
        """Quelle der geöffneten Abfrage (und der Abfragen, auf denen sie aufbaut) neu einlesen, Vorschau neu aufbauen."""
        self._param_ansicht = None
        try:
            schluessel = json.dumps(self.abfrage.quelle, sort_keys=True, default=str)
            self._cache_q.pop(schluessel, None)
        except Exception:
            pass
        self._cache_t.clear()
        self._cache_basis.clear()
        self._kontext_setzen()
        if self.abfrage.quelle:
            self.quelle_laden(neu=True)
        self.liste_neu(self.gewaehlter_schritt())
        self.zeige()

    def alle_vorschau_aktualisieren(self):
        """Alle Zwischenspeicher verwerfen und die Quelle der geöffneten Abfrage neu einlesen; die übrigen Abfragen
        lesen ihre Quelle beim nächsten Öffnen neu."""
        self.cache_leeren()
        self.vorschau_aktualisieren()
        self.meld("Alle Quellen werden neu eingelesen (die geöffnete Abfrage sofort, die übrigen beim Öffnen).", "INFOBOX")

    def ins_blatt_schreiben(self):
        """Gewählte Abfrage ins Blatt schreiben, ohne den Editor zu schließen."""
        self.cache_leeren()
        r = self.laden(schliessen=False)
        if r:
            self.meld("Abfrage „%s“ aktualisiert (%d Zeilen)." % (self.abfrage.name, r[0]), "INFOBOX")

    def laden(self, schliessen=True):
        d = self.d
        if self.roh is None:
            self.meld("Bitte zuerst eine Quelle wählen.")
            return
        name = d.ctrl("txtName").getText().strip() or "Abfrage1"
        self.abfrage.name = name
        try:
            neu_sp = uebernehme_neue_spalten(self.doc, self.abfrage)
            if neu_sp:
                self.liste_neu(self.gewaehlter_schritt())
        except E.FormelFehler as e:
            self.meld(str(e), "ERRORBOX")
            return
        except Exception:
            traceback.print_exc()
        try:
            tab = self.tabelle_bis(len(self.abfrage.schritte))
        except E.StepError as e:
            self.meld("Die Abfrage enthält einen Fehler und kann nicht geladen werden:\n%s" % e, "ERRORBOX")
            return
        if self.doc is None:
            self.meld("Es ist kein Calc-Dokument geöffnet.", "ERRORBOX")
            return
        try:
            pruefe_ziel(self.doc, self.abfrage)
        except E.FormelFehler as e:
            self.meld(str(e), "ERRORBOX")
            return
        gespeichert = gespeicherte_abfragen(self.doc)
        if hand_geaendert(self.doc, self.abfrage):
            if self.meld("Die Ausgabetabelle dieser Abfrage wurde von Hand geändert.\n\nBeim Laden gehen diese Änderungen "
                         "verloren (außer in manuell hinzugefügten Spalten).\n\nTrotzdem laden?", "QUERYBOX", 3) != 2:
                return
        umbenennen = False
        if self.alter_name and self.alter_name != name and self.alter_name in gespeichert:
            antwort = self.meld("Die Abfrage hieß bisher „%s“.\n\nJa = umbenennen (die alte Abfrage wird ersetzt)\n"
                                "Nein = zusätzlich als neue Abfrage „%s“ speichern" % (self.alter_name, name),
                                "QUERYBOX", 3)
            umbenennen = antwort == 2
        if name in gespeichert and name != self.alter_name:
            if self.meld("Es gibt schon eine Abfrage namens „%s“. Soll sie überschrieben werden?" % name,
                         "QUERYBOX", 3) != 2:
                return
        art = (self.abfrage.ziel or {}).get("art", "blatt")
        blatt = gueltiger_blattname(name)
        if art not in ("zelle", "keine") and self.doc.getSheets().hasByName(blatt) and name not in gespeichert \
                and not (umbenennen and self.alter_name):
            if self.meld("Das Tabellenblatt '%s' gibt es schon und gehört zu keiner Abfrage.\n"
                         "Soll sein Inhalt ersetzt werden?" % blatt, "QUERYBOX", 3) != 2:
                return
        if umbenennen and art not in ("zelle", "keine"):       # altes Zielblatt mit umbenennen, falls möglich
            alt_blatt = gueltiger_blattname(self.alter_name)
            sheets = self.doc.getSheets()
            if sheets.hasByName(alt_blatt) and not sheets.hasByName(blatt):
                sheets.getByName(alt_blatt).Name = blatt
        try:
            try:
                schreibe_ergebnis(self.doc, tab, self.abfrage)
            except ZielBelegt as e:
                if self.meld("%s\n\nSoll der Inhalt überschrieben werden?" % e, "QUERYBOX", 3) != 2:
                    return
                schreibe_ergebnis(self.doc, tab, self.abfrage, bestaetigt=True)
        except E.FormelFehler as e:
            self.meld(str(e), "ERRORBOX")
            return
        if umbenennen:
            loesche_abfrage(self.doc, self.alter_name)
        speichere_abfrage(self.doc, self.abfrage)
        self.alter_name = name
        self.ergebnis_ok = True
        fehler = self._andere_speichern()
        if fehler:
            self.meld("Diese Abfragen konnten nicht aktualisiert werden:\n" + "\n".join(fehler))
        if schliessen:
            self._zum_ausgabeblatt()
            d.schliessen(1)
        return (len(tab.zeilen),)

    def _zum_ausgabeblatt(self):
        """Nach „Schließen und Laden“ in das Blatt springen, in das die Abfrage geschrieben wurde."""
        try:
            ziel = self.abfrage.ziel or {}
            if ziel.get("art") == "keine":
                return                      # Verbindung: es gibt kein Ausgabeblatt
            blatt = ziel.get("blatt") if ziel.get("art") == "zelle" else gueltiger_blattname(self.abfrage.name)
            sheets = self.doc.getSheets()
            if blatt and sheets.hasByName(blatt):
                sh = sheets.getByName(blatt)
                ctrl = self.doc.getCurrentController()
                ctrl.setActiveSheet(sh)
                start = ziel.get("zelle") or "A1"
                try:
                    ctrl.setFirstVisibleColumn(0)           # Ansicht ganz nach oben links, Cursor auf den Tabellenanfang
                    ctrl.setFirstVisibleRow(0)
                    ctrl.select(sh.getCellRangeByName(start))
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()

    # -- Start -----------------------------------------------------------------
    def run(self, ohne_dialog=False):
        try:
            if self.doc is not None and ist_calc(self.doc):
                registriere_menue(self.doc)
        except Exception:
            traceback.print_exc()
        self.bauen()
        self.d.klick_verfolgen()
        self._ansicht_laden()
        self.layout(self.d.model.Width, self.d.model.Height)
        self._gitter_anwenden()
        try:
            self.d.ctrl("chkAuto").getModel().State = 1 if self.autospeichern_an() else 0
        except Exception:
            traceback.print_exc()
        self._arbeit_aufbauen()
        self._kontext_setzen()
        self.abfragen_liste_neu()
        if self.abfrage.quelle:
            self.quelle_laden()
        self.liste_neu()
        self.zeige()
        if ohne_dialog:
            return
        def nach_anzeige():             # erst jetzt (Fenster sichtbar) gibt es verlässliche Maße
            self._sichtbar = True
            if self.symbole_an():
                self.knopfart_anwenden()
            try:                         # Layout nach der echten Fenstergröße (nicht nach der Modellgröße)
                ps = self.d.dlg.getPosSize()
                self.layout(*self._fenster_logik(ps.Width, ps.Height))
            except Exception:
                self.layout(self.d.model.Width, self.d.model.Height)
            self._spaeter(self._update_still)
        self._spaeter(nach_anzeige)
        self.d.nach_farbe = lambda dunkel: (self._farben() if dunkel else None)
        _EINST_KONTEXT.update({"ctx": self.ctx, "parent": self.parent})
        try:
            self.d.zeigen(self.parent, 0.9)      # Editor: höchstens 90 % der Arbeitsfläche (Calc-Fenster wird ignoriert)
        finally:
            _ARBEIT["fn"] = None
            self.d.klick_beenden()
        self.d.weg()


# ---------------------------------------------------------------------------
# Menübefehle
# ---------------------------------------------------------------------------
def ist_calc(doc):
    try:
        return doc is not None and doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")
    except Exception:
        return False


def _parent(frame):
    try:
        return frame.getContainerWindow() if frame else None
    except Exception:
        return None


def befehl_neu(ctx, frame, doc):
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen (ein leeres genügt).", "WARNINGBOX")
        return
    q = QuellenDialog(ctx, doc, None, parent).zeigen()
    if not q:
        return
    vorhanden = gespeicherte_abfragen(doc)
    i = 1
    while "Abfrage%d" % i in vorhanden or doc.getSheets().hasByName("Abfrage%d" % i):
        i += 1
    schritte = [dict(s_) for s_ in NEUE_TABELLE_SCHRITTE] if q.get("art") == "blatt" else []
    ed = Editor(ctx, frame, doc, E.Abfrage("Abfrage%d" % i, q, schritte))
    ed.run()


def _abfrage_waehlen(ctx, frame, doc, titel):
    """-> (name, Abfrage) oder None."""
    parent = _parent(frame)
    gesp = gespeicherte_abfragen(doc)
    if not gesp:
        meldung(ctx, parent, "In diesem Dokument sind noch keine Abfragen gespeichert.\n"
                             "Legen Sie über „Neue Abfrage…“ eine an.")
        return None
    namen = geordnete_namen(doc, gesp)
    i = waehle_aus_liste(ctx, titel, "Welche Abfrage?", namen, parent)
    if i is None:
        return None
    try:
        return namen[i], E.Abfrage.from_json(gesp[namen[i]])
    except Exception as e:
        meldung(ctx, parent, "Die gespeicherte Abfrage ist beschädigt: %s" % e, "ERRORBOX")
        return None


def befehl_bearbeiten(ctx, frame, doc):
    if not ist_calc(doc):
        meldung(ctx, _parent(frame), "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    res = _abfrage_waehlen(ctx, frame, doc, "Abfrage bearbeiten")
    if res:
        Editor(ctx, frame, doc, res[1]).run()


def befehl_loeschen(ctx, frame, doc):
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    res = _abfrage_waehlen(ctx, frame, doc, "Abfrage löschen")
    if not res:
        return
    name, a = res
    if meldung(ctx, parent, "Abfrage „%s“ aus diesem Dokument löschen?" % name, "QUERYBOX", 3) != 2:
        return
    loesche_abfrage(doc, name, True)
    ziel = a.ziel or {}
    sheets = doc.getSheets()
    if ziel.get("art") == "zelle":
        if ziel.get("letzter") and ziel.get("letzter_blatt") and sheets.hasByName(ziel["letzter_blatt"]):
            if meldung(ctx, parent, "Soll auch der Ausgabebereich %s auf Blatt „%s“ geleert werden?"
                       % (ziel["letzter"], ziel["letzter_blatt"]), "QUERYBOX", 3) == 2:
                sheets.getByName(ziel["letzter_blatt"]).getCellRangeByName(ziel["letzter"]).clearContents(1023)
    elif ziel.get("art") != "keine":
        blatt = gueltiger_blattname(name)
        if sheets.hasByName(blatt) and sheets.getCount() > 1:
            if meldung(ctx, parent, "Soll auch das Ausgabeblatt „%s“ gelöscht werden?" % blatt,
                       "QUERYBOX", 3) == 2:
                sheets.removeByName(blatt)


def handgeaenderte_abfragen(doc, nur_auto=False):
    """Namen der Abfragen, deren Ausgabetabelle seit dem letzten Schreiben von Hand geändert wurde."""
    namen = []
    for name, text in sorted(gespeicherte_abfragen(doc).items()):
        try:
            a = E.Abfrage.from_json(text)
            if nur_auto and not a.auto:
                continue
            if hand_geaendert(doc, a):
                namen.append(name)
        except Exception:
            pass
    return namen


def aktualisiere_alle(ctx, doc, nur_auto=False, trotzdem=False, ausser=()):
    """-> (ok-Liste, Fehler-Liste) für alle (bzw. nur automatisch zu aktualisierende) Abfragen.
    trotzdem: von Hand geänderte Tabellen trotzdem überschreiben; ausser: Namen, die übersprungen werden."""
    ok, fehler = [], []
    gesp = gespeicherte_abfragen(doc)
    for name in sorted(gesp):
        if name in ausser:
            fehler.append("%s: übersprungen (Tabelle wurde von Hand geändert)" % name)
            continue
        try:
            a = E.Abfrage.from_json(gesp[name])
            if nur_auto and not a.auto:
                continue
            n = aktualisiere_abfrage(ctx, doc, a, trotzdem=trotzdem)
            hint = ("; " + "; ".join(E.HINWEISE)) if E.HINWEISE else ""
            ok.append("%s (nur Verbindung, %d Zeilen%s)" % (name, n, hint) if ist_verbindung(a)
                      else "%s (%d Zeilen%s)" % (name, n, hint))
        except (E.StepError, E.FormelFehler) as e:
            fehler.append("%s: %s" % (name, e))
        except Exception as e:
            traceback.print_exc()
            fehler.append("%s: %s" % (name, e))
    return ok, fehler


def befehl_aktualisieren(ctx, frame, doc):
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    if not gespeicherte_abfragen(doc):
        meldung(ctx, parent, "In diesem Dokument sind keine Abfragen gespeichert.")
        return
    geaendert = handgeaenderte_abfragen(doc)
    trotzdem, ausser = False, ()
    if geaendert:
        antwort = meldung(ctx, parent, "Bei diesen Abfragen wurde die Ausgabetabelle von Hand geändert:\n  %s\n\n"
                          "Beim Aktualisieren gehen diese Änderungen verloren (außer in manuell hinzugefügten Spalten).\n\n"
                          "Ja = trotzdem alle aktualisieren\nNein = diese Abfragen überspringen"
                          % "\n  ".join(geaendert), "QUERYBOX", 3)
        if antwort == 2:
            trotzdem = True
        else:
            ausser = set(geaendert)
    ok, fehler = aktualisiere_alle(ctx, doc, trotzdem=trotzdem, ausser=ausser)
    text = ""
    if ok:
        text += "Aktualisiert:\n  " + "\n  ".join(ok)
    if fehler:
        text += ("\n\n" if text else "") + "Fehler:\n  " + "\n  ".join(fehler)
    meldung(ctx, parent, text, "WARNINGBOX" if fehler else "INFOBOX")


def befehl_oeffnen(ctx, frame, doc):
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    p = datei_waehlen(ctx, False, "Abfrage-Dateien", "*.abfrage.json;*.json")
    if not p:
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            a = E.Abfrage.from_json(f.read())
    except Exception as e:
        meldung(ctx, parent, "Die Datei ist keine gültige Abfrage: %s" % e, "ERRORBOX")
        return
    a.ziel = {"art": "blatt"}      # Ausgabeziel gehört zur Datei, nicht zur Abfrage-Datei
    belegt = {n.casefold() for n in gespeicherte_abfragen(doc)}
    basis, i = a.name or "Abfrage1", 2
    while a.name.casefold() in belegt:                 # eine bestehende Abfrage gleichen Namens bleibt unberührt
        a.name = "%s (%d)" % (basis, i)
        i += 1
    Editor(ctx, frame, doc, a).run()


def befehl_speichern(ctx, frame, doc):
    """Menü „Abfrage speichern …“: eine der Abfragen dieser Datei als Datei sichern."""
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    texte = abfragen_texte(doc)
    namen = geordnete_namen(doc, texte)
    if not namen:
        meldung(ctx, parent, "In dieser Datei gibt es noch keine gespeicherte Abfrage.", "INFOBOX")
        return
    i = waehle_aus_liste(ctx, "Abfrage speichern", "Welche Abfrage soll in eine Datei gesichert werden?", namen, parent)
    if i is None:
        return
    name = namen[i]
    p = datei_waehlen(ctx, True, "Abfrage-Dateien", "*.abfrage.json;*.json", name + ".abfrage.json")
    if not p:
        return
    if not p.lower().endswith(".json"):
        p += ".abfrage.json"
    with open(p, "w", encoding="utf-8") as f:
        f.write(texte[name])
    meldung(ctx, parent, "Abfrage „%s“ gespeichert:\n%s" % (name, p), "INFOBOX")


def befehl_editor(ctx, frame, doc):
    """Editor mit der Abfragenliste öffnen (erste gespeicherte Abfrage); ohne Abfragen: neue anlegen."""
    if not ist_calc(doc):
        meldung(ctx, _parent(frame), "Bitte zuerst ein Calc-Dokument öffnen (ein leeres genügt).", "WARNINGBOX")
        return
    gesp = gespeicherte_abfragen(doc)
    for name in geordnete_namen(doc, gesp):
        try:
            Editor(ctx, frame, doc, E.Abfrage.from_json(gesp[name])).run()
            return
        except Exception:
            raise
    befehl_neu(ctx, frame, doc)


def abfrage_fuer_blatt(doc, blatt):
    """Name der Abfrage, deren Tabelle auf dem Blatt liegt (sonst None). Maßgeblich ist der Datenbereich tbl_…
    (folgt verschobenen Tabellen); steht der Cursor in einer Tabelle, gilt diese, sonst die erste auf dem Blatt.
    Erst danach zählt der Blattname (ältere Abfragen ohne Bereich)."""
    gesp = gespeicherte_abfragen(doc)
    cur = None
    try:
        ra = doc.getCurrentSelection().getRangeAddress()
        cur = (ra.Sheet, ra.StartColumn, ra.StartRow)
    except Exception:
        pass
    auf_blatt = []
    for name in geordnete_namen(doc, gesp):
        try:
            a = E.Abfrage.from_json(gesp[name])
        except Exception:
            continue
        ad = _bereichs_adresse(doc, (a.ziel or {}).get("bereich"))
        if ad is not None and ad[0] == blatt:
            if cur and cur[0] == ad[1] and ad[2] <= cur[1] <= ad[4] and ad[3] <= cur[2] <= ad[5]:
                return name
            auf_blatt.append(name)
    if auf_blatt:
        return auf_blatt[0]
    for name in geordnete_namen(doc, gesp):
        try:
            a = E.Abfrage.from_json(gesp[name])
        except Exception:
            continue
        if (a.ziel or {}).get("bereich") and _bereichs_adresse(doc, a.ziel["bereich"]) is not None:
            continue                        # hat einen Bereich anderswo: gehört nicht zu diesem Blatt
        if zielblatt_name(a) and zielblatt_name(a) == blatt:
            return name
    return None


def befehl_spalten_uebernehmen(ctx, frame, doc):
    """Blatt-Menü: neue manuelle Spalten der Tabelle unter dem Cursor sofort übernehmen (ohne neu zu rechnen):
    Überschriften ergänzen, Tabellenbereich erweitern, Schritt ergänzen, Abfrage speichern."""
    parent = _parent(frame)
    if not ist_calc(doc):
        return
    name = abfrage_fuer_blatt(doc, aktives_blatt_name(doc))
    if name is None:
        meldung(ctx, parent, "Der Cursor steht in keiner OpenQuery-Tabelle.", "WARNINGBOX")
        return
    try:
        a = E.Abfrage.from_json(gespeicherte_abfragen(doc)[name])
        if not any(x.get("op") == "hand_behalten" for x in a.schritte):
            meldung(ctx, parent, "Die Abfrage „%s“ hat keinen Schritt „Manuelle Spalten behalten“." % name, "WARNINGBOX")
            return
        if not (a.ziel or {}).get("spalten"):
            meldung(ctx, parent, "Die Abfrage „%s“ bitte erst einmal aktualisieren; danach kennt sie ihre Spalten." % name, "WARNINGBOX")
            return
        vorher = a.to_json()
        neu = uebernehme_neue_spalten(doc, a)
        if neu or a.to_json() != vorher:
            speichere_abfrage(doc, a)
            meldung(ctx, parent, "%d neue manuelle Spalte(n) übernommen: %s" % (len(neu), ", ".join(neu)), "INFOBOX")
        else:
            meldung(ctx, parent, "Keine neuen Spalten gefunden.", "INFOBOX")
    except Exception as e:
        traceback.print_exc()
        meldung(ctx, parent, "%s: %s" % (name, e), "WARNINGBOX")


def _abfrage_mit_bereich(doc, blatt_idx, c0, r0, c1, r1, enthaelt=False):
    """Name der Abfrage, deren Ausgabetabelle (Datenbereich) genau diesen Bereich belegt (enthaelt=True: den die
    Zelle/der Bereich ganz einschließt bzw. in dem er liegt); sonst None."""
    gesp = gespeicherte_abfragen(doc)
    for name in geordnete_namen(doc, gesp):
        try:
            a = E.Abfrage.from_json(gesp[name])
        except Exception:
            continue
        ad = _bereichs_adresse(doc, (a.ziel or {}).get("bereich"))
        if ad is None or ad[1] != blatt_idx:
            continue
        if (ad[2], ad[3], ad[4], ad[5]) == (c0, r0, c1, r1):
            return name
        if enthaelt and ad[2] <= c0 and c1 <= ad[4] and ad[3] <= r0 and r1 <= ad[5] and (c0, r0) == (c1, r1):
            return name                          # einzelne Zelle in einer Abfrage-Tabelle = diese Tabelle
    return None


def _neue_abfrage_mit_quelle(ctx, frame, doc, quelle, schritte):
    vorhanden = gespeicherte_abfragen(doc)
    i = 1
    while "Abfrage%d" % i in vorhanden or doc.getSheets().hasByName("Abfrage%d" % i):
        i += 1
    Editor(ctx, frame, doc, E.Abfrage("Abfrage%d" % i, quelle, schritte)).run()


def befehl_blatt_quelle(ctx, frame, doc):
    """Blatt-Menü: das aktuelle Blatt als Quelle einer neuen Abfrage. Ist das ganze genutzte Blatt die Tabelle einer
    Abfrage, entsteht ein Verweis auf diese Abfrage statt einer Abfrage auf das Blatt."""
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    try:
        sh = doc.getCurrentController().getActiveSheet()
        cur = sh.createCursor()
        cur.gotoEndOfUsedArea(False)
        ra = cur.getRangeAddress()
        if ra.EndColumn == 0 and ra.EndRow == 0 and not sh.getCellByPosition(0, 0).getFormula():
            meldung(ctx, parent, "Das Blatt „%s“ ist leer." % sh.Name, "WARNINGBOX")
            return
        name = _abfrage_mit_bereich(doc, sh.RangeAddress.Sheet, 0, 0, ra.EndColumn, ra.EndRow)
        if name:
            _neue_abfrage_mit_quelle(ctx, frame, doc, {"art": "abfrage", "name": name}, [])
        else:
            _neue_abfrage_mit_quelle(ctx, frame, doc, {"art": "blatt", "blatt": sh.Name},
                                     [dict(s_) for s_ in NEUE_TABELLE_SCHRITTE])
    except Exception as e:
        traceback.print_exc()
        meldung(ctx, parent, "Das Blatt konnte nicht als Quelle übernommen werden: %s" % e, "WARNINGBOX")


def befehl_bereich_quelle(ctx, frame, doc):
    """Blatt-Menü: den markierten Bereich als Quelle. Entspricht er genau der Tabelle einer Abfrage (oder steht nur der
    Cursor in einer solchen Tabelle), entsteht ein Verweis auf diese Abfrage."""
    parent = _parent(frame)
    if not ist_calc(doc):
        meldung(ctx, parent, "Bitte zuerst ein Calc-Dokument öffnen.", "WARNINGBOX")
        return
    try:
        sel = doc.getCurrentController().getSelection()
        if sel is None or not hasattr(sel, "getRangeAddress"):
            meldung(ctx, parent, "Bitte einen zusammenhängenden Zellbereich markieren.", "WARNINGBOX")
            return
        ra = sel.getRangeAddress()
        sh = doc.getSheets().getByIndex(ra.Sheet)
        name = _abfrage_mit_bereich(doc, ra.Sheet, ra.StartColumn, ra.StartRow, ra.EndColumn, ra.EndRow, True)
        if name:
            _neue_abfrage_mit_quelle(ctx, frame, doc, {"art": "abfrage", "name": name}, [])
            return
        if (ra.StartColumn, ra.StartRow) == (ra.EndColumn, ra.EndRow):
            meldung(ctx, parent, "Bitte einen Bereich markieren (mehr als eine Zelle) oder in eine OpenQuery-Tabelle klicken.",
                    "WARNINGBOX")
            return
        _neue_abfrage_mit_quelle(ctx, frame, doc,
                                 {"art": "blatt", "blatt": sh.Name,
                                  "bereich": adresse_text(ra.StartColumn, ra.StartRow, ra.EndColumn, ra.EndRow)},
                                 [dict(s_) for s_ in NEUE_TABELLE_SCHRITTE])
    except Exception as e:
        traceback.print_exc()
        meldung(ctx, parent, "Der Bereich konnte nicht als Quelle übernommen werden: %s" % e, "WARNINGBOX")


def befehl_hier_aktualisieren(ctx, frame, doc):
    """Rechtsklick im Blatt: die Abfrage des aktuellen Blatts aktualisieren."""
    parent = _parent(frame)
    if not ist_calc(doc):
        return
    blatt = aktives_blatt_name(doc)
    name = abfrage_fuer_blatt(doc, blatt)
    if name is None:
        meldung(ctx, parent, "Dieses Blatt gehört zu keiner Abfrage.", "WARNINGBOX")
        return
    try:
        a = E.Abfrage.from_json(gespeicherte_abfragen(doc)[name])
        trotzdem = False
        if hand_geaendert(doc, a):
            if meldung(ctx, parent, "Die Tabelle der Abfrage „%s“ wurde von Hand geändert.\n\nBeim Aktualisieren gehen diese "
                       "Änderungen verloren (außer in manuell hinzugefügten Spalten).\n\nTrotzdem aktualisieren?" % name,
                       "QUERYBOX", 3) != 2:
                return
            trotzdem = True
        aktualisiere_abfrage(ctx, doc, a, trotzdem=trotzdem)
    except Exception as e:
        meldung(ctx, parent, "%s: %s" % (name, e), "WARNINGBOX")


def befehl_hier_editor(ctx, frame, doc):
    """Rechtsklick im Blatt: Editor mit der Abfrage dieses Blatts, sonst mit der ersten Abfrage."""
    if not ist_calc(doc):
        befehl_editor(ctx, frame, doc)
        return
    name = abfrage_fuer_blatt(doc, aktives_blatt_name(doc))
    if name is None:
        befehl_editor(ctx, frame, doc)
        return
    Editor(ctx, frame, doc, E.Abfrage.from_json(gespeicherte_abfragen(doc)[name])).run()


BEFEHLE = {"neu": befehl_neu, "editor": befehl_editor, "bearbeiten": befehl_bearbeiten, "loeschen": befehl_loeschen,
           "aktualisieren": befehl_aktualisieren, "oeffnen": befehl_oeffnen, "speichern": befehl_speichern,
           "hier_aktualisieren": befehl_hier_aktualisieren, "spalten_uebernehmen": befehl_spalten_uebernehmen, "hier_editor": befehl_hier_editor,
           "blatt_quelle": befehl_blatt_quelle, "bereich_quelle": befehl_bereich_quelle,
           "parameter": befehl_parameter}


class MenueAbfangen(unohelper.Base, XContextMenuInterceptor):
    """Hängt „OpenQuery ▸ …“ an das Kontextmenü der Zellen."""
    def __init__(self, doc):
        self.doc = doc

    def notifyContextMenuExecute(self, ev):
        try:
            c = ev.ActionTriggerContainer
            urls = []
            for i in range(c.getCount()):
                try:
                    urls.append(c.getByIndex(i).CommandURL)
                except Exception:
                    pass
            diag_global("Kontextmenü: %d Einträge, z. B. %s" % (len(urls), urls[:8]))
            if ".uno:Copy" not in urls and ".uno:Paste" not in urls and ".uno:Cut" not in urls:
                return _CM_IGNORED
            blatt = aktives_blatt_name(self.doc)
            eigene = abfrage_fuer_blatt(self.doc, blatt) is not None
            fabrik = c

            def eintrag(text, befehl):
                e = fabrik.createInstance("com.sun.star.ui.ActionTrigger")
                e.setPropertyValue("Text", text)
                e.setPropertyValue("CommandURL", PROTOKOLL + befehl)
                return e
            trenn = fabrik.createInstance("com.sun.star.ui.ActionTriggerSeparator")
            trenn.setPropertyValue("SeparatorType", 0)
            c.insertByIndex(c.getCount(), trenn)
            c.insertByIndex(c.getCount(), eintrag("OpenQuery öffnen", "hier_editor"))
            c.insertByIndex(c.getCount(), eintrag("OpenQuery Dieses Blatt als Quelle", "blatt_quelle"))
            c.insertByIndex(c.getCount(), eintrag("OpenQuery Diesen Bereich als Quelle", "bereich_quelle"))
            if eigene:
                c.insertByIndex(c.getCount(), eintrag("OpenQuery Abfrage aktualisieren", "hier_aktualisieren"))
                c.insertByIndex(c.getCount(), eintrag("OpenQuery Neue Spalten übernehmen", "spalten_uebernehmen"))
            c.insertByIndex(c.getCount(), eintrag("OpenQuery Alle Abfragen aktualisieren", "aktualisieren"))
            diag_global("Kontextmenü: OpenQuery angehängt")
            return _CM_MODIFIED
        except Exception:
            traceback.print_exc()
            return _CM_IGNORED


_MENUE_REFS = []


def registriere_menue(doc):
    """Kontextmenü-Erweiterung am Controller dieses Dokuments anmelden (einmal je Controller)."""
    ctl = doc.getCurrentController()
    if ctl is None or any(r[0] == ctl for r in _MENUE_REFS):
        return
    m = MenueAbfangen(doc)
    ctl.registerContextMenuInterceptor(m)
    _MENUE_REFS.append((ctl, m))
    diag_global("Kontextmenü angemeldet")



class Handler(unohelper.Base, XInitialization, XDispatchProvider, XDispatch, XServiceInfo):
    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None

    # XInitialization
    def initialize(self, args):
        if args:
            self.frame = args[0]

    # XDispatchProvider
    def queryDispatch(self, url, target, flags):
        if url.Protocol == PROTOKOLL and url.Path in BEFEHLE:
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    # XDispatch
    def dispatch(self, url, args):
        fn = BEFEHLE.get(url.Path)
        if not fn:
            return
        doc = None
        try:
            doc = self.frame.getController().getModel()
        except Exception:
            pass
        try:
            if doc is not None and ist_calc(doc):
                registriere_menue(doc)
        except Exception:
            traceback.print_exc()
        try:
            fn(self.ctx, self.frame, doc)
        except Exception as e:
            traceback.print_exc()
            meldung(self.ctx, _parent(self.frame), "Unerwarteter Fehler:\n%s" % e, "ERRORBOX")

    def addStatusListener(self, listener, url):
        pass

    def removeStatusListener(self, listener, url):
        pass

    # XServiceInfo
    def getImplementationName(self):
        return IMPL_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ProtocolHandler",)


# ---------------------------------------------------------------------------
# Aktualisieren beim Öffnen der Datei (Job, der von LibreOffice beim Öffnen eines Dokuments startet)
# ---------------------------------------------------------------------------
_AUTO_LAEUFT = set()
_AUTO_ZULETZT = {}


def _modell_aus_args(args):
    for a in args or ():
        name = getattr(a, "Name", None)
        if name == "Model":
            return a.Value
        if name == "Environment":
            m = _modell_aus_args(a.Value)
            if m is not None:
                return m
    return None


def _ereignis_aus_args(args):
    for a in args or ():
        if getattr(a, "Name", None) == "EventName":
            return a.Value
        if getattr(a, "Name", None) == "Environment":
            e = _ereignis_aus_args(a.Value)
            if e:
                return e
    return None


def _ist_versteckt(doc):
    try:
        return any(p.Name == "Hidden" and p.Value for p in doc.getArgs())
    except Exception:
        return False


def aktualisiere_auto(ctx, doc):
    """Alle Abfragen mit „Beim Öffnen aktualisieren“ neu rechnen; Fehler werden gemeldet."""
    schluessel = doc.getURL() or str(id(doc))
    jetzt = time.time()
    if schluessel in _AUTO_LAEUFT or jetzt - _AUTO_ZULETZT.get(schluessel, 0) < 3:
        return
    _AUTO_LAEUFT.add(schluessel)
    try:
        ok, fehler = aktualisiere_alle(ctx, doc, nur_auto=True)
    finally:
        _AUTO_LAEUFT.discard(schluessel)
        _AUTO_ZULETZT[schluessel] = time.time()
    if fehler:
        try:
            parent = doc.getCurrentController().getFrame().getContainerWindow()
        except Exception:
            parent = None
        meldung(ctx, parent, "Beim automatischen Aktualisieren sind Fehler aufgetreten:\n  " + "\n  ".join(fehler),
                "WARNINGBOX")


class AutoJob(unohelper.Base, XJob, XServiceInfo):
    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self, args):
        try:
            doc = _modell_aus_args(args)
            if doc is None or not ist_calc(doc) or _ist_versteckt(doc):
                return None
            try:
                registriere_menue(doc)
            except Exception:
                traceback.print_exc()
            ereignis = _ereignis_aus_args(args)
            diag_global("Job: Ereignis %s" % ereignis)
            if ereignis in ("OnNew", "OnLoad", "OnViewCreated"):      # nur das Kontextmenü anmelden, nicht aktualisieren
                return None
            if not any(True for _ in gespeicherte_abfragen(doc)):
                return None
            aktualisiere_auto(self.ctx, doc)
        except Exception:
            traceback.print_exc()
        return None

    def getImplementationName(self):
        return JOB_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.task.Job",)


for _kl, _namen in ((_Aktion, ("actionPerformed",)), (_Auswahl, ("itemStateChanged",)),
                    (_Maus, ("mousePressed", "mouseReleased")), (_MausBew, ("mouseMoved", "mouseDragged")),
                    (_GridAuswahl, ("selectionChanged",)), (_Fenster, ("windowResized",)),
                    (_Taste, ("keyPressed",)), (_Fokus, ("focusGained",)), (_Strg, ("keyPressed",))):
    for _n in _namen:
        setattr(_kl, _n, _ohne_durchschlag(getattr(_kl, _n)))


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Handler, IMPL_NAME, ("com.sun.star.frame.ProtocolHandler",))
g_ImplementationHelper.addImplementation(AutoJob, JOB_NAME, ("com.sun.star.task.Job",))
