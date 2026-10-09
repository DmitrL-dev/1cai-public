from pathlib import Path
import difflib, hashlib, json

def instrument(r):
    report = []
    for v in ('6.8', '6.12'):
        root = r / f'strace-{v}'
        for name in ('syscall.c', 'strace.c'):
            p = root / 'src' / name
            old = p.read_text()
            s = old
            assert not 'RENTGEN_OBSERVER' in old, 'fresh source required'
            if name == 'syscall.c':
                needle = '\t\tif (ptrace(PTRACE_GET_SYSCALL_INFO, tcp->pid,\n\t\t\t   (void *) size, &ptrace_sci) < 0) {'
                repl = '\t\tlong audit_ret = ptrace(PTRACE_GET_SYSCALL_INFO, tcp->pid,\n\t\t\t   (void *) size, &ptrace_sci);\n\t\tint audit_errno = errno;\n\t\t(void) dprintf(2, "RENTGEN_OBSERVER info pid=%d entering=%u ret=%ld errno=%d op=%u retained_union_nr=%llu a0=%llu a1=%llu\\n",\n\t\t\ttcp->pid, !!entering(tcp), audit_ret, audit_ret < 0 ? audit_errno : 0,\n\t\t\t(unsigned) ptrace_sci.op, (unsigned long long) ptrace_sci.entry.nr,\n\t\t\t(unsigned long long) ptrace_sci.entry.args[0], (unsigned long long) ptrace_sci.entry.args[1]);\n\t\terrno = audit_errno;\n\t\tif (audit_ret < 0) {'
                assert s.count(needle) >= 1
                s = s.replace(needle, repl)
                needle = '\tget_regs_error = ptrace_getregset_or_getregs(tcp->pid);\n'
                repl = '\tget_regs_error = ptrace_getregset_or_getregs(tcp->pid);\n#if defined(X86_64)\n\t{\n\t\tint audit_errno = errno;\n\t\t(void) dprintf(2, "RENTGEN_OBSERVER regs pid=%d entering=%u ret=%ld errno=%d orig_rax=%llu rdi=%llu rsi=%llu rdx=%llu\\n",\n\t\t\ttcp->pid, !!entering(tcp), get_regs_error, get_regs_error < 0 ? audit_errno : 0,\n\t\t\t(unsigned long long) x86_64_regs.orig_rax, (unsigned long long) x86_64_regs.rdi,\n\t\t\t(unsigned long long) x86_64_regs.rsi, (unsigned long long) x86_64_regs.rdx);\n\t\terrno = audit_errno;\n\t}\n#endif\n'
                assert s.count(needle) >= 1
                s = s.replace(needle, repl)
            else:
                needle = '\t\tif (debug_flag)\n\t\t\tprint_debug_info(pid, status);'
                repl = '\t\t{\n\t\t\tint audit_errno = errno;\n\t\t\t(void) dprintf(2, "RENTGEN_OBSERVER wait pid=%d status=%u\\n", pid, (unsigned) status);\n\t\t\terrno = audit_errno;\n\t\t}\n\t\tif (debug_flag)\n\t\t\tprint_debug_info(pid, status);'
                assert s.count(needle) >= 1
                s = s.replace(needle, repl)
            p.write_text(s)
            (r / f'instrument-{v}-{name}.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True), s.splitlines(True), fromfile=name, tofile=name)))
            report.append({'version': v, 'path': name, 'before': hashlib.sha256(old.encode()).hexdigest(), 'after': hashlib.sha256(s.encode()).hexdigest()})
    for name in ('sched_attr.h', 'sched.c'):
        p = r / 'strace-6.8/src' / name
        old = p.read_text()
        new = old.replace('struct sched_attr', 'struct rentgen_compat_sched_attr')
        assert old != new
        p.write_text(new)
        (r / f'compat-6.8-{name}.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=name, tofile=name)))
        report.append({'version':'6.8','path':name,'before':hashlib.sha256(old.encode()).hexdigest(),'after':hashlib.sha256(new.encode()).hexdigest(),'kind':'glibc-private-tag-compatibility'})
    (r / 'instrumented-source.json').write_text(json.dumps(report, indent=2) + '\n')
