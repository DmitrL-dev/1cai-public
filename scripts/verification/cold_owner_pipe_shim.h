/* Source proposal only: the single cp ABI for Root-private negative fixtures.
 * No execution admission, Editor role, production dispatch, SDK/model/1C API.
 * Root registers fresh zeroed CP_ARGS/CP_OUT storage before cp_call. Slots are
 * single use; all output memory and pointed-to input/OVERLAPPED/buffers remain
 * owned until the native producer has returned AND the exact IO has settled.
 */
#ifndef RENTGEN_COLD_OWNER_PIPE_SHIM_H
#define RENTGEN_COLD_OWNER_PIPE_SHIM_H
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#include <windows.h>
#include <stdint.h>
#include <stddef.h>

#define CP_ABI_VERSION 1u
#define CP_ABI_WORDS 6u
#define CP_IMAGE_CHARS 1024u
#define CP_EXPORT __declspec(dllexport)

typedef struct CP_ARGS {
    HANDLE a, b;
    void *p, *q;
    uint32_t count, flags;
    uint64_t number;
    LPCWSTR path;
    LPWSTR command;
    LPCWSTR environment, cwd;
} CP_ARGS;

typedef struct CP_OUT {
    uint32_t entered, done, ok, error;
    HANDLE h1, h2;
    uint32_t value, extra;
    uint64_t birth;
    WCHAR image[CP_IMAGE_CHARS];
} CP_OUT;

enum CP_OP {
    CP_CREATE_JOB=1, CP_SET_JOB=2, CP_JOB_LIMITS=3, CP_JOB_PIDS=4,
    CP_MEMBER=5, CP_CREATE_SD=6, CP_LOCAL_FREE=7, CP_CREATE_PIPE=8,
    CP_CREATE_EVENT=9, CP_CREATE_PROCESS=10, CP_RESUME=11,
    CP_IDENTITY=12, CP_PEER_PID=13, CP_CONNECT=14, CP_READ=15,
    CP_WRITE=16, CP_RESULT=17, CP_CANCEL=18, CP_CLOSE=19,
    CP_TERMINATE_JOB=20, CP_TERMINATE_PROCESS=21,
    CP_PROCESS_WAIT=22, CP_DUP_JOB=23
};

/* Compiler-enforced expected layouts. These are Source constraints; actual
 * compiler/build/layout evidence must be retained by Root separately. */
_Static_assert(sizeof(void*)==8, "Win64 required");
_Static_assert(sizeof(WCHAR)==2 && sizeof(DWORD)==4 && sizeof(LONG)==4,
               "Win64 Windows scalar ABI");
_Static_assert(sizeof(CP_ARGS)==80 && _Alignof(CP_ARGS)==8, "CP_ARGS ABI");
_Static_assert(sizeof(CP_OUT)==2096 && _Alignof(CP_OUT)==8, "CP_OUT ABI");
_Static_assert(sizeof(OVERLAPPED)==32 && _Alignof(OVERLAPPED)==8, "OVERLAPPED ABI");
#define CP_OFFSET(type, field, wanted) \
    _Static_assert(offsetof(type, field)==wanted, #type "." #field)
CP_OFFSET(CP_ARGS,a,0); CP_OFFSET(CP_ARGS,b,8);
CP_OFFSET(CP_ARGS,p,16); CP_OFFSET(CP_ARGS,q,24);
CP_OFFSET(CP_ARGS,count,32); CP_OFFSET(CP_ARGS,flags,36);
CP_OFFSET(CP_ARGS,number,40); CP_OFFSET(CP_ARGS,path,48);
CP_OFFSET(CP_ARGS,command,56); CP_OFFSET(CP_ARGS,environment,64);
CP_OFFSET(CP_ARGS,cwd,72);
CP_OFFSET(CP_OUT,entered,0); CP_OFFSET(CP_OUT,done,4);
CP_OFFSET(CP_OUT,ok,8); CP_OFFSET(CP_OUT,error,12);
CP_OFFSET(CP_OUT,h1,16); CP_OFFSET(CP_OUT,h2,24);
CP_OFFSET(CP_OUT,value,32); CP_OFFSET(CP_OUT,extra,36);
CP_OFFSET(CP_OUT,birth,40); CP_OFFSET(CP_OUT,image,48);
CP_OFFSET(OVERLAPPED,Internal,0); CP_OFFSET(OVERLAPPED,InternalHigh,8);
CP_OFFSET(OVERLAPPED,Offset,16); CP_OFFSET(OVERLAPPED,OffsetHigh,20);
CP_OFFSET(OVERLAPPED,hEvent,24);
_Static_assert(sizeof(SECURITY_ATTRIBUTES)==24, "SECURITY_ATTRIBUTES ABI");
_Static_assert(sizeof(STARTUPINFOEXW)==112, "STARTUPINFOEXW ABI");
_Static_assert(sizeof(PROCESS_INFORMATION)==24, "PROCESS_INFORMATION ABI");
#undef CP_OFFSET

/* cp_abi writes exactly six words: 1,8,80,2096,32,2.
 * cp_call returns no handle or status. CP_OUT is the sole result:
 * entered CAS 0->1, fields, release barrier, done=1.
 * READ/WRITE use NULL byte-count output for overlapped handles; CP_RESULT
 * retrieves the exact count from the same handle/OVERLAPPED, including after
 * immediate success. ERROR_IO_PENDING retains call/OV/buffer/event until result.
 * CONNECT ERROR_PIPE_CONNECTED: connected without pending request.
 * CONNECT count is undefined. CANCEL success/NOT_FOUND never settles IO.
 * CP_CLOSE/CP_LOCAL_FREE require Python's tombstone BEFORE dispatch, and
 * ambiguous outcome cannot be retried with the same numeric handle.
 * CP_ARGS carries only held resources from the exact Root lease; there is no
 * ownership adoption of client wire fields and no PID-open operation.
 */
CP_EXPORT void WINAPI cp_abi(uint32_t out_six[CP_ABI_WORDS]);
CP_EXPORT void WINAPI cp_call(uint32_t op, CP_ARGS *retained_args,
                             CP_OUT *retained_out);
#endif
