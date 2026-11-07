#!/bin/bash
# Vigilante: open the Biblioteca disc from this USB stick when the user picks "Disco" on
# the Chinoppo home menu, and by itself when the player is switched on or wakes up.
# Started in the background by AutoScript at boot.
#
# How (measured 2026-11-04): bdpprog.1 writes its UI log to /dev/console. Picking the Disc
# icon logs "[mc_homemenu_select_disc_entry_new]". The M901 has no drive, so that icon was
# useless, and the home opens on it after power-on. (Until 2026-11-04 it was Películas,
# "e_curr_browser_type=3" after a home selection, which took away the USB file browser.)
# The log is read with `consola` (TIOCCONS on our own pty): nothing attaches to or stops
# the player. The first version used strace, which froze the player now and then.
#
# Standby cuts USB power: the stick comes back as a new disk (/mnt/sda1 -> /mnt/sdb1) and
# AutoScript does not run again. So this never exits: it follows the stick wherever it
# is mounted, and its reappearance is the "woke up" signal.
# Stop it: create a file named PARAR on the stick.
CHINOPPO_IP=192.168.1.16   # EDIT THIS: your player's fixed IP
PIDF=/tmp/vigilante.pid
API=http://127.0.0.1:436
D=/tmp/vigilante

[ -e "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null && exit 0   # already running
echo $$ > $PIDF

stick() {  # mount point of our stick, if it is in
  local d
  for d in /mnt/sd*; do [ -e "$d/Biblioteca.iso" ] && [ -d "$d/AutoScript" ] && { echo "$d"; return; }; done
}
log() { [ -n "$USB" ] && [ -d "$USB" ] && echo "$(date '+%F %T') $*" >> "$USB/vigilante.log"; }

wake() {  # after a cold boot :436 stays closed until this UDP packet arrives (bash /dev/udp)
  local h; for h in 127.0.0.1 $CHINOPPO_IP; do printf 'NOTIFY OREMOTE LOGIN' > /dev/udp/$h/7624; done
  sleep 2
}

open_library() {
  local inner="\"path\":\"$USB/Biblioteca.iso\",\"index\":0,\"type\":1,\"appDeviceType\":2,\"extraNetPath\":\"\",\"playMode\":0"
  local q r
  log "abriendo la Biblioteca ($1)"   # with the line below: how long the player takes to accept
  q=$(printf '%s' "$inner" | sed 's/"/%22/g; s/:/%3A/g; s/,/%2C/g')   # same encoding the service uses
  curl -s -m 1 "$API/getglobalinfo" | grep -q success || wake          # 2 s, only after a cold boot
  # Exactly ONE play order (-g: literal braces like the service): a retry after a slow
  # answer queued a second open that fired later by itself and jammed the player API.
  r=$(curl -g -s -m 90 "$API/playnormalfile?{$q}")   # cold BD-J after boot: >40 s
  log "aceptada: rc=$? $r"
}

open_when_ready() {  # power-on / wake: once the API answers and nothing is playing
  local i
  for ((i = 0; i < 30; i++)); do curl -s -m 2 "$API/getglobalinfo" | grep -q success && break; wake; sleep 1; done
  sleep 5   # let the home menu finish loading
  curl -s -m 3 "$API/getglobalinfo" | grep -q '"is_bdmv_playing":true\|"is_video_playing":true' \
    || open_library "$1"
}

busy() {
  curl -s -m 3 "$API/getglobalinfo" | grep -q '"is_bdmv_playing":true\|"is_video_playing":true'
}

on_disco() {
  # Presses made while an open is in flight queue up and arrive together (seen 2026-11-03:
  # five opens in one second; two opens jam the API): drop them while a disc is open.
  # A disc that is still closing (HOME right before Disco) gets a few seconds first.
  # The first version dropped everything for 20 s after an open, which ignored a quick
  # HOME -> Disco.
  local i
  for ((i = 0; i < 6; i++)); do
    if ! busy; then
      [ $i -gt 0 ] && sleep 3   # just closed: opening at once gives "No se puede reproducir"
      open_library Disco
      return
    fi
    sleep 1
  done
  log "Disco ignorado: la Biblioteca ya está abierta"
}

kill_consola() {
  local p
  for p in $(ps | awk '/[c]onsola/ {print $1}'); do kill $p 2>/dev/null; done
}

read -r up _ < /proc/uptime   # the player has no seq/cut: bash builtins only
first=1; gone=; prev=
while :; do
  USB=$(stick)
  if [ -z "$USB" ]; then gone=1; sleep 3; continue; fi
  [ -e "$USB/PARAR" ] && break
  if [ -n "$first" ]; then
    mkdir -p $D && cp "$USB/AutoScript/consola" $D/ && chmod 755 $D/consola   # /tmp: stick may be noexec
    log "vigilante arrancado (pid $$, $USB)"
    # The first BD-J disc after boot takes ~40 s (Java starts cold): opening it now means
    # the user's first Disco is instant.
    [ "${up%.*}" -lt 180 ] && open_when_ready encendido
  elif [ -n "$gone" ] || [ "$USB" != "$prev" ]; then   # gone, or back under a new name
    log "el pendrive volvió en $USB (despertó del standby)"
    open_when_ready despertar
  fi
  first=; gone=; prev=$USB
  # the loop below only wakes on menu lines: this ends it as soon as the stick goes
  # (standby) by killing consola, instead of on the next menu selection
  ( while [ -e "$USB/Biblioteca.iso" ] && [ ! -e "$USB/PARAR" ]; do sleep 3; done; kill_consola ) &
  watch=$!
  # awk keeps only the line that matters (the full log can reach ~80 KB/s while the
  # player indexes a share) so the bash loop never falls behind
  $D/consola 2>> "$USB/vigilante_err.txt" \
    | awk '/mc_homemenu_select_disc_entry_new/ {print; fflush()}' \
    | while read -r line; do
        [ -e "$USB/Biblioteca.iso" ] && [ ! -e "$USB/PARAR" ] || break
        on_disco
      done
  kill $watch 2>/dev/null
  kill_consola; sleep 1   # a leftover consola would keep the console and the next one would fail
done
log "vigilante parado"
rm -f $PIDF
