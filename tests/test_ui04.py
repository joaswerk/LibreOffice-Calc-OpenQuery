# -*- coding: utf-8 -*-
"""Tests für 0.2.5: Escape-Sperre, Umbenennen in Folgeschritten, Fehleranzeige, Ansicht, Layout, verzögerter Aufbau."""
import os
import sys
import threading
import time
import traceback
import types

import uno

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T  # noqa: E402

AE, E = T.AE, T.E
pruefe = T.pruefe
SCRATCH = os.environ.get("SCRATCH", "/tmp")


def main():
    import faulthandler
    faulthandler.dump_traceback_later(240, exit=True)
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        T.fuelle_auszug(doc)
        frame = doc.getCurrentController().getFrame()
        os.environ["ABFRAGE_AUTOCLOSE"] = "14"
        a = E.Abfrage("Bericht", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4]))
        ed = AE.Editor(ctx, frame, doc, a)
        res = {}

        def tun():
            try:
                time.sleep(7)
                ed.zeige()
                d = ed.d
                # Layout
                pos = lambda n: d.modell(n)
                u, l = pos("btnUndoK"), pos("lstSchritte")
                res["layout_undo"] = u.PositionY >= l.PositionY + l.Height - 1 and u.PositionX >= l.PositionX - 2
                res["layout_hinzu"] = pos("btnHinzu").PositionY > l.PositionY + l.Height - 1
                res["layout_vor"] = pos("lstVor").PositionY > pos("grid").PositionY + pos("grid").Height - 2
                res["umben_btn"] = pos("btnUmben").PositionY > l.PositionY
                res["nr"] = d.ctrl("grid").getModel().ColumnModel.getColumns()[0].Title
                # Escape (echter Tastendruck)
                from Xlib import X, display, XK
                from Xlib.ext import xtest
                dp = display.Display(":99")
                kc = dp.keysym_to_keycode(XK.XK_Escape)
                dp.screen().root.warp_pointer(700, 560); dp.sync(); time.sleep(0.3)
                xtest.fake_input(dp, X.ButtonPress, 1); dp.sync(); time.sleep(0.05)
                xtest.fake_input(dp, X.ButtonRelease, 1); dp.sync(); time.sleep(0.5)
                xtest.fake_input(dp, X.KeyPress, kc); dp.sync(); time.sleep(0.1)
                xtest.fake_input(dp, X.KeyRelease, kc); dp.sync(); time.sleep(1.5)
                res["esc_offen"] = bool(ed.d.dlg.isVisible()) if hasattr(ed.d.dlg, "isVisible") else True
                # Fehleranzeige
                ed.spalte_markieren("Verbrauch kWh")
                res["qual"] = d.ctrl("lblQual").getModel().Label
                ed.spalte_markieren("Objekt")
                res["name_label"] = d.ctrl("lblMarkiert").getModel().Label
                # Umbenennen vorne einfügen -> Folgeschritte
                ed.lstS.waehle(2)   # nach "erste Zeile als Kopf"
                ed.neuer_schritt("spalte_umbenennen", {"spalte": "Verbrauch kWh", "neu": "Menge"}, True, "nach")
                ed.abfrage.schritte.append({"op": "benutzerdefinierte_spalte", "neu": "Doppelt", "formel": "[Menge] * 2"})
                res["schritte_ok"] = None
                try:
                    E.fuehre_aus(ed.roh, ed.abfrage.schritte)
                    res["schritte_ok"] = True
                except E.StepError as e:
                    res["schritte_ok"] = str(e)
                # bestehenden Umbenennen-Schritt ändern (über Engine-Hook wie in aendern)
                k = [i for i, s_ in enumerate(ed.abfrage.schritte) if s_["op"] == "spalte_umbenennen"][0]
                alt = dict(ed.abfrage.schritte[k])
                neu = dict(alt, neu="Verbrauch")
                tab_vor = ed.tabelle_bis(k)
                ed.abfrage.schritte[k] = neu
                ed._umbenennung_weitergeben(k, alt, neu, tab_vor)
                res["formel_neu"] = ed.abfrage.schritte[-1]["formel"]
                try:
                    E.fuehre_aus(ed.roh, ed.abfrage.schritte)
                    res["schritte_ok2"] = True
                except E.StepError as e:
                    res["schritte_ok2"] = str(e)
                # Verzögerter Aufbau beim Schrittwechsel
                ed.liste_neu(2)
                ed._schritt_gewaehlt()
                time.sleep(1.5)
                res["gewaehlt_info"] = d.ctrl("lblInfo").getModel().Label
                # Ansicht bleibt nach Neuaufbau (nach rechts gescrollt)
                g = d.ctrl("grid")
                ed.liste_neu(len(ed.abfrage.schritte) + 1)
                ed.zeige(); time.sleep(1)
                g = d.ctrl("grid")
                g.goToCell(11, 0); time.sleep(0.8)
                vor = g.getColumnAtPoint(3, 5)
                ps_ = g.getPosSize()
                res["merk"] = (ps_.X, ps_.Y, ps_.Width, ps_.Height, [g.getColumnAtPoint(x_, 8) for x_ in (3, 100, 300, ps_.Width - 25, ps_.Width - 5)], g.getRowAtPoint(10, ps_.Height - 25), g.getRowAtPoint(10, 40))
                ed.zeige(); time.sleep(1.5)
                g = d.ctrl("grid")
                nach = g.getColumnAtPoint(3, 5)
                res["scroll"] = (vor, nach); res["merk"] = res.get("merk")
                os.system("DISPLAY=:99 import -window root %s/shot_025.png" % SCRATCH)
            except Exception:
                traceback.print_exc()
        th = threading.Thread(target=tun, daemon=True)
        th.start()
        t0 = time.time()
        ed.run()
        dauer = time.time() - t0
        th.join()
        pruefe("Layout: Zurück/Wiederholen als Icon-Knöpfe unter der Schrittliste", res.get("layout_undo") is True, str(res))
        pruefe("Layout: Schritt hinzufügen unter der Liste", res.get("layout_hinzu") is True, str(res))
        pruefe("Layout: Zeilenzahl-Auswahl unter der Tabelle", res.get("layout_vor") is True, str(res))
        pruefe("Schaltfläche Umbenennen unter der Liste", res.get("umben_btn") is True, str(res))
        pruefe("Nummernspalte heißt 'Nr.'", res.get("nr") == "Nr.", str(res.get("nr")))
        pruefe("Escape schließt den Editor nicht (Dialog lief bis AUTOCLOSE, %.1fs)" % dauer, dauer >= 13, str(res))
        pruefe("Fehleranzeige: 'Fehler: n · Leer: n'", res.get("qual", "").startswith("Fehler: ") and "Leer: " in res.get("qual", ""), res.get("qual", ""))
        pruefe("Name der angeklickten Spalte steht im Label", res.get("name_label") == "Objekt", str(res.get("name_label")))
        pruefe("Neuer Umbenennen-Schritt: Folgeschritte laufen weiter", res.get("schritte_ok") is True, str(res.get("schritte_ok")))
        pruefe("Geänderter Umbenennen-Schritt passt Formel an", res.get("formel_neu") == "[Verbrauch] * 2", str(res.get("formel_neu")))
        pruefe("... und alles läuft weiter", res.get("schritte_ok2") is True, str(res.get("schritte_ok2")))
        pruefe("Ansicht springt nach Neuaufbau nicht zu Spalte 1 zurück", res.get("scroll", (0, 0))[0] > 0 and res["scroll"][0] == res["scroll"][1], str(res.get("scroll")))
        pruefe("Schrittwechsel baut die Tabelle verzögert auf", res.get("gewaehlt_info", "").startswith("Schritt "), str(res.get("gewaehlt_info")))
    except Exception:
        traceback.print_exc()
        pruefe("UI-Test 0.2.5 ohne unerwartete Ausnahme", False, traceback.format_exc().splitlines()[-1])
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    for n, _, d in fehler:
        print("  FEHLER:", n, d)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
