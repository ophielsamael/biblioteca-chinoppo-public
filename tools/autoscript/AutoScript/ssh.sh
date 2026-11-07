#!/bin/bash
# SSH into the Chinoppo, key-only (no passwords, no forwarding), started from the stick
# by arrancar.sh when a file named SSH is on it. Nothing is installed on the player:
# without the stick (or after a reboot) it is gone.
#   ssh -i ~/.ssh/chinoppo root@<IP-del-Chinoppo>
# Put YOUR public key in ssh/authorized_keys (see authorized_keys.example).
S=/mnt/sda1/AutoScript/ssh
D=/tmp/dropbear
mkdir -p $D
mkdir -p $D/.ssh
cp $S/dropbear $S/dropbearkey $D/   # run from /tmp: the stick may be noexec
cp $S/authorized_keys $D/.ssh/authorized_keys
chmod 700 $D $D/.ssh; chmod 600 $D/.ssh/authorized_keys; chmod 755 $D/dropbear $D/dropbearkey
# host key kept on the stick so its fingerprint survives reboots
[ -s $S/hostkey ] || $D/dropbearkey -t ed25519 -f $S/hostkey
# built with no password auth and no forwarding; its home (~/.ssh) is patched to /tmp/dropbear
$D/dropbear -r $S/hostkey -j -p 22 -P $D/pid
echo "$(date '+%F %T') dropbear rc=$? pid=$(cat $D/pid 2>/dev/null)" >> /mnt/sda1/ssh.log
sync
