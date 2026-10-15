"""One synchronous pair-read owner. Accounting bounds are not a hard RSS limit.

The POSIX/SQLite seams reserve conservative envelopes *before* their eager
allocations. Cumulative work is never refunded; held leases are released only
after their concrete owner has closed the corresponding native resources.
"""
from dataclasses import asdict, dataclass
import os
from threading import get_ident
from time import monotonic

from .errors import CoreError


@dataclass(frozen=True)
class ReadOperationLimits:
    copied_bytes: int = 512 * 1024**2
    image_bytes: int = 8 * 1024**3
    source_entries: int = 40_000
    inventory_items: int = 1_200_000
    row_bytes: int = 128 * 1024**2
    vm_steps: int = 20_000_000
    descriptors: int = 8192
    cursors: int = 32
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (5 * 1024**3, 16 * 1024**3, 40_000, 1_200_000,
                  2 * 1024**3, 200_000_000, 131_072, 128, 30)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded read-operation limits required")


def _invalid():
    return CoreError("SNAPSHOT_READ_SESSION_INVALID", "Read operation is not active on its owner")


def _limit():
    return CoreError("SNAPSHOT_READ_LIMIT_EXCEEDED", "Shared read-operation budget exceeded")


class _Lease:
    def __init__(self, budget, kind, amount):
        self._budget, self._kind, self._amount = budget, kind, amount

    def close(self):
        budget = self._budget
        if budget is not None:
            budget._owner_check()
            budget._held[self._kind] -= self._amount
            self._budget = None

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close()
        return False


class ReadOperationBudget:
    """Trusted composition input; never construct it from public request fields.

    Defaults admit two ordinary capture envelopes (64 MiB sources, 64 MiB
    graphs, 8 MiB manifests each), including the 256x manifest parse/index
    allowance. This is deliberately conservative accounting, not measured RAM
    or a promise that every historical maximum-sized retained tree fits.
    """
    def __init__(self, limits=None, *, cancelled=lambda: False):
        self.limits = ReadOperationLimits() if limits is None else limits
        if type(self.limits) is not ReadOperationLimits or not callable(cancelled):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed operation limits and cancellation required")
        self._owner = (os.getpid(), get_ident())
        self.deadline = monotonic() + self.limits.deadline_seconds
        self._cancelled, self._busy, self._closed = cancelled, False, False
        self._used = dict.fromkeys(("copied_bytes", "source_entries", "inventory_items", "row_bytes", "vm_steps"), 0)
        self._held = dict.fromkeys(("image_bytes", "descriptors", "cursors"), 0)
        self._peaks = dict(self._held)
        self._owners = set()
        self._acknowledged = 0

    def _owner_check(self):
        if self._owner != (os.getpid(), get_ident()) or self._closed or self._busy:
            raise _invalid()

    def checkpoint(self):
        self._owner_check()
        self._busy = True
        try:
            if monotonic() >= self.deadline:
                raise CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "Shared read-operation deadline exceeded")
            if self._cancelled():
                raise CoreError("REQUEST_CANCELLED", "Snapshot comparison was cancelled")
            if monotonic() >= self.deadline:
                raise CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "Shared read-operation deadline exceeded")
        finally:
            self._busy = False

    def _charge(self, kind, amount):
        self.checkpoint()
        if type(amount) is not int or amount < 0:
            raise _invalid()
        if self._used[kind] + amount > getattr(self.limits, kind):
            raise _limit()
        self._used[kind] += amount

    def charge_copy(self, amount): self._charge("copied_bytes", amount)
    def charge_entries(self, amount): self._charge("source_entries", amount)
    def charge_inventory(self, amount): self._charge("inventory_items", amount)
    def charge_rows(self, amount): self._charge("row_bytes", amount)
    def charge_vm(self, amount): self._charge("vm_steps", amount)

    def _reserve(self, kind, amount):
        self.checkpoint()
        if type(amount) is not int or amount < 0:
            raise _invalid()
        if self._held[kind] + amount > getattr(self.limits, kind):
            raise _limit()
        self._held[kind] += amount
        self._peaks[kind] = max(self._peaks[kind], self._held[kind])
        return _Lease(self, kind, amount)

    def reserve_images(self, amount): return self._reserve("image_bytes", amount)
    def reserve_descriptors(self, amount): return self._reserve("descriptors", amount)
    def reserve_cursor(self): return self._reserve("cursors", 1)

    def owner_opened(self, owner):
        self.checkpoint()
        if id(owner) in self._owners:
            raise _invalid()
        self._owners.add(id(owner))

    def owner_closed(self, owner):
        self._owner_check()  # Cleanup remains possible after deadline/cancellation.
        if id(owner) not in self._owners:
            raise _invalid()
        self._owners.remove(id(owner))
        self._acknowledged += 1

    def _finish(self):
        self._owner_check()
        if self._owners or any(self._held.values()):
            raise _invalid()
        self._closed = True
        self._cancelled = None

    def close(self):
        self.checkpoint()
        self._finish()

    def abort(self):
        self._finish()

    def summary(self):
        if self._owner != (os.getpid(), get_ident()) or self._busy:
            raise _invalid()
        return {"cumulative": dict(self._used), "held": dict(self._held),
                "peaks": dict(self._peaks), "owners_closed": self._acknowledged,
                "active_owners": len(self._owners), "closed": self._closed,
                "accounting": "conservative_precharges_not_hard_rss"}
