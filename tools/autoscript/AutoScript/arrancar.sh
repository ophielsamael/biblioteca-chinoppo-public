#!/bin/sh
# Launched by AutoScript (which can't background a command itself): start the vigilante
# in the background and return at once.
date > /mnt/sda1/autoscript_ok.txt
/bin/bash /mnt/sda1/AutoScript/vigilante.sh > /dev/null 2> /mnt/sda1/vigilante_err.txt &
echo "vigilante lanzado: pid $!" >> /mnt/sda1/autoscript_ok.txt
# ponytail: temporary probe, remove after the remote-key test
[ -e /mnt/sda1/TECLAS ] && /bin/bash /mnt/sda1/AutoScript/teclas.sh > /dev/null 2> /mnt/sda1/teclas_err.txt &
# key-only SSH while the stick is in (see ssh.sh)
[ -e /mnt/sda1/SSH ] && /bin/bash /mnt/sda1/AutoScript/ssh.sh > /dev/null 2> /mnt/sda1/ssh_err.txt &
sync
