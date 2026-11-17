# -*- coding: utf-8 -*-
import os, sys, threading, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE = T.AE
def main():
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    d = AE.Dlg(ctx, "Exp", 400, 200)
    smgr = ctx.ServiceManager
    d.add("Grid", "g", 10, 10, 380, 80, ShowRowHeader=False, VScroll=False, HScroll=False)
    cm = smgr.createInstance("com.sun.star.awt.grid.DefaultGridColumnModel")
    for i, (w, fl) in enumerate(((30, 0), (60, 0), (60, 1))):
        c = cm.createColumn(); c.Title = "Sp%d" % i; c.Resizeable = False; c.ColumnWidth = w; c.Flexibility = fl
        if fl:
            c.MaxWidth = 0
        cm.addColumn(c)
    gm = d.model.getByName("g"); gm.ColumnModel = cm
    dm = smgr.createInstance("com.sun.star.awt.grid.DefaultGridDataModel")
    dm.addRows(("1", "2", "3"), (("1", "a", "b"), ("2", "c", "d"), ("3", "e", "f")))
    gm.GridDataModel = dm
    gm.RowBackgroundColors = (0xFFFFFF, 0xE9F1FB)
    d.add("Button", "u", 10, 100, 70, 16, Label="Rückgängig", ImageURL="private:graphicrepository/cmd/lc_undo.png", ImagePosition=0)
    d.add("Button", "r", 90, 100, 70, 16, Label="Wiederholen", ImageURL="private:graphicrepository/cmd/lc_redo.png", ImagePosition=0)
    d.add("Button", "u2", 170, 100, 30, 16, Label="", ImageURL="private:graphicrepository/cmd/sc_undo.png")
    d.add("Button", "b1", 210, 100, 24, 16, Label="<>"); d.add("Button", "b2", 240, 100, 24, 16, Label="><")
    os.environ["ABFRAGE_AUTOCLOSE"] = "5"
    def t():
        time.sleep(2.5)
        subprocess.run("DISPLAY=:99 import -window root /tmp/exp_flex.png", shell=True)
        cols = list(d.ctrl("g").getModel().ColumnModel.getColumns())
        print("Breiten:", [c.ColumnWidth for c in cols])
    threading.Thread(target=t, daemon=True).start()
    d.zeigen(None); d.weg(); doc.close(True)
sys.exit(main())
