#!/bin/bash
set -e
cd ~/ssh-build
[ -d zig-linux-x86_64-0.13.0 ] || tar xf zig-linux-x86_64-0.13.0.tar.xz
rm -rf dropbear-2024.86 && tar xf dropbear-2024.86.tar.bz2 && cd dropbear-2024.86
cat > localoptions.h <<'H'
/* key-only: no password logins at all */
#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PAM_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_X11FWD 0
#define DROPBEAR_SVR_AGENTFWD 0
#define DROPBEAR_SVR_LOCALTCPFWD 0
#define DROPBEAR_SVR_REMOTETCPFWD 0
#define DEFAULT_PATH "/usr/bin:/usr/sbin:/bin:/sbin:/usr/local/bin"
H
# the player's /root is on read-only flash: home (and so ~/.ssh/authorized_keys) lives in /tmp
sed -i 's|ses.authstate.pw_dir = m_strdup(pw->pw_dir);|ses.authstate.pw_dir = m_strdup("/tmp/dropbear");|' src/common-session.c
grep -q '"/tmp/dropbear"' src/common-session.c
# root's shell may be missing from /etc/shells on the player: accept it
sed -i 's|^\tsetusershell();$|\tgoto goodshell;\n\tsetusershell();|' src/svr-auth.c
grep -q 'goto goodshell;' src/svr-auth.c
Z=~/ssh-build/zig-linux-x86_64-0.13.0/zig
export CC="$Z cc -target arm-linux-musleabihf -mcpu=cortex_a7"
export AR="$Z ar" RANLIB="$Z ranlib"
./configure --host=arm-linux-musleabihf --disable-zlib --disable-lastlog --disable-utmp --disable-utmpx \
  --disable-wtmp --disable-wtmpx --disable-pututline --disable-pututxline --enable-static >/dev/null
make -j8 PROGRAMS="dropbear dropbearkey" STATIC=1 >/dev/null
file dropbear dropbearkey
ls -la dropbear dropbearkey
