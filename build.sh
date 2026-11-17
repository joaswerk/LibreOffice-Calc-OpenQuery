#!/bin/bash
# Baut OpenQuery.oxt aus src/ und oxt/
set -e
cd "$(dirname "$0")"
rm -rf build/pkg && mkdir -p build/pkg
cp -r oxt/. build/pkg/
cp src/abfrage_editor.py build/pkg/abfrage_editor.py
cp src/engine.py build/pkg/abfrage_engine.py
python3 -I - <<'PY'
import zipfile, os
os.chdir("build/pkg")
with zipfile.ZipFile("../OpenQuery.oxt", "w", zipfile.ZIP_DEFLATED) as z:
    z.write("META-INF/manifest.xml")          # Manifest zuerst
    for root, _, files in os.walk("."):
        for f in sorted(files):
            p = os.path.relpath(os.path.join(root, f), ".")
            if p != "META-INF/manifest.xml":
                z.write(p)
print("gebaut:", os.path.abspath("../OpenQuery.oxt"))
PY
