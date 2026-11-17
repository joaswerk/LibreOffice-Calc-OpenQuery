#!/bin/bash
# Installiert die .oxt in ein frisches Profil, startet LibreOffice unter Xvfb und führt die Tests aus.
cd "$(dirname "$0")/.."
SCRATCH=${SCRATCH:-/tmp/claude-0/-home-claude/ea0bcda6-313b-5a47-b1ad-65d9b38f4ccc/scratchpad}
export SCRATCH
PROFIL="$SCRATCH/lo_profil"
rm -rf "$PROFIL" "$SCRATCH/ae_test" "$SCRATCH/meldungen.log"; mkdir -p "$SCRATCH"
pkill -x soffice.bin 2>/dev/null; pkill -x Xvfb 2>/dev/null; sleep 1
Xvfb :99 -screen 0 ${SCREEN:-1280x900x24} >/dev/null 2>&1 &
export DISPLAY=:99
sleep 1
./build.sh >/dev/null
unopkg remove --shared org.joaswerk.abfrageeditor >/dev/null 2>&1
unopkg add --shared build/OpenQuery.oxt 2>&1 | tail -3
unopkg list --shared 2>&1 | grep -i -A3 abfrage | head -6
ABFRAGE_MELDUNGSLOG="$SCRATCH/meldungen.log" ABFRAGE_AUTOCLOSE=${AUTOCLOSE:-5} ABFRAGE_AUTOOK=2 LC_ALL=C.UTF-8 soffice -env:UserInstallation=file://$PROFIL --norestore --nologo --nodefault \
  --accept="socket,host=localhost,port=2002;urp;" >"$SCRATCH/soffice.log" 2>&1 &
python3 -I tests/${TESTDATEI:-test_lo.py} 2>&1 | tail -${LINES_OUT:-80}
RC=${PIPESTATUS[0]}
if grep -q Traceback "$SCRATCH/soffice.log"; then echo "FEHLER: Ausnahmen im LibreOffice-Log:"; grep -B2 -A6 Traceback "$SCRATCH/soffice.log" | head -40; RC=1; fi
exit $RC
