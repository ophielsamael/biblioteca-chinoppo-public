#!/usr/bin/env bash
# Build Biblioteca.iso with bdj-sdk inside WSL Ubuntu (~/bdj/bdj-sdk, commit 9c48049).
# Run from Git Bash on the Windows PC:   bash disc/build.sh          -> disc/out/Biblioteca.iso
#                                        bash disc/build.sh test     -> runs ProtoTest on the host JDK
# WSL can't read the SMB share, so the sources are copied into the WSL filesystem first.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
distro=${WSL_DISTRO:-Ubuntu}
wsl_user=$(wsl -d "$distro" -- whoami | tr -d '\r')
work="//wsl.localhost/$distro/home/$wsl_user/bdj/bdj-sdk/samples/biblioteca"

rm -rf "$work" && mkdir -p "$work"
cp -r "$here/src" "$here/Makefile" "$work/"
target=${1:-all}
MSYS_NO_PATHCONV=1 wsl -d "$distro" -- bash -lc "cd ~/bdj/bdj-sdk/samples/biblioteca && make $target"
if [ "$target" = all ]; then
  mkdir -p "$here/out"
  cp "$work/Biblioteca.iso" "$here/out/Biblioteca.iso"
  ls -l "$here/out/Biblioteca.iso"
fi
