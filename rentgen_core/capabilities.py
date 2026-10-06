"""OS support is distinct from project authority and installed tool availability.

The adapter allowlists deliberately fail closed: a new command is not portable
until it has an explicit contract here. This module never reads project files.
"""
import sys

from .errors import CoreError

_platform = sys.platform
CONTRACT_VERSION = 1

_GROUPS = {
    "runtime.inspect": ("capabilities",),
    "identity.local": ("identity",),
    "identity.bootstrap": ("identity-init",),
    "registry.bootstrap": ("registry-init", "project-register"),
    "project.state.read": (
        "project-list", "project-head", "layers-get", "publication-receipt",
        "membership-list", "membership-receipt",
    ),
    "draft.history.read": (
        "draft-get", "draft-list", "draft-history", "draft-receipt", "draft-read",
    ),
    "analysis.submitted.zip": ("export-analyze",),
    "analysis.submitted.source_facts": ("source-facts",),
    "analysis.bytes.plan": (
        "metadata-materialize", "edt-attribute-plan", "edt-inventory-plan",
    ),
    "state.administration.write": (
        "layers-set", "state-migrate", "state-upgrade-access",
        "state-upgrade-workflows", "membership-set", "membership-revoke",
        "draft-archive", "draft-restore",
    ),
    "snapshot.retained.read": (
        "source-list", "snapshot-diff", "source-read", "graph-resolve", "impact",
        "proposal-create", "proposal-diff", "draft-save", "draft-start",
        "draft-edit", "edt-inventory", "metadata-plan",
    ),
    "source.capture": ("capture",),
    "native.execution": (
        "proposal-check", "proposal-platform-check", "proposal-platform-result",
        "proposal-test", "proposal-test-result", "test-profile-register",
        "test-profile-list", "test-profile-disable", "edt-profile-register",
        "edt-profile-list", "edt-profile-disable", "metadata-preview",
        "metadata-result", "metadata-evidence", "native-archive", "draft-check",
    ),
    "source.live.mutate": (
        "proposal-live-apply", "proposal-live-undo", "proposal-live-recover",
        "metadata-live-apply", "metadata-live-undo", "metadata-live-recover",
    ),
    "source.live.status": ("proposal-live-status", "metadata-live-status"),
    "workspace.managed": (
        "metadata-workspace-create", "metadata-workspace-apply",
        "metadata-workspace-undo", "metadata-workspace-status",
        "metadata-workspace-recover",
    ),
    "owner.report.store": (
        "owner-report-build", "owner-report-save", "owner-report-get",
        "owner-report-list",
    ),
}
COMMAND_CAPABILITIES = {
    command: capability
    for capability, commands in _GROUPS.items()
    for command in commands
}
_PORTABLE = frozenset({
    "identity.local", "registry.bootstrap", "project.state.read",
    "draft.history.read", "analysis.bytes.plan",
})


def capability_status(capability):
    if capability not in _GROUPS:
        return {"supported": False, "reason": "No reviewed OS contract exists"}
    if capability in {"analysis.submitted.zip", "analysis.submitted.source_facts"}:
        return {"supported": _platform == "linux", "reason": None if _platform == "linux" else "Experimental imported-byte sidecar is qualified only on Linux"}
    if capability == "identity.bootstrap":
        return {"supported": _platform == "linux", "reason": None if _platform == "linux" else "Local profile bootstrap is Linux-only; Windows uses its process token"}
    if capability == "runtime.inspect" or _platform == "win32":
        return {"supported": True, "reason": None}
    if _platform == "linux" and capability in _PORTABLE:
        return {"supported": True, "reason": None}
    reason = (
        "Local identity adapter has not been qualified for this OS"
        if capability in _PORTABLE
        else "Requires the Windows adapter; no equivalent retained IO/process contract is enabled"
    )
    return {"supported": False, "reason": reason}


def operation_name(name):
    """Normalize only the fixed local MCP tool naming convention."""
    return name.removeprefix("rentgen_").replace("_", "-")


def operation_supported(name):
    return capability_status(COMMAND_CAPABILITIES.get(operation_name(name)))["supported"]


def require_operation(name):
    capability = COMMAND_CAPABILITIES.get(operation_name(name))
    status = capability_status(capability)
    if not status["supported"]:
        raise CoreError(
            "CAPABILITY_UNAVAILABLE",
            "This operation is unavailable on the current OS",
            details={
                "operation": name, "capability": capability,
                "platform": _platform, "contract_version": CONTRACT_VERSION,
                "reason": status["reason"],
            },
        )


def capability_report():
    """Support matrix only: this grants no membership or installed-runtime claim."""
    return {
        "contract_version": CONTRACT_VERSION,
        "platform": _platform,
        "scope": "os-adapter-support",
        "capabilities": {
            capability: {**capability_status(capability), "operations": list(commands)}
            for capability, commands in _GROUPS.items()
        },
        "permissions": "Current project membership is checked independently on every operation",
        "dependencies": "Installed native runtimes and profiles are checked by their adapters",
    }
