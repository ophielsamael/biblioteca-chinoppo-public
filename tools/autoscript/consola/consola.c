/* consola: copy the player's console log to stdout without ptrace.
 *
 * bdpprog.1 writes its UI log to /dev/console (fd 1). TIOCCONS on a pty we own redirects
 * everything written to /dev/console into that pty, so we read it from the master side,
 * the way bootlogd does. Nothing attaches to or stops the player.
 *
 * The player must never block on its log: stdout is non-blocking and whatever does not
 * fit is dropped. When this process exits the pty is released and the kernel sends the
 * console back to the UART by itself.
 *
 * Build: zig cc -target arm-linux-musleabihf -mcpu=cortex_a7 -static -O2 -o consola consola.c
 */
#define _XOPEN_SOURCE 600
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(void) {
    int m = posix_openpt(O_RDWR | O_NOCTTY);
    if (m < 0 || grantpt(m) || unlockpt(m)) { perror("pty"); return 1; }
    int s = open(ptsname(m), O_RDWR | O_NOCTTY);
    if (s < 0) { perror("pts"); return 1; }
    if (ioctl(s, TIOCCONS) < 0) { perror("TIOCCONS"); return 1; }
    fcntl(1, F_SETFL, fcntl(1, F_GETFL) | O_NONBLOCK);
    char buf[4096];
    for (;;) {
        ssize_t n = read(m, buf, sizeof buf);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 0;
        if (write(1, buf, n) < 0 && errno != EAGAIN) return 0;   /* reader gone: give the console back */
    }
}
