/* Ancillary transport fault double. Never a source-accuracy implementation.
 * Compile only after source review. Mode/event FD exist only in the test wrapper.
 * No filesystem input, network, fork, or source-bearing output is implemented. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

static int events;
static int input_seen;
static void pause_ms(long ms) {
    struct timespec delay = {ms / 1000, (ms % 1000) * 1000000};
    while (nanosleep(&delay, &delay) && errno == EINTR) {}
}
static int write_all(int fd, const void *data, size_t size) {
    const char *p = data;
    while (size) {
        ssize_t n = write(fd, p, size);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 0;
        p += n; size -= (size_t)n;
    }
    return 1;
}
static void emit(char event) {
    if (!write_all(events, &event, 1)) _exit(3);
}
static void length(uint32_t n) {
    unsigned char h[4] = {n & 255, (n >> 8) & 255, (n >> 16) & 255, (n >> 24) & 255};
    if (!write_all(1, h, sizeof h)) _exit(3);
}
static void frame(const char *text) {
    size_t n = strlen(text); length((uint32_t)n);
    if (!write_all(1, text, n)) _exit(3);
}
static void fill(int fd, size_t n) {
    char block[1024]; memset(block, 'X', sizeof block);
    while (n) { size_t part = n < sizeof block ? n : sizeof block;
        if (!write_all(fd, block, part)) _exit(3);
        n -= part;
    }
}
/* The ordinary controls require these exact bytes, not merely nonempty input.
 * framed_exchange_delay is test-only: it validates framing/EOF for the actual
 * Go request used by the cancellation driver, without claiming schema validity. */
static int request(const char *mode) {
    static const char expected[] = "{\"SYNTH_REQUEST\":true}";
    unsigned char prefix[4]; size_t have = 0;
    while (have < sizeof prefix) {
        ssize_t n = read(0, prefix + have, sizeof prefix - have);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 0;
        if (!input_seen) { emit('I'); input_seen = 1; }
        have += (size_t)n;
    }
    uint32_t size = (uint32_t)prefix[0] | ((uint32_t)prefix[1] << 8) |
                    ((uint32_t)prefix[2] << 16) | ((uint32_t)prefix[3] << 24);
    int framed_only = !strcmp(mode, "framed_exchange_delay");
    if (!size || size > 1500000 || (!framed_only && size != sizeof expected - 1)) return 0;
    char block[4096]; size_t offset = 0;
    while (offset < size) {
        size_t part = size - offset < sizeof block ? size - offset : sizeof block;
        ssize_t n = read(0, block, part);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 0;
        if (!framed_only && memcmp(block, expected + offset, (size_t)n)) return 0;
        offset += (size_t)n;
    }
    ssize_t tail;
    do { tail = read(0, block, 1); } while (tail < 0 && errno == EINTR);
    if (tail != 0) return 0;
    emit('E'); return 1;
}
int main(int argc, char **argv) {
    if (argc != 7 || strcmp(argv[1], "--parent-pid") || strcmp(argv[3], "--probe")) return 2;
    int parent = atoi(argv[2]); events = atoi(argv[6]);
    struct rlimit zero = {0, 0}; int death = 0;
    if (parent <= 1 || prctl(PR_SET_PDEATHSIG, SIGKILL) ||
        prctl(PR_GET_PDEATHSIG, &death) || death != SIGKILL ||
        getppid() != parent || setrlimit(RLIMIT_CORE, &zero)) return 2;
    alarm(20); emit('S');
    const char *mode = argv[5];
    const char *protocol = !strcmp(argv[4], "scanner") ? "source_fact_scan_v1" : "submitted_source_facts_v1";
    if (!strcmp(mode, "hello_delay")) pause_ms(6000);
    if (!strcmp(mode, "hello_oversize")) { length(513); pause_ms(15000); return 2; }
    char hello[600];
    snprintf(hello, sizeof hello, "{\"protocol\":\"%s\",\"kind\":\"hello\",\"ownership\":\"linux_parent_death_v1\"}", protocol);
    if (!strcmp(mode, "hello_protocol")) strcpy(hello, "{\"protocol\":\"SYNTH_WRONG_PROTOCOL\",\"kind\":\"hello\",\"ownership\":\"linux_parent_death_v1\"}");
    if (!strcmp(mode, "hello_ownership")) snprintf(hello, sizeof hello, "{\"protocol\":\"%s\",\"kind\":\"hello\",\"ownership\":\"SYNTH_WRONG_OWNER\"}", protocol);
    if (!strcmp(mode, "hello_shape")) snprintf(hello, sizeof hello, "{\"protocol\":\"%s\",\"kind\":\"hello\",\"ownership\":\"linux_parent_death_v1\",\"SYNTH_EXTRA\":0}", protocol);
    if (!strcmp(mode, "hello_duplicate")) snprintf(hello, sizeof hello, "{\"protocol\":\"%s\",\"protocol\":\"%s\",\"kind\":\"hello\",\"ownership\":\"linux_parent_death_v1\"}", protocol, protocol);
    if (!strcmp(mode, "hello_limit")) { size_t n = strlen(hello); memset(hello+n-1, ' ', 512-n); hello[511] = '}'; hello[512] = 0; }
    frame(hello); emit('H');
    if (!request(mode)) return 3;
    if (!strcmp(mode, "exchange_delay") || !strcmp(mode, "framed_exchange_delay")) pause_ms(15000);
    if (!strcmp(mode, "stderr_limit")) fill(2, 65536);
    if (!strcmp(mode, "stderr_over")) fill(2, 65537);
    if (!strcmp(mode, "response_oversize")) { length(65537); pause_ms(15000); return 2; }
    if (!strcmp(mode, "partial")) { length(20); write_all(1, "{", 1); return 0; }
    if (!strcmp(mode, "empty")) return 0;
    if (!strcmp(mode, "response_limit")) { length(65536); fill(1, 65536); }
    else frame("{\"probe\":true}");
    emit('R');
    if (!strcmp(mode, "trailing")) { pause_ms(30); write_all(1, "SYNTH_TRAILING", 14); }
    if (!strcmp(mode, "nonzero")) return 2;
    if (!strcmp(mode, "stdout_open")) { close(2); pause_ms(15000); }
    if (!strcmp(mode, "stderr_open")) { close(1); pause_ms(15000); }
    if (!strcmp(mode, "unexited")) { close(1); close(2); pause_ms(15000); }
    emit('X'); return 0;
}
