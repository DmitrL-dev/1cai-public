package deployment_safety

import future.keywords.if
import future.keywords.contains

# Default: Allow if no deny rules match
default allow := true

# Deny if any violation exists
allow := false if count(deny) > 0

# Rule: Deny containers with 'latest' tag
deny contains msg if {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    endswith(container.image, ":latest")
    msg := sprintf("Container '%v' uses 'latest' tag, which is forbidden in production.", [container.name])
}

# Rule: Deny access to Prod DB from Dev namespace
deny contains msg if {
    input.kind == "NetworkPolicy"
    input.metadata.namespace == "dev"
    egress := input.spec.egress[_]
    egress.to[_].ipBlock.cidr == "192.168.1.100/32" # Hypothetical Prod DB IP
    msg := "Access to Production DB from Dev namespace is strictly forbidden."
}

# --- RLTF Reward Signal Generation ---

# Calculate Reward based on compliance
# Base reward: 0
# Violation: -100 per violation
# Compliance: +10 (if explicitly checked and passed)

reward := score if {
    violations := count(deny)
    violations > 0
    score := -100 * violations
}

reward := 10 if {
    count(deny) == 0
    input.kind == "Deployment" # Only reward for valid deployments
}

# Default reward is 0 (neutral)
default reward := 0
