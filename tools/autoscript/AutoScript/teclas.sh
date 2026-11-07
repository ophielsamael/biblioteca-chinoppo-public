#!/bin/bash
# Read-only probe (no ptrace): does the remote reach Linux as an input device?
# 1) inventory of input devices; 2) for 60 s, raw events from every /dev/input/event*
# (evdev allows several readers: the player keeps getting every key).
O=/mnt/sda1/teclas_out   # not "teclas": FAT is case-insensitive and TECLAS is the switch file
mkdir -p $O
cat /proc/bus/input/devices > $O/devices.txt 2>&1
ls -l /dev/input /dev | grep -i "input\|event\|ir\|key\|remote" > $O/dev.txt 2>&1
grep -i "ir\|input\|key" /proc/devices /proc/misc > $O/proc.txt 2>&1
pids=
for e in /dev/input/event*; do
  [ -e "$e" ] || continue
  cat "$e" > $O/$(basename $e).bin 2>> $O/err.txt &
  pids="$pids $!"
done
sleep 60
kill $pids 2>/dev/null
ls -l $O >> $O/dev.txt
echo listo > $O/terminado.txt
sync
