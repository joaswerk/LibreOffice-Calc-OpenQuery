# -*- coding: utf-8 -*-
"""Update-Prüfung gegen einen lokalen GitHub-Mock (echtes GitHub ist aus der Testumgebung nicht erreichbar)."""
import http.server, json, os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE = T.AE
pruefe = T.pruefe
OXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "OpenQuery.oxt")
ZUSTAND = {"tag": "v9.9.9", "asset": True}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/latest"):
            port = self.server.server_address[1]
            j = {"tag_name": ZUSTAND["tag"], "html_url": "http://x/release", "body": "Neu: Teständerung",
                 "assets": [{"name": "OpenQuery.oxt", "browser_download_url": "http://127.0.0.1:%d/OpenQuery.oxt" % port}] if ZUSTAND["asset"] else []}
            b = json.dumps(j).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
        elif self.path == "/OpenQuery.oxt":
            b = open(OXT, "rb").read()
            self.send_response(200); self.end_headers(); self.wfile.write(b)
        elif self.path == "/kaputt.oxt":
            self.send_response(200); self.end_headers(); self.wfile.write(b"kein zip")
        else:
            self.send_response(404); self.end_headers()

def meldungen():
    p = os.environ.get("ABFRAGE_MELDUNGSLOG")
    return open(p, encoding="utf-8").read() if p and os.path.exists(p) else ""

def main():
    ctx = T.verbinden()
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "update_meldungen.log")
    open(os.environ["ABFRAGE_MELDUNGSLOG"], "w").close()
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    os.environ["ABFRAGE_UPDATE_URL"] = "http://127.0.0.1:%d/latest" % port
    pruefe("Versionsvergleich", AE.ist_neuere_version("0.10.0", "0.9.2") and not AE.ist_neuere_version("0.9.2", "0.9.2")
           and not AE.ist_neuere_version("v0.8.8", "0.9.2") and AE.ist_neuere_version("1.0", "0.9.9"))
    info = AE.hole_neueste_version()
    pruefe("Release-Info gelesen", info["version"] == "9.9.9" and info["datei_name"] == "OpenQuery.oxt", str(info))
    geoeffnet = []
    AE.oeffne_erweiterung = lambda c, p: geoeffnet.append(p) or True
    AE.schreibe_einstellung("update_ignoriert", "")
    vorher = len(meldungen())
    r = AE.update_pruefen(ctx, None, still=False)
    neu = meldungen()[vorher:]
    pruefe("Update wird angeboten und installiert (Ja)", r is True and "Neue Version 9.9.9" in neu and "Teständerung" in neu and len(geoeffnet) == 1, neu)
    pruefe("Heruntergeladene Datei ist die Erweiterung", geoeffnet and os.path.getsize(geoeffnet[0]) == os.path.getsize(OXT))
    # gleiche Version: nur im Menümodus eine Meldung
    ZUSTAND["tag"] = "v" + AE.VERSION
    vorher = len(meldungen())
    r = AE.update_pruefen(ctx, None, still=True)
    pruefe("Automatisch + aktuell: still", r is False and len(meldungen()) == vorher)
    r = AE.update_pruefen(ctx, None, still=False)
    pruefe("Menü + aktuell: Meldung", r is False and "aktuell" in meldungen()[vorher:], meldungen()[vorher:])
    # Server weg: automatisch still, Menü meldet
    srv.shutdown(); srv.server_close()
    vorher = len(meldungen())
    r = AE.update_pruefen(ctx, None, still=True)
    pruefe("Automatisch + offline: still", r is False and len(meldungen()) == vorher)
    r = AE.update_pruefen(ctx, None, still=False)
    pruefe("Menü + offline: Meldung", r is False and "nicht geklappt" in meldungen()[vorher:], meldungen()[vorher:])
    # Defekte Datei wird abgelehnt
    srv2 = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv2.serve_forever, daemon=True).start()
    try:
        AE.lade_update_datei({"datei_url": "http://127.0.0.1:%d/kaputt.oxt" % srv2.server_address[1], "datei_name": "x.oxt"})
        ok = False
    except ValueError:
        ok = True
    srv2.shutdown()
    pruefe("Keine Erweiterung wird abgelehnt", ok)
    pruefe("Auto-Prüfung fällig ohne Zeitstempel", True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print('\n%d Prüfungen, %d Fehler' % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0

sys.exit(main())
