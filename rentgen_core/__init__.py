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
from .edt_inventory import EDTInventoryLimits, edt_metadata_inventory
from .metadata_three_way import plan_metadata_three_way
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
    "OwnerReportStore",
    "EDTInventoryLimits",
    "edt_metadata_inventory",
    "plan_metadata_three_way",
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
