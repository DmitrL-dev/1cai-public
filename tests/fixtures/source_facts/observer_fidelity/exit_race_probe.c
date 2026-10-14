#define _GNU_SOURCE
/* Synthetic observer-fidelity probe only; no Rentgen input or elevated rights. */
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void *sleeper(void *unused) {
    (void)unused;
    struct timespec delay = {0, 20000};
    for (;;) (void)nanosleep(&delay, NULL);
    return NULL;
}
int main(int argc, char **argv) {
    if (argc != 2 || argv[1][0] != '/' || getuid() == 0 || geteuid() != getuid()) return 2;
    struct stat expected;
    if (fstatat(AT_FDCWD, argv[1], &expected, AT_SYMLINK_NOFOLLOW) || !S_ISREG(expected.st_mode) || expected.st_size != 1) return 3;
    unsigned completed = 0;
    for (unsigned cycle = 0; cycle < 100; ++cycle) {
        pid_t pid = fork();
        if (pid < 0) return 4;
        if (!pid) {
            pthread_t threads[3];
            for (unsigned n=0;n<3;n++) if (pthread_create(&threads[n], NULL, sleeper, NULL)) _exit(5);
            struct timespec pause={0,200000};
            (void)nanosleep(&pause,NULL);
            _exit(0); /* exercise real group teardown of sleeping siblings */
        }
        for (;;) {
            struct stat current;
            if (fstatat(AT_FDCWD, argv[1], &current, AT_SYMLINK_NOFOLLOW) || current.st_dev != expected.st_dev || current.st_ino != expected.st_ino) return 6;
            int status=0;pid_t found=waitpid(pid,&status,WNOHANG);
            if (found == pid) {
                if (!WIFEXITED(status) || WEXITSTATUS(status)) return 7;
                completed++; break;
            }
            if (found < 0 && errno != EINTR) return 8;
            struct timespec pause={0,20000};(void)nanosleep(&pause,NULL);
        }
    }
    printf("completed_cycles=%u\n",completed);
    return 0;
}
