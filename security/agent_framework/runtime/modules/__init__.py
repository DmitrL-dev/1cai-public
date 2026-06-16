
"""Module registry for security agent."""

from .bsl import BSLStaticSecurityModule
from .http_basic import (HttpReachabilityModule, HttpTelemetryModule,
                         SecurityHeadersModule)
from .n8n_workflow import N8nWorkflowSecurityModule
from .repo_static import RepoSecretsModule, SensitiveFilesModule

DEFAULT_PROFILE = "web-api"
PROFILE_MODULES = {
    "web-api": (
        HttpReachabilityModule(),
        HttpTelemetryModule(),
        SecurityHeadersModule(),
    ),
    "repo-static": (
        SensitiveFilesModule(),
        RepoSecretsModule(),
    ),
    "n8n-workflow": (
        N8nWorkflowSecurityModule(),
    ),
    "bsl-1c": (
        BSLStaticSecurityModule(),
    ),
}
DEFAULT_MODULES = PROFILE_MODULES[DEFAULT_PROFILE]

__all__ = [
    "DEFAULT_PROFILE",
    "PROFILE_MODULES",
    "DEFAULT_MODULES",
    "HttpReachabilityModule",
    "HttpTelemetryModule",
    "SecurityHeadersModule",
    "RepoSecretsModule",
    "SensitiveFilesModule",
    "N8nWorkflowSecurityModule",
    "BSLStaticSecurityModule",
]

