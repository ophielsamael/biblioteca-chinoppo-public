#!/bin/sh
# Read-only probe v7: 45 s of bdpprog.1 console writes via strace (observe only), keeping
# only home-menu lines, to learn which ui1_hlt_item_idx is "Películas". Writes to the stick.
O=/mnt/sda1/v7
mkdir -p $O
P=$(pidof bdpprog.1 2>/dev/null || ps | awk '/bdpprog\.1/ && !/awk/ {print $1; exit}')
echo "pid=$P" > $O/pid.txt
[ -n "$P" ] || exit 0
strace -f -p $P -e trace=write -s 160 -o $O/raw.txt &
S=$!
sleep 45
kill $S 2>/dev/null
sleep 1
grep -a "homemenu\|hlt_item_idx\|hlt_idx\|BTN_\|elem_type_movie\|e_curr_browser_type\|_mc_app_resume\|USB\|sda1" $O/raw.txt > $O/menu.txt 2>&1
wc -c $O/raw.txt >> $O/pid.txt 2>&1
echo listo > $O/terminado.txt
sync
