#define _GNU_SOURCE
/* Test-only, non-installed privilege reducer for one disposable Actions run.
 * No setuid bit, file capabilities, namespace, sysctl or sudoers modification.
 * Root is used only to reduce to the invoking user + CAP_SYS_PTRACE. The fixed
 * tracer gets that single capability; its fixed child clears all capabilities
 * before reading configuration or executing the pinned Python driver.
 */
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/capability.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef RENTGEN_PYTHON
#error RENTGEN_PYTHON must name the same-job test interpreter
#endif
#ifndef RENTGEN_SOURCE_ROOT
#error RENTGEN_SOURCE_ROOT must name the exact same-job source checkout
#endif

#define TRACE_BIT (1U << CAP_SYS_PTRACE)
#define LIMIT 4096
static char *const clean_env[] = {
    "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8",
    "PYTHONUTF8=1", "PYTHONDONTWRITEBYTECODE=1", NULL
};
static const char bootstrap[] =
    "import runpy,sys;root=sys.argv.pop(1);"
    "sys.path[:0]=[root,root+'/tests/unit'];"
    "runpy.run_path(sys.argv.pop(1),run_name='__main__')";

static void fail(void) {
    static const char message[] = "Owned trace capability setup failed\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1);
    _exit(125);
}

static unsigned identifier(const char *text) {
    if (!text || text[0] < '1' || text[0] > '9') fail();
    uint64_t value = 0;
    for (size_t i = 0; text[i]; ++i) {
        if (i >= 10 || text[i] < '0' || text[i] > '9') fail();
        value = value * 10 + (unsigned)(text[i] - '0');
        if (value > 2147483647U) fail();
    }
    return (unsigned)value;
}

static void caps(struct __user_cap_data_struct data[2], int write_caps) {
    struct __user_cap_header_struct header = {_LINUX_CAPABILITY_VERSION_3, 0};
    if (syscall(write_caps ? SYS_capset : SYS_capget, &header, data) != 0) fail();
}

static int last_cap(void) {
    for (int cap = 0; cap < 64; ++cap) {
        errno = 0;
        int value = prctl(PR_CAPBSET_READ, cap, 0L, 0L, 0L);
        if (value < 0) {
            if (errno == EINVAL && cap > CAP_SYS_PTRACE) return cap - 1;
            fail();
        }
    }
    fail();
    return -1;
}

static void verify_self(unsigned uid, unsigned gid, unsigned bit) {
    uid_t ruid, euid, suid;
    gid_t rgid, egid, sgid;
    struct __user_cap_data_struct data[2] = {{0}};
    if (getresuid(&ruid, &euid, &suid) || getresgid(&rgid, &egid, &sgid)
            || ruid != uid || euid != uid || suid != uid
            || rgid != gid || egid != gid || sgid != gid
            || getgroups(0, NULL) != 0) fail();
    caps(data, 0);
    if (data[0].effective != bit || data[0].permitted != bit
            || data[0].inheritable != bit || data[1].effective
            || data[1].permitted || data[1].inheritable) fail();
    for (int cap = 0, end = last_cap(); cap <= end; ++cap) {
        int want = bit && cap == CAP_SYS_PTRACE;
        if (prctl(PR_CAPBSET_READ, cap, 0L, 0L, 0L) != 0
                || prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_IS_SET, cap, 0L, 0L) != want) fail();
    }
    if (prctl(PR_GET_NO_NEW_PRIVS, 0L, 0L, 0L, 0L) != 1
            || prctl(PR_GET_KEEPCAPS, 0L, 0L, 0L, 0L) != 0) fail();
}

static void reduce_to_tracer(unsigned uid, unsigned gid) {
    if (getuid() != 0 || geteuid() != 0) fail();
    struct __user_cap_data_struct data[2] = {{0}};
    caps(data, 0);
    if (!(data[0].permitted & TRACE_BIT)) fail();
    /* I must be set while its bit is still in Bnd. Removing Bnd does not
       remove I; ambient exec propagation is independent of Bnd. */
    data[0].inheritable = TRACE_BIT;
    data[1].inheritable = 0;
    caps(data, 1);
    for (int cap = 0, end = last_cap(); cap <= end; ++cap)
        if (prctl(PR_CAPBSET_DROP, cap, 0L, 0L, 0L) != 0) fail();
    if (prctl(PR_SET_KEEPCAPS, 1L, 0L, 0L, 0L)
            || setgroups(0, NULL) || setresgid(gid, gid, gid)
            || setresuid(uid, uid, uid)) fail();
    memset(data, 0, sizeof(data));
    data[0].permitted = data[0].effective = data[0].inheritable = TRACE_BIT;
    caps(data, 1);
    if (prctl(PR_SET_KEEPCAPS, 0L, 0L, 0L, 0L)
            || prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0L, 0L, 0L)
            || prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_SYS_PTRACE, 0L, 0L)
            || prctl(PR_SET_NO_NEW_PRIVS, 1L, 0L, 0L, 0L)) fail();
    verify_self(uid, gid, TRACE_BIT);
    struct rlimit limit;
    if (getrlimit(RLIMIT_FSIZE, &limit)) fail();
    if (limit.rlim_cur > 32 * 1024 * 1024) limit.rlim_cur = 32 * 1024 * 1024;
    if (limit.rlim_max > 32 * 1024 * 1024) limit.rlim_max = 32 * 1024 * 1024;
    if (setrlimit(RLIMIT_FSIZE, &limit)) fail();
    limit.rlim_cur = limit.rlim_max = 0;
    if (setrlimit(RLIMIT_CORE, &limit)) fail();
}

static void drop_tracee(unsigned uid, unsigned gid) {
    /* No path selected by the caller is opened before these irreversible drops. */
    struct __user_cap_data_struct data[2] = {{0}};
    if (getuid() == 0 || geteuid() == 0
            || prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0L, 0L, 0L)) fail();
    caps(data, 1);
    if (prctl(PR_SET_NO_NEW_PRIVS, 1L, 0L, 0L, 0L)) fail();
    verify_self(uid, gid, 0);
}

static void read_status(pid_t pid, char *body, size_t capacity) {
    char path[80];
    if (pid <= 1 || snprintf(path, sizeof(path), "/proc/%ld/status", (long)pid) >= (int)sizeof(path)) fail();
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) fail();
    size_t used = 0;
    for (;;) {
        if (used == capacity - 1) fail();
        ssize_t size = read(fd, body + used, capacity - 1 - used);
        if (size < 0 && errno == EINTR) continue;
        if (size < 0) fail();
        if (!size) break;
        used += (size_t)size;
    }
    if (!used || close(fd)) fail();
    body[used] = 0;
}

static void record_parent(unsigned uid, unsigned gid, const char *config) {
    char body[16384], receipt[LIMIT];
    pid_t parent = getppid();
    read_status(getpid(), body, sizeof(body));
    unsigned self_fields = 0;
    for (char *line = strtok(body, "\n"); line; line = strtok(NULL, "\n")) {
        unsigned a, b, c, d;
        if (sscanf(line, "TracerPid:\t%u", &a) == 1) {
            if (a != (unsigned)parent) fail();
            self_fields |= 1;
        } else if (sscanf(line, "Uid:\t%u %u %u %u", &a, &b, &c, &d) == 4) {
            if (a != uid || b != uid || c != uid || d != uid) fail();
            self_fields |= 2;
        } else if (sscanf(line, "Gid:\t%u %u %u %u", &a, &b, &c, &d) == 4) {
            if (a != gid || b != gid || c != gid || d != gid) fail();
            self_fields |= 4;
        }
    }
    if (self_fields != 7) fail();
    struct stat carrier;
    int access = fcntl(STDIN_FILENO, F_GETFL), flags = fcntl(STDIN_FILENO, F_GETFD);
    if (fstat(STDIN_FILENO, &carrier) || !S_ISFIFO(carrier.st_mode)
            || access < 0 || (access & O_ACCMODE) != O_WRONLY
            || flags < 0 || (flags & FD_CLOEXEC)) fail();
    read_status(parent, body, sizeof(body));
    unsigned fields = 0;
    for (char *line = strtok(body, "\n"); line; line = strtok(NULL, "\n")) {
        unsigned a, b, c, d;
        unsigned long long value;
        if (!strncmp(line, "Groups:", 7)) {
            for (const char *p = line + 7; *p; ++p)
                if (*p != ' ' && *p != '\t') fail();
            fields |= 256;
        } else if (sscanf(line, "Uid:\t%u %u %u %u", &a, &b, &c, &d) == 4) {
            if (a != uid || b != uid || c != uid || d != uid) fail();
            fields |= 1;
        } else if (sscanf(line, "Gid:\t%u %u %u %u", &a, &b, &c, &d) == 4) {
            if (a != gid || b != gid || c != gid || d != gid) fail();
            fields |= 2;
        } else if (sscanf(line, "CapInh:\t%llx", &value) == 1) {
            if (value != TRACE_BIT) fail();
            fields |= 4;
        } else if (sscanf(line, "CapPrm:\t%llx", &value) == 1) {
            if (value != TRACE_BIT) fail();
            fields |= 8;
        } else if (sscanf(line, "CapEff:\t%llx", &value) == 1) {
            if (value != TRACE_BIT) fail();
            fields |= 16;
        } else if (sscanf(line, "CapBnd:\t%llx", &value) == 1) {
            if (value != 0) fail();
            fields |= 32;
        } else if (sscanf(line, "CapAmb:\t%llx", &value) == 1) {
            if (value != TRACE_BIT) fail();
            fields |= 64;
        } else if (sscanf(line, "NoNewPrivs:\t%u", &a) == 1) {
            if (a != 1) fail();
            fields |= 128;
        }
    }
    if (fields != 511 || getppid() != parent) fail();
    const char *slash = strrchr(config, '/');
    if (!slash || strcmp(slash, "/config.json")) fail();
    if (snprintf(receipt, sizeof(receipt), "%.*s/trace-capabilities.json",
                 (int)(slash - config), config) >= (int)sizeof(receipt)) fail();
    int fd = open(receipt, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) fail();
    int length = snprintf(body, sizeof(body),
        "{\"schema\":1,\"uid\":%u,\"gid\":%u,\"tracer_pid\":%ld,"
        "\"tracee_pid\":%ld,\"tracer_capability\":\"0000000000080000\","
        "\"tracer_bounding\":0,\"tracee_capabilities\":0,\"no_new_privs\":true}\n",
        uid, gid, (long)parent, (long)getpid());
    if (length <= 0 || length >= (int)sizeof(body)) fail();
    size_t written = 0;
    while (written < (size_t)length) {
        ssize_t n = write(fd, body + written, (size_t)length - written);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) fail();
        written += (size_t)n;
    }
    if (close(fd)) fail();
}

int main(int argc, char **argv) {
    if (argc == 4 && !strcmp(argv[1], "--tracer")) {
        unsigned uid = identifier(getenv("SUDO_UID")), gid = identifier(getenv("SUDO_GID"));
        if (argv[2][0] != '/' || argv[3][0] != '/' || strlen(argv[2]) > LIMIT - 32 || strlen(argv[3]) >= LIMIT) fail();
        reduce_to_tracer(uid, gid);
        char self[LIMIT], user[12], group[12];
        ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
        if (n <= 0 || n >= (ssize_t)sizeof(self) - 1) fail();
        self[n] = 0;
        if (self[0] != '/' || strstr(self, " (deleted)")) fail();
        snprintf(user, sizeof(user), "%u", uid); snprintf(group, sizeof(group), "%u", gid);
        char *command[] = {"/usr/bin/strace", "--kill-on-exit", "-f", "-qq", "-ttt", "-yy", "-s", "4096", "-o", argv[3],
            "--", self, "--tracee", user, group, argv[2], NULL};
        execve(command[0], command, clean_env);
        fail();
    }
    if (argc == 5 && !strcmp(argv[1], "--tracee")) {
        unsigned uid = identifier(argv[2]), gid = identifier(argv[3]);
        drop_tracee(uid, gid);
        if (argv[4][0] != '/' || strlen(argv[4]) > LIMIT - 32) fail();
        record_parent(uid, gid, argv[4]);
        char *command[] = {RENTGEN_PYTHON, "-I", "-B", "-c", (char *)bootstrap,
            RENTGEN_SOURCE_ROOT, RENTGEN_SOURCE_ROOT "/tests/unit/test_source_fact_lifecycle_completion.py",
            "trace-host", argv[4], "0", NULL};
        execve(command[0], command, clean_env);
        fail();
    }
    fail();
}
