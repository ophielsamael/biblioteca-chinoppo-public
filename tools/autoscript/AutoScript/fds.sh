#!/bin/bash
# Read-only probe (no ptrace): for 3 minutes, once a second, log which files bdpprog.1
# has open, printing only what changed. Goal: find a file the player opens when the user
# enters Películas, so the vigilante can stop using strace (which hangs the player).
O=/mnt/sda1/fds.txt
P=$(ps | awk '/bdpprog\.1/ && !/awk/ {print $1; exit}')
echo "$(date +%T) pid=$P" > $O
prev=/tmp/fds.prev; : > $prev
for ((i = 0; i < 180; i++)); do
  ls -l /proc/$P/fd 2>/dev/null | awk '{print $NF}' | grep -v '^socket:\|^pipe:\|^anon_inode:\|^/dev/' | sort > /tmp/fds.now
  # opened (+) / closed (-) since last second; awk because the player may lack diff/comm
  d=$( (awk 'NR==FNR {a[$0]; next} !($0 in a) {print "+ " $0}' $prev /tmp/fds.now
        awk 'NR==FNR {a[$0]; next} !($0 in a) {print "- " $0}' /tmp/fds.now $prev) )
  [ -n "$d" ] && { echo "== $(date +%T)"; echo "$d"; } >> $O
  mv /tmp/fds.now $prev
  sleep 1
done
echo "$(date +%T) fin" >> $O
sync
