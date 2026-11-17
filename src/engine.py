# -*- coding: utf-8 -*-
"""
Abfrage-Engine: Tabellenumformung in Schritten (Power-Query-Stil).

Reines Python (nur Standardbibliothek), keine Abhängigkeit von LibreOffice.
Eine Abfrage besteht aus einer Rohtabelle und einer Liste von Schritten.
Jeder Schritt ist ein einfaches dict: {"op": "...", ...Parameter}.
"""
import copy
import csv
import datetime as dt
import io
import json
import math
import re
import unicodedata

VERSION = "0.2.0"


# --------------------------------------------------------------------------
# Fehler und Grundtypen
# --------------------------------------------------------------------------
class FormelFehler(Exception):
    """Fehler in einer Formel oder beim Umwandeln eines Werts."""


class StepError(Exception):
    """Fehler in einem Schritt; kennt die Nummer (ab 0) des Schritts."""

    def __init__(self, index, titel, meldung):
        super().__init__("Schritt %d (%s): %s" % (index + 1, titel, meldung))
        self.index = index
        self.titel = titel
        self.meldung = meldung


class FehlerWert(str):
    """Fehlerwert (z. B. #DIV/0! aus Calc): ein Text, den man vom normalen Text unterscheiden kann."""
    __slots__ = ()


def ist_fehler(v):
    return isinstance(v, FehlerWert)


class Waehrung(float):
    """Zahl mit Typ 'Währung' (auf 2 Stellen gerundet, Anzeige mit Tausenderpunkt). Rechnet wie ein float."""
    __slots__ = ()


class Prozent(float):
    """Zahl mit Typ 'Prozent' (Bruchteil, z. B. 0,125 = 12,50 %; auf 4 Stellen gerundet)."""
    __slots__ = ()


class Dezimal(float):
    """Dezimalzahl mit festen Anzeigestellen (nur Anzeige: der Wert selbst bleibt ungerundet)."""
    __slots__ = ("stellen",)


class ProzentA(Prozent):
    """Prozent mit festen Anzeigestellen (Stellen der Prozentzahl, nur Anzeige)."""
    __slots__ = ("stellen",)


def mit_stellen(x, n, prozent=False):
    v = ProzentA(x) if prozent else Dezimal(x)
    v.stellen = max(0, min(15, int(n)))
    return v


def ist_leer(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


class Tabelle:
    def __init__(self, spalten, zeilen):
        self.spalten = [str(s) for s in spalten]
        n = len(self.spalten)
        self.zeilen = []
        for z in zeilen:
            z = list(z)
            if len(z) < n:
                z += [None] * (n - len(z))
            elif len(z) > n:
                z = z[:n]
            self.zeilen.append(z)

    def kopie(self):
        return Tabelle(self.spalten, [list(z) for z in self.zeilen])

    def idx(self, name):
        if name in self.spalten:
            return self.spalten.index(name)
        low = [s.casefold() for s in self.spalten]
        if str(name).casefold() in low:
            return low.index(str(name).casefold())
        raise FormelFehler("Spalte '%s' nicht gefunden. Vorhanden: %s"
                           % (name, ", ".join(self.spalten) or "(keine)"))

    def idxs(self, namen):
        return [self.idx(n) for n in namen]


def eindeutige_namen(namen):
    """Leere Namen -> SpalteN, doppelte -> Name.1, Name.2 (wie Power Query)."""
    ergebnis, gesehen = [], set()
    for i, n in enumerate(namen):
        n = "" if n is None else str(n).strip()
        if n == "":
            n = "Spalte%d" % (i + 1)
        basis, k, kand = n, 0, n
        while kand in gesehen:
            k += 1
            kand = "%s.%d" % (basis, k)
        gesehen.add(kand)
        ergebnis.append(kand)
    return ergebnis


# --------------------------------------------------------------------------
# Zahlen, Daten, Text: Umwandlung und Formatierung
# --------------------------------------------------------------------------
_WAEHRUNG = re.compile(r"[€$£¥]|\bEUR\b|\bUSD\b|\bCHF\b|\bGBP\b", re.I)
_RE_ZAHL = {
    "de": re.compile(r"^[+-]?(\d{1,3}(\.\d{3})+|\d*)(,\d*)?$"),
    "en": re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d*)(\.\d*)?$"),
}
EXCEL_EPOCHE = dt.datetime(1899, 12, 30)


def parse_zahl(wert, ort="de"):
    """Text -> int/float. Strenge Prüfung, damit '12.5' im deutschen Format
    nicht stillschweigend 125 wird."""
    if isinstance(wert, bool):
        return int(wert)
    if isinstance(wert, (int, float)):
        return wert
    if isinstance(wert, (dt.datetime, dt.date, dt.time)):
        raise FormelFehler("'%s' ist keine Zahl" % wert)
    s = str(wert).strip()
    if s == "":
        raise FormelFehler("leerer Text ist keine Zahl")
    s = _WAEHRUNG.sub("", s).replace("\xa0", "").replace(" ", "").replace("'", "")
    neg, prozent = False, False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.endswith("%"):
        prozent, s = True, s[:-1]
    muster = _RE_ZAHL["en" if ort == "en" else "de"]
    if not muster.match(s) or not re.search(r"\d", s):
        raise FormelFehler("'%s' ist keine Zahl (Gebietsschema %s)" % (wert, ort))
    if ort == "en":
        s = s.replace(",", "")
    else:
        s = s.replace(".", "").replace(",", ".")
    if s.startswith("+"):
        s = s[1:]
    f = float(s)
    if neg:
        f = -f
    if prozent:
        f /= 100.0
    return int(f) if f.is_integer() and abs(f) < 1e15 and "." not in s and not prozent else f


_DATUM_DE = ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y",
             "%d.%m.%y %H:%M:%S", "%d.%m.%y %H:%M", "%d.%m.%y",
             "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
             "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]
_DATUM_EN = ["%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p",
             "%m/%d/%Y %H:%M", "%m/%d/%Y", "%m/%d/%y",
             "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
             "%Y-%m-%d"]
_ZEIT = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"]


def seriennummer_zu_datetime(x):
    return EXCEL_EPOCHE + dt.timedelta(days=float(x))


def datetime_zu_serie(d):
    if isinstance(d, dt.datetime):
        delta = d - EXCEL_EPOCHE
    elif isinstance(d, dt.date):
        delta = dt.datetime.combine(d, dt.time()) - EXCEL_EPOCHE
    else:
        raise FormelFehler("kein Datum")
    return delta.days + delta.seconds / 86400.0 + delta.microseconds / 86400e6


def parse_datum(wert, ort="de", mit_zeit=False):
    """-> datetime (mit_zeit) oder date."""
    if isinstance(wert, dt.datetime):
        return wert if mit_zeit else wert.date()
    if isinstance(wert, dt.date):
        return dt.datetime.combine(wert, dt.time()) if mit_zeit else wert
    if isinstance(wert, (int, float)) and not isinstance(wert, bool):
        d = seriennummer_zu_datetime(wert)
        return d if mit_zeit else d.date()
    s = str(wert).strip()
    if s == "":
        raise FormelFehler("leerer Text ist kein Datum")
    for fmt in (_DATUM_EN if ort == "en" else _DATUM_DE):
        try:
            d = dt.datetime.strptime(s, fmt)
            return d if mit_zeit else d.date()
        except ValueError:
            continue
    raise FormelFehler("'%s' ist kein Datum (Gebietsschema %s)" % (wert, ort))


def parse_zeit(wert, ort="de"):
    if isinstance(wert, dt.time):
        return wert
    if isinstance(wert, dt.datetime):
        return wert.time()
    if isinstance(wert, (int, float)) and not isinstance(wert, bool):
        return seriennummer_zu_datetime(float(wert) % 1).time()
    s = str(wert).strip()
    for fmt in _ZEIT:
        try:
            return dt.datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise FormelFehler("'%s' ist keine Uhrzeit" % wert)


def parse_bool(wert):
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    s = str(wert).strip().casefold()
    if s in ("wahr", "true", "ja", "yes", "1", "x", "j", "y"):
        return True
    if s in ("falsch", "false", "nein", "no", "0", "n"):
        return False
    raise FormelFehler("'%s' ist kein Ja/Nein-Wert" % wert)


def zahl_zu_text(v, ort="de"):
    if isinstance(v, bool):
        return "WAHR" if v else "FALSCH"
    if isinstance(v, int):
        return str(v)
    if v != v:
        return "#ZAHL!"
    if v in (float("inf"), float("-inf")):
        return "#ZAHL!"
    if isinstance(v, Dezimal):
        t = format(round(float(v), v.stellen), ".%df" % v.stellen)
        return t.replace(".", ",") if ort != "en" else t
    if isinstance(v, (Waehrung, Prozent)):
        zahl = v * 100 if isinstance(v, Prozent) else v
        st = v.stellen if isinstance(v, ProzentA) else 2
        t = format(round(zahl, st), ",.%df" % st)               # 1,234.50
        t = t.replace(",", "\x00").replace(".", "," if ort != "en" else ".").replace("\x00", "." if ort != "en" else ",")
        return t + " %" if isinstance(v, Prozent) else t
    s = format(v, ".15g")
    if "e" in s:
        s = format(v, "f").rstrip("0").rstrip(".")
    return s.replace(".", ",") if ort != "en" else s


def datum_zu_text(v, ort="de"):
    if isinstance(v, dt.datetime):
        if ort == "en":
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return v.strftime("%d.%m.%Y %H:%M:%S")
    if isinstance(v, dt.date):
        return v.strftime("%Y-%m-%d") if ort == "en" else v.strftime("%d.%m.%Y")
    if isinstance(v, dt.time):
        return v.strftime("%H:%M:%S")
    return str(v)


def als_text(v, ort="de"):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (dt.date, dt.time)):
        return datum_zu_text(v, ort)
    return zahl_zu_text(v, ort)


def format_text(v, muster):
    """TEXT()-Funktion: Zahlen- und Datumsmuster nach deutscher Schreibweise."""
    if isinstance(v, (dt.date, dt.time)):
        if isinstance(v, dt.time):
            v = dt.datetime.combine(dt.date(2000, 1, 1), v)
        elif not isinstance(v, dt.datetime):
            v = dt.datetime.combine(v, dt.time())

        def ers(m):
            t = m.group(0)
            return {"JJJJ": "%Y", "JJ": "%y", "TT": "%d", "MM": "%m", "hh": "%H",
                    "HH": "%H", "mm": "%M", "ss": "%S", "SS": "%S"}.get(t, t)
        fmt = re.sub(r"JJJJ|JJ|TT|MM|hh|HH|mm|ss|SS", ers, muster)
        return v.strftime(fmt)
    zahl = parse_zahl(v) if isinstance(v, str) else v
    prozent = muster.strip().endswith("%")
    if prozent:
        zahl = zahl * 100
    kern = muster.replace("%", "").strip()
    dez = len(re.sub(r"[^0#]", "", kern.split(",")[1])) if "," in kern else 0
    tausend = "." in kern.split(",")[0] if "." in kern else False
    min_stellen = len(re.sub(r"[^0]", "", kern.split(",")[0].replace(".", "")))
    s = ("{:,.%df}" % dez).format(abs(zahl)) if tausend else ("{:.%df}" % dez).format(abs(zahl))
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    ganz = s.split(",")[0].replace(".", "")
    if len(ganz) < min_stellen:
        s = ("0" * (min_stellen - len(ganz))) + s
    if zahl < 0 and float(s.replace(".", "").replace(",", ".") or 0) != 0:
        s = "-" + s
    return s + ("%" if prozent else "")


# --------------------------------------------------------------------------
# Typ-Umwandlung
# --------------------------------------------------------------------------
TYPEN = [("text", "Text"), ("ganzzahl", "Ganzzahl"), ("dezimal", "Dezimalzahl"),
         ("waehrung", "Währung (Tausenderpunkt, 2 Nachkommastellen)"),
         ("prozent", "Prozent (2 Nachkommastellen)"),
         ("datum", "Datum"), ("datumzeit", "Datum und Uhrzeit"), ("zeit", "Uhrzeit"),
         ("bool", "Ja/Nein")]


def in_typ(v, typ, ort="de"):
    if ist_leer(v) and typ != "text":
        return None
    if v is None:
        return None
    if typ == "text":
        return als_text(v, ort)
    if typ == "ganzzahl":
        f = parse_zahl(v, ort)
        return int(math.floor(abs(f) + 0.5)) * (1 if f >= 0 else -1)
    if typ == "dezimal":
        return float(parse_zahl(v, ort))
    if typ == "waehrung":
        return Waehrung(round(float(parse_zahl(v, ort)), 2))
    if typ == "prozent":
        f = float(parse_zahl(v, ort))      # "12,5 %" -> 0,125 (parse_zahl teilt bei %-Zeichen durch 100); Zahl ohne % bleibt unverändert
        return Prozent(round(f, 4))
    if typ == "datum":
        return parse_datum(v, ort, False)
    if typ == "datumzeit":
        return parse_datum(v, ort, True)
    if typ == "zeit":
        return parse_zeit(v, ort)
    if typ == "bool":
        return parse_bool(v)
    raise FormelFehler("Unbekannter Typ '%s'" % typ)


# --------------------------------------------------------------------------
# Parameter aus Tabellenzellen: {Name} (benannte Zelle der Datei)
# --------------------------------------------------------------------------
PARAMETER = {"fn": None}      # fn(name) -> Wert (Zahl, Text, Datum); setzt die Oberfläche
_PAR = re.compile(r"\{([^{}]+)\}")


def hole_parameter(name):
    name = str(name).strip()
    fn = PARAMETER.get("fn")
    if fn is None:
        raise FormelFehler("Parameter '%s': Parameter aus Zellen sind hier nicht verfügbar" % name)
    return fn(name)


def loese_parameter(step):
    """Kopie des Schritts, in der {Name} in Textfeldern durch den Zellwert ersetzt ist.
    Formelfelder bleiben unverändert: die Formel löst {Name} beim Übersetzen selbst auf (Zahl, Text, Datum)."""
    def hat(x):
        if isinstance(x, str):
            return "{" in x
        if isinstance(x, list):
            return any(hat(v) for v in x)
        if isinstance(x, dict):
            return any(hat(v) for v in x.values())
        return False
    if not hat(step):
        return step
    d = OPS.get(step.get("op")) or {}
    felder = {f["name"]: f["art"] for f in d.get("felder", [])}
    ort = step.get("ort", "de")

    def ers(text):
        return _PAR.sub(lambda m: als_text(hole_parameter(m.group(1)), ort), text)

    def walk(x, formel=False):
        if isinstance(x, str):
            return x if formel else ers(x)
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                f = ((k == "wert" and x.get("wert_art") == "formel") or (k == "dann" and x.get("dann_art") == "formel")
                     or (k == "sonst" and x.get("sonst_art") == "formel"))
                out[k] = walk(v, f)
            return out
        return x
    neu = dict(step)
    for name, art in felder.items():
        if name in step and art != "formel":
            neu[name] = walk(step[name])
        if art == "klauseln" and name in step:
            neu[name] = walk(step[name])
    if "sonst" in step and step.get("sonst_art") != "formel":
        neu["sonst"] = walk(step["sonst"])
    # Typgerechte Auflösung: Ja/Nein, Spaltenlisten und Auswahlfelder aus einem Parameter
    ganz = re.compile(r"^\s*\{[^{}]+\}\s*$")
    for f in d.get("felder", []):
        name, art = f["name"], f["art"]
        orig = step.get(name)
        if art == "ja_nein" and isinstance(orig, str) and "{" in orig:
            neu[name] = parse_bool(neu[name])
        elif art == "spalten" and isinstance(orig, list):
            teile = []
            for o, r in zip(orig, neu[name]):
                if isinstance(o, str) and ganz.match(o):          # {Liste}: Werte mit ; getrennt -> mehrere Spalten
                    teile += [x.strip() for x in str(r).split(";") if x.strip()]
                else:
                    teile.append(r)
            neu[name] = teile
        elif art == "wahl" and isinstance(orig, str) and "{" in orig:
            r = str(neu[name]).strip()
            paare = [(w[0], w[1]) if isinstance(w, (tuple, list)) else (w, w) for w in (f.get("wahl") or [])]
            treffer = [v for v, l in paare if r.casefold() in (str(v).casefold(), str(l).casefold())]
            if not treffer:
                raise FormelFehler("Der Parameterwert '%s' passt nicht zu '%s'. Erlaubt: %s"
                                   % (r, f["label"], ", ".join("%s (%s)" % (v, l) if v != l else str(v) for v, l in paare)))
            neu[name] = treffer[0]
    return neu


BED_VERGLEICHE = [("=", "ist gleich"), ("<>", "ist ungleich"), (">", "ist größer als"), (">=", "ist größer oder gleich"),
                  ("<", "ist kleiner als"), ("<=", "ist kleiner oder gleich"), ("enthält", "enthält (Text oder Liste)")]


def bedingung_erfuellt(b):
    """Schritt-Bedingung {parameter, vergleich, wert}: True = Schritt wird ausgeführt."""
    name = str(b.get("parameter") or "").strip()
    if not name:
        return True
    vgl = b.get("vergleich") or "="
    soll = str(b.get("wert") if b.get("wert") is not None else "")
    ist = hole_parameter(name)
    if vgl == "enthält":
        teile = [x.strip().casefold() for x in re.split(r"[;\n]", als_text(ist))]
        return soll.strip().casefold() in teile or soll.strip().casefold() in als_text(ist).casefold()
    if isinstance(ist, bool):
        a, c = ist, parse_bool(soll)
    elif isinstance(ist, dt.datetime):
        a, c = ist, parse_datum(soll, "de", True)
    elif isinstance(ist, dt.date):
        a, c = ist, parse_datum(soll, "de", False)
    elif isinstance(ist, dt.time):
        a, c = ist, parse_zeit(soll)
    elif isinstance(ist, (int, float)):
        a, c = float(ist), float(parse_zahl(soll))
    else:
        a, c = als_text(ist).strip().casefold(), soll.strip().casefold()
        try:                                    # Text, der wie Zahlen aussieht, numerisch vergleichen
            a2, c2 = float(parse_zahl(a)), float(parse_zahl(c))
            a, c = a2, c2
        except Exception:
            pass
    if vgl == "=":
        return a == c
    if vgl == "<>":
        return a != c
    if isinstance(a, bool):
        raise FormelFehler("Ja/Nein-Werte lassen sich nur mit „ist gleich“ oder „ist ungleich“ vergleichen")
    return {">": a > c, ">=": a >= c, "<": a < c, "<=": a <= c}[vgl]


# --------------------------------------------------------------------------
# Formel-Sprache (an Calc angelehnt, Argumente mit ; getrennt)
# --------------------------------------------------------------------------
_TOKEN = re.compile(r'''\s*(?:
    (?P<str>"(?:[^"]|"")*")
   |(?P<par>\{[^{}]+\})
   |(?P<col>\[[^\]]+\])
   |(?P<num>\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?|[.,]\d+)
   |(?P<id>[A-Za-zÄÖÜäöüß_][A-Za-zÄÖÜäöüß0-9_.]*)
   |(?P<op><>|<=|>=|[-+*/^&=<>();%])
  )''', re.X)


def _tokens(text):
    pos, out = 0, []
    text = text.strip()
    if text.startswith("="):
        text = text[1:]
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise FormelFehler("Unerwartetes Zeichen bei Position %d: '%s'"
                               % (pos + 1, text[pos:pos + 10].strip()))
        pos = m.end()
        for art in ("str", "par", "col", "num", "id", "op"):
            if m.group(art) is not None:
                out.append((art, m.group(art)))
                break
    return out


def _norm_name(n):
    n = n.upper()
    for a, b in (("Ä", "AE"), ("Ö", "OE"), ("Ü", "UE"), ("ß", "SS")):
        n = n.replace(a, b)
    return n


class _Parser:
    def __init__(self, tokens, tabelle):
        self.t, self.i, self.tab = tokens, 0, tabelle

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def nimm(self):
        tok = self.peek()
        self.i += 1
        return tok

    def erwarte(self, op):
        art, w = self.nimm()
        if not (art == "op" and w == op):
            raise FormelFehler("'%s' erwartet" % op)

    def parse(self):
        if not self.t:
            raise FormelFehler("Die Formel ist leer")
        node = self.vergleich()
        if self.i < len(self.t):
            raise FormelFehler("Unerwartet: '%s'" % self.t[self.i][1])
        return node

    def vergleich(self):
        n = self.verkette()
        while self.peek()[0] == "op" and self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.nimm()[1]
            n = ("bin", op, n, self.verkette())
        return n

    def verkette(self):
        n = self.summe()
        while self.peek() == ("op", "&"):
            self.nimm()
            n = ("bin", "&", n, self.summe())
        return n

    def summe(self):
        n = self.produkt()
        while self.peek()[0] == "op" and self.peek()[1] in ("+", "-"):
            op = self.nimm()[1]
            n = ("bin", op, n, self.produkt())
        return n

    def produkt(self):
        n = self.potenz()
        while self.peek()[0] == "op" and self.peek()[1] in ("*", "/"):
            op = self.nimm()[1]
            n = ("bin", op, n, self.potenz())
        return n

    def potenz(self):
        n = self.unaer()
        while self.peek() == ("op", "^"):
            self.nimm()
            n = ("bin", "^", n, self.unaer())
        return n

    def unaer(self):
        if self.peek()[0] == "op" and self.peek()[1] in ("-", "+"):
            op = self.nimm()[1]
            n = self.unaer()
            return ("neg", n) if op == "-" else n
        return self.nachsatz()

    def nachsatz(self):
        n = self.primaer()
        while self.peek() == ("op", "%"):
            self.nimm()
            n = ("bin", "/", n, ("lit", 100))
        return n

    def primaer(self):
        art, w = self.nimm()
        if art == "num":
            return ("lit", float(w.replace(",", ".")) if re.search(r"[.,eE]", w) else int(w))
        if art == "str":
            return ("lit", w[1:-1].replace('""', '"'))
        if art == "par":
            return ("lit", hole_parameter(w[1:-1]))
        if art == "col":
            return ("col", self.tab.idx(w[1:-1]))
        if art == "id":
            name = _norm_name(w)
            if self.peek() == ("op", "("):
                self.nimm()
                args = []
                if self.peek() == ("op", ")"):
                    self.nimm()
                else:
                    while True:
                        args.append(self.vergleich())
                        if self.peek() == ("op", ";"):
                            self.nimm()
                            continue
                        self.erwarte(")")
                        break
                if name not in FUNKTIONEN and name not in _LAZY:
                    raise FormelFehler("Unbekannte Funktion '%s'" % w)
                lo, hi = (FUNKTIONEN[name][1:3] if name in FUNKTIONEN else _LAZY[name])
                if len(args) < lo or (hi is not None and len(args) > hi):
                    raise FormelFehler("%s erwartet %s Argument(e)"
                                       % (w.upper(), ("%d" % lo) if lo == hi else
                                          ("mindestens %d" % lo if hi is None else "%d bis %d" % (lo, hi))))
                return ("call", name, args)
            if name in ("WAHR", "TRUE"):
                return ("lit", True)
            if name in ("FALSCH", "FALSE"):
                return ("lit", False)
            raise FormelFehler("'%s' ist weder Funktion noch Wert. Spaltennamen gehören in [eckige Klammern]." % w)
        if art == "op" and w == "(":
            n = self.vergleich()
            self.erwarte(")")
            return n
        raise FormelFehler("Unerwartetes Ende der Formel" if art is None else "Unerwartet: '%s'" % w)


def _zahl(v):
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        if v.strip() == "":
            return 0
        return parse_zahl(v)
    raise FormelFehler("'%s' ist keine Zahl" % (v,))


def _vgl_rang(v):
    if v is None:
        return (0, 0)
    if isinstance(v, bool):
        return (3, v)
    if isinstance(v, (int, float)):
        return (1, v)
    if isinstance(v, (dt.date, dt.datetime)):
        return (1, datetime_zu_serie(v))
    if isinstance(v, dt.time):
        return (1, (v.hour * 3600 + v.minute * 60 + v.second) / 86400.0)
    return (2, str(v).casefold())


def _vergleiche(a, b):
    """-1/0/1 nach Calc-Regeln (Text > Zahl > Wahrheitswert)."""
    if a is None and isinstance(b, str):
        a = ""
    if b is None and isinstance(a, str):
        b = ""
    if a is None:
        a = 0 if not isinstance(b, str) else ""
    if b is None:
        b = 0
    ra, rb = _vgl_rang(a), _vgl_rang(b)
    if ra[0] != rb[0]:
        return -1 if ra[0] < rb[0] else 1
    return (ra[1] > rb[1]) - (ra[1] < rb[1])


def _plus(a, b, vorz):
    if isinstance(a, dt.datetime) or isinstance(a, dt.date) and not isinstance(a, dt.datetime):
        if isinstance(b, (int, float)) and not isinstance(b, bool):
            return a + vorz * dt.timedelta(days=b)
        if vorz == -1 and isinstance(b, (dt.date, dt.datetime)):
            da, db = datetime_zu_serie(a), datetime_zu_serie(b)
            diff = da - db
            return int(diff) if float(diff).is_integer() else diff
    return _zahl(a) + vorz * _zahl(b)


def _auswerten(node, zeile):
    art = node[0]
    if art == "lit":
        return node[1]
    if art == "col":
        return zeile[node[1]]
    if art == "neg":
        return -_zahl(_auswerten(node[1], zeile))
    if art == "bin":
        op = node[1]
        a = _auswerten(node[2], zeile)
        b = _auswerten(node[3], zeile)
        if op == "&":
            return als_text(a) + als_text(b)
        if op == "+":
            return _plus(a, b, 1)
        if op == "-":
            return _plus(a, b, -1)
        if op == "*":
            return _zahl(a) * _zahl(b)
        if op == "/":
            nenner = _zahl(b)
            if nenner == 0:
                raise FormelFehler("Division durch 0")
            return _zahl(a) / nenner
        if op == "^":
            try:
                r = _zahl(a) ** _zahl(b)
            except (OverflowError, ZeroDivisionError):
                raise FormelFehler("Ungültige Potenz")
            if isinstance(r, complex):
                raise FormelFehler("Ungültige Potenz")
            return r
        c = _vergleiche(a, b)
        return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0,
                "<=": c <= 0, ">=": c >= 0}[op]
    if art == "call":
        name, args = node[1], node[2]
        if name in _LAZY:
            return _LAZY_FUNC[name](args, zeile)
        werte = [_auswerten(a, zeile) for a in args]
        return FUNKTIONEN[name][0](*werte)
    raise FormelFehler("Interner Fehler")


def _wenn(args, zeile):
    bed = _auswerten(args[0], zeile)
    if isinstance(bed, str):
        bed = parse_bool(bed)
    if bed:
        return _auswerten(args[1], zeile)
    return _auswerten(args[2], zeile) if len(args) > 2 else False


def _wennfehler(args, zeile):
    try:
        return _auswerten(args[0], zeile)
    except (FormelFehler, ValueError, ZeroDivisionError, OverflowError, TypeError):
        return _auswerten(args[1], zeile)


_LAZY = {"WENN": (2, 3), "IF": (2, 3), "WENNFEHLER": (2, 2), "IFERROR": (2, 2)}
_LAZY_FUNC = {"WENN": _wenn, "IF": _wenn, "WENNFEHLER": _wennfehler, "IFERROR": _wennfehler}


def _t(v):
    return als_text(v)


def _int_arg(v, minimum=None):
    n = int(_zahl(v))
    if minimum is not None and n < minimum:
        raise FormelFehler("Ungültiges Argument: %s" % n)
    return n


def _runden(x, n=0, modus="halb"):
    x, n = _zahl(x), int(_zahl(n))
    faktor = 10 ** n
    v = abs(x) * faktor
    if modus == "auf":
        r = math.ceil(v - 1e-9)
    elif modus == "ab":
        r = math.floor(v + 1e-9)
    else:
        r = math.floor(v + 0.5 + 1e-9)
    r = math.copysign(r / faktor, x) if x else 0.0
    return int(r) if n <= 0 and float(r).is_integer() else r


def _teil(text, start, n):
    s, a, b = _t(text), _int_arg(start), _int_arg(n, 0)
    if a < 1:
        raise FormelFehler("TEIL: Start muss mindestens 1 sein")
    return s[a - 1:a - 1 + b]


def _finden(such, text, start=1, ohne_gk=False):
    s, t = _t(such), _t(text)
    a = _int_arg(start, 1)
    if ohne_gk:
        pos = t.casefold().find(s.casefold(), a - 1)
    else:
        pos = t.find(s, a - 1)
    if pos < 0:
        raise FormelFehler("FINDEN: '%s' nicht gefunden" % s)
    return pos + 1


def _datum(j, m, t):
    j, m, t = int(_zahl(j)), int(_zahl(m)), int(_zahl(t))
    j += (m - 1) // 12
    m = (m - 1) % 12 + 1
    try:
        return dt.date(j, m, 1) + dt.timedelta(days=t - 1)
    except (ValueError, OverflowError):
        raise FormelFehler("DATUM: ungültige Angaben")


def _aus_datum(v):
    if ist_leer(v):
        raise FormelFehler("Datum erwartet, Zelle ist leer")
    if isinstance(v, (dt.date, dt.datetime)):
        return v
    if isinstance(v, dt.time):
        return dt.datetime.combine(dt.date(1899, 12, 30), v)
    return parse_datum(v, "de", True)


def _logisch(v):
    if v is None:
        return False
    return parse_bool(v) if isinstance(v, str) else bool(v)


def _und(*a):
    return all(_logisch(x) for x in a)


def _oder(*a):
    return any(_logisch(x) for x in a)


def _zahlen_liste(args):
    out = []
    for a in args:
        if a is None or (isinstance(a, str) and a.strip() == ""):
            continue
        out.append(_zahl(a))
    return out


def _sum(*a):
    return sum(_zahlen_liste(a))


def _mw(*a):
    z = _zahlen_liste(a)
    if not z:
        raise FormelFehler("MITTELWERT: keine Zahlen")
    return sum(z) / len(z)


def _max(*a):
    z = _zahlen_liste(a)
    return max(z) if z else 0


def _min(*a):
    z = _zahlen_liste(a)
    return min(z) if z else 0


def _glaetten(t):
    return re.sub(r" +", " ", _t(t)).strip()


def _saubern(t):
    return "".join(c for c in _t(t) if unicodedata.category(c)[0] != "C")


def _titel(t):
    return " ".join(w[:1].upper() + w[1:].lower() for w in _t(t).split(" "))


def _wert(t):
    if ist_leer(t):
        return 0
    return parse_zahl(t)


def _datwert(t):
    return parse_datum(_t(t), "de", False)


def _rest(a, b):
    b = _zahl(b)
    if b == 0:
        raise FormelFehler("REST: Division durch 0")
    return _zahl(a) - b * math.floor(_zahl(a) / b)


# name -> (funktion, min, max)  (max None = beliebig viele)
FUNKTIONEN = {
    "UND": (_und, 1, None), "AND": (_und, 1, None),
    "ODER": (_oder, 1, None), "OR": (_oder, 1, None),
    "NICHT": (lambda a: not _logisch(a), 1, 1), "NOT": (lambda a: not _logisch(a), 1, 1),
    "LINKS": (lambda t, n=1: _t(t)[:_int_arg(n, 0)], 1, 2),
    "LEFT": (lambda t, n=1: _t(t)[:_int_arg(n, 0)], 1, 2),
    "RECHTS": (lambda t, n=1: _t(t)[len(_t(t)) - _int_arg(n, 0):] if _int_arg(n, 0) else "", 1, 2),
    "RIGHT": (lambda t, n=1: _t(t)[len(_t(t)) - _int_arg(n, 0):] if _int_arg(n, 0) else "", 1, 2),
    "TEIL": (_teil, 3, 3), "MID": (_teil, 3, 3),
    "LAENGE": (lambda t: len(_t(t)), 1, 1), "LEN": (lambda t: len(_t(t)), 1, 1),
    "GROSS": (lambda t: _t(t).upper(), 1, 1), "UPPER": (lambda t: _t(t).upper(), 1, 1),
    "KLEIN": (lambda t: _t(t).lower(), 1, 1), "LOWER": (lambda t: _t(t).lower(), 1, 1),
    "GROSS2": (_titel, 1, 1), "PROPER": (_titel, 1, 1),
    "GLAETTEN": (_glaetten, 1, 1), "TRIM": (_glaetten, 1, 1),
    "SAEUBERN": (_saubern, 1, 1), "CLEAN": (_saubern, 1, 1),
    "WECHSELN": (lambda t, a, n: _t(t).replace(_t(a), _t(n)) if _t(a) != "" else _t(t), 3, 3),
    "SUBSTITUTE": (lambda t, a, n: _t(t).replace(_t(a), _t(n)) if _t(a) != "" else _t(t), 3, 3),
    "FINDEN": (lambda s, t, a=1: _finden(s, t, a, False), 2, 3),
    "FIND": (lambda s, t, a=1: _finden(s, t, a, False), 2, 3),
    "SUCHEN": (lambda s, t, a=1: _finden(s, t, a, True), 2, 3),
    "SEARCH": (lambda s, t, a=1: _finden(s, t, a, True), 2, 3),
    "VERKETTEN": (lambda *a: "".join(_t(x) for x in a), 1, None),
    "CONCAT": (lambda *a: "".join(_t(x) for x in a), 1, None),
    "WIEDERHOLEN": (lambda t, n: _t(t) * _int_arg(n, 0), 2, 2),
    "RUNDEN": (lambda x, n=0: _runden(x, n), 1, 2), "ROUND": (lambda x, n=0: _runden(x, n), 1, 2),
    "AUFRUNDEN": (lambda x, n=0: _runden(x, n, "auf"), 1, 2),
    "ABRUNDEN": (lambda x, n=0: _runden(x, n, "ab"), 1, 2),
    "ABS": (lambda x: abs(_zahl(x)), 1, 1),
    "GANZZAHL": (lambda x: int(math.floor(_zahl(x))), 1, 1),
    "INT": (lambda x: int(math.floor(_zahl(x))), 1, 1),
    "REST": (_rest, 2, 2), "MOD": (_rest, 2, 2),
    "ISTGERADE": (lambda x: int(_zahl(x)) % 2 == 0, 1, 1), "ISEVEN": (lambda x: int(_zahl(x)) % 2 == 0, 1, 1),
    "ISTUNGERADE": (lambda x: int(_zahl(x)) % 2 == 1, 1, 1), "ISODD": (lambda x: int(_zahl(x)) % 2 == 1, 1, 1),
    "VORZEICHEN": (lambda x: (_zahl(x) > 0) - (_zahl(x) < 0), 1, 1), "SIGN": (lambda x: (_zahl(x) > 0) - (_zahl(x) < 0), 1, 1),
    "SUMME": (_sum, 1, None), "SUM": (_sum, 1, None),
    "MITTELWERT": (_mw, 1, None), "AVERAGE": (_mw, 1, None),
    "MAX": (_max, 1, None), "MIN": (_min, 1, None),
    "WERT": (_wert, 1, 1), "VALUE": (_wert, 1, 1),
    "TEXT": (lambda x, f: "" if x is None else format_text(x, _t(f)), 2, 2),
    "DATUM": (_datum, 3, 3), "DATE": (_datum, 3, 3),
    "JAHR": (lambda d: _aus_datum(d).year, 1, 1), "YEAR": (lambda d: _aus_datum(d).year, 1, 1),
    "MONAT": (lambda d: _aus_datum(d).month, 1, 1), "MONTH": (lambda d: _aus_datum(d).month, 1, 1),
    "TAG": (lambda d: _aus_datum(d).day, 1, 1), "DAY": (lambda d: _aus_datum(d).day, 1, 1),
    "STUNDE": (lambda d: getattr(_aus_datum(d), "hour", 0), 1, 1),
    "MINUTE": (lambda d: getattr(_aus_datum(d), "minute", 0), 1, 1),
    "WOCHENTAG": (lambda d, typ=1: (_aus_datum(d).weekday() + 1) if int(_zahl(typ)) == 2
                  else ((_aus_datum(d).weekday() + 1) % 7 + 1), 1, 2),
    "HEUTE": (lambda: dt.date.today(), 0, 0), "TODAY": (lambda: dt.date.today(), 0, 0),
    "JETZT": (lambda: dt.datetime.now().replace(microsecond=0), 0, 0),
    "DATWERT": (_datwert, 1, 1), "DATEVALUE": (_datwert, 1, 1),
    "ISTLEER": (lambda x: ist_leer(x), 1, 1), "ISBLANK": (lambda x: ist_leer(x), 1, 1),
    "ISTZAHL": (lambda x: isinstance(x, (int, float)) and not isinstance(x, bool), 1, 1),
    "ISTTEXT": (lambda x: isinstance(x, str), 1, 1),
}


def kompiliere_formel(text, tabelle):
    """Formeltext -> Funktion zeile -> Wert. Wirft FormelFehler bei Syntaxfehlern."""
    baum = _Parser(_tokens(text), tabelle).parse()
    return lambda zeile: _auswerten(baum, zeile)


def werte_formel(text, tabelle, zeile):
    return kompiliere_formel(text, tabelle)(zeile)


# --------------------------------------------------------------------------
# Operationen (Schritte)
# --------------------------------------------------------------------------
OPS = {}   # op -> dict(titel, gruppe, felder, vorlage, func)
GRUPPEN = ["Zeilen", "Spalten", "Text und Werte", "Standardoperationen", "Neue Spalten", "Gruppieren und Drehen", "Typen", "Tabellen"]

BEDINGUNGEN = [
    ("gleich", "ist gleich"), ("ungleich", "ist ungleich"),
    ("enthaelt", "enthält"), ("enthaelt_nicht", "enthält nicht"),
    ("beginnt_mit", "beginnt mit"), ("endet_mit", "endet mit"),
    ("groesser", "ist größer als"), ("groesser_gleich", "ist größer oder gleich"),
    ("kleiner", "ist kleiner als"), ("kleiner_gleich", "ist kleiner oder gleich"),
    ("leer", "ist leer"), ("nicht_leer", "ist nicht leer"),
    ("gerade", "ist gerade (Zahl)"), ("ungerade", "ist ungerade (Zahl)"),
    ("positiv", "ist positiv (Zahl > 0)"), ("negativ", "ist negativ (Zahl < 0)"), ("null", "ist null (Zahl = 0)"),
    ("in_liste", "ist eines von (mit ; getrennt)"),
]
ZAHL_BED = ("gerade", "ungerade", "positiv", "negativ", "null")
OHNE_WERT = ("leer", "nicht_leer") + ZAHL_BED          # Bedingungen ohne Vergleichswert
ORTE = [("de", "Deutsch (1.234,56 / TT.MM.JJJJ)"), ("en", "Englisch (1,234.56 / MM/DD/YYYY)")]
FEHLER_WAHL = [("stoppen", "Mit Fehlermeldung abbrechen"), ("leer", "Fehlerhafte Werte leer lassen"),
               ("fehler", "Fehlerwert einsetzen (später ersetzbar)"),
               ("behalten", "Fehlerhafte Werte unverändert lassen")]


def F(name, label, art, **kw):
    d = {"name": name, "label": label, "art": art}
    d.update(kw)
    return d


def operation(op, titel, gruppe, felder, vorlage):
    def deko(func):
        OPS[op] = {"titel": titel, "gruppe": gruppe, "felder": felder,
                   "vorlage": vorlage, "func": func}
        return func
    return deko


def _wahl_label(felddef, wert):
    for w, l in felddef.get("wahl", []):
        if w == wert:
            return l
    return wert


def beschreibe(step):
    """Lesbarer deutscher Text für die Schrittliste (mit Bedingung, falls gesetzt)."""
    t = _beschreibe(step)
    b = step.get("nur_wenn")
    if isinstance(b, dict) and b.get("parameter"):
        t += "  [nur wenn {%s} %s %s]" % (b["parameter"], b.get("vergleich") or "=", b.get("wert", ""))
    return t


def _beschreibe(step):
    step = normalisiere_schritt(step)
    d = OPS.get(step.get("op"))
    if not d:
        return "Unbekannter Schritt: %s" % step.get("op")
    werte = {}
    for f in d["felder"]:
        w = step.get(f["name"], f.get("standard"))
        if f["art"] == "spalten":
            w = ", ".join(w or []) or "(alle)"
        elif f["art"] == "wahl":
            w = _wahl_label(f, w)
        elif f["art"] == "ja_nein":
            w = "ja" if w else "nein"
        elif f["art"] == "aggregation":
            w = ", ".join(("%s(%s)" % (AGG_LABEL.get(a.get("fn"), a.get("fn")), a.get("spalte") or "*"))
                          for a in (w or []) if a.get("fn")) or "(keine)"
        elif f["art"] == "textblock":
            if f.get("anzeige") == "umbenennung":
                w = "%d Spalte(n)" % len([1 for l in str(w or "").splitlines()
                                          if "=" in l and l.split("=", 1)[0].strip() != l.split("=", 1)[1].strip()])
            else:
                w = "%d Zeile(n)" % len([l for l in str(w or "").splitlines() if l.strip()])
        elif f["art"] == "klauseln":
            kl, _, _ = normalisiere_bedingt(step)
            w = "%d Klausel(n) + Sonst" % len(kl)
        elif f["art"] == "schluessel":
            w = ", ".join("%s = %s" % (p.get("links"), p.get("rechts")) for p in (w or [])) or "(kein Schlüssel)"
        elif f["art"] in ("abfragenliste", "spalten_rechts"):
            w = ", ".join(w or []) or "(alle)"
        elif f["art"] == "liste":
            w = ", ".join(("(leer)" if x == "" else str(x)) for x in (w or []))
            w = w if len(w) <= 60 else w[:57] + "..."
        elif f["art"] == "listenparam":
            w = ("{%s}" % w) if w else ""
        elif w is None:
            w = ""
        werte[f["name"]] = w
    if step.get("listenparameter") and "werte" in werte:
        werte["werte"] = "Liste {%s}" % step["listenparameter"]
    try:
        return d["vorlage"].format(**werte)
    except (KeyError, IndexError):
        return d["titel"]


def _pflichtfelder_pruefen(step, d):
    for f in d["felder"]:
        if f.get("optional"):
            continue
        w = step.get(f["name"], f.get("standard"))
        if f["art"] == "liste" and not w and not step.get("listenparameter"):
            raise FormelFehler("Bitte mindestens einen Wert auswählen")
        if f["art"] in ("spalte", "spalten", "text", "formel", "textblock") and (w is None or w == "" or w == []):
            if f["art"] == "text" and f.get("leer_ok"):
                continue
            raise FormelFehler("Bitte '%s' angeben" % f["label"])


def _spalten_liste(tab, step, name="spalten", alle_wenn_leer=False):
    namen = step.get(name) or []
    if not namen and alle_wenn_leer:
        return list(range(len(tab.spalten)))
    return tab.idxs(namen)


def _zahl_param(step, name, standard=0):
    try:
        v = step.get(name, standard)
        if v is None or v == "":
            v = standard
        return int(float(str(v).replace(",", ".")))
    except ValueError:
        raise FormelFehler("'%s' muss eine ganze Zahl sein" % name)


# --- Zeilen ---------------------------------------------------------------
@operation("zeilen_entfernen_oben", "Obere Zeilen entfernen", "Zeilen",
           [F("anzahl", "Anzahl Zeilen", "zahl", standard=1)],
           "Obere {anzahl} Zeile(n) entfernt")
def _op_oben(tab, s):
    n = _zahl_param(s, "anzahl", 1)
    return Tabelle(tab.spalten, tab.zeilen[max(n, 0):])


@operation("zeilen_entfernen_unten", "Untere Zeilen entfernen", "Zeilen",
           [F("anzahl", "Anzahl Zeilen", "zahl", standard=1)],
           "Untere {anzahl} Zeile(n) entfernt")
def _op_unten(tab, s):
    n = _zahl_param(s, "anzahl", 1)
    return Tabelle(tab.spalten, tab.zeilen[:len(tab.zeilen) - n] if n > 0 else tab.zeilen)


@operation("zeilen_behalten_oben", "Obere Zeilen beibehalten", "Zeilen",
           [F("anzahl", "Anzahl Zeilen", "zahl", standard=100)],
           "Nur die ersten {anzahl} Zeile(n) beibehalten")
def _op_behalten_oben(tab, s):
    n = _zahl_param(s, "anzahl", 100)
    return Tabelle(tab.spalten, tab.zeilen[:max(n, 0)])


@operation("leere_zeilen_entfernen", "Leere Zeilen entfernen", "Zeilen",
           [F("spalten", "Nur diese Spalten prüfen (leer = alle)", "spalten", optional=True)],
           "Leere Zeilen entfernt (Prüfung: {spalten})")
def _op_leere_zeilen(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    return Tabelle(tab.spalten, [z for z in tab.zeilen if not all(ist_leer(z[i]) for i in idx)])


@operation("duplikate_entfernen", "Doppelte Werte entfernen", "Zeilen",
           [F("spalten", "Spalten für den Vergleich (leer = alle)", "spalten", optional=True)],
           "Duplikate entfernt (Vergleich: {spalten})")
def _op_duplikate(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    gesehen, aus = set(), []
    for z in tab.zeilen:
        schluessel = tuple(_hash_wert(z[i]) for i in idx)
        if schluessel not in gesehen:
            gesehen.add(schluessel)
            aus.append(z)
    return Tabelle(tab.spalten, aus)

@operation("duplikate_behalten", "Doppelte Werte beibehalten", "Zeilen",
           [F("spalten", "Spalten für den Vergleich (leer = alle)", "spalten", optional=True)],
           "Nur doppelte Werte beibehalten (Vergleich: {spalten})")
def _op_duplikate_behalten(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    schluessel = [tuple(_hash_wert(z[i]) for i in idx) for z in tab.zeilen]
    anzahl = {}
    for k in schluessel:
        anzahl[k] = anzahl.get(k, 0) + 1
    return Tabelle(tab.spalten, [z for z, k in zip(tab.zeilen, schluessel) if anzahl[k] > 1])


def _hash_wert(v):
    if isinstance(v, str):
        return ("s", v)
    if v is None:
        return ("n", None)
    return ("v", v)


def _vergleichswert(zelle, text, ort="de"):
    """Filterwert in den Typ der Zelle bringen."""
    if text is None:
        return None
    if isinstance(zelle, bool):
        return parse_bool(text)
    if isinstance(zelle, (int, float)):
        return parse_zahl(text, ort)
    if isinstance(zelle, dt.datetime):
        return parse_datum(text, ort, True)
    if isinstance(zelle, dt.date):
        return parse_datum(text, ort, False)
    if isinstance(zelle, dt.time):
        return parse_zeit(text, ort)
    return str(text)


def _zahl_oder_none(v):
    """Zahl der Zelle (auch Text wie '12,5'); None bei leer, Fehlerwert, Wahrheitswert oder Nicht-Zahl."""
    if v is None or isinstance(v, (bool, FehlerWert)):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return parse_zahl(v) if v.strip() != "" else None
        except FormelFehler:
            return None
    return None


def trifft_zu(zelle, bedingung, wert, ignoriere_gk=True, ort="de"):
    if bedingung == "leer":
        return ist_leer(zelle)
    if bedingung == "nicht_leer":
        return not ist_leer(zelle)
    if bedingung in ZAHL_BED:
        n = _zahl_oder_none(zelle)
        if n is None:
            return False
        if bedingung == "positiv":
            return n > 0
        if bedingung == "negativ":
            return n < 0
        if bedingung == "null":
            return n == 0
        if n != int(n):
            return False                       # 2,5 ist weder gerade noch ungerade
        return int(n) % 2 == (0 if bedingung == "gerade" else 1)
    if bedingung == "in_liste":
        teile = [t.strip() for t in str(wert or "").split(";")]
        return any(trifft_zu(zelle, "gleich", t, ignoriere_gk, ort) for t in teile)
    if zelle is None:
        return bedingung in ("ungleich", "enthaelt_nicht") if wert not in (None, "") else bedingung in ("gleich", "enthaelt")
    text_bed = bedingung in ("enthaelt", "enthaelt_nicht", "beginnt_mit", "endet_mit")
    if text_bed:
        z, w = als_text(zelle, ort), str(wert or "")
        if ignoriere_gk:
            z, w = z.casefold(), w.casefold()
        erg = {"enthaelt": w in z, "enthaelt_nicht": w not in z,
               "beginnt_mit": z.startswith(w), "endet_mit": z.endswith(w)}[bedingung]
        return erg
    try:
        w = _vergleichswert(zelle, wert, ort)
    except FormelFehler:
        # Wert passt nicht zum Zelltyp -> als Text vergleichen
        w, zelle = str(wert), als_text(zelle, ort)
    z = zelle
    if isinstance(z, str) and isinstance(w, str) and ignoriere_gk:
        z, w = z.casefold(), w.casefold()
    elif isinstance(z, str) and isinstance(w, str):
        z, w = z.strip(), w.strip()
    if bedingung == "gleich":
        return z == w
    if bedingung == "ungleich":
        return z != w
    try:
        return {"groesser": z > w, "groesser_gleich": z >= w,
                "kleiner": z < w, "kleiner_gleich": z <= w}[bedingung]
    except TypeError:
        return False


@operation("filtern", "Zeilen filtern", "Zeilen",
           [F("spalte", "Spalte", "spalte"),
            F("bedingung", "Bedingung", "wahl", wahl=BEDINGUNGEN, standard="enthaelt"),
            F("wert", "Wert", "text", optional=True, zeige=("bedingung", OHNE_WERT, "nicht")),
            F("aktion", "Aktion", "wahl", wahl=[("behalten", "Passende Zeilen beibehalten"),
                                                  ("entfernen", "Passende Zeilen entfernen")],
              standard="behalten"),
            F("gross_klein", "Groß-/Kleinschreibung beachten", "ja_nein", standard=False,
              zeige=("bedingung", OHNE_WERT, "nicht")),
            F("ort", "Zahlen-/Datumsformat des Werts", "wahl", wahl=ORTE, standard="de",
              zeige=("bedingung", OHNE_WERT, "nicht"))],
           "{aktion}: {spalte} {bedingung} {wert}")
def _op_filtern(tab, s):
    i = tab.idx(s["spalte"])
    bed = s.get("bedingung", "gleich")
    wert = s.get("wert")
    if bed not in OHNE_WERT and (wert is None or wert == "") and bed != "gleich" \
            and bed != "ungleich":
        raise FormelFehler("Bitte einen Wert angeben")
    behalten = s.get("aktion", "behalten") == "behalten"
    ign = not s.get("gross_klein", False)
    ort = s.get("ort", "de")
    aus = [z for z in tab.zeilen if trifft_zu(z[i], bed, wert, ign, ort) == behalten]
    return Tabelle(tab.spalten, aus)


def werte_liste(wert):
    """Wert eines Parameters -> Liste von Texten: ein Text wird an ';' getrennt, alles andere ist ein einzelner Wert."""
    if isinstance(wert, str) and not isinstance(wert, FehlerWert):
        return [x.strip() for x in wert.split(";") if x.strip()]
    return [als_text(wert)]


@operation("filtern_werte", "Nach Einzelwerten filtern (Auswahlliste)", "Zeilen",
           [F("spalte", "Spalte", "spalte"),
            F("listenparameter", "Werte aus Parameter", "listenparam", optional=True),
            F("werte", "Werte", "liste"),
            F("aktion", "Aktion", "wahl", wahl=[("behalten", "Ausgewählte Werte beibehalten"),
                                                  ("entfernen", "Ausgewählte Werte entfernen")],
              standard="behalten")],
           "{aktion}: {spalte} = {werte}")
def _op_filtern_werte(tab, s):
    i = tab.idx(s["spalte"])
    if s.get("listenparameter"):
        werte = set(werte_liste(hole_parameter(s["listenparameter"])))      # Werte aus einem Listenparameter
        if not werte:
            raise FormelFehler("Der Parameter '%s' enthält keine Werte" % s["listenparameter"])
    else:
        werte = set(s.get("werte") or [])
    behalten = s.get("aktion", "behalten") == "behalten"
    return Tabelle(tab.spalten, [z for z in tab.zeilen
                                 if (("" if ist_leer(z[i]) else als_text(z[i])) in werte) == behalten])


def eindeutige_werte(tab, spalte, limit=2000):
    """Sortierte, eindeutige Anzeigewerte einer Spalte ('' = leer)."""
    i = tab.idx(spalte)
    menge = {}
    for z in tab.zeilen:
        v = z[i]
        t = "" if ist_leer(v) else als_text(v)
        if t not in menge:
            menge[t] = v
            if len(menge) >= limit:
                break
    return sorted(menge, key=lambda t: (t != "", _sortier_schluessel(menge[t]) if t else (0, 0)))


def _sortier_schluessel(v):
    if isinstance(v, bool):
        return (1, float(v))
    if isinstance(v, (int, float)):
        return (1, float(v))
    if isinstance(v, (dt.date, dt.datetime)):
        return (2, datetime_zu_serie(v))
    if isinstance(v, dt.time):
        return (3, v.hour * 3600 + v.minute * 60 + v.second)
    t = unicodedata.normalize("NFKD", str(v).casefold())
    return (4, "".join(c for c in t if not unicodedata.combining(c)))


RICHTUNG = [("auf", "Aufsteigend"), ("ab", "Absteigend")]


@operation("sortieren", "Zeilen sortieren", "Zeilen",
           [F("spalte1", "Sortieren nach", "spalte"),
            F("richtung1", "Richtung", "wahl", wahl=RICHTUNG, standard="auf"),
            F("spalte2", "Danach nach", "spalte", optional=True, block_vor=True),
            F("richtung2", "Richtung", "wahl", wahl=RICHTUNG, standard="auf"),
            F("spalte3", "Danach nach", "spalte", optional=True, block_vor=True),
            F("richtung3", "Richtung", "wahl", wahl=RICHTUNG, standard="auf")],
           "Sortiert nach {spalte1} ({richtung1}) {spalte2} {spalte3}")
def _op_sortieren(tab, s):
    krit = []
    for k in "123":
        name = s.get("spalte" + k)
        if name:
            krit.append((tab.idx(name), s.get("richtung" + k, "auf") == "ab"))
    zeilen = list(tab.zeilen)
    for i, absteigend in reversed(krit):
        mit = [z for z in zeilen if not ist_leer(z[i])]
        ohne = [z for z in zeilen if ist_leer(z[i])]
        mit.sort(key=lambda z: _sortier_schluessel(z[i]), reverse=absteigend)
        zeilen = mit + ohne
    return Tabelle(tab.spalten, zeilen)


@operation("fuellen_unten", "Nach unten ausfüllen", "Spalten",
           [F("spalten", "Spalten", "spalten")],
           "Nach unten ausgefüllt: {spalten}")
def _op_fuellen_unten(tab, s):
    idx = _spalten_liste(tab, s)
    neu = tab.kopie()
    for i in idx:
        letzte = None
        for z in neu.zeilen:
            if ist_leer(z[i]):
                if letzte is not None:
                    z[i] = letzte
            else:
                letzte = z[i]
    return neu


@operation("fuellen_oben", "Nach oben ausfüllen", "Spalten",
           [F("spalten", "Spalten", "spalten")],
           "Nach oben ausgefüllt: {spalten}")
def _op_fuellen_oben(tab, s):
    idx = _spalten_liste(tab, s)
    neu = tab.kopie()
    for i in idx:
        naechste = None
        for z in reversed(neu.zeilen):
            if ist_leer(z[i]):
                if naechste is not None:
                    z[i] = naechste
            else:
                naechste = z[i]
    return neu


@operation("erste_zeile_als_kopf", "Erste Zeile als Überschriften verwenden", "Zeilen", [],
           "Erste Zeile als Spaltenüberschriften verwendet")
def _op_kopf(tab, s):
    if not tab.zeilen:
        raise FormelFehler("Keine Zeile vorhanden")
    namen = [als_text(v) for v in tab.zeilen[0]]
    return Tabelle(eindeutige_namen(namen), tab.zeilen[1:])


@operation("kopf_als_erste_zeile", "Überschriften als erste Zeile", "Zeilen", [],
           "Überschriften in die erste Zeile verschoben")
def _op_kopf_zurueck(tab, s):
    n = len(tab.spalten)
    return Tabelle(["Spalte%d" % (i + 1) for i in range(n)], [list(tab.spalten)] + tab.zeilen)


# --- Spalten ---------------------------------------------------------------
@operation("spalten_entfernen", "Spalten entfernen", "Spalten",
           [F("spalten", "Spalten", "spalten")], "Spalten entfernt: {spalten}")
def _op_sp_entf(tab, s):
    weg = set(_spalten_liste(tab, s))
    behalt = [i for i in range(len(tab.spalten)) if i not in weg]
    return Tabelle([tab.spalten[i] for i in behalt], [[z[i] for i in behalt] for z in tab.zeilen])


@operation("spalten_behalten", "Spalten auswählen", "Spalten",
           [F("spalten", "Spalten", "spalten")], "Nur diese Spalten beibehalten: {spalten}")
def _op_sp_beh(tab, s):
    idx = _spalten_liste(tab, s)
    return Tabelle([tab.spalten[i] for i in idx], [[z[i] for i in idx] for z in tab.zeilen])


@operation("spalte_umbenennen", "Spalte umbenennen", "Spalten",
           [F("spalte", "Spalte", "spalte"), F("neu", "Neuer Name", "text")],
           "Spalte {spalte} umbenannt in {neu}")
def _op_umbenennen(tab, s):
    i = tab.idx(s["spalte"])
    neu = str(s["neu"]).strip()
    if neu == "":
        raise FormelFehler("Der neue Name darf nicht leer sein")
    if neu in tab.spalten and tab.spalten.index(neu) != i:
        raise FormelFehler("Eine Spalte '%s' gibt es schon" % neu)
    namen = list(tab.spalten)
    namen[i] = neu
    return Tabelle(namen, tab.zeilen)


POSITION = [("anfang", "An den Anfang"), ("ende", "Ans Ende"),
            ("vor", "Vor eine Spalte"), ("nach", "Hinter eine Spalte")]


@operation("spalten_verschieben", "Spalten verschieben", "Spalten",
           [F("spalten", "Spalten", "spalten"),
            F("position", "Wohin", "wahl", wahl=POSITION, standard="anfang"),
            F("ziel", "Zielspalte (bei vor/hinter)", "spalte", optional=True)],
           "Spalten verschoben ({position}): {spalten}")
def _op_verschieben(tab, s):
    idx = _spalten_liste(tab, s)
    pos = s.get("position", "anfang")
    rest = [i for i in range(len(tab.spalten)) if i not in idx]
    if pos == "anfang":
        neu = idx + rest
    elif pos == "ende":
        neu = rest + idx
    else:
        if not s.get("ziel"):
            raise FormelFehler("Bitte eine Zielspalte wählen")
        z = tab.idx(s["ziel"])
        if z in idx:
            raise FormelFehler("Die Zielspalte darf nicht selbst verschoben werden")
        p = rest.index(z) + (0 if pos == "vor" else 1)
        neu = rest[:p] + idx + rest[p:]
    return Tabelle([tab.spalten[i] for i in neu], [[z[i] for i in neu] for z in tab.zeilen])


@operation("spalte_duplizieren", "Spalte duplizieren", "Spalten",
           [F("spalte", "Spalte", "spalte"), F("neu", "Name der Kopie", "text")],
           "Spalte {spalte} dupliziert als {neu}")
def _op_dupl(tab, s):
    i = tab.idx(s["spalte"])
    return _anfuegen(tab, s["neu"], [z[i] for z in tab.zeilen], nach=i)


def _anfuegen(tab, name, werte, nach=None):
    name = str(name).strip()
    if name == "":
        raise FormelFehler("Der Spaltenname darf nicht leer sein")
    if name in tab.spalten:
        raise FormelFehler("Eine Spalte '%s' gibt es schon" % name)
    namen = list(tab.spalten)
    zeilen = [list(z) for z in tab.zeilen]
    pos = len(namen) if nach is None else nach + 1
    namen.insert(pos, name)
    for z, w in zip(zeilen, werte):
        z.insert(pos, w)
    return Tabelle(namen, zeilen)


# --- Sonderzeichen in Textfeldern: #(lf) Zeilenumbruch, #(cr) Wagenrücklauf, #(tab) Tabulator (wie in Power Query) ---
_SONDER = {"lf": "\n", "cr": "\r", "tab": "\t"}


def sonderzeichen(text):
    """„#(lf)“, „#(cr)“, „#(tab)“ in echte Zeichen umsetzen (Groß-/Kleinschreibung egal)."""
    t = "" if text is None else str(text)
    if "#(" not in t:
        return t
    return re.sub(r"#\((lf|cr|tab)\)", lambda m: _SONDER[m.group(1).lower()], t, flags=re.I)


# --- Text und Werte --------------------------------------------------------
def normalisiere_schritt(st):
    """Ältere Schritte an neue Felder anpassen (Werte ersetzen: eine Spalte -> mehrere)."""
    if st.get("op") == "ersetzen" and not st.get("spalten") and st.get("spalte"):
        st = dict(st)
        st["spalten"] = [st["spalte"]]
    return st


@operation("ersetzen", "Werte ersetzen", "Text und Werte",
           [F("spalten", "Spalten", "spalten"),
            F("suchen", "Suchen nach"+" (#(lf) = Zeilenumbruch, #(tab) = Tabulator)", "text", leer_ok=True),
            F("ersetzen_durch", "Ersetzen durch", "text", leer_ok=True, optional=True),
            F("ganze_zelle", "Nur ganze Zelle ersetzen", "ja_nein", standard=True),
            F("gross_klein", "Groß-/Kleinschreibung beachten", "ja_nein", standard=False)],
           "In {spalten}: '{suchen}' durch '{ersetzen_durch}' ersetzt")
def _op_ersetzen(tab, s):
    s = normalisiere_schritt(s)
    if not s.get("spalten"):
        raise FormelFehler("Bitte mindestens eine Spalte wählen")
    idx = tab.idxs(s["spalten"])
    such = sonderzeichen(s.get("suchen"))
    neu = sonderzeichen(s.get("ersetzen_durch"))
    ganze = s.get("ganze_zelle", False)
    gk = s.get("gross_klein", False)
    if such == "" and not ganze:
        raise FormelFehler("Bitte angeben, wonach gesucht werden soll")
    ergebnis = tab.kopie()
    muster = re.compile(re.escape(such), 0 if gk else re.I)
    for z in ergebnis.zeilen:
      for i in idx:
        v = z[i]
        if ganze:
            vt = als_text(v)
            if (vt == such) if gk else (vt.casefold() == such.casefold()):
                z[i] = neu if neu != "" else None
        elif isinstance(v, str):
            z[i] = muster.sub(lambda m: neu, v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            # Teiltext in einer Zahl: auf der Textform ersetzen; wieder Zahl, wenn das Ergebnis eine gültige Zahl ist
            t = muster.sub(lambda m: neu, als_text(v))
            if re.fullmatch(r"-?\d+(,\d+)?", t):
                z[i] = parse_zahl(t)
            else:
                z[i] = t
    return ergebnis


@operation("leere_ersetzen", "Leere Werte ersetzen", "Text und Werte",
           [F("spalten", "Spalten", "spalten"), F("wert", "Neuer Wert", "text", leer_ok=True)],
           "Leere Werte ersetzt durch '{wert}' in {spalten}")
def _op_leere_ers(tab, s):
    idx = _spalten_liste(tab, s)
    neu = tab.kopie()
    for z in neu.zeilen:
        for i in idx:
            if ist_leer(z[i]):
                z[i] = s.get("wert")
    return neu


TEXTART = [("trimmen", "Leerzeichen am Rand entfernen"), ("saubern", "Trimmen und Sonderzeichen entfernen"),
           ("gross", "GROSSBUCHSTABEN"), ("klein", "kleinbuchstaben"),
           ("titel", "Jedes Wort Groß")]


@operation("text_umwandeln", "Text umformatieren", "Text und Werte",
           [F("spalten", "Spalten", "spalten"), F("art", "Art", "wahl", wahl=TEXTART, standard="trimmen")],
           "Text umformatiert ({art}): {spalten}")
def _op_text(tab, s):
    idx = _spalten_liste(tab, s)
    art = s.get("art", "trimmen")
    f = {"trimmen": lambda t: t.strip(), "saubern": lambda t: _saubern(t).strip(),
         "gross": lambda t: t.upper(), "klein": lambda t: t.lower(), "titel": _titel}[art]
    neu = tab.kopie()
    for z in neu.zeilen:
        for i in idx:
            if isinstance(z[i], str):
                z[i] = f(z[i])
    return neu


@operation("praefix_suffix", "Präfix/Suffix hinzufügen", "Text und Werte",
           [F("spalten", "Spalten", "spalten"),
            F("praefix", "Präfix (vorn anfügen)" + " (#(lf) = Zeilenumbruch, #(tab) = Tabulator)", "text", leer_ok=True, optional=True),
            F("suffix", "Suffix (hinten anfügen)", "text", leer_ok=True, optional=True),
            F("leere_auslassen", "Leere Zellen nicht ändern", "ja_nein", standard=True)],
           "Präfix/Suffix in {spalten}: {praefix} … {suffix}")
def _op_praefix_suffix(tab, s):
    idx = _spalten_liste(tab, s)
    pre, suf = sonderzeichen(s.get("praefix")), sonderzeichen(s.get("suffix"))
    if pre == "" and suf == "":
        raise FormelFehler("Bitte ein Präfix oder ein Suffix angeben")
    auslassen = s.get("leere_auslassen", True) not in (False, "false", "nein")
    neu = tab.kopie()
    for z in neu.zeilen:
        for i in idx:
            v = z[i]
            if ist_fehler(v) or (auslassen and ist_leer(v)):
                continue
            z[i] = pre + als_text(v) + suf
    return neu


# --- Zahlen ------------------------------------------------------------------
RECHEN_OPS = [("addieren", "Addieren (Spalte + Operand)"), ("subtrahieren", "Subtrahieren (Spalte − Operand)"),
              ("multiplizieren", "Multiplizieren (Spalte × Operand)"), ("dividieren", "Dividieren (Spalte ÷ Operand)"),
              ("ganzzahlig", "Ganzzahlig dividieren (Spalte ÷ Operand, abgerundet)"),
              ("rest", "Rest der Division (Modulo)"), ("potenz", "Potenz (Spalte hoch Operand)"),
              ("prozent_von", "Prozent von (Spalte ÷ Operand × 100)"),
              ("prozentwert", "Prozentwert (Spalte × Operand ÷ 100)")]
OPERAND_ART = [("wert", "Fester Wert oder Parameter"), ("spalte", "Werte einer anderen Spalte")]


def _zelle_zahl(v):
    """Zahl einer Zelle für Rechenschritte; None = leer (bleibt leer); wirft ValueError bei Nicht-Zahl/Fehlerwert."""
    if ist_leer(v):
        return None
    if isinstance(v, bool) or ist_fehler(v):
        raise ValueError
    if isinstance(v, (int, float)):
        return v
    try:
        return parse_zahl(v)
    except FormelFehler:
        raise ValueError


def _typ_wie(vorlage, r):
    """Ergebnis r im Typ der Vorlage (Währung/Prozent bleiben erhalten); Gleitkommarauschen wird entfernt."""
    if isinstance(r, float):
        r = round(r, 10)
        if isinstance(vorlage, Waehrung):
            return Waehrung(round(r, 2))
        if isinstance(vorlage, Prozent):
            return Prozent(round(r, 4))
        if r == int(r) and abs(r) < 1e15 and isinstance(vorlage, int) and not isinstance(vorlage, bool):
            return int(r)
    return r


def _rechne(a, op, b):
    if op == "addieren":
        return a + b
    if op == "subtrahieren":
        return a - b
    if op == "multiplizieren":
        return a * b
    if op == "potenz":
        return a ** b
    if b == 0:
        raise ZeroDivisionError
    if op == "dividieren":
        return a / b
    if op == "ganzzahlig":
        return int(math.floor(a / b))
    if op == "rest":
        return a - b * math.floor(a / b)
    if op == "prozent_von":
        return a / b * 100
    if op == "prozentwert":
        return a * b / 100
    raise FormelFehler("Unbekannte Rechenart '%s'" % op)


def _neue_oder_ersetzte(tab, s, idx, werte_fn, name_neu):
    """Spalten ersetzen oder (bei genau einer Spalte und Namen) als neue Spalte hinter die Quellspalte setzen."""
    if name_neu:
        if len(idx) != 1:
            raise FormelFehler("Eine neue Spalte geht nur, wenn genau eine Spalte gewählt ist. Bei mehreren Spalten das Namensfeld leer lassen.")
        i = idx[0]
        return _anfuegen(tab, name_neu, [werte_fn(z, i) for z in tab.zeilen], nach=i)
    neu = tab.kopie()
    for z in neu.zeilen:
        for i in idx:
            z[i] = werte_fn(z, i)
    return neu


@operation("rechnen", "Rechnen", "Standardoperationen",
           [F("spalten", "Spalten", "spalten"),
            F("rechenart", "Rechenart", "wahl", wahl=RECHEN_OPS, standard="addieren"),
            F("operand_art", "Operand", "wahl", wahl=OPERAND_ART, standard="wert"),
            F("operand", "Wert (Zahl oder {Parameter})", "text", optional=True, zeige=("operand_art", ("wert",))),
            F("operand_spalte", "Spalte mit dem Operanden", "spalte", optional=True, zeige=("operand_art", ("spalte",))),
            F("neu", "Neue Spalte (leer = Spalten ersetzen)", "text", leer_ok=True, optional=True),
            F("ort", "Zahlenformat des Werts", "wahl", wahl=ORTE, standard="de", zeige=("operand_art", ("wert",)))],
           "Rechnen ({rechenart}): {spalten}")
def _op_rechnen(tab, s):
    idx = _spalten_liste(tab, s)
    op = s.get("rechenart", "addieren")
    if s.get("operand_art", "wert") == "spalte":
        if not s.get("operand_spalte"):
            raise FormelFehler("Bitte die Spalte mit dem Operanden wählen")
        bi = tab.idx(s["operand_spalte"])
        hole_b = lambda z: z[bi]
    else:
        t = "" if s.get("operand") is None else str(s.get("operand")).strip()
        if t == "":
            raise FormelFehler("Bitte einen Wert für die Rechnung angeben")
        try:
            fest = parse_zahl(t, s.get("ort", "de"))
        except FormelFehler:
            raise FormelFehler("„%s“ ist keine Zahl (Format %s)" % (t, "1.234,56" if s.get("ort", "de") == "de" else "1,234.56"))
        hole_b = lambda z: fest

    def zelle(z, i):
        a = z[i]
        try:
            x, y = _zelle_zahl(a), _zelle_zahl(hole_b(z))
        except ValueError:
            return FehlerWert("#WERT!")
        if x is None or y is None:
            return None if ist_leer(a) or hole_b(z) is None or ist_leer(hole_b(z)) else a
        try:
            r = _rechne(x, op, y)
            if op == "prozent_von":                       # Ergebnis ist ein Prozentwert -> Typ Prozent (Bruchteil)
                return Prozent(round(r / 100.0, 8))
            return _typ_wie(a, r)
        except ZeroDivisionError:
            return FehlerWert("#DIV/0!")
        except (OverflowError, ValueError):
            return FehlerWert("#ZAHL!")
    return _neue_oder_ersetzte(tab, s, idx, zelle, str(s.get("neu") or "").strip())


RUNDEN_ARTEN = [("halb", "Kaufmännisch runden (ab 5 auf)"), ("auf", "Aufrunden"), ("ab", "Abrunden")]


@operation("runden", "Runden", "Standardoperationen",
           [F("spalten", "Spalten", "spalten"),
            F("modus", "Art", "wahl", wahl=RUNDEN_ARTEN, standard="halb"),
            F("stellen", "Nachkommastellen", "zahl", standard=2),
            F("nur_anzeige", "Nur Anzeige (Wert bleibt ungerundet)", "ja_nein", standard=False),
            F("neu", "Neue Spalte (leer = Spalten ersetzen)", "text", leer_ok=True, optional=True)],
           "Runden ({modus}, {stellen} Stellen): {spalten}")
def _op_runden(tab, s):
    idx = _spalten_liste(tab, s)
    modus = s.get("modus", "halb")
    n = _zahl_param(s, "stellen", 2)
    nur = bool(s.get("nur_anzeige"))

    def zelle(z, i):
        a = z[i]
        try:
            x = _zelle_zahl(a)
        except ValueError:
            return FehlerWert("#WERT!")
        if x is None:
            return None
        prozent = isinstance(a, Prozent)
        if nur:
            if isinstance(a, Waehrung):
                return a                                  # Währung zeigt immer 2 Stellen
            return mit_stellen(x, max(n, 0), prozent)
        if prozent:
            return Prozent(_runden(x * 100, n, modus) / 100.0)
        r = _runden(x, n, modus)
        if isinstance(a, Waehrung):
            return Waehrung(r)
        return r
    return _neue_oder_ersetzte(tab, s, idx, zelle, str(s.get("neu") or "").strip())


ZAHL_EIGENSCHAFTEN = [("ist_gerade", "Ist gerade (Ja/Nein)"), ("ist_ungerade", "Ist ungerade (Ja/Nein)"),
                      ("vorzeichen", "Vorzeichen (−1, 0, 1)"), ("absolutwert", "Absolutwert (ohne Vorzeichen)")]


@operation("zahleneigenschaft", "Zahleneigenschaft (gerade, ungerade, Vorzeichen)", "Standardoperationen",
           [F("spalten", "Spalten", "spalten"),
            F("eigenschaft", "Eigenschaft", "wahl", wahl=ZAHL_EIGENSCHAFTEN, standard="ist_gerade"),
            F("neu", "Neue Spalte (leer = Spalten ersetzen)", "text", leer_ok=True, optional=True)],
           "Zahleneigenschaft ({eigenschaft}): {spalten}")
def _op_zahleneigenschaft(tab, s):
    idx = _spalten_liste(tab, s)
    e = s.get("eigenschaft", "ist_gerade")

    def zelle(z, i):
        a = z[i]
        try:
            x = _zelle_zahl(a)
        except ValueError:
            return FehlerWert("#WERT!")
        if x is None:
            return None
        if e == "absolutwert":
            return _typ_wie(a, abs(x))
        if e == "vorzeichen":
            return (x > 0) - (x < 0)
        if e in ("ist_gerade", "ist_ungerade"):
            if x != int(x):
                return False                   # 2,5 ist weder gerade noch ungerade
            return int(x) % 2 == (0 if e == "ist_gerade" else 1)
        raise FormelFehler("Unbekannte Eigenschaft '%s'" % e)
    return _neue_oder_ersetzte(tab, s, idx, zelle, str(s.get("neu") or "").strip())


# --- Typen -----------------------------------------------------------------
@operation("typ_aendern", "Datentyp ändern", "Typen",
           [F("spalten", "Spalten", "spalten"),
            F("typ", "Neuer Typ", "wahl", wahl=TYPEN, standard="text", als_liste=True),
            F("ort", "Gebietsschema des Quelltexts", "wahl", wahl=ORTE, standard="de"),
            F("stellen", "Nachkommastellen (leer = Standard)", "text", optional=True, leer_ok=True,
              zeige=("typ", ("dezimal", "prozent"))),
            F("nur_anzeige", "Nur Anzeige (Wert bleibt ungerundet)", "ja_nein", standard=False,
              zeige=("typ", ("dezimal", "prozent"))),
            F("bei_fehler", "Bei Fehlern", "wahl", wahl=FEHLER_WAHL, standard="fehler")],
           "Typ geändert zu {typ}: {spalten}")
def _op_typ(tab, s):
    idx = _spalten_liste(tab, s)
    typ, ort = s.get("typ", "text"), s.get("ort", "de")
    modus = s.get("bei_fehler", "stoppen")
    stellen = None
    if typ in ("dezimal", "prozent") and str(s.get("stellen") or "").strip() != "":
        try:
            stellen = int(float(str(s.get("stellen")).strip().replace(",", ".")))
        except ValueError:
            raise FormelFehler("Nachkommastellen: „%s“ ist keine Zahl" % s.get("stellen"))
        stellen = max(0, min(15, stellen))
    nur = bool(s.get("nur_anzeige"))
    neu = tab.kopie()
    fehler = []
    for n, z in enumerate(neu.zeilen):
        for i in idx:
            try:
                z[i] = in_typ(z[i], typ, ort)
                if stellen is not None and isinstance(z[i], float):
                    if nur:
                        z[i] = mit_stellen(z[i], stellen, typ == "prozent")
                    elif typ == "prozent":
                        z[i] = Prozent(_runden(z[i] * 100, stellen) / 100.0)
                    else:
                        z[i] = float(_runden(z[i], stellen))
            except (FormelFehler, ValueError, OverflowError) as e:
                if modus == "leer":
                    z[i] = None
                elif modus == "fehler":
                    z[i] = FehlerWert("#WERT!")
                elif modus == "behalten":
                    pass
                else:
                    fehler.append((n + 1, tab.spalten[i], str(e)))
    if fehler:
        z0 = fehler[0]
        rest = (" (und %d weitere)" % (len(fehler) - 1)) if len(fehler) > 1 else ""
        raise FormelFehler("Zeile %d, Spalte %s: %s%s" % (z0[0], z0[1], z0[2], rest))
    return neu


_RE_INT = {"de": re.compile(r"^[+-]?(\d{1,3}(\.\d{3})+|\d+)$"), "en": re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)$")}
_RE_DEZ = {"de": re.compile(r"^[+-]?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$"), "en": re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")}


def erkenne_typ(werte, ort="de"):
    """Rät den Typ einer Spalte aus Textwerten. -> Typname oder None (= Text lassen)."""
    texte = [str(v).strip() for v in werte if not ist_leer(v)]
    if not texte or any(not isinstance(v, str) for v in werte if not ist_leer(v)):
        return None
    if all(_RE_INT[ort].match(t) for t in texte):
        if any(len(re.sub(r"\D", "", t)) > 1 and re.sub(r"\D", "", t).startswith("0") for t in texte):
            return None
        return "ganzzahl"
    if all(_RE_DEZ[ort].match(t) for t in texte):
        if any(re.match(r"^[+-]?0\d", t) for t in texte):
            return None
        return "dezimal"
    try:
        for t in texte:
            parse_datum(t, ort, True)
        mit_zeit = any(re.search(r"\d:\d", t) for t in texte)
        return "datumzeit" if mit_zeit else "datum"
    except FormelFehler:
        pass
    return None


def spalten_qualitaet(werte, ort="de"):
    """(fehler, leer) einer Spalte: Anzahl Fehlerwerte (#WERT! …) und leerer Zellen."""
    leer = sum(1 for v in werte if ist_leer(v))
    fehler = sum(1 for v in werte if ist_fehler(v))
    return fehler, leer


@operation("typen_erkennen", "Datentypen automatisch erkennen", "Typen",
           [F("spalten", "Spalten (leer = alle)", "spalten", optional=True),
            F("ort", "Gebietsschema des Quelltexts", "wahl", wahl=ORTE, standard="de")],
           "Datentypen automatisch erkannt ({spalten})")
def _op_erkennen(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    ort = s.get("ort", "de")
    neu = tab.kopie()
    for i in idx:
        typ = erkenne_typ([z[i] for z in tab.zeilen], ort)
        if typ:
            for z in neu.zeilen:
                try:
                    z[i] = in_typ(z[i], typ, ort)
                except (FormelFehler, ValueError):
                    pass
    return neu


# --- Neue Spalten ------------------------------------------------------------
@operation("spalten_zusammenfuehren", "Spalten verbinden", "Neue Spalten",
           [F("spalten", "Spalten", "spalten"), F("trenner", "Trennzeichen"+" (#(lf) = Zeilenumbruch, #(tab) = Tabulator)", "text", leer_ok=True, optional=True),
            F("neu", "Name der neuen Spalte", "text"),
            F("quellen_behalten", "Ursprungsspalten beibehalten", "ja_nein", standard=False)],
           "Spalten {spalten} verbunden zu {neu}")
def _op_zusammen(tab, s):
    idx = _spalten_liste(tab, s)
    tr = sonderzeichen(s.get("trenner"))
    werte = [tr.join(als_text(z[i]) for i in idx if not ist_leer(z[i])) for z in tab.zeilen]
    erg = _anfuegen(tab, s["neu"], werte, nach=max(idx))
    if not s.get("quellen_behalten", False):
        erg = _op_sp_entf(erg, {"spalten": [tab.spalten[i] for i in idx]})
    return erg


WERT_ARTEN = [("text", "Text/Zahl"), ("spalte", "Spalte"), ("formel", "Formel")]
MAX_BEDINGUNGEN = 4


def normalisiere_bedingt(s):
    """Schritt (altes oder neues Format) -> (klauseln, sonst_art, sonst).
    Klausel: {"verknuepfung": "und"|"oder", "bedingungen": [{"spalte", "bedingung", "wert_art", "wert"}],
              "dann_art", "dann"}"""
    if "klauseln" in s:
        return list(s.get("klauseln") or []), s.get("sonst_art", "text"), s.get("sonst")
    if not s.get("spalte"):
        return [], "text", s.get("sonst")
    kl = {"verknuepfung": "und",
          "bedingungen": [{"spalte": s.get("spalte"), "bedingung": s.get("bedingung", "gleich"),
                           "wert_art": "text", "wert": s.get("wert")}],
          "dann_art": "text", "dann": s.get("dann")}
    return [kl], "text", s.get("sonst")


def _wert_quelle(art, wert, tab, label):
    """Wertangabe (fester Text / Spalte / Formel) -> Funktion zeile -> Wert."""
    if art == "spalte":
        if not wert:
            raise FormelFehler("%s: Bitte eine Spalte wählen" % label)
        i = tab.idx(wert)
        return lambda z: z[i]
    if art == "formel":
        if not str(wert or "").strip():
            raise FormelFehler("%s: Bitte eine Formel eingeben" % label)
        try:
            return kompiliere_formel(wert, tab)
        except FormelFehler as e:
            raise FormelFehler("%s: %s" % (label, e))
    fest = None if wert in (None, "") else wert
    return lambda z: fest


def _vergleiche_werte(a, bedingung, b, ort):
    """Zellwert a mit berechnetem Wert b (aus Spalte oder Formel) vergleichen."""
    if bedingung in OHNE_WERT + ("enthaelt", "enthaelt_nicht", "beginnt_mit", "endet_mit", "in_liste"):
        return trifft_zu(a, bedingung, als_text(b, ort), True, ort)
    if ist_leer(a) or ist_leer(b):
        gleich = ist_leer(a) and ist_leer(b)
        return gleich if bedingung == "gleich" else (not gleich if bedingung == "ungleich" else False)
    zahl = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if zahl(a) and zahl(b):
        x, y = a, b
    elif isinstance(a, str) and isinstance(b, str):
        x, y = a.casefold(), b.casefold()
    elif type(a) is type(b) and isinstance(a, (dt.date, dt.time)):
        x, y = a, b
    else:
        return trifft_zu(a, bedingung, als_text(b, ort), True, ort)
    return {"gleich": x == y, "ungleich": x != y, "groesser": x > y, "groesser_gleich": x >= y,
            "kleiner": x < y, "kleiner_gleich": x <= y}[bedingung]


@operation("bedingte_spalte", "Bedingte Spalte hinzufügen", "Neue Spalten",
           [F("neu", "Name der neuen Spalte", "text"),
            F("klauseln", "Wenn … Dann … Sonst", "klauseln"),
            F("ort", "Zahlen-/Datumsformat fester Werte", "wahl", wahl=ORTE, standard="de")],
           "Bedingte Spalte {neu}: {klauseln}")
def _op_bedingt(tab, s):
    klauseln, sonst_art, sonst = normalisiere_bedingt(s)
    ort = s.get("ort", "de")
    if not klauseln:
        raise FormelFehler("Bitte mindestens eine Klausel (Wenn … Dann …) angeben")
    plan = []
    for k, kl in enumerate(klauseln):
        name = "Klausel %d" % (k + 1)
        bed = []
        if not kl.get("bedingungen"):
            raise FormelFehler("%s: Bitte mindestens eine Bedingung angeben" % name)
        for j, b in enumerate(kl["bedingungen"]):
            if not b.get("spalte"):
                raise FormelFehler("%s, Bedingung %d: Bitte eine Spalte wählen" % (name, j + 1))
            if b.get("bedingung") not in dict(BEDINGUNGEN):
                raise FormelFehler("%s, Bedingung %d: Bitte einen Operator wählen" % (name, j + 1))
            art = b.get("wert_art", "text")
            quelle = None if art == "text" else _wert_quelle(art, b.get("wert"), tab, "%s, Wert" % name)
            bed.append((tab.idx(b["spalte"]), b["bedingung"], art, b.get("wert"), quelle))
        dann = _wert_quelle(kl.get("dann_art", "text"), kl.get("dann"), tab, "%s, Dann" % name)
        plan.append((kl.get("verknuepfung", "und") == "oder", bed, dann))
    sonst_f = _wert_quelle(sonst_art, sonst, tab, "Sonst")
    werte = []
    for n, z in enumerate(tab.zeilen):
        try:
            ergebnis, gefunden = None, False
            for oder, bed, dann in plan:
                treffer = []
                for i, bedingung, art, wert, quelle in bed:
                    if quelle is None:
                        treffer.append(trifft_zu(z[i], bedingung, wert, True, ort))
                    else:
                        treffer.append(_vergleiche_werte(z[i], bedingung, quelle(z), ort))
                if (any(treffer) if oder else all(treffer)):
                    ergebnis, gefunden = dann(z), True
                    break
            if not gefunden:
                ergebnis = sonst_f(z)
        except (FormelFehler, ValueError, OverflowError, TypeError) as e:
            raise FormelFehler("Zeile %d: %s" % (n + 1, e))
        werte.append(None if ergebnis == "" else ergebnis)
    return _anfuegen(tab, s["neu"], werte)


@operation("benutzerdefinierte_spalte", "Benutzerdefinierte Spalte hinzufügen", "Neue Spalten",
           [F("neu", "Name der neuen Spalte", "text"),
            F("formel", "Formel, z. B. [Menge] * [Preis]", "formel"),
            F("bei_fehler", "Bei Fehlern in einer Zeile", "wahl",
              wahl=[("stoppen", "Mit Fehlermeldung abbrechen"), ("leer", "Zelle leer lassen"),
                    ("fehler", "Fehlerwert einsetzen (später ersetzbar)")],
              standard="stoppen")],
           "Neue Spalte {neu} = {formel}")
def _op_formel(tab, s):
    f = kompiliere_formel(s["formel"], tab)
    modus = s.get("bei_fehler", "stoppen")
    werte = []
    for n, z in enumerate(tab.zeilen):
        try:
            werte.append(f(z))
        except (FormelFehler, ValueError, OverflowError) as e:
            if modus == "leer":
                werte.append(None)
            elif modus == "fehler":
                werte.append(FehlerWert("#FEHLER!"))
            else:
                raise FormelFehler("Zeile %d: %s" % (n + 1, e))
    return _anfuegen(tab, s["neu"], werte)


@operation("indexspalte", "Indexspalte", "Neue Spalten",
           [F("neu", "Name", "text", standard="Index"),
            F("start", "Beginnen bei", "zahl", standard=1),
            F("schritt", "Schrittweite", "zahl", standard=1)],
           "Indexspalte {neu} (ab {start})")
def _op_index(tab, s):
    st, sw = _zahl_param(s, "start", 1), _zahl_param(s, "schritt", 1)
    return _anfuegen(tab, s.get("neu") or "Index", [st + k * sw for k in range(len(tab.zeilen))])


# ==========================================================================
# Version 0.2: Gruppieren, Drehen, Text, Zeilen, Fehler, Umbenennen
# ==========================================================================
AGG_FN = [("summe", "Summe"), ("anzahl", "Anzahl Zeilen"), ("anzahl_werte", "Anzahl gefüllter Werte"),
          ("mittelwert", "Mittelwert"), ("median", "Median"), ("min", "Minimum"), ("max", "Maximum"),
          ("anzahl_eindeutig", "Eindeutige Werte zählen"),
          ("erster", "Erster Wert"), ("letzter", "Letzter Wert"), ("verketten", "Alle Werte verketten")]
AGG_LABEL = dict(AGG_FN)


def _zahlen_aus(werte):
    out = []
    for v in werte:
        if ist_leer(v):
            continue
        if ist_fehler(v):
            raise FormelFehler("Fehlerwert %s in den Daten – bitte zuerst die Fehler ersetzen" % v)
        if isinstance(v, bool):
            out.append(int(v))
        elif isinstance(v, (int, float)):
            out.append(v)
        elif isinstance(v, str):
            try:
                out.append(parse_zahl(v))
            except FormelFehler:
                raise FormelFehler("'%s' ist keine Zahl – bitte zuerst den Datentyp ändern" % v)
        else:
            raise FormelFehler("'%s' lässt sich nicht berechnen" % (v,))
    return out


def aggregiere(fn, werte, trenner=", ", eindeutig=False):
    """Eine Aggregation über die Werte einer Gruppe (trenner: nur für "verketten")."""
    if fn == "anzahl":
        return len(werte)
    if fn == "anzahl_werte":
        return sum(1 for v in werte if not ist_leer(v))
    if fn == "anzahl_eindeutig":
        return len({_hash_wert(v) for v in werte if not ist_leer(v)})
    if fn == "median":
        z = sorted(_zahlen_aus(werte))
        if not z:
            return None
        m = len(z) // 2
        if len(z) % 2:
            return z[m]
        r = (z[m - 1] + z[m]) / 2
        return int(r) if isinstance(r, float) and r.is_integer() else r
    if fn in ("summe", "mittelwert"):
        z = _zahlen_aus(werte)
        if fn == "summe":
            if all(isinstance(x, int) for x in z):
                return sum(z)
            return math.fsum(z)
        return math.fsum(z) / len(z) if z else None
    gefuellt = [v for v in werte if not ist_leer(v)]
    if fn in ("min", "max"):
        if not gefuellt:
            return None
        return (min if fn == "min" else max)(gefuellt, key=_sortier_schluessel)
    if fn == "erster":
        return gefuellt[0] if gefuellt else None
    if fn == "letzter":
        return gefuellt[-1] if gefuellt else None
    if fn == "verketten":
        if eindeutig:                      # jeden Wert nur einmal (erstes Vorkommen bleibt)
            gesehen, einzig = set(), []
            for v in gefuellt:
                h = _hash_wert(v)
                if h not in gesehen:
                    gesehen.add(h)
                    einzig.append(v)
            gefuellt = einzig
        return (trenner if trenner else ", ").join(als_text(v) for v in gefuellt) if gefuellt else None
    raise FormelFehler("Unbekannte Berechnung '%s'" % fn)


def _schluessel(z, idx):
    return tuple(("n", None) if ist_leer(z[i]) else _hash_wert(z[i]) for i in idx)


def _namen_pruefen(namen):
    gesehen = set()
    for n in namen:
        k = str(n).casefold()
        if k in gesehen:
            raise FormelFehler("Der Spaltenname '%s' kommt doppelt vor" % n)
        gesehen.add(k)


@operation("gruppieren", "Gruppieren und aggregieren", "Gruppieren und Drehen",
           [F("spalten", "Gruppieren nach (leer = ganze Tabelle)", "spalten", optional=True),
            F("aggregationen", "Berechnungen", "aggregation", zeilen=4),
            F("trenner", "Trenner für „Alle Werte verketten“", "text", standard=", ", optional=True, leer_ok=True),
            F("doppelte_weglassen", "Beim Verketten doppelte Werte weglassen", "ja_nein", standard=False)],
           "Gruppiert nach {spalten}: {aggregationen}")
def _op_gruppieren(tab, s):
    gidx = _spalten_liste(tab, s)
    plan = []
    for a in (s.get("aggregationen") or []):
        fn = a.get("fn")
        if not fn:
            continue
        sp = a.get("spalte") or ""
        if fn != "anzahl" and not sp:
            raise FormelFehler("Bei '%s' bitte eine Spalte wählen" % AGG_LABEL.get(fn, fn))
        idx = tab.idx(sp) if sp else None
        name = (a.get("name") or "").strip()
        if not name:
            name = "Anzahl" if fn == "anzahl" else "%s von %s" % (AGG_LABEL.get(fn, fn), tab.spalten[idx])
        plan.append((fn, idx, name))
    if not gidx and not plan:
        raise FormelFehler("Bitte Gruppierspalten oder mindestens eine Berechnung angeben")
    _namen_pruefen([tab.spalten[i] for i in gidx] + [n for _, _, n in plan])
    gruppen = {}
    for z in tab.zeilen:
        gruppen.setdefault(_schluessel(z, gidx), []).append(z)
    if not gidx and not gruppen:
        gruppen[()] = []
    zeilen = []
    for key, rows in gruppen.items():
        erste = rows[0] if rows else None
        zeile = [erste[i] for i in gidx] if erste else []
        for fn, idx, _ in plan:
            zeile.append(aggregiere(fn, [r[idx] for r in rows] if idx is not None else rows,
                                    s.get("trenner") or ", ", bool(s.get("doppelte_weglassen"))))
        zeilen.append(zeile)
    return Tabelle([tab.spalten[i] for i in gidx] + [n for _, _, n in plan], zeilen)


@operation("entpivotieren", "Spalten entpivotieren", "Gruppieren und Drehen",
           [F("spalten", "Spalten", "spalten"),
            F("modus", "Welche Spalten entpivotieren?", "wahl",
              wahl=[("ausgewaehlte", "Die ausgewählten Spalten"),
                    ("andere", "Alle außer den ausgewählten")], standard="ausgewaehlte"),
            F("attribut_name", "Name der Spalte für die bisherigen Spaltennamen", "text", standard="Attribut"),
            F("wert_name", "Name der Spalte für die Werte", "text", standard="Wert"),
            F("leere_weg", "Leere Werte überspringen", "ja_nein", standard=True)],
           "Entpivotiert ({modus}): {spalten}")
def _op_entpivot(tab, s):
    gewaehlt = set(_spalten_liste(tab, s))
    if s.get("modus", "ausgewaehlte") == "andere":
        drehen = [i for i in range(len(tab.spalten)) if i not in gewaehlt]
    else:
        drehen = [i for i in range(len(tab.spalten)) if i in gewaehlt]
    if not drehen:
        raise FormelFehler("Es bleibt keine Spalte zum Entpivotieren übrig")
    bleibt = [i for i in range(len(tab.spalten)) if i not in drehen]
    an, wn = (s.get("attribut_name") or "Attribut").strip(), (s.get("wert_name") or "Wert").strip()
    _namen_pruefen([tab.spalten[i] for i in bleibt] + [an, wn])
    leere_weg = s.get("leere_weg", True)
    zeilen = []
    for z in tab.zeilen:
        for i in drehen:
            if leere_weg and ist_leer(z[i]):
                continue
            zeilen.append([z[k] for k in bleibt] + [tab.spalten[i], z[i]])
    return Tabelle([tab.spalten[i] for i in bleibt] + [an, wn], zeilen)


PIVOT_FN = [("auto", "Automatisch (Zahlen summieren, sonst erster Wert)")] + AGG_FN


@operation("pivotieren", "Spalte pivotieren", "Gruppieren und Drehen",
           [F("spalte", "Spalte, deren Werte zu Spaltennamen werden", "spalte"),
            F("werte", "Spalte mit den Werten", "spalte"),
            F("fn", "Bei mehreren Werten je Feld", "wahl", wahl=PIVOT_FN, standard="auto")],
           "Pivot: Spalten aus {spalte}, Werte aus {werte}")
def _op_pivot(tab, s):
    a, w = tab.idx(s["spalte"]), tab.idx(s["werte"])
    if a == w:
        raise FormelFehler("Namens- und Wertespalte müssen verschieden sein")
    schl = [i for i in range(len(tab.spalten)) if i not in (a, w)]
    neue = []
    sicht = {}
    for z in tab.zeilen:
        n = "(leer)" if ist_leer(z[a]) else als_text(z[a])
        if n not in sicht:
            sicht[n] = len(neue)
            neue.append(n)
    _namen_pruefen([tab.spalten[i] for i in schl] + neue)
    fn = s.get("fn", "auto")
    if fn == "auto":
        fn = "summe" if all(isinstance(z[w], (int, float)) and not isinstance(z[w], bool)
                            for z in tab.zeilen if not ist_leer(z[w])) else "erster"
    gruppen = {}
    for z in tab.zeilen:
        g = gruppen.setdefault(_schluessel(z, schl), {"basis": [z[i] for i in schl], "zellen": {}})
        n = "(leer)" if ist_leer(z[a]) else als_text(z[a])
        g["zellen"].setdefault(n, []).append(z[w])
    zeilen = []
    for g in gruppen.values():
        zeile = list(g["basis"])
        for n in neue:
            vals = g["zellen"].get(n)
            zeile.append(aggregiere(fn, vals) if vals is not None else None)
        zeilen.append(zeile)
    return Tabelle([tab.spalten[i] for i in schl] + neue, zeilen)


@operation("transponieren", "Tabelle transponieren", "Gruppieren und Drehen",
           [F("mit_kopf", "Überschriften als erste Zeile mitnehmen", "ja_nein", standard=True)],
           "Tabelle transponiert (Zeilen und Spalten getauscht)")
def _op_transponieren(tab, s):
    zeilen = ([list(tab.spalten)] if s.get("mit_kopf", True) else []) + tab.zeilen
    if not zeilen:
        return Tabelle([], [])
    spalten = [list(c) for c in zip(*zeilen)]
    return Tabelle(["Spalte%d" % (i + 1) for i in range(len(zeilen))], spalten)


# --- Zeilen ----------------------------------------------------------------
@operation("zeilen_behalten_unten", "Untere Zeilen beibehalten", "Zeilen",
           [F("anzahl", "Anzahl Zeilen", "zahl", standard=10)],
           "Nur die letzten {anzahl} Zeile(n) beibehalten")
def _op_behalten_unten(tab, s):
    n = _zahl_param(s, "anzahl", 10)
    return Tabelle(tab.spalten, tab.zeilen[len(tab.zeilen) - n:] if n > 0 else [])


AKTION_BEREICH = [("behalten", "Beibehalten"), ("entfernen", "Entfernen")]


@operation("zeilen_bereich", "Zeilenbereich beibehalten", "Zeilen",
           [F("aktion", "Aktion", "wahl", wahl=AKTION_BEREICH, standard="behalten"),
            F("von", "Von Zeile", "zahl", standard=1), F("bis", "Bis Zeile (einschließlich)", "zahl", standard=10)],
           "{aktion}: Zeile {von} bis {bis}")
def _op_bereich(tab, s):
    von, bis = _zahl_param(s, "von", 1), _zahl_param(s, "bis", 10)
    if von < 1 or bis < von:
        raise FormelFehler("Ungültiger Bereich: 'Von' muss mindestens 1 sein und höchstens 'Bis'")
    innen = [z for k, z in enumerate(tab.zeilen, 1) if von <= k <= bis]
    aussen = [z for k, z in enumerate(tab.zeilen, 1) if not (von <= k <= bis)]
    return Tabelle(tab.spalten, innen if s.get("aktion", "behalten") == "behalten" else aussen)


@operation("jede_nte_zeile", "Alternative Zeilen entfernen", "Zeilen",
           [F("aktion", "Aktion", "wahl", wahl=AKTION_BEREICH, standard="behalten"),
            F("n", "Jede … Zeile", "zahl", standard=2), F("start", "Beginnend mit Zeile", "zahl", standard=1)],
           "{aktion}: jede {n}. Zeile ab Zeile {start}")
def _op_jede_nte(tab, s):
    n, start = _zahl_param(s, "n", 2), _zahl_param(s, "start", 1)
    if n < 1 or start < 1:
        raise FormelFehler("'Jede … Zeile' und 'Beginnend mit Zeile' müssen mindestens 1 sein")
    treffer = [k >= start and (k - start) % n == 0 for k in range(1, len(tab.zeilen) + 1)]
    beh = s.get("aktion", "behalten") == "behalten"
    return Tabelle(tab.spalten, [z for z, t in zip(tab.zeilen, treffer) if t == beh])


@operation("zeilen_umkehren", "Zeilen umkehren", "Zeilen", [], "Reihenfolge der Zeilen umgekehrt")
def _op_zeilen_umkehren(tab, s):
    return Tabelle(tab.spalten, list(reversed(tab.zeilen)))


@operation("fehler_zeilen_entfernen", "Fehler entfernen", "Zeilen",
           [F("spalten", "Nur diese Spalten prüfen (leer = alle)", "spalten", optional=True)],
           "Zeilen mit Fehlerwerten entfernt ({spalten})")
def _op_fehler_zeilen(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    return Tabelle(tab.spalten, [z for z in tab.zeilen if not any(ist_fehler(z[i]) for i in idx)])


@operation("fehler_zeilen_behalten", "Fehler beibehalten", "Zeilen",
           [F("spalten", "Nur diese Spalten prüfen (leer = alle)", "spalten", optional=True)],
           "Nur Zeilen mit Fehlerwerten beibehalten ({spalten})")
def _op_fehler_zeilen_behalten(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    return Tabelle(tab.spalten, [z for z in tab.zeilen if any(ist_fehler(z[i]) for i in idx)])


# --- Spalten -----------------------------------------------------------------
@operation("spalten_umbenennen", "Mehrere Spalten umbenennen", "Spalten",
           [F("umbenennungen", "Alt = Neu (eine Zeile je Spalte)", "textblock",
              vorbelegung="spaltenliste", anzeige="umbenennung")],
           "Spalten umbenannt: {umbenennungen}")
def _op_mehrfach_umbenennen(tab, s):
    neu = list(tab.spalten)
    n_aenderungen = 0
    for nr, zeile in enumerate(str(s.get("umbenennungen") or "").splitlines(), 1):
        if not zeile.strip():
            continue
        if "=" not in zeile:
            raise FormelFehler("Zeile %d: Bitte 'Alt = Neu' schreiben" % nr)
        alt, nw = [t.strip() for t in zeile.split("=", 1)]
        if nw == "":
            raise FormelFehler("Zeile %d: Der neue Name für '%s' darf nicht leer sein" % (nr, alt))
        i = tab.idx(alt)
        if neu[i] != nw:
            neu[i] = nw
            n_aenderungen += 1
    _namen_pruefen(neu)
    return Tabelle(neu, tab.zeilen)


@operation("spaltenreihenfolge_umkehren", "Spaltenreihenfolge umkehren", "Spalten", [],
           "Reihenfolge der Spalten umgekehrt")
def _op_sp_umkehren(tab, s):
    n = len(tab.spalten)
    return Tabelle(list(reversed(tab.spalten)), [list(reversed(z)) for z in tab.zeilen])


@operation("spalten_sortieren", "Spalten alphabetisch sortieren", "Spalten",
           [F("richtung", "Richtung", "wahl", wahl=RICHTUNG, standard="auf")],
           "Spalten alphabetisch sortiert ({richtung})")
def _op_sp_sortieren(tab, s):
    idx = sorted(range(len(tab.spalten)), key=lambda i: _sortier_schluessel(tab.spalten[i]),
                 reverse=s.get("richtung", "auf") == "ab")
    return Tabelle([tab.spalten[i] for i in idx], [[z[i] for i in idx] for z in tab.zeilen])


# --- Fehlerwerte -----------------------------------------------------------------
@operation("fehler_ersetzen", "Fehlerwerte ersetzen", "Text und Werte",
           [F("spalten", "Spalten (leer = alle)", "spalten", optional=True),
            F("wert", "Ersetzen durch (leer = leere Zelle)", "text", leer_ok=True, optional=True)],
           "Fehlerwerte ersetzt durch '{wert}' ({spalten})")
def _op_fehler_ersetzen(tab, s):
    idx = _spalten_liste(tab, s, alle_wenn_leer=True)
    ers = s.get("wert")
    ers = None if ers in (None, "") else ers
    neu = tab.kopie()
    for z in neu.zeilen:
        for i in idx:
            if ist_fehler(z[i]):
                z[i] = ers
    return neu


# --- Text extrahieren ---------------------------------------------------------------
EXTRAKT = [("vor_trenner", "Text vor dem Trennzeichen"), ("nach_trenner", "Text nach dem Trennzeichen"),
           ("zwischen_trennern", "Text zwischen zwei Trennzeichen"),
           ("erste_zeichen", "Die ersten n Zeichen"), ("letzte_zeichen", "Die letzten n Zeichen"),
           ("ab_position", "n Zeichen ab Position"), ("laenge", "Länge des Texts"),
           ("nur_ziffern", "Nur die Ziffern"), ("ohne_ziffern", "Alles außer Ziffern")]
VORKOMMEN = [("erstes", "Erstes Vorkommen"), ("letztes", "Letztes Vorkommen")]


def _extrahiere(text, art, tr1, tr2, vork, n, start):
    t = als_text(text)
    if art in ("vor_trenner", "nach_trenner", "zwischen_trennern"):
        if tr1 == "":
            raise FormelFehler("Bitte ein Trennzeichen angeben")
        pos = t.rfind(tr1) if vork == "letztes" else t.find(tr1)
        if pos < 0:
            return None
        if art == "vor_trenner":
            return t[:pos]
        rest = t[pos + len(tr1):]
        if art == "nach_trenner":
            return rest
        if tr2 == "":
            raise FormelFehler("Bitte auch das zweite Trennzeichen angeben")
        p2 = rest.find(tr2)
        return None if p2 < 0 else rest[:p2]
    if art == "erste_zeichen":
        return t[:max(n, 0)]
    if art == "letzte_zeichen":
        return t[len(t) - n:] if n > 0 else ""
    if art == "ab_position":
        return t[max(start, 1) - 1:max(start, 1) - 1 + max(n, 0)]
    if art == "laenge":
        return len(t)
    if art == "nur_ziffern":
        return "".join(c for c in t if c.isdigit())
    if art == "ohne_ziffern":
        return "".join(c for c in t if not c.isdigit())
    raise FormelFehler("Unbekannte Art '%s'" % art)


@operation("text_extrahieren", "Text extrahieren", "Text und Werte",
           [F("spalte", "Spalte", "spalte"),
            F("art", "Was extrahieren?", "wahl", wahl=EXTRAKT, standard="vor_trenner"),
            F("trenner", "Trennzeichen (bzw. erstes)"+" (#(lf) = Zeilenumbruch, #(tab) = Tabulator)", "text", leer_ok=True, optional=True,
              zeige=("art", ("vor_trenner", "nach_trenner", "zwischen_trennern"))),
            F("trenner2", "Zweites Trennzeichen", "text", leer_ok=True, optional=True, zeige=("art", ("zwischen_trennern",))),
            F("vorkommen", "Welches Vorkommen?", "wahl", wahl=VORKOMMEN, standard="erstes",
              zeige=("art", ("vor_trenner", "nach_trenner", "zwischen_trennern"))),
            F("anzahl", "Anzahl Zeichen", "zahl", standard=3, optional=True,
              zeige=("art", ("erste_zeichen", "letzte_zeichen", "ab_position"))),
            F("start", "Ab Position (1 = erstes Zeichen)", "zahl", standard=1, optional=True, zeige=("art", ("ab_position",))),
            F("neu", "Neue Spalte (leer = Spalte ersetzen)", "text", leer_ok=True, optional=True)],
           "Text extrahiert aus {spalte}: {art}")
def _op_extrahieren(tab, s):
    i = tab.idx(s["spalte"])
    art = s.get("art", "vor_trenner")
    tr1, tr2 = sonderzeichen(s.get("trenner")), sonderzeichen(s.get("trenner2"))
    n, st = _zahl_param(s, "anzahl", 3), _zahl_param(s, "start", 1)
    vork = s.get("vorkommen", "erstes")
    werte = [None if ist_leer(z[i]) else _extrahiere(z[i], art, tr1, tr2, vork, n, st) for z in tab.zeilen]
    werte = [None if (isinstance(w, str) and w == "") else w for w in werte]
    neu = (s.get("neu") or "").strip()
    if neu:
        return _anfuegen(tab, neu, werte, nach=i)
    ergebnis = tab.kopie()
    for z, w in zip(ergebnis.zeilen, werte):
        z[i] = w
    return ergebnis


# --- Spalte teilen (erweitert) -----------------------------------------------------------
TEILEN_MODUS = [("trenner", "Bei einem Trennzeichen"), ("position", "Vor bestimmten Zeichenpositionen"),
                ("anzahl", "Nach jeweils n Zeichen (wiederholt)"),
                ("einmal_links", "Einmal nach den ersten n Zeichen"), ("einmal_rechts", "Einmal vor den letzten n Zeichen"),
                ("ziffer_buchstabe", "Beim Wechsel Ziffer ↔ Buchstabe"),
                ("klein_gross", "Beim Wechsel klein → GROSS")]


def _teile_text(t, modus, tr, positionen, anzahl, max_teile):
    if modus == "trenner":
        if tr == "":
            raise FormelFehler("Bitte ein Trennzeichen angeben")
        return t.split(tr, max_teile - 1) if max_teile > 1 else t.split(tr)
    if modus == "position":
        pos = sorted({p - 1 for p in positionen if p > 1})
        grenzen = [0] + [p for p in pos if p < len(t)] + [len(t)]
        return [t[a:b] for a, b in zip(grenzen, grenzen[1:])] if t else []
    if modus == "anzahl":
        return [t[k:k + anzahl] for k in range(0, len(t), anzahl)]
    if modus == "einmal_links":
        return [t[:anzahl], t[anzahl:]] if len(t) > anzahl else [t]
    if modus == "einmal_rechts":
        return [t[:len(t) - anzahl], t[len(t) - anzahl:]] if len(t) > anzahl else [t]
    if modus == "ziffer_buchstabe":
        return re.findall(r"\d+|\D+", t)
    if modus == "klein_gross":
        return re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", "\x00", t).split("\x00") if t else []
    raise FormelFehler("Unbekannter Teilungsmodus '%s'" % modus)


@operation("spalte_teilen", "Spalte teilen", "Neue Spalten",
           [F("spalte", "Spalte", "spalte"),
            F("modus", "Teilen", "wahl", wahl=TEILEN_MODUS, standard="trenner"),
            F("trenner", "Trennzeichen"+" (#(lf) = Zeilenumbruch, #(tab) = Tabulator)", "text", leer_ok=True, optional=True,
              zeige=("modus", ("trenner",))),
            F("positionen", "Positionen, mit ; getrennt (z. B. 4;7)", "text", leer_ok=True, optional=True,
              zeige=("modus", ("position",))),
            F("anzahl_zeichen", "Zeichen (je Teil bzw. n)", "zahl", standard=3, optional=True,
              zeige=("modus", ("anzahl", "einmal_links", "einmal_rechts"))),
            F("max_teile", "Höchstens so viele Teile (0 = beliebig)", "zahl", standard=0,
              optional=True, zeige=("modus", ("trenner",)))],
           "Spalte {spalte} geteilt ({modus})")
def _op_teilen(tab, s):
    i = tab.idx(s["spalte"])
    modus = s.get("modus", "trenner")
    tr = sonderzeichen(s.get("trenner"))
    pos = []
    if modus == "position":
        try:
            pos = [int(x) for x in re.split(r"[;,\s]+", str(s.get("positionen") or "").strip()) if x]
        except ValueError:
            raise FormelFehler("Die Positionen müssen ganze Zahlen sein, z. B. 4;7")
        if not pos:
            raise FormelFehler("Bitte mindestens eine Position angeben")
    az = _zahl_param(s, "anzahl_zeichen", 3)
    if modus in ("anzahl", "einmal_links", "einmal_rechts") and az < 1:
        raise FormelFehler("'Zeichen' muss mindestens 1 sein")
    mx = _zahl_param(s, "max_teile", 0)
    teile = [[] if ist_leer(z[i]) else _teile_text(als_text(z[i]), modus, tr, pos, az, mx) for z in tab.zeilen]
    n = max([len(t) for t in teile] + [1])
    basis = tab.spalten[i]
    neue_namen = ["%s.%d" % (basis, k + 1) for k in range(n)]
    for nm in neue_namen:
        if nm in tab.spalten and nm != basis:
            raise FormelFehler("Eine Spalte '%s' gibt es schon" % nm)
    namen = tab.spalten[:i] + neue_namen + tab.spalten[i + 1:]
    zeilen = []
    for z, t in zip(tab.zeilen, teile):
        t = [x.strip() if x.strip() != "" else None for x in t] + [None] * (n - len(t))
        zeilen.append(z[:i] + t + z[i + 1:])
    return Tabelle(namen, zeilen)



# --------------------------------------------------------------------------
# Abfrage = Quelle + Schritte
# --------------------------------------------------------------------------
def pruefe_schritt(step):
    d = OPS.get(step.get("op"))
    if not d:
        raise FormelFehler("Unbekannter Schritt '%s'" % step.get("op"))
    _pflichtfelder_pruefen(normalisiere_schritt(step), d)
    return d


def fuehre_aus(roh, schritte, bis=None):
    """Wendet Schritte auf eine Rohtabelle an (bis = Anzahl Schritte)."""
    tab = roh.kopie()
    n = len(schritte) if bis is None else bis
    for k, s in enumerate(schritte[:n]):
        if s.get("aktiv") is False:   # ausgeschalteter Schritt
            continue
        try:
            if s.get("nur_wenn") and not bedingung_erfuellt(s["nur_wenn"]):
                continue              # Bedingung nicht erfüllt: Schritt wird übersprungen
            d = pruefe_schritt(s)
            tab = d["func"](tab, loese_parameter(s))
        except StepError:
            raise
        except Exception as e:   # auch unerwartete Fehler als Meldung statt Absturz
            titel = OPS.get(s.get("op"), {}).get("titel", str(s.get("op")))
            if isinstance(e, (FormelFehler, ValueError, OverflowError)):
                meldung = str(e.args[0]) if e.args else repr(e)
            else:
                meldung = "Unerwarteter Fehler (%s): %s" % (type(e).__name__, e)
            raise StepError(k, titel, meldung)
    return tab


def wende_schritt(tab, step):
    """Einen einzelnen Schritt auf eine Tabelle anwenden (z. B. zur Prüfung im Dialog)."""
    return fuehre_aus(tab, [step])


# --- Handeinträge behalten (Selbstreferenz: letzter Stand der eigenen Ausgabe im Blatt) ------------------------
SNAPSHOT = {"fn": None}       # fn() -> Tabelle | None (letzter Stand dieser Abfrage im Blatt); setzt die Oberfläche
HINWEISE = []                 # Hinweise des letzten Laufs (z. B. verworfene Handeinträge)


def hole_eigenen_stand():
    fn = SNAPSHOT.get("fn")
    return fn() if fn else None


def _schluessel_eindeutig(tab, idx, keys, wo):
    """Handeinträge werden über den Schlüssel zugeordnet: doppelte Schlüssel würden Einträge der falschen Zeile
    zuordnen -> abbrechen und die doppelten Zeilen nennen."""
    erste, doppelt = {}, {}
    for n, z in enumerate(tab.zeilen, 1):
        k = _schluessel(z, idx)
        if k in erste:
            doppelt.setdefault(k, [erste[k]]).append(n)
        else:
            erste[k] = n
    if not doppelt:
        return
    teile = []
    for k, zl in list(doppelt.items())[:5]:
        wert = " | ".join("(leer)" if ist_leer(tab.zeilen[zl[0] - 1][i]) else als_text(tab.zeilen[zl[0] - 1][i]) for i in idx)
        teile.append("%s – Zeilen %s" % (wert, ", ".join(str(x) for x in zl[:8]) + (" …" if len(zl) > 8 else "")))
    mehr = len(doppelt) - 5
    raise FormelFehler("Die Schlüsselspalte(n) %s sind %s nicht eindeutig (%d Wert(e) mehrfach). Einträge in manuellen Spalten ließen sich "
                       "sonst der falschen Zeile zuordnen.\n%s%s\nBitte weitere Schlüsselspalten wählen oder die "
                       "Doppelten beseitigen."
                       % (", ".join("'%s'" % k for k in keys), wo, len(doppelt), "\n".join(teile),
                          ("\n… und %d weitere" % mehr) if mehr > 0 else ""))


@operation("hand_behalten", "Manuelle Spalten behalten (eigener letzter Stand)", "Tabellen",
           [F("schluessel", "Schlüsselspalten (eindeutig je Zeile)", "spalten"),
            F("handspalten", "Manuelle Spalten (ein Name pro Zeile)", "textblock"),
            F("auto_neu", "Neue Spalten rechts neben der Tabelle automatisch übernehmen", "ja_nein", standard=False)],
           "Manuelle Spalten behalten: {handspalten} (Schlüssel: {schluessel})")
def _op_hand_behalten(tab, s):
    namen = [n.strip() for n in str(s.get("handspalten") or "").splitlines() if n.strip()]
    if not namen:
        raise FormelFehler("Bitte mindestens eine manuelle Spalte angeben")
    keys = list(s.get("schluessel") or [])
    li = tab.idxs(keys)
    spalten = list(tab.spalten)
    ziel = []
    for n in namen:
        low = [c.casefold() for c in spalten]
        if n.casefold() in low:
            ziel.append(low.index(n.casefold()))
        else:
            spalten.append(n)
            ziel.append(len(spalten) - 1)
    zeilen = [list(z) + [None] * (len(spalten) - len(z)) for z in tab.zeilen]
    _schluessel_eindeutig(tab, li, keys, "in der neuen Ausgabe")
    alt = hole_eigenen_stand()
    if alt is not None and alt.zeilen:
        for k in keys:
            try:
                alt.idx(k)
            except FormelFehler:
                raise FormelFehler("Der letzte Stand im Blatt hat die Schlüsselspalte '%s' nicht. Damit gingen die "
                                   "Einträge verloren. Wurde die Spalte umbenannt? Dann die Überschrift im Blatt auf den "
                                   "neuen Namen ändern; sonst die Spalte dort wiederherstellen." % k)
        ai = alt.idxs(keys)
        _schluessel_eindeutig(alt, ai, keys, "im letzten Stand im Blatt")
        ah = []
        for n in namen:
            try:
                ah.append(alt.idx(n))
            except FormelFehler:
                ah.append(None)
        karte = {}
        for z in alt.zeilen:
            karte.setdefault(_schluessel(z, ai), z)
        benutzt = set()
        for z in zeilen:
            k = _schluessel(z, li)
            a = karte.get(k)
            if a is None:
                continue
            benutzt.add(k)
            for j, i in zip(ziel, ah):
                if i is not None and not ist_leer(a[i]):
                    z[j] = a[i]
        verloren = sum(1 for k, a in karte.items() if k not in benutzt
                       and any(i is not None and not ist_leer(a[i]) for i in ah))
        if verloren:
            HINWEISE.append("%d Eintrag/Einträge in manuellen Spalten ohne passende Zeile verworfen" % verloren)
            del HINWEISE[:-50]
    return Tabelle(spalten, zeilen)


# --- Dateiinhalt einlesen (Dateiliste aus einer Ordner-Quelle -> Inhalt der Dateien) -------------------------------
DATEI_LESER = {"fn": None}    # fn(pfad, schritt) -> Tabelle; setzt die Oberfläche (liest CSV/Excel/ODS nach den Zielangaben)

DATEI_MODI = [("erste", "Nur die Datei der ersten Zeile"),
              ("alle", "Alle Dateien der Liste untereinander anfügen (gleicher Aufbau nötig)")]


def _dateiname(pfad):
    return str(pfad).replace("\\", "/").rsplit("/", 1)[-1]


@operation("datei_einlesen", "Dateien einlesen (Dateiliste → Daten)", "Tabellen",
           [F("pfadspalte", "Spalte mit dem Dateipfad", "spalte", standard="Pfad"),
            F("modus", "Welche Dateien", "wahl", wahl=DATEI_MODI, standard="erste"),
            F("herkunft", "Name der Herkunftsspalte (leer = keine)", "text", standard="Quelle.Datei", optional=True),
            F("trenner", "Trennzeichen (CSV)", "text", standard="auto", optional=True),
            F("blatt", "Blatt", "text", optional=True),
            F("tabelle", "Tabelle", "text", optional=True),
            F("bereichsname", "Benannter Bereich", "text", optional=True),
            F("bereich", "Bereich", "text", optional=True)],
           "Dateien einlesen ({modus}), Pfad in Spalte {pfadspalte}")
def _op_datei_einlesen(tab, s):
    fn = DATEI_LESER.get("fn")
    if fn is None:
        raise FormelFehler("Dateien einlesen ist hier nicht verfügbar")
    pcol = s.get("pfadspalte") or "Pfad"
    try:
        pi = tab.idx(pcol)
    except FormelFehler:
        raise FormelFehler("Die Spalte „%s“ mit dem Dateipfad gibt es nicht. In der Ordner-Quelle (Schritt 01) die Spalte "
                           "„Pfad“ ankreuzen oder hier die richtige Spalte wählen." % pcol)
    pfade = [str(z[pi]).strip() for z in tab.zeilen if not ist_leer(z[pi])]
    if not pfade:
        raise FormelFehler("Die Dateiliste ist leer: Es gibt keine Datei zum Einlesen (Muster oder Filter prüfen)")
    alle = s.get("modus") == "alle"
    if not alle:
        pfade = pfade[:1]
    herkunft = str(s.get("herkunft") or "").strip()
    spalten, zeilen = None, []
    for p in pfade:
        name = _dateiname(p)
        try:
            t = fn(p, s)
        except FormelFehler as e:
            raise FormelFehler("Datei %s: %s" % (name, e.args[0] if e.args else e))
        if spalten is None:
            spalten = list(t.spalten)
            if herkunft and herkunft.casefold() in [c.casefold() for c in spalten]:
                raise FormelFehler("Die Herkunftsspalte „%s“ gibt es in den Daten schon. Bitte einen anderen Namen wählen." % herkunft)
        elif len(t.spalten) != len(spalten):
            raise FormelFehler("Abgebrochen: Die Datei %s hat %d Spalten, die erste Datei (%s) hat %d. Beim Untereinander-Anfügen "
                               "müssen alle Dateien gleich aufgebaut sein." % (name, len(t.spalten), _dateiname(pfade[0]), len(spalten)))
        elif [c.casefold() for c in t.spalten] != [c.casefold() for c in spalten]:
            diff = next(c for c, e in zip(t.spalten, spalten) if c.casefold() != e.casefold())
            raise FormelFehler("Abgebrochen: Die Spaltenüberschriften der Datei %s weichen von der ersten Datei (%s) ab (z. B. „%s“). "
                               "Beim Untereinander-Anfügen müssen alle Dateien gleich aufgebaut sein." % (name, _dateiname(pfade[0]), diff))
        for z in t.zeilen:
            zeilen.append(([name] if herkunft else []) + list(z))
    return Tabelle(([herkunft] if herkunft else []) + spalten, zeilen)


# --- Tabellen verbinden und anfügen (zweite Tabelle = Ergebnis einer anderen Abfrage) --------------------------
AUFLOESER ={"fn": None}      # fn(name) -> Tabelle; setzt die Oberfläche (liest und berechnet die andere Abfrage)

JOIN_ARTEN = [("links", "Links außen (alle Zeilen der ersten Tabelle, passende der zweiten)"),
              ("innen", "Innen (nur Zeilen mit Übereinstimmung in beiden)"),
              ("voll", "Vollständig außen (alle Zeilen beider Tabellen)"),
              ("rechts", "Rechts außen (alle Zeilen der zweiten Tabelle, passende der ersten)"),
              ("anti_links", "Links-Anti (nur Zeilen der ersten ohne Entsprechung in der zweiten)"),
              ("anti_rechts", "Rechts-Anti (nur Zeilen der zweiten ohne Entsprechung in der ersten)"),
              ("kreuz", "Kreuzprodukt (jede Zeile mit jeder)")]
AUSRICHTUNG = [("name", "Nach Spaltennamen"), ("position", "Nach Position")]


def hole_tabelle(name):
    fn = AUFLOESER.get("fn")
    if fn is None:
        raise FormelFehler("Andere Abfragen sind hier nicht verfügbar (Abfrage '%s')" % name)
    if not str(name or "").strip():
        raise FormelFehler("Bitte eine zweite Tabelle (Abfrage) wählen")
    return fn(name).kopie()


@operation("tabellen_verbinden", "Abfragen zusammenführen", "Tabellen",
           [F("abfrage", "Zweite Tabelle (Abfrage)", "text"),
            F("schluessel", "Schlüsselspalten (links = rechts)", "schluessel", optional=True),
            F("join", "Verknüpfungsart", "wahl", wahl=JOIN_ARTEN, standard="links"),
            F("spalten_rechts", "Spalten aus der zweiten Tabelle (leer = alle)", "spalten_rechts", optional=True),
            F("praefix", "Präfix für Spalten der zweiten Tabelle", "text", optional=True, leer_ok=True)],
           "Verbunden mit {abfrage} ({join}) über {schluessel}")
def _op_verbinden(tab, s):
    rt = hole_tabelle(s.get("abfrage"))
    join = s.get("join", "links")
    paare = [p for p in (s.get("schluessel") or []) if p.get("links") or p.get("rechts")]
    if join != "kreuz" and not paare:
        raise FormelFehler("Bitte mindestens ein Schlüsselspaltenpaar angeben")
    for p in paare:
        if not p.get("links") or not p.get("rechts"):
            raise FormelFehler("Jedes Schlüsselpaar braucht eine Spalte links und rechts")
    li = [tab.idx(p["links"]) for p in paare]
    ri = [rt.idx(p["rechts"]) for p in paare]
    if s.get("spalten_rechts"):
        rcols = rt.idxs(s["spalten_rechts"])
    else:
        rcols = [i for i in range(len(rt.spalten)) if i not in ri] if join != "anti_rechts" else list(range(len(rt.spalten)))
    pre = s.get("praefix") or ""
    rnamen = [pre + rt.spalten[i] for i in rcols]
    nl, nr = len(tab.spalten), len(rcols)
    leer_r = [None] * nr
    if join == "anti_links":
        rkeys = {_schluessel(z, ri) for z in rt.zeilen}
        return Tabelle(tab.spalten, [z for z in tab.zeilen if _schluessel(z, li) not in rkeys])
    if join == "anti_rechts":
        lkeys = {_schluessel(z, li) for z in tab.zeilen}
        return Tabelle([rt.spalten[i] for i in rcols],
                       [[z[i] for i in rcols] for z in rt.zeilen if _schluessel(z, ri) not in lkeys])
    namen = eindeutige_namen(list(tab.spalten) + rnamen)
    zeilen = []
    if join == "kreuz":
        for z in tab.zeilen:
            for r in rt.zeilen:
                zeilen.append(list(z) + [r[i] for i in rcols])
        return Tabelle(namen, zeilen)
    rindex = {}
    for k, r in enumerate(rt.zeilen):
        rindex.setdefault(_schluessel(r, ri), []).append(k)
    benutzt = set()
    if join == "rechts":
        lindex = {}
        for z in tab.zeilen:
            lindex.setdefault(_schluessel(z, li), []).append(z)
        for r in rt.zeilen:
            treffer = lindex.get(_schluessel(r, ri))
            rest = [r[i] for i in rcols]
            if treffer:
                for z in treffer:
                    zeilen.append(list(z) + rest)
            else:
                neu = [None] * nl
                for a, b in zip(li, ri):
                    neu[a] = r[b]
                zeilen.append(neu + rest)
        return Tabelle(namen, zeilen)
    for z in tab.zeilen:
        treffer = rindex.get(_schluessel(z, li))
        if treffer:
            benutzt.update(treffer)
            if join in ("links", "innen", "voll"):
                for k in treffer:
                    zeilen.append(list(z) + [rt.zeilen[k][i] for i in rcols])
        elif join in ("links", "voll"):
            zeilen.append(list(z) + leer_r)
    if join == "voll":
        for k, r in enumerate(rt.zeilen):
            if k not in benutzt:
                neu = [None] * nl
                for a, b in zip(li, ri):
                    neu[a] = r[b]
                zeilen.append(neu + [r[i] for i in rcols])
    return Tabelle(namen, zeilen)


@operation("tabellen_anfuegen", "Abfragen anfügen", "Tabellen",
           [F("abfragen", "Tabellen (Abfragen), die angefügt werden", "abfragenliste"),
            F("ausrichtung", "Spalten zuordnen", "wahl", wahl=AUSRICHTUNG, standard="name"),
            F("herkunft", "Name der Herkunftsspalte (leer = keine)", "text", optional=True, leer_ok=True),
            F("herkunft_eigen", "Herkunftswert der aktuellen Tabelle", "text", optional=True, leer_ok=True),
            F("zuordnung", "Abweichende Spaltennamen zuordnen (je Zeile: Spalte der angefügten Tabelle = Spalte der "
                           "aktuellen Tabelle)", "textblock", optional=True, leer_ok=True),
            F("nur_spalten", "Nur diese Spalten der angefügten Tabellen übernehmen (leer = alle)", "spalten",
              optional=True)],
           "Angefügt: {abfragen} ({ausrichtung})")
def _op_anfuegen(tab, s):
    namen_q = [n for n in (s.get("abfragen") or []) if str(n).strip()]
    if not namen_q:
        raise FormelFehler("Bitte mindestens eine Tabelle (Abfrage) zum Anfügen wählen")
    herkunft = (s.get("herkunft") or "").strip()
    tabellen = [(None, tab)] + [(n, hole_tabelle(n)) for n in namen_q]
    spalten = list(tab.spalten)
    pos = s.get("ausrichtung", "name") == "position"
    zuordnung = {}
    for zl in str(s.get("zuordnung") or "").splitlines():       # "Angefügt = Aktuell"
        if "=" in zl:
            links, rechts = zl.split("=", 1)
            if links.strip() and rechts.strip():
                zuordnung[links.strip().casefold()] = rechts.strip()
    nur = {str(x).strip().casefold() for x in (s.get("nur_spalten") or []) if str(x).strip()}
    if nur:                                   # nur gewählte Spalten der angefügten Tabellen (Originalname oder zugeordneter Name)
        gefiltert = [tabellen[0]]
        for n, t in tabellen[1:]:
            behalten = [k for k, c in enumerate(t.spalten)
                        if c.casefold() in nur or zuordnung.get(c.casefold(), "").casefold() in nur]
            gefiltert.append((n, Tabelle([t.spalten[k] for k in behalten],
                                         [[z[k] for k in behalten] for z in t.zeilen])))
        tabellen = gefiltert
    if zuordnung and not pos:
        umbenannt = [tabellen[0]]
        for n, t in tabellen[1:]:
            neue = [zuordnung.get(c.casefold(), c) for c in t.spalten]
            umbenannt.append((n, Tabelle(eindeutige_namen(neue), t.zeilen)))
        tabellen = umbenannt
    if pos:
        breite = max(len(t.spalten) for _, t in tabellen)
        for _, t in tabellen:
            for k in range(len(spalten), len(t.spalten)):
                spalten.append(t.spalten[k])
        spalten = eindeutige_namen(spalten)
    else:
        low = {c.casefold(): k for k, c in enumerate(spalten)}
        for _, t in tabellen[1:]:
            for c in t.spalten:
                if c.casefold() not in low:
                    low[c.casefold()] = len(spalten)
                    spalten.append(c)
    zeilen = []
    for n, t in tabellen:
        if pos:
            abb = list(range(len(t.spalten)))
        else:
            low = {c.casefold(): k for k, c in enumerate(spalten)}
            abb = [low[c.casefold()] for c in t.spalten]
        for z in t.zeilen:
            neu = [None] * len(spalten)
            for src, dst in enumerate(abb):
                if dst < len(spalten):
                    neu[dst] = z[src]
            if herkunft:
                neu.append(s.get("herkunft_eigen") or "" if n is None else n)
            zeilen.append(neu)
    if herkunft:
        spalten = eindeutige_namen(spalten + [herkunft])
    return Tabelle(spalten, zeilen)


# --- Spalte umbenannt: Folgeschritte anpassen -----------------------------------
def _gleicher_name(a, b):
    return isinstance(a, str) and isinstance(b, str) and a.strip().casefold() == b.strip().casefold()


def _formel_umbenennen(text, alt, neu):
    if not isinstance(text, str):
        return text, False
    muster = re.compile(r"\[\s*" + re.escape(alt.strip()) + r"\s*\]", re.IGNORECASE)
    ergebnis = muster.sub(lambda m: "[" + neu + "]", text)
    return ergebnis, ergebnis != text


def ersetze_spaltenname_im_schritt(step, alt, neu):
    """Spaltenverweise alt -> neu in einem Schritt (an Ort und Stelle). Gibt True zurück, wenn sich etwas änderte."""
    d = OPS.get(step.get("op"))
    if not d:
        return False
    geaendert = False

    def formel(obj, key):
        nonlocal geaendert
        t, ok = _formel_umbenennen(obj.get(key), alt, neu)
        if ok:
            obj[key] = t
            geaendert = True

    def spalte(obj, key):
        nonlocal geaendert
        if _gleicher_name(obj.get(key), alt):
            obj[key] = neu
            geaendert = True

    for f in d["felder"]:
        n, art = f["name"], f["art"]
        if n not in step:
            continue
        if art == "spalte":
            spalte(step, n)
        elif art == "spalten":
            liste = step.get(n)
            if isinstance(liste, list):
                for k, v in enumerate(liste):
                    if _gleicher_name(v, alt):
                        liste[k] = neu
                        geaendert = True
        elif art == "formel":
            formel(step, n)
        elif art == "schluessel":
            for p in (step.get(n) or []):
                spalte(p, "links")
        elif art == "aggregation":
            for a in (step.get(n) or []):
                spalte(a, "spalte")
        elif art == "textblock" and f.get("anzeige") == "umbenennung":
            zeilen = str(step.get(n) or "").splitlines()
            for k, z in enumerate(zeilen):
                if "=" in z:
                    links, rechts = z.split("=", 1)
                    if _gleicher_name(links, alt):
                        zeilen[k] = "%s = %s" % (neu, rechts.strip())
                        geaendert = True
            step[n] = "\n".join(zeilen)
        elif art == "klauseln":
            for kl in (step.get(n) or []):
                for b in kl.get("bedingungen", []):
                    spalte(b, "spalte")
                    if b.get("wert_art") == "spalte":
                        spalte(b, "wert")
                    elif b.get("wert_art") == "formel":
                        formel(b, "wert")
                if kl.get("dann_art") == "spalte":
                    spalte(kl, "dann")
                elif kl.get("dann_art") == "formel":
                    formel(kl, "dann")
            if step.get("sonst_art") == "spalte":
                spalte(step, "sonst")
            elif step.get("sonst_art") == "formel":
                formel(step, "sonst")
    if step.get("op") == "bedingte_spalte" and "klauseln" not in step and step.get("spalte"):
        spalte(step, "spalte")           # altes Format
    return geaendert


def folge_schritte_anpassen(schritte, ab, alt, neu, tab_vor=None):
    """In schritte[ab:] den Spaltennamen alt durch neu ersetzen. tab_vor = Tabelle vor schritte[ab] (mit dem Namen alt).
    Die Ersetzung endet, sobald alt wieder als neue Spalte auftaucht oder die Spalte entfernt/umbenannt wird.
    Gibt die Anzahl geänderter Schritte zurück."""
    if _gleicher_name(alt, neu) and alt == neu:
        return 0
    anzahl, tab = 0, tab_vor
    for k in range(ab, len(schritte)):
        st = schritte[k]
        if ersetze_spaltenname_im_schritt(st, alt, neu):
            anzahl += 1
        if tab is None or st.get("aktiv") is False:
            continue
        try:
            tab = wende_schritt(tab, st)
        except Exception:
            break
        low = [c.casefold() for c in tab.spalten]
        if neu.strip().casefold() not in low:
            break                                   # Spalte entfernt oder weiter umbenannt
        if alt.strip().casefold() in low and alt.strip().casefold() != neu.strip().casefold():
            break                                   # eine neue Spalte heißt wieder wie die alte
    return anzahl


def abfragename_in_verweisen(abfrage, alt, neu):
    """Alle Verweise auf die Abfrage alt (Quelle 'andere Abfrage', Verbinden, Anfügen) in abfrage auf neu umstellen.
    Gibt die Anzahl geänderter Stellen zurück."""
    n = 0
    q = abfrage.quelle
    if q.get("art") == "abfrage" and q.get("name") == alt:
        q["name"] = neu
        n += 1
    for st in abfrage.schritte:
        if st.get("op") == "tabellen_verbinden" and st.get("abfrage") == alt:
            st["abfrage"] = neu
            n += 1
        elif st.get("op") == "tabellen_anfuegen" and alt in (st.get("abfragen") or []):
            st["abfragen"] = [neu if x == alt else x for x in st["abfragen"]]
            n += 1
    return n


def abfrage_verweist_auf(abfrage):
    """Namen der Abfragen, auf die abfrage direkt zugreift."""
    namen = []
    if abfrage.quelle.get("art") == "abfrage" and abfrage.quelle.get("name"):
        namen.append(abfrage.quelle["name"])
    for st in abfrage.schritte:
        if st.get("op") == "tabellen_verbinden" and st.get("abfrage"):
            namen.append(st["abfrage"])
        elif st.get("op") == "tabellen_anfuegen":
            namen += [x for x in (st.get("abfragen") or []) if x]
    return namen


# Reihenfolge der Schritte im Menü: gleichartige Gegenstücke stehen untereinander
REIHENFOLGE = [
    "erste_zeile_als_kopf", "kopf_als_erste_zeile",
    "zeilen_entfernen_oben", "zeilen_behalten_oben", "zeilen_entfernen_unten", "zeilen_behalten_unten",
    "zeilen_bereich", "jede_nte_zeile", "filtern", "filtern_werte", "leere_zeilen_entfernen",
    "duplikate_entfernen", "duplikate_behalten", "fehler_zeilen_entfernen", "fehler_zeilen_behalten", "sortieren", "zeilen_umkehren",
    "spalten_entfernen", "spalten_behalten", "spalte_umbenennen", "spalten_umbenennen", "spalten_verschieben",
    "spalte_duplizieren", "fuellen_unten", "fuellen_oben", "spaltenreihenfolge_umkehren", "spalten_sortieren",
    "ersetzen", "leere_ersetzen", "fehler_ersetzen", "text_umwandeln", "text_extrahieren",
    "spalten_zusammenfuehren", "spalte_teilen", "bedingte_spalte", "benutzerdefinierte_spalte", "indexspalte",
    "gruppieren", "pivotieren", "entpivotieren", "transponieren",
    "rechnen", "runden", "zahleneigenschaft",
]


def ops_der_gruppe(gruppe):
    """[(op, definition)] einer Gruppe in Menüreihenfolge."""
    ops = [(op, d) for op, d in OPS.items() if d["gruppe"] == gruppe]
    rang = {op: k for k, op in enumerate(REIHENFOLGE)}
    return sorted(ops, key=lambda t: rang.get(t[0], len(REIHENFOLGE)))


SPALTEN_NAMEN_OPS = ("erste_zeile_als_kopf", "kopf_als_erste_zeile")


def umbenennungen_von(step):
    """[(alt, neu)] eines Umbenennen-Schritts (spalte_umbenennen / spalten_umbenennen)."""
    paare = []
    if step.get("op") == "spalte_umbenennen" and step.get("spalte") and str(step.get("neu") or "").strip():
        paare.append((step["spalte"], str(step["neu"]).strip()))
    elif step.get("op") == "spalten_umbenennen":
        for z in str(step.get("umbenennungen") or "").splitlines():
            if "=" in z:
                a, n = [t.strip() for t in z.split("=", 1)]
                if a and n and a != n:
                    paare.append((a, n))
    return paare


class Abfrage:
    def __init__(self, name="Abfrage1", quelle=None, schritte=None, ziel=None, auto=False, beschreibung=""):
        self.name = name
        self.beschreibung = beschreibung or ""
        self.quelle = quelle or {}
        self.schritte = schritte or []
        self.ziel = ziel or {"art": "blatt"}      # {"art": "blatt"} | {"art": "zelle", "blatt", "zelle", "letzter"}
        self.auto = bool(auto)                    # beim Öffnen der Datei aktualisieren

    def to_json(self):
        return json.dumps({"format": "abfrage-editor", "version": 1, "name": self.name,
                           "quelle": self.quelle, "schritte": self.schritte,
                           "ziel": self.ziel, "auto": self.auto, "beschreibung": self.beschreibung},
                          ensure_ascii=False, indent=1)

    @staticmethod
    def from_json(text):
        d = json.loads(text)
        if d.get("format") != "abfrage-editor":
            raise ValueError("Das ist keine Abfrage-Datei dieses Editors")
        return Abfrage(d.get("name", "Abfrage1"), d.get("quelle", {}), d.get("schritte", []),
                       d.get("ziel"), d.get("auto", False), d.get("beschreibung", ""))


# --------------------------------------------------------------------------
# Quellen lesen (ohne LibreOffice): CSV/Text, Zwischenablage, Excel (optional)
# --------------------------------------------------------------------------
def lese_text_bytes(daten):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return daten.decode(enc)
        except UnicodeDecodeError:
            continue
    return daten.decode("utf-8", errors="replace")


def erkenne_trenner(text):
    probe = text[:20000]
    zeilen = [z for z in probe.splitlines() if z.strip()][:20]
    if not zeilen:
        return ";"
    beste, bestzahl = ";", -1
    for t in (";", "\t", ",", "|"):
        zahlen = [z.count(t) for z in zeilen]
        if min(zahlen) > 0 and len(set(zahlen)) <= 2:
            wert = min(zahlen) * 100 - len(set(zahlen))
        else:
            wert = max(zahlen) - 1000 if max(zahlen) else -2000
        if wert > bestzahl:
            beste, bestzahl = t, wert
    return beste


def tabelle_aus_text(text, trenner=None):
    """CSV-/Tabulatortext -> Rohtabelle mit Spalten Spalte1..N (alles Text)."""
    if trenner in (None, "auto", ""):
        trenner = erkenne_trenner(text)
    zeilen = [r for r in csv.reader(io.StringIO(text), delimiter=trenner, quotechar='"')]
    breite = max([len(r) for r in zeilen] + [1])
    daten = [[(c if c != "" else None) for c in r] + [None] * (breite - len(r)) for r in zeilen]
    return Tabelle(["Spalte%d" % (i + 1) for i in range(breite)], daten)


def tabelle_aus_liste(zeilen):
    breite = max([len(r) for r in zeilen] + [1])
    return Tabelle(["Spalte%d" % (i + 1) for i in range(breite)],
                   [[(None if (isinstance(c, str) and c == "") else c) for c in r] for r in zeilen])
