#!/bin/bash
# Startet Xvfb + LibreOffice (socket 2002) im Hintergrund; installiert die aktuelle .oxt (shared).
cd "$(dirname "$0")/.."
SCRATCH=${SCRATCH:-/tmp/claude-0/-home-claude/ea0bcda6-313b-5a47-b1ad-65d9b38f4ccc/scratchpad}
export SCRATCH
PROFIL="$SCRATCH/lo_profil"
rm -rf "$PROFIL" "$SCRATCH/ae_test" "$SCRATCH/meldungen.log"; mkdir -p "$SCRATCH"
pkill -x soffice.bin 2>/dev/null; pkill -x Xvfb 2>/dev/null; sleep 1
Xvfb :99 -screen 0 1280x900x24 >/dev/null 2>&1 &
export DISPLAY=:99
sleep 1
./build.sh >/dev/null
unopkg remove --shared org.joaswerk.abfrageeditor >/dev/null 2>&1
unopkg add --shared build/OpenQuery.oxt 2>&1 | tail -2
ABFRAGE_MELDUNGSLOG="$SCRATCH/meldungen.log" ABFRAGE_AUTOCLOSE=${AUTOCLOSE:-5} ABFRAGE_AUTOOK=2 \
  soffice -env:UserInstallation=file://$PROFIL --norestore --nologo --nodefault \
  --accept="socket,host=localhost,port=2002;urp;" >"$SCRATCH/soffice.log" 2>&1 &
for i in $(seq 1 60); do
  python3 -I -c "
import socket; s=socket.socket(); s.settimeout(1)
s.connect(('localhost',2002))" 2>/dev/null && break; sleep 1
done
echo "LibreOffice bereit"
