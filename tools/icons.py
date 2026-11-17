# -*- coding: utf-8 -*-
"""Zeichnet die Symbole der OpenQuery-Leiste (einheitlicher Stil, zwei bis drei Farben, hell/dunkel tauglich).
Aufruf: python3 tools/icons.py  -> oxt/icons/*.png (96x96)"""
import os, math
from PIL import Image, ImageDraw

S = 8                      # Supersampling
N = 32 * S
BLAU, GRAU, HELL = (59, 130, 196), (125, 133, 144), (214, 222, 232)
ROT, GRUEN, ORANGE, GELB = (214, 69, 69), (47, 158, 91), (224, 138, 30), (240, 196, 60)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "oxt", "icons")


def p(v):
    return int(v * S)


class Bild:
    def __init__(self):
        self.im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, w=1, r=0):
        self.d.rounded_rectangle([p(x0), p(y0), p(x1), p(y1)], radius=p(r), fill=fill, outline=outline, width=p(w))

    def line(self, pts, fill=GRAU, w=1.5):
        self.d.line([(p(x), p(y)) for x, y in pts], fill=fill, width=p(w), joint="curve")

    def poly(self, pts, fill):
        self.d.polygon([(p(x), p(y)) for x, y in pts], fill=fill)

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, w=1):
        self.d.ellipse([p(x0), p(y0), p(x1), p(y1)], fill=fill, outline=outline, width=p(w))

    def arc(self, x0, y0, x1, y1, a0, a1, fill=GRAU, w=2):
        self.d.arc([p(x0), p(y0), p(x1), p(y1)], a0, a1, fill=fill, width=p(w))

    def speichern(self, name):
        os.makedirs(OUT, exist_ok=True)
        self.im.resize((96, 96), Image.LANCZOS).save(os.path.join(OUT, name + ".png"))


def tabelle(b, x=3, y=5, w=26, h=22, spalten=3, zeilen=4, kopf=BLAU, rot_z=None, rot_s=None, hell_z=(), hell_s=(),
            nur_kopf=False):
    """Tabellensymbol; Zeilen/Spalten hervorheben (hell_*) oder rot durchstreichen (rot_*)."""
    b.rect(x, y, x + w, y + h, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=1.5)
    zh, sb = h / zeilen, w / spalten
    for i in hell_z:
        b.rect(x + 1, y + i * zh, x + w - 1, y + (i + 1) * zh, fill=HELL + (255,))
    for j in hell_s:
        b.rect(x + j * sb, y + 1, x + (j + 1) * sb, y + h - 1, fill=HELL + (255,))
    if kopf:
        b.rect(x + 0.6, y + 0.6, x + w - 0.6, y + zh, fill=kopf + (255,), r=1)
    for i in range(1, zeilen):
        b.line([(x, y + i * zh), (x + w, y + i * zh)], fill=GRAU, w=0.8)
    for j in range(1, spalten):
        b.line([(x + j * sb, y), (x + j * sb, y + h)], fill=GRAU, w=0.8)
    if rot_z is not None:
        b.rect(x, y + rot_z * zh, x + w, y + (rot_z + 1) * zh, fill=ROT + (170,))
    if rot_s is not None:
        b.rect(x + rot_s * sb, y, x + (rot_s + 1) * sb, y + h, fill=ROT + (170,))


def kreuz(b, cx, cy, r=4, farbe=ROT, w=2.2):
    b.line([(cx - r, cy - r), (cx + r, cy + r)], farbe, w)
    b.line([(cx - r, cy + r), (cx + r, cy - r)], farbe, w)


def plus(b, cx, cy, r=4, farbe=GRUEN, w=2.4):
    b.line([(cx - r, cy), (cx + r, cy)], farbe, w)
    b.line([(cx, cy - r), (cx, cy + r)], farbe, w)


def pfeil(b, x0, y0, x1, y1, farbe=ORANGE, w=2.2, k=3.2):
    b.line([(x0, y0), (x1, y1)], farbe, w)
    a = math.atan2(y1 - y0, x1 - x0)
    for d in (2.6, -2.6):
        b.line([(x1, y1), (x1 - k * math.cos(a + d * 0.5 - 0.0) , y1 - k * math.sin(a + d * 0.5))], farbe, w)


def spitze(b, x, y, richtung, farbe=ORANGE, g=4):
    """Gefülltes Dreieck (richtung: u/o/l/r)."""
    t = {"u": [(x - g, y - g / 1.5), (x + g, y - g / 1.5), (x, y + g)],
         "o": [(x - g, y + g / 1.5), (x + g, y + g / 1.5), (x, y - g)],
         "l": [(x + g / 1.5, y - g), (x + g / 1.5, y + g), (x - g, y)],
         "r": [(x - g / 1.5, y - g), (x - g / 1.5, y + g), (x + g, y)]}[richtung]
    b.poly(t, farbe)


def buchstabe(b, x, y, txt, farbe=BLAU, gr=11):
    from PIL import ImageFont
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", p(gr))
    except Exception:
        f = ImageFont.load_default()
    b.d.text((p(x), p(y)), txt, fill=farbe, font=f)


def trichter(b, x=16, y=16, g=9, farbe=BLAU):
    b.poly([(x - g, y - g * 0.7), (x + g, y - g * 0.7), (x + 2, y + 1), (x + 2, y + g * 0.9), (x - 2, y + g * 0.6), (x - 2, y + 1)], farbe)


SYMBOLE = {}


def sym(name):
    def deko(f):
        SYMBOLE[name] = f
        return f
    return deko


def kreispfeile(b, cx=16, cy=16, r=11, farbe=BLAU, w=2.8):
    """Zwei Kreispfeile (Aktualisieren-Zeichen) um den Mittelpunkt."""
    b.arc(cx - r, cy - r, cx + r, cy + r, 200, 330, farbe, w)
    b.arc(cx - r, cy - r, cx + r, cy + r, 20, 150, farbe, w)
    spitze(b, cx + r * math.cos(math.radians(330)) + 1.5, cy + r * math.sin(math.radians(330)) + 1, "r", farbe, 3.6)
    spitze(b, cx + r * math.cos(math.radians(150)) - 1.5, cy + r * math.sin(math.radians(150)) - 1, "l", farbe, 3.6)


@sym("aktualisieren")
def _(b):
    tabelle(b, x=9.5, y=11, w=13, h=10, spalten=2, zeilen=3, kopf=BLAU)
    kreispfeile(b)


@sym("alle_aktualisieren")
def _(b):
    tabelle(b, x=11.5, y=12.5, w=11, h=8, spalten=2, zeilen=3, kopf=None)
    tabelle(b, x=8.5, y=10, w=11, h=8, spalten=2, zeilen=3, kopf=BLAU)
    kreispfeile(b)


@sym("ins_blatt")
def _(b):
    tabelle(b, x=3, y=9, w=26, h=20, spalten=3, zeilen=4, kopf=BLAU)
    b.line([(16, 1.5), (16, 14)], GRUEN, 3.2)
    spitze(b, 16, 15.5, "u", GRUEN, 4.8)


@sym("laden_schliessen")
def _(b):
    tabelle(b, x=3, y=11, w=26, h=18, spalten=3, zeilen=4, kopf=BLAU)
    b.line([(16, 1.5), (16, 12)], GRUEN, 3.2)
    spitze(b, 16, 13.5, "u", GRUEN, 4.6)
    kreuz(b, 26, 6, 2.6, ROT, 2.2)


@sym("laden_schliessen_in")
def _(b):
    tabelle(b, x=3, y=11, w=26, h=18, spalten=3, zeilen=4, kopf=BLAU)
    b.line([(12, 1.5), (12, 12)], GRUEN, 3.2)
    spitze(b, 12, 13.5, "u", GRUEN, 4.6)
    for x in (20, 25, 30):
        b.ellipse(x - 1.4, 5.4, x + 1.4, 8.2, fill=GRAU + (255,))


@sym("maximieren")
def _(b):
    b.rect(3.5, 3.5, 28.5, 28.5, outline=GRAU, w=1.8, r=3)
    b.line([(12, 20), (20, 12)], BLAU, 2.6)
    b.poly([(16.5, 7.5), (24.5, 7.5), (24.5, 15.5)], BLAU)
    b.poly([(15.5, 24.5), (7.5, 24.5), (7.5, 16.5)], BLAU)


@sym("speichern")
def _(b):
    b.rect(5, 4, 27, 28, fill=BLAU + (255,), r=2.5)
    b.rect(9, 4, 23, 12, fill=(255, 255, 255, 240))
    b.rect(10, 17, 22, 28, fill=(255, 255, 255, 240), r=1)
    b.rect(18, 5.5, 21, 10.5, fill=GRAU + (255,))


def text_mitte(b, cx, cy, txt, farbe=BLAU, gr=10):
    """Text genau um (cx, cy) zentrieren (gemessen), damit nichts aus dem Rahmen rutscht."""
    from PIL import ImageFont
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", p(gr))
    except Exception:
        f = ImageFont.load_default()
    x0, y0, x1, y1 = b.d.textbbox((0, 0), txt, font=f)
    b.d.text((p(cx) - (x0 + x1) / 2, p(cy) - (y0 + y1) / 2), txt, fill=farbe, font=f)


@sym("parameter")
def _(b):
    b.rect(3, 7, 29, 25, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=3)
    text_mitte(b, 16, 16, "{x}", BLAU, 10)


@sym("start_anpassen")
def _(b):
    for i, (y, kx) in enumerate(((8, 10), (16, 21), (24, 14))):
        b.line([(4, y), (28, y)], GRAU, 1.6)
        b.ellipse(kx - 3, y - 3, kx + 3, y + 3, fill=BLAU + (255,), outline=(255, 255, 255, 255), w=0.8)


@sym("symbole")
def _(b):
    b.rect(2.5, 5, 29.5, 15, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=2)
    text_mitte(b, 10, 10, "Abc", GRAU, 6.5)
    b.rect(18, 7, 27, 13, fill=BLAU + (255,), r=1)
    b.rect(2.5, 18, 29.5, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=2)
    tabelle(b, x=5, y=20, w=8, h=6, spalten=2, zeilen=2, kopf=BLAU)
    text_mitte(b, 22, 23, "Abc", GRAU, 6.5)


@sym("protokoll")
def _(b):
    b.rect(7, 3, 25, 29, fill=(255, 255, 255, 240), outline=GRAU, w=1.4, r=2)
    for y in (9, 14, 19):
        b.line([(10, y), (22, y)], GRAU, 1.3)
    b.ellipse(17, 20, 25, 28, fill=ROT + (255,))


@sym("spalten_waehlen")
def _(b):
    tabelle(b, hell_s=(0, 2), kopf=BLAU)
    b.line([(7, 15), (9.5, 17.5), (13.5, 12)], GRUEN, 2.2)
    b.line([(23.2, 15), (25.6, 17.5), (29, 12)], GRUEN, 0)


@sym("spalten_entfernen")
def _(b):
    tabelle(b, rot_s=1)
    kreuz(b, 16, 17, 4, ROT)


@sym("zeilen_behalten")
def _(b):
    tabelle(b, hell_z=(1, 2))
    b.line([(7, 16), (9.5, 18.5), (13.5, 13)], GRUEN, 2.2)


@sym("zeilen_entfernen")
def _(b):
    tabelle(b, rot_z=2)
    kreuz(b, 16, 17.7, 4, ROT)


@sym("sortieren")
def _(b):
    buchstabe(b, 3, 2, "A", BLAU, 10)
    buchstabe(b, 3, 15, "Z", GRAU, 10)
    b.line([(23, 6), (23, 24)], ORANGE, 2.4)
    spitze(b, 23, 27, "u", ORANGE, 4.5)


@sym("filtern")
def _(b):
    tabelle(b, x=3, y=4, w=20, h=14, spalten=2, zeilen=3)
    trichter(b, 21, 21, 8, BLAU)


@sym("ueberschrift")
def _(b):
    tabelle(b, zeilen=4, kopf=None, hell_z=(0,))
    b.rect(3.6, 5.6, 28.4, 10.5, fill=BLAU + (255,), r=1)
    pfeil(b, 16, 30, 16, 23, ORANGE)


@sym("gruppieren")
def _(b):
    tabelle(b, x=3, y=3, w=26, h=14, zeilen=3, spalten=3)
    b.rect(5, 21, 27, 28, fill=BLAU + (255,), r=1.5)
    buchstabe(b, 9, 19.5, "Σ", (255, 255, 255), 9)


@sym("datentyp")
def _(b):
    b.rect(3, 6, 29, 26, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=2.5)
    buchstabe(b, 5.5, 7.5, "1,2", BLAU, 9)
    b.rect(20, 17, 29, 26, fill=ORANGE + (255,), r=2)
    buchstabe(b, 21.7, 16.5, "A", (255, 255, 255), 8)


@sym("typen_erkennen")
def _(b):
    b.rect(3, 6, 29, 26, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=2.5)
    buchstabe(b, 5.5, 7.5, "123", BLAU, 9)
    b.line([(19, 20), (22, 23), (28, 15)], GRUEN, 2.6)


@sym("ersetzen")
def _(b):
    buchstabe(b, 3, 2, "a", BLAU, 11)
    buchstabe(b, 18, 15, "b", ORANGE, 11)
    pfeil(b, 9, 20, 19, 8, GRAU, 2)


@sym("ausfuellen")
def _(b):
    tabelle(b, zeilen=4, hell_z=(1,))
    pfeil(b, 16, 14, 16, 28, ORANGE, 2.4)


@sym("text")
def _(b):
    buchstabe(b, 2, 3, "Ab", BLAU, 15)
    b.line([(4, 26), (28, 26)], ORANGE, 2.4)


@sym("teilen")
def _(b):
    tabelle(b, spalten=3, hell_s=(0,))
    pfeil(b, 16, 30, 16, 20, ORANGE, 2)


@sym("runden")
def _(b):
    buchstabe(b, 2, 4, "1,5", GRAU, 10)
    spitze(b, 22, 22, "r", ORANGE, 4)
    buchstabe(b, 17, 12, "2", BLAU, 14)


@sym("rechnen")
def _(b):
    b.rect(5, 4, 27, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=2.5)
    b.rect(8, 7, 24, 12, fill=BLAU + (255,), r=1)
    for i in range(3):
        for j in range(3):
            b.rect(8 + j * 5.8, 15 + i * 4.2, 11.4 + j * 5.8, 17.8 + i * 4.2, fill=GRAU + (255,), r=0.6)


@sym("umbenennen")
def _(b):
    # Namensfeld mit Textcursor und Stift
    b.rect(3, 9, 24, 21, fill=(255, 255, 255, 240), outline=GRAU, w=1.4, r=2)
    buchstabe(b, 6, 11, "ab", BLAU, 9)
    b.line([(21, 11), (21, 19)], ORANGE, 1.6)
    b.poly([(18, 30), (19, 25), (29, 14), (32, 17), (22, 28)], ORANGE + (255,))
    b.poly([(18, 30), (19, 25), (22, 28)], GRAU + (255,))


@sym("transponieren")
def _(b):
    tabelle(b, x=3, y=3, w=16, h=16, spalten=2, zeilen=3)
    tabelle(b, x=15, y=15, w=15, h=14, spalten=3, zeilen=2, kopf=ORANGE)


@sym("entpivotieren")
def _(b):
    tabelle(b, x=3, y=4, w=26, h=10, zeilen=2, spalten=4)
    pfeil(b, 16, 16, 16, 21, ORANGE, 2.2)
    tabelle(b, x=9, y=22, w=14, h=8, zeilen=2, spalten=2)


@sym("pivotieren")
def _(b):
    tabelle(b, x=9, y=3, w=14, h=8, zeilen=2, spalten=2)
    pfeil(b, 16, 13, 16, 18, ORANGE, 2.2)
    tabelle(b, x=3, y=20, w=26, h=10, zeilen=2, spalten=4)


@sym("benutzerdefiniert")
def _(b):
    tabelle(b, spalten=3, hell_s=(2,))
    plus(b, 23.5, 17, 3.2, GRUEN)
    buchstabe(b, 0.5, 0, "fx", ORANGE, 8)


@sym("bedingt")
def _(b):
    tabelle(b, spalten=3, hell_s=(2,))
    buchstabe(b, 18, 11, "?", GRUEN, 14)


@sym("index")
def _(b):
    tabelle(b, spalten=3, hell_s=(0,))
    buchstabe(b, 4.2, 10.5, "123", GRAU, 5)
    plus(b, 25, 6, 3, GRUEN)


@sym("duplizieren")
def _(b):
    tabelle(b, x=3, y=3, w=17, h=17, spalten=2, zeilen=3, hell_s=(1,))
    tabelle(b, x=12, y=12, w=17, h=17, spalten=2, zeilen=3, hell_s=(1,))


@sym("zusammenfuehren")
def _(b):
    tabelle(b, spalten=3, hell_s=(0, 1))
    b.line([(8, 16), (24, 16)], ORANGE, 2.2)
    spitze(b, 22, 16, "r", ORANGE, 3.4)
    spitze(b, 10, 16, "l", ORANGE, 3.4)


@sym("manuell")
def _(b):
    tabelle(b, spalten=3, hell_s=(2,))
    b.line([(19, 24), (27, 12)], ORANGE, 2.6)
    b.poly([(17.5, 27), (18.5, 22.5), (21.5, 25)], GRAU)


@sym("verbinden")
def _(b):
    b.ellipse(3, 8, 19, 24, outline=BLAU, w=2)
    b.ellipse(13, 8, 29, 24, outline=ORANGE, w=2)
    b.d.pieslice([p(13), p(8), p(19.5), p(24)], 0, 360, fill=None)


@sym("anfuegen")
def _(b):
    tabelle(b, x=5, y=2, w=22, h=11, zeilen=3, spalten=3)
    tabelle(b, x=5, y=18, w=22, h=11, zeilen=3, spalten=3, kopf=ORANGE)
    spitze(b, 16, 15.7, "u", ORANGE, 2.2)


@sym("datei")
def _(b):
    b.poly([(7, 3), (20, 3), (26, 9), (26, 29), (7, 29)], (255, 255, 255, 240))
    b.line([(7, 3), (20, 3), (26, 9), (26, 29), (7, 29), (7, 3)], GRAU, 1.3)
    b.poly([(20, 3), (20, 9), (26, 9)], HELL + (255,))
    for y in (14, 18, 22):
        b.line([(10, y), (23, y)], BLAU, 1.6)


@sym("verweis")
def _(b):
    tabelle(b, x=3, y=3, w=18, h=14, zeilen=3, spalten=2)
    b.line([(21, 10), (26, 10), (26, 24), (17, 24)], ORANGE, 2.2)
    spitze(b, 16, 24, "l", ORANGE, 3.4)
    tabelle(b, x=10, y=20, w=14, h=10, zeilen=2, spalten=2, kopf=ORANGE)


@sym("gitter")
def _(b):
    b.rect(4, 4, 28, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=1.5)
    for i in (1, 2, 3):
        b.line([(4, 4 + i * 6), (28, 4 + i * 6)], GRAU, 1)
        b.line([(4 + i * 6, 4), (4 + i * 6, 28)], GRAU, 1)


@sym("details")
def _(b):
    tabelle(b, x=3, y=3, w=26, h=13, zeilen=3, spalten=3)
    b.rect(3, 19, 29, 29, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=1.5)
    b.line([(15, 19), (15, 29)], GRAU, 1)
    b.line([(3, 24), (29, 24)], GRAU, 1)


@sym("breite")
def _(b):
    tabelle(b, x=4, y=6, w=24, h=18, spalten=3, hell_s=(1,))
    pfeil(b, 9, 28, 23, 28, ORANGE, 1.8, 3)
    spitze(b, 9, 28, "l", ORANGE, 3)
    spitze(b, 23, 28, "r", ORANGE, 3)


@sym("breite_alle")
def _(b):
    tabelle(b, x=4, y=6, w=24, h=18, spalten=3, hell_s=(0, 1, 2))
    b.line([(7, 28), (25, 28)], ORANGE, 1.8)
    spitze(b, 7, 28, "l", ORANGE, 3)
    spitze(b, 25, 28, "r", ORANGE, 3)


@sym("abfragen_liste")
def _(b):
    b.rect(3, 4, 12, 28, fill=BLAU + (255,), r=1.5)
    b.rect(14, 4, 29, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=1.5)
    for y in (9, 14, 19):
        b.line([(5, y), (10, y)], (255, 255, 255, 255), 1.4)


@sym("schritte_liste")
def _(b):
    b.rect(20, 4, 29, 28, fill=BLAU + (255,), r=1.5)
    b.rect(3, 4, 18, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=1.5)
    for y in (9, 14, 19):
        b.line([(22, y), (27, y)], (255, 255, 255, 255), 1.4)


@sym("suche")
def _(b):
    b.ellipse(4, 4, 20, 20, fill=(255, 255, 255, 200), outline=BLAU, w=2.6)
    b.line([(18, 18), (28, 28)], BLAU, 3.4)


@sym("abfrage_neu")
def _(b):
    tabelle(b, x=3, y=7, w=22, h=20, spalten=3, zeilen=4)
    plus(b, 24, 8, 4.2, GRUEN, 2.8)


@sym("oeffnen")
def _(b):
    b.poly([(3, 9), (12, 9), (14, 12), (27, 12), (27, 26), (3, 26)], BLAU + (255,))
    b.poly([(3, 26), (7, 15), (30, 15), (26, 26)], (110, 168, 224, 255))


@sym("exportieren")
def _(b):
    # Blatt mit Eselsohr und Pfeil nach rechts aus dem Blatt heraus = in Datei speichern
    b.poly([(4, 3), (17, 3), (23, 9), (23, 29), (4, 29)], (255, 255, 255, 240))
    b.line([(4, 3), (17, 3), (23, 9), (23, 29), (4, 29), (4, 3)], GRAU, 1.4)
    b.line([(17, 3), (17, 9), (23, 9)], GRAU, 1.2)
    for yy in (13, 17, 21):
        b.line([(8, yy), (19, yy)], BLAU, 1.4)
    pfeil(b, 18, 25, 29, 25, ORANGE, 2.6)


@sym("updates")
def _(b):
    kreispfeile(b)
    pfeil(b, 16, 9, 16, 21, GRUEN, 2.8)
    b.line([(10, 25), (22, 25)], GRUEN, 2.4)


@sym("loeschen")
def _(b):
    b.rect(8, 10, 24, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.4, r=2)
    b.rect(6, 6, 26, 9, fill=GRAU + (255,), r=1)
    b.rect(13, 3, 19, 7, fill=GRAU + (255,), r=1)
    for x in (13, 16, 19):
        b.line([(x, 13), (x, 25)], ROT, 1.6)


@sym("eigenschaften")
def _(b):
    b.rect(4, 4, 28, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=2.5)
    buchstabe(b, 12.5, 4, "i", BLAU, 17)
    b.line([(8, 22), (24, 22)], GRAU, 1.6)
    b.line([(8, 26), (20, 26)], GRAU, 1.6)


@sym("ausgabe")
def _(b):
    tabelle(b, x=3, y=4, w=20, h=18, spalten=2, zeilen=3)
    pfeil(b, 16, 25, 29, 25, ORANGE, 2.4)
    spitze(b, 29, 25, "r", ORANGE, 3.4)


@sym("hoch")
def _(b):
    b.poly([(16, 5), (28, 20), (4, 20)], BLAU + (255,))
    b.rect(12.5, 20, 19.5, 28, fill=BLAU + (255,))


@sym("runter")
def _(b):
    b.poly([(16, 27), (28, 12), (4, 12)], BLAU + (255,))
    b.rect(12.5, 4, 19.5, 12, fill=BLAU + (255,))


@sym("autospeichern")
def _(b):
    b.rect(4, 5, 24, 27, fill=BLAU + (255,), r=2)
    b.rect(8, 5, 20, 12, fill=(255, 255, 255, 240))
    b.rect(8, 17, 20, 27, fill=(255, 255, 255, 240))
    b.ellipse(18, 18, 30, 30, fill=GRUEN + (255,))
    b.line([(24, 21), (24, 25), (27, 25)], (255, 255, 255), 1.6)


@sym("aendern")
def _(b):
    b.poly([(6, 26), (7.5, 20), (22, 5.5), (26.5, 10), (12, 24.5)], GELB + (255,))
    b.poly([(6, 26), (7.5, 20), (12, 24.5)], GRAU)
    b.line([(7.5, 20), (12, 24.5)], GRAU, 1)
    b.line([(22, 5.5), (26.5, 10)], ROT, 3)


@sym("ein_aus")
def _(b):
    b.arc(5, 6, 27, 28, -60, 240, GRUEN, 3)
    b.line([(16, 3), (16, 15)], GRUEN, 3)


@sym("bis_ende")
def _(b):
    tabelle(b, x=4, y=3, w=22, h=18, spalten=2, zeilen=4, rot_z=2)
    b.rect(4, 15, 26, 21, fill=ROT + (170,))
    spitze(b, 16, 27, "u", ROT, 4)
    b.line([(16, 21), (16, 24)], ROT, 2)


@sym("bedingung_schritt")
def _(b):
    b.rect(3, 4, 29, 28, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=3)
    buchstabe(b, 6, 6, "if", ORANGE, 14)


@sym("einfuegen_vor")
def _(b):
    b.rect(5, 17, 27, 25, fill=HELL + (255,), outline=GRAU, w=1, r=1.5)
    b.rect(5, 6, 27, 14, fill=GRUEN + (200,), r=1.5)
    plus(b, 16, 10, 3, (255, 255, 255), 2)


@sym("einfuegen_nach")
def _(b):
    b.rect(5, 6, 27, 14, fill=HELL + (255,), outline=GRAU, w=1, r=1.5)
    b.rect(5, 17, 27, 25, fill=GRUEN + (200,), r=1.5)
    plus(b, 16, 21, 3, (255, 255, 255), 2)


@sym("schritt_hinzu")
def _(b):
    b.rect(4, 4, 28, 12, fill=HELL + (255,), outline=GRAU, w=1, r=1.5)
    b.rect(4, 16, 22, 24, fill=HELL + (255,), outline=GRAU, w=1, r=1.5)
    plus(b, 25, 22, 4, GRUEN, 3)


@sym("rueckgaengig")
def _(b):
    b.arc(6, 8, 28, 28, 180, 360 + 70, BLAU, 3)
    spitze(b, 6.5, 15, "o", BLAU, 4.5)


@sym("wiederholen")
def _(b):
    b.arc(4, 8, 26, 28, 110, 360, BLAU, 3)
    spitze(b, 25.5, 15, "o", BLAU, 4.5)


@sym("spalten_ordnen")
def _(b):
    tabelle(b, spalten=3, hell_s=(0,))
    pfeil(b, 6, 30, 26, 30, ORANGE, 2)
    spitze(b, 26, 30, "r", ORANGE, 3)



@sym("mehr")
def _(b):
    b.rect(3, 9, 29, 23, fill=(255, 255, 255, 235), outline=GRAU, w=1.2, r=3)
    for x in (9, 16, 23):
        b.ellipse(x - 1.8, 14.2, x + 1.8, 17.8, fill=BLAU + (255,))


if __name__ == "__main__":
    for name, f in SYMBOLE.items():
        b = Bild()
        f(b)
        b.speichern(name)
        b.im.resize((22, 22), Image.LANCZOS).save(os.path.join(OUT, name + "_k.png"))     # kleine Fassung für Icon-Knöpfe (Knöpfe skalieren Bilder nicht)
        b.im.resize((33, 33), Image.LANCZOS).save(os.path.join(OUT, name + "_g.png"))     # große Fassung (+50 %) für die Knöpfe unter den Listen
    print(len(SYMBOLE), "Symbole ->", os.path.abspath(OUT))
