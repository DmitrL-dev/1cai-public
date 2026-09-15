"""Local project foundation using only Python's standard library.

Optional platform and diagnostic adapters remain explicit capabilities. This
name avoids shadowing legacy tools/rentgen.
"""

from .context import (
    Explicit,
    Principal,
    ProjectContext,
    SnapshotRef,
    UseConfiguredDefault,
)
from .errors import CoreError
from .registry import ProjectRegistry
from .resolver import ContextResolver, require_permission, require_snapshot
from .state import ProjectState
from .source_configuration import (
    SourceConfiguration,
    SourceLayerSpec,
    configure_source_layers,
    get_source_configuration,
)
from .snapshots import (
    ProjectHead,
    PublishResult,
    SnapshotCatalogEntry,
    SnapshotLayer,
    get_project_head,
    get_publication,
)
from .publication import capture_and_publish
from .owner_report import RuntimeMetric, RuntimeMetricReport, build_owner_report
from .owner_report_store import OwnerReportStore
from .runtime_metrics import (
    RuntimeFreshnessPolicy,
    RuntimeMetricAssessment,
    assess_runtime_report,
    load_runtime_report,
)
from .runtime_source import load_onec_register_export
from .service_host import WindowsServiceHost
from .service_installer import (
    ServiceInstallPlan,
    ServiceInstallSpec,
    ServiceOperationResult,
    WindowsServiceInstaller,
)
from .notification_delivery import (
    DeliveryResult,
    DeliveryStatus,
    WebhookAdapter,
    deliver_outbox,
)
from .git_snapshot_evidence import GitSnapshotEvidence
from .edt_inventory import EDTInventoryLimits, edt_metadata_inventory
from .metadata_three_way import materialize_metadata_three_way, plan_metadata_three_way
from .metadata_live_apply import (
    apply_live,
    get_live_status,
    recover_live,
    undo_live,
)
from .proposal_live_apply import (
    apply_live as apply_proposal_live,
    get_live_status as get_proposal_live_status,
    recover_live as recover_proposal_live,
    undo_live as undo_proposal_live,
)
from .edt_attribute_three_way import plan_edt_attribute_three_way
from .edt_identity_three_way import (
    EDTIdentityThreeWayLimits,
    plan_edt_identity_three_way,
)
from .three_way import materialize_three_way
from .bsl_three_way import materialize_bsl_three_way
from .sources import (
    SourceRef,
    SourceEntry,
    SourcePage,
    SnapshotSources,
    SnapshotGraph,
    SnapshotCapabilities,
    read_source,
)

__all__ = [
    "capture_and_publish",
    "build_owner_report",
    "RuntimeMetric",
    "RuntimeMetricReport",
    "RuntimeFreshnessPolicy",
    "RuntimeMetricAssessment",
    "assess_runtime_report",
    "load_runtime_report",
    "load_onec_register_export",
    "WindowsServiceHost",
    "ServiceInstallPlan",
    "ServiceInstallSpec",
    "ServiceOperationResult",
    "WindowsServiceInstaller",
    "DeliveryResult",
    "DeliveryStatus",
    "WebhookAdapter",
    "deliver_outbox",
    "GitSnapshotEvidence",
    "OwnerReportStore",
    "EDTInventoryLimits",
    "edt_metadata_inventory",
    "plan_metadata_three_way",
    "plan_edt_attribute_three_way",
    "EDTIdentityThreeWayLimits",
    "plan_edt_identity_three_way",
    "materialize_metadata_three_way",
    "apply_live",
    "undo_live",
    "get_live_status",
    "recover_live",
    "apply_proposal_live",
    "undo_proposal_live",
    "get_proposal_live_status",
    "recover_proposal_live",
    "materialize_three_way",
    "materialize_bsl_three_way",
    "SourceRef",
    "SourceEntry",
    "SourcePage",
    "SnapshotSources",
    "SnapshotGraph",
    "SnapshotCapabilities",
    "read_source",
    "ContextResolver",
    "CoreError",
    "Explicit",
    "Principal",
    "ProjectContext",
    "ProjectRegistry",
    "ProjectState",
    "ProjectHead",
    "SourceConfiguration",
    "SourceLayerSpec",
    "configure_source_layers",
    "get_source_configuration",
    "get_project_head",
    "get_publication",
    "PublishResult",
    "SnapshotCatalogEntry",
    "SnapshotLayer",
    "SnapshotRef",
    "UseConfiguredDefault",
    "require_permission",
    "require_snapshot",
]
