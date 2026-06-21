import axios from "axios"
import { useAuthStore } from "@/stores/auth-store"

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
})

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = "/login"
    }
    return Promise.reject(error)
  },
)

// ── Auth ──
export const authApi = {
  login: (username: string, password: string) =>
    apiClient.post<{ access_token: string; token_type: string; expires_in: number }>(
      "/api/v1/auth/token",
      new URLSearchParams({ username, password }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
    ),
  me: (token?: string) =>
    apiClient.get("/api/v1/auth/me", token
      ? { headers: { Authorization: `Bearer ${token}` } }
      : undefined),
}

// ── Dashboard ──
export const dashboardApi = {
  developer: () => apiClient.get("/api/v1/developer"),
  executive: () => apiClient.get("/api/v1/executive"),
  pm: () => apiClient.get("/api/v1/pm"),
  owner: () => apiClient.get("/api/v1/owner"),
}

export type OpenFirstPathItem = {
  step: number
  stage: string
  label: string
  title: string
  route: string
  line: string
  file: string
  status: string
  source: string
}

export interface ExecutiveDashboardResponse {
  generated_at: string
  available: boolean
  decision: {
    status: "ready" | "watch" | "risk" | "critical" | "blocked"
    score: number
    headline: string
    release_policy: string
  }
  kpis: {
    modules: number
    modules_with_issues: number
    avg_maintainability: number
    red_areas: number
    yellow_areas: number
    review_queue: number
    call_edges: number
    offline_score: number
    coverage_score: number
  }
  risk_summary: {
    high_hotspots: number
    top_risk: number
    top_risks: Array<{
      module_path?: string
      domain: string
      risk: number
      fan_in: number
      maintainability?: number
      reasons: Array<Record<string, unknown>>
    }>
    domains: Array<Record<string, unknown>>
  }
  workstreams: Array<{
    id: string
    title: string
    score: number
    status: string
    signal: string
  }>
  governance: {
    summary: Record<string, unknown>
    status_counts: Record<string, number>
    review_queue: Array<Record<string, unknown>>
    trend: Record<string, unknown>
  }
  coverage: {
    total: number
    done: number
    partial: number
    planned: number
    score: number
    p0_score: number
    by_stage: Record<string, number>
  }
  offline: {
    decision: Record<string, unknown>
    summary: Record<string, unknown>
    runtime: Record<string, string>
  }
  manager_actions: Array<{
    severity: "critical" | "high" | "medium" | "low" | string
    owner: string
    title: string
    impact: string
  }>
  caveats: string[]
  coverage_ledger: CoverageLedgerResponse
  markdown: string
}

export interface BuyerPulseResponse {
  status: string
  score: number
  purchase_status: string
  source: string
  purchase_path: {
    status: string
    headline: string
    buyer_line: string
    primary_route: string
    procurement_handoff: {
      status: string
      title: string
      owner_line: string
      acceptance: string
      open_order: Array<{
        step: number
        label: string
        route: string
        endpoint?: string
        file: string
        hash_header: string
        check: string
      }>
      attachments: Array<{
        title: string
        route: string
        endpoint?: string
        file: string
        hash_header?: string
        why: string
      }>
      routes: string[]
    }
    buyer_room_packet_artifact: {
      title: string
      route: string
      endpoint: string
      file: string
      hash_header: string
      line: string
    }
    verification_packet_artifact: {
      title: string
      route: string
      endpoint: string
      file: string
      hash_header: string
      line: string
    }
    steps: Array<{
      step: number
      label: string
      route: string
      artifact: string
      file: string
      line: string
    }>
    send_files: string[]
  }
  launch: {
    status: string
    score: number
    purchase_spine_status: string
    journey_ready: number
    journey_steps: number
    governance_gates: number
    proof_routes: number
    route: string
  }
  concierge: {
    status: string
    score: number
    purchase_router_status: string
    persona_cards: number
    shortest_paths: number
    route: string
  }
  commercial: {
    monthly_ai_rent: string
    annual_ai_rent: string
    three_year_ai_rent: string
    local_license_anchor: string
    buyer_line: string
    route: string
  }
  evidence: {
    proof_routes: number
    governance_gates: number
    route: string
  }
  executive: {
    red_areas: number
    review_queue: number
    high_hotspots: number
    headline: string
  }
}

export interface CoverageLedgerResponse {
  status: string
  score: number
  summary: {
    items: number
    measured: number
    unknown: number
    ready: number
    partial: number
    risk: number
    caveats: number
  }
  items: Array<{
    id: string
    title: string
    status: string
    score: number
    measured: boolean
    source: string
    evidence: string
    caveat?: string | null
  }>
  caveats: string[]
}

export interface BuyerBriefResponse {
  status: string
  score: number
  purchase_status: string
  source: string
  pulse: BuyerPulseResponse
  primary_motion: {
    label: string
    route: string
    status: string
    ask: string
    reason: string
  }
  room_line: string
  commercial: BuyerPulseResponse["commercial"]
  coverage_ledger: CoverageLedgerResponse
  buyer_room_plan: {
    mode: string
    role: string
    title: string
    route: string
    status: string
    start_with: string
    show: string
    proof_file: string
    close_question: string
    why: string
    sequence: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    send_files: string[]
    evidence_contract: string
  }
  purchase_path: {
    status: string
    headline: string
    buyer_line: string
    primary_route: string
    procurement_handoff: {
      status: string
      title: string
      owner_line: string
      acceptance: string
      open_order: Array<{
        step: number
        label: string
        route: string
        endpoint?: string
        file: string
        hash_header: string
        check: string
      }>
      attachments: Array<{
        title: string
        route: string
        endpoint?: string
        file: string
        hash_header?: string
        why: string
      }>
      routes: string[]
    }
    buyer_room_packet_artifact: {
      title: string
      route: string
      endpoint: string
      file: string
      hash_header: string
      line: string
    }
    close_artifact: {
      title: string
      route: string
      file: string
      line: string
    }
    activation_artifact: {
      title: string
      route: string
      file: string
      line: string
    }
    archive_receipt_artifact: {
      title: string
      route: string
      file: string
      line: string
    }
    verification_packet_artifact: {
      title: string
      route: string
      endpoint: string
      file: string
      hash_header: string
      line: string
    }
    steps: Array<{
      step: number
      label: string
      route: string
      artifact: string
      file: string
      line: string
    }>
    send_files: string[]
  }
  open_first_path: OpenFirstPathItem[]
  role_cards: Array<{
    role: string
    title: string
    route: string
    status: string
    spark: string
    proof_file: string
  }>
  proof_readiness: Array<{
    id: string
    title: string
    route: string
    status: string
    signal: string
    file: string
  }>
  meeting_flow: Array<{
    step: number
    label: string
    route: string
    line: string
  }>
  routes: string[]
  summary: {
    roles: number
    proof_items: number
    meeting_steps: number
    open_first_steps: number
    purchase_path_steps: number
    purchase_path_files: number
    procurement_handoff_steps: number
    room_plan_files: number
    red_areas: number
    review_queue: number
    high_hotspots: number
    coverage_caveats: number
  }
}

export interface DemoAction {
  label: string
  to: string
}

export interface RoleReport {
  role: string
  title: string
  status: string
  tone: "ok" | "warn" | "danger" | "muted" | string
  headline: string
  proof_points: string[]
  next_actions: DemoAction[]
  markdown: string
  download_name: string
}

export interface DemoStoryResponse {
  generated_at: string
  mode: string
  scenario: {
    id: string
    title: string
    subtitle: string
    configuration: string
    setup_minutes: number
    coverage: {
      status: string
      score?: number | null
      caveat: string
    }
  }
  first_value: Array<{
    title: string
    value: string
    tone: "ok" | "warn" | "danger" | "muted" | string
    why: string
    next_action: string
    to: string
  }>
  pain_map: Array<{
    role: string
    pain: string
    proof: string
    action: string
    to: string
  }>
  query_surgeon_case: {
    title: string
    problem: string
    unsafe_pattern: string
    safe_options: string[]
    evidence: string
    test: string
  }
  demo_steps: Array<{
    id: string
    title: string
    role: string
    minutes: number
    to: string
    evidence: string
  }>
  role_reports: RoleReport[]
  coverage_ledger: CoverageLedgerResponse
  export: {
    markdown: string
    download_name: string
  }
}

export interface IntakePlanResponse {
  generated_at: string
  source: {
    path: string
    exists: boolean
    is_dir: boolean
    requested_type: string
    detected_type: string
  }
  decision: {
    status: "ready" | "partial" | "blocked" | string
    score: number
    headline: string
  }
  inventory: {
    bsl_files: number
    xml_files: number
    form_files: number
    rights_files: number
    test_files: number
    scanned_files: number
    scan_truncated: boolean
    scan_limit: number
  }
  coverage: Array<{
    id: string
    title: string
    status: "ready" | "partial" | "missing" | string
    count: number
    caveat?: string | null
  }>
  configuration_genome: {
    headline: string
    scale: {
      id: string
      files: number
      line: string
    }
    source_mix: Array<{
      id: string
      label: string
      count: number
      status: string
    }>
    readiness_tracks: Array<{
      id: string
      label: string
      route: string
      status: string
      line: string
    }>
    risk_flags: Array<{
      id: string
      severity: string
      line: string
    }>
    first_proof: {
      label: string
      route: string
      reason: string
    }
    buyer_story: Array<{
      role: string
      spark: string
      route: string
    }>
  }
  estimate: {
    minutes: number
    mode: string
    notes: string[]
  }
  next_actions: Array<{
    label: string
    to: string
    enabled: boolean
    reason: string
  }>
  caveats: string[]
}

export interface PlatformDoctorCheck {
  id: string
  title: string
  status: "pass" | "warn" | "fail" | string
  severity: "high" | "medium" | "low" | string
  evidence: Record<string, unknown> | string | number | boolean | null
  action: string
}

export interface PlatformDoctorResponse {
  generated_at: string
  config_path: string
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  inventory: {
    configuration_name?: string
    configuration_version?: string
    platform_version?: string
    target_platform_version?: string
    compatibility_mode?: string
    dbms?: string
    cluster?: string
    infobase_mode?: string
    clients?: string
    tech_journal: Record<string, unknown>
    openmetrics_url?: string
    license_events: Record<string, unknown>
    extensions_count: number
  }
  checks: PlatformDoctorCheck[]
  capabilities: Array<{
    id: string
    title: string
    available: boolean
    evidence: Record<string, unknown>
  }>
  upgrade: {
    from?: string
    to?: string
    readiness: string
    checklist: string[]
  }
  caveats: string[]
  markdown: string
}

export interface VendorPortfolioSignal {
  id: string
  title: string
  value: string
  offer: string
}

export interface VendorPortfolioWorkPackage {
  id: string
  title: string
  priority: "P0" | "P1" | "P2" | string
  effort: string
  evidence: string
  outcome: string
}

export interface VendorDealBoard {
  recommended_motion: string
  primary_package: {
    id: string
    title: string
    priority: string
    evidence: string
  }
  next_step: {
    label: string
    to: string
    reason: string
  }
  role_sparks: Array<{
    role: string
    spark: string
  }>
  proof_packet: Array<{
    title: string
    route: string
    artifact: string
  }>
}

export interface VendorPortfolioResponse {
  generated_at: string
  client: {
    name: string
    configuration: string
    configuration_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  portfolio: {
    clients: number
    configurations: number
    avg_score: number
    red_areas: number
    modules: number
    modules_with_issues: number
    vendor_room_roles: number
    vendor_room_proofs: number
    vendor_room_steps: number
    vendor_room_open_first: number
    coverage_caveats?: number
  }
  commercial_signals: VendorPortfolioSignal[]
  work_packages: VendorPortfolioWorkPackage[]
  deal_board: VendorDealBoard
  vendor_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    vendor_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
    coverage_ledger?: CoverageLedgerResponse
  }
  coverage_ledger?: CoverageLedgerResponse
  top_risks: Array<{
    module_path?: string
    domain?: string
    risk?: number
    fan_in?: number
    reasons?: Array<Record<string, unknown>>
  }>
  next_actions: DemoAction[]
  proof_routes: string[]
  caveats: string[]
  markdown: string
}

export interface VendorPortfolioBookResponse {
  generated_at: string
  decision: {
    status: "ready" | "watch" | "risk" | "blocked" | string
    score: number
    headline: string
  }
  portfolio: {
    name: string
    clients: number
    avg_score: number
    ready: number
    watch: number
    risk: number
    modules: number
    modules_with_issues: number
    red_areas: number
  }
  clients: Array<{
    name: string
    configuration: string
    configuration_version: string
    status: string
    score: number
    modules: number
    modules_with_issues: number
    red_areas: number
    headline: string
    top_risks: Array<Record<string, unknown>>
  }>
  opportunities: Array<{
    id: string
    title: string
    priority: string
    clients: number
    evidence: string[]
  }>
  decision_board: {
    status: string
    next_commercial_move: {
      label: string
      to: string
      reason: string
    }
    segments: Array<{
      id: string
      title: string
      clients: string[]
      motion: string
      route: string
    }>
    offer_sequence: Array<{
      step: number
      title: string
      route: string
      evidence: string
    }>
    proof_packet: Array<{
      title: string
      route: string
      artifact: string
    }>
  }
  next_actions: DemoAction[]
  caveats: string[]
  markdown: string
}

export interface UpdateWarRoomCheck {
  id: string
  title: string
  status: "pass" | "warn" | "fail" | string
  severity: "high" | "medium" | "low" | string
  evidence: Record<string, unknown> | string | number | boolean | null
  action: string
}

export interface UpdateWarRoomResponse {
  generated_at: string
  release_name: string
  config_path: string
  configuration: {
    path: string
    exists: boolean
    name: string
    version?: string
    vendor?: string
    compatibility_mode?: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    checks: number
    attention: number
    extensions: number
    changed_modules: number
    target_platform_version: string
    release_impact_measured: boolean
  }
  checks: UpdateWarRoomCheck[]
  extensions: {
    count: number
    truncated: boolean
    items: Array<{ name: string; path: string; kind: string }>
  }
  platform: {
    decision: Record<string, unknown>
    upgrade: Record<string, unknown>
    inventory: Record<string, unknown>
  }
  intake: {
    decision: Record<string, unknown>
    inventory: Record<string, unknown>
  }
  release: {
    included: boolean
    reason?: string
    release_name?: string
    decision?: Record<string, unknown>
    summary?: Record<string, unknown>
    gate?: Record<string, unknown>
    tests?: Record<string, unknown>
    recommended_actions?: Array<Record<string, unknown>>
  }
  workstreams: Array<{
    id: string
    title: string
    owner: string
    status: string
    evidence: Record<string, unknown> | string | number | boolean | null
    action: string
    to: string
  }>
  caveats: string[]
  markdown: string
}

export interface SafeAutopilotResponse {
  generated_at: string
  goal: string
  scenario: {
    id: string
    title: string
    route: string
    why: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    changed_modules: number
    impact_edges: number
    impacted_modules: number
    violations: number
    tests: number
    diff_candidates: number
    approval_roles: number
    evidence_items: number
    blocked_actions: number
    external_ai_required: boolean
    local_sources: number
    write_allowed: boolean
    approval_required: boolean
  }
  safety_policy: {
    mode: string
    direct_apply: boolean
    writes_allowed: boolean
    requested_write: boolean
    approval_required: boolean
    audit_line: string
  }
  steps: Array<{
    id: string
    title: string
    status: string
    owner: string
    action: string
    evidence: Record<string, unknown>
  }>
  impact: {
    gate: {
      status: string
      violations: Array<Record<string, unknown>>
      summary: Record<string, number>
    }
    modules: Array<Record<string, unknown>>
    unmeasured_modules: string[]
  }
  patch_blueprint: {
    id: string
    title: string
    mode: string
    targets: string[]
    changes: string[]
    risk: string
    test: string
  }
  diff_proposal: {
    status: string
    title: string
    route: string
    direct_apply: boolean
    candidates: Array<{
      id: string
      target: string
      finding: string
      confidence: string
      before: string
      after: string
      unified_diff: string
      approval_required: boolean
      review_notes: string[]
      tests: string[]
    }>
    acceptance: string[]
    caveat: string
  }
  approval_handoff: {
    status: string
    can_request_approval: boolean
    request_endpoint: string
    approval_record_kind: string
    handoff_line: string
    blocked_actions: string[]
    roles: Array<{
      role: string
      required: string
      decision: string
      route: string
    }>
    evidence_packet: Array<{
      title: string
      route: string
      artifact: string
      why: string
    }>
    audit_requirements: string[]
    local_asset_line: string
  }
  ai_independence: {
    mode: string
    external_ai_required: boolean
    buyer_line: string
    license_line: string
    local_sources: Array<{
      title: string
      available: boolean
      evidence: string
    }>
    deterministic_rules: string[]
    optional_ai_controls: string[]
  }
  tests: Array<{
    module_path: string
    selector: string
    framework: string
    priority: string
    status: string
    command: string
    reason: string
  }>
  approvals: Array<{
    role: string
    required: string
    reason: string
  }>
  evidence: Array<{
    title: string
    route: string
    artifact: string
  }>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface SafeAutopilotApprovalResponse {
  record: {
    id: string
    status: string
    tool_name: string
    risk: string
    requested_by: string
    approval_reason: string
    linked_record: Record<string, unknown>
    argument_constraints: Record<string, unknown>
    expires_at: string
  }
  classification: Record<string, unknown>
  plan_id: string
  safe_autopilot: SafeAutopilotResponse
  handoff: SafeAutopilotResponse["approval_handoff"]
}

export interface RightsRlsMatrixRow {
  role: string
  object: string
  rights: string[]
  dangerous: string[]
  can_read: boolean
  can_write: boolean
  can_admin: boolean
  rls: Array<{ tag: string; text: string }>
}

export interface RightsRlsResponse {
  available: boolean
  generated_at: string
  config_path: string
  configuration: Record<string, string | null>
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    roles: number
    roles_scanned: number
    roles_with_rights: number
    roles_without_rights: number
    objects: number
    total_rights: number
    dangerous_rights: number
    rls_rules: number
    findings: number
    by_right: Record<string, number>
    matrix_rows: number
    role_limit: number
    object_limit: number
  }
  roles: Array<{
    role: string
    name: string
    path: string
    rights_path?: string | null
    objects: number
    rights: number
    dangerous_rights: number
    rls_rules: number
    missing_rights_xml?: boolean
    parse_error?: boolean
    by_right?: Record<string, number>
  }>
  diff: {
    enabled: boolean
    status: string
    baseline_path?: string | null
    summary: {
      added_rights: number
      removed_rights: number
      added_dangerous_rights: number
      removed_dangerous_rights: number
      changed_roles: number
    }
    changes: Array<{
      change: "added" | "removed" | string
      role: string
      object: string
      right: string
      dangerous: boolean
      can_write: boolean
    }>
    caveat?: string | null
  }
  matrix: RightsRlsMatrixRow[]
  findings: Array<{
    severity: string
    code: string
    role: string
    message: string
    details: Record<string, unknown>
  }>
  gate: {
    status: "pass" | "warn" | "fail" | string
    block_release: boolean
    reasons: string[]
  }
  recommended_actions: Array<{
    owner: string
    severity: string
    title: string
    details: Record<string, unknown>
  }>
  caveats: string[]
  markdown: string
}

export interface ValuePack {
  id: string
  title: string
  audience: string
  outcome: string
  maturity: "pilot-ready" | "beta" | string
  routes: DemoAction[]
  proof_points: string[]
  deliverables: string[]
  price_story: string
  caveats: string[]
}

export interface ValuePacksResponse {
  generated_at: string
  decision: {
    status: "ready" | "watch" | string
    score: number
    headline: string
  }
  summary: {
    packs: number
    pilot_ready: number
    beta: number
    executive_score?: number | null
    coverage_score?: number | null
    value_room_roles: number
    value_room_proofs: number
    value_room_steps: number
    value_room_open_first: number
  }
  packs: ValuePack[]
  value_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    value_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  licensing_story: string
  caveats: string[]
  markdown: string
}

export interface BusinessCaseAssumptions {
  monthly_ai_subscription_cost: number
  hourly_rate: number
  manual_review_hours_month: number
  incident_cost: number
  release_delay_hours_per_item: number
  release_windows_per_month: number
  currency: string
}

export interface BusinessCaseLever {
  id: string
  title: string
  audience: string
  annual_value: number
  currency: string
  evidence: string
  route: string
  confidence: string
  why_buy_now: string
}

export interface BusinessCaseResponse {
  generated_at: string
  client: {
    name: string
    configuration: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  assumptions: BusinessCaseAssumptions
  summary: {
    manual_review_month: number
    manual_review_year: number
    ai_subscription_year: number
    release_delay_exposure: number
    risk_exposure: number
    red_area_exposure: number
    hotspot_exposure: number
    platform_exposure: number
    first_year_visible_value: number
    failed_platform_checks: number
    work_packages: number
    value_packs: number
    modules: number
    modules_with_issues: number
    red_areas: number
    review_queue: number
    three_year_ai_subscription: number
    local_license_anchor: number
    subscription_escape_months: number
    subscription_break_even_months: number
    business_room_roles: number
    business_room_proofs: number
    business_room_steps: number
    business_room_open_first: number
  }
  subscription_escape_plan: {
    headline: string
    monthly_ai_rent: number
    annual_ai_rent: number
    three_year_ai_rent: number
    local_license_anchor: number
    visible_value_month: number
    break_even_months: number
    ai_rent_equivalent_months: number
    currency: string
    decision_line: string
    guardrails: string[]
    stakeholder_lines: Array<{
      role: string
      line: string
      route: string
    }>
    evidence_files: Array<{
      title: string
      filename: string
      route: string
    }>
  }
  business_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    business_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  business_levers: BusinessCaseLever[]
  buyer_committee: Array<{
    role: string
    wants: string
    proof: string
    route: string
    decision_trigger: string
  }>
  offer_stack: Array<{
    id: string
    title: string
    target_buyer: string
    includes: string[]
    routes: string[]
    commercial_note: string
  }>
  objections: Array<{
    question: string
    answer: string
    proof_route: string
  }>
  plan_30_60_90: Array<{
    stage: string
    goal: string
    actions: string[]
    exit_criteria: string
  }>
  evidence_routes: DemoAction[]
  caveats: string[]
  markdown: string
}

export interface GuidedDemoStep {
  id: string
  title: string
  role: string
  minutes: number
  route: string
  proof: string
  success_signal: string
  buyer_question: string
  talk_track: string
}

export interface GuidedDemoResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    total_minutes: number
    steps: number
    roles: number
    proof_routes: number
    value_packs: number
    business_value: number
    productization_findings: number
    guided_room_roles: number
    guided_room_proofs: number
    guided_room_steps: number
    guided_room_open_first: number
  }
  guided_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    guided_path: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
      minutes: number
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
      buying_trigger?: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  opening: Array<{
    claim: string
    proof: string
    route: string
  }>
  guided_steps: GuidedDemoStep[]
  role_paths: Array<{
    role: string
    headline: string
    steps: Array<{
      label: string
      to: string
      proof: string
    }>
    buying_trigger: string
  }>
  close_plan: Array<{
    window: string
    owner: string
    actions: string[]
    exit_criteria: string
  }>
  objection_cards: Array<{
    question: string
    answer: string
    proof_route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface ScenarioHubScenario {
  id: string
  title: string
  pain: string
  buyer_line: string
  primary_role: string
  roles: string[]
  minutes: number
  severity: number
  route: string
  proof: string
  success_signal: string
  demo_script: string[]
  evidence_routes: DemoAction[]
  outputs: string[]
  why_buy_now: string
  maturity: "live" | "pilot" | string
}

export interface ScenarioHubResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    scenarios: number
    killer_scenarios: number
    roles: number
    total_minutes: number
    proof_routes: number
    value_packs: number
    scenario_room_roles: number
    scenario_room_proofs: number
    scenario_room_steps: number
    scenario_room_open_first: number
  }
  scenario_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    scenario_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
      scenario_ids?: string[]
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  scenarios: ScenarioHubScenario[]
  role_lenses: Array<{
    role: string
    outcome: string
    first_route: string
    scenario_ids: string[]
  }>
  recommended_path: Array<{
    step: number
    scenario_id: string
    title: string
    route: string
    role: string
    why: string
  }>
  objection_map: Array<{
    objection: string
    answer: string
    scenario_ids: string[]
    proof_route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface PilotLaunchpadResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    pilot_days: number
    offers: number
    stages: number
    acceptance_checks: number
    procurement_items: number
    risk_burndown_items: number
    value_packs: number
    activation_ready: boolean
    activation_gates: number
    acceptance_register_items: number
    acceptance_register_ready: boolean
    acceptance_register_watch: number
    acceptance_register_blocked: number
    pilot_room_roles: number
    pilot_room_proofs: number
    pilot_room_steps: number
    pilot_room_open_first: number
  }
  pilot_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    activation_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
      invoice_trigger: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    activation_question: string
  }
  pilot_offers: Array<{
    id: string
    title: string
    buyer: string
    duration: string
    price_frame: string
    route: string
    includes: string[]
    acceptance: string
    why_buy: string
    evidence: string[]
  }>
  day_plan: Array<{
    window: string
    owner: string
    goal: string
    actions: string[]
    exit_criteria: string
  }>
  acceptance_matrix: Array<{
    role: string
    must_believe: string
    scenario_id: string
    proof_route: string
    pass_criteria: string
  }>
  procurement_pack: Array<{
    owner: string
    question: string
    artifact: string
    route: string
    answer: string
  }>
  activation_contract: {
    ready_to_activate: boolean
    selected_offer_id: string
    selected_offer_title: string
    primary_ask: string
    commercial_frame: string
    invoice_trigger: string
    start_route: string
    activation_line: string
    gates: Array<{
      gate: string
      route: string
      evidence: string
    }>
    milestones: Array<{
      window: string
      owner: string
      route: string
      acceptance: string
    }>
    buyer_commitments: Array<{
      role: string
      commitment: string
      route: string
    }>
    handoff_files: Array<{
      title: string
      filename: string
      route: string
      endpoint?: string
      hash_header?: string
      reason: string
    }>
    proof_routes: string[]
    script: string[]
  }
  acceptance_register: {
    ready_to_sign: boolean
    owner_line: string
    items: Array<{
      id: string
      role: string
      owner: string
      window: string
      decision: string
      acceptance: string
      evidence_route: string
      evidence_file: string
      required_routes: string[]
      status: "ready" | "watch" | "blocked" | string
      blocker: string
      next_action: string
    }>
    ready_items: number
    watch_items: number
    blocked_items: number
    proof_routes: string[]
  }
  risk_burndown: Array<{
    scenario_id: string
    buyer_risk: string
    close_action: string
    route: string
  }>
  close_script: string[]
  exports: Array<{
    title: string
    filename: string
    route: string
    endpoint?: string
    hash_header?: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface DemoCommandCenterResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    stages: number
    role_pivots: number
    proof_assets: number
    total_minutes: number
    objections: number
    recovery_cards: number
    demo_room_roles: number
    demo_room_proofs: number
    demo_room_steps: number
    demo_room_open_first: number
  }
  demo_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    presenter_opening: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
      minutes: number
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
      close_question?: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  live_stages: Array<{
    id: string
    title: string
    role: string
    route: string
    minutes: number
    cue: string
    talk_track: string
    proof: string
    expected_reaction: string
    next_click: string
    fallback_line: string
    evidence_asset: string
  }>
  role_pivots: Array<{
    role: string
    opener: string
    route: string
    prove_with: string
    if_time_short: string
    close_question: string
  }>
  live_checklist: {
    before_demo: string[]
    during_demo: string[]
    close: string[]
  }
  objections: Array<{
    question: string
    answer: string
    route: string
  }>
  proof_assets: Array<{
    title: string
    route: string
    why: string
  }>
  recovery_cards: Array<{
    signal: string
    response: string
    route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface EnterpriseTrustCenterResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    controls: number
    passed_controls: number
    warning_controls: number
    failed_controls: number
    security_questions: number
    questionnaire_sections: number
    questionnaire_ready: number
    questionnaire_watch: number
    questionnaire_blocked: number
    procurement_items: number
    install_modes: number
    risk_items: number
    proof_routes: number
    evidence_artifacts: number
    offline_score: number
    productization_findings: number
    security_findings: number
    rights_findings: number
    trust_room_roles: number
    trust_room_proofs: number
    trust_room_steps: number
    trust_room_open_first: number
  }
  trust_controls: Array<{
    id: string
    title: string
    owner: string
    status: "pass" | "warn" | "fail" | string
    severity: "high" | "medium" | "low" | string
    route: string
    evidence: string
    acceptance: string
    caveats: string[]
  }>
  security_questions: Array<{
    question: string
    answer: string
    proof_route: string
    artifact: string
  }>
  security_questionnaire: {
    status: "ready" | "review_required" | "blocked" | string
    ready_to_send: boolean
    ready_to_approve: boolean
    owner_line: string
    sections: Array<{
      id: string
      title: string
      audience: string
      owner: string
      status: "ready" | "watch" | "blocked" | string
      answer: string
      proof_routes: string[]
      evidence_files: string[]
      acceptance: string
      linked_controls: string[]
      blockers: string[]
      caveats: string[]
    }>
    ready_sections: number
    watch_sections: number
    blocked_sections: number
    send_files: string[]
    proof_routes: string[]
    verification_steps: Array<{
      owner: string
      action: string
      route: string
      expected: string
    }>
    high_risks: Array<{
      owner: string
      severity: "high" | "medium" | "low" | string
      risk: string
      route: string
      next_action: string
    }>
  }
  trust_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    trust_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  procurement_pack: Array<{
    owner: string
    document: string
    route: string
    why: string
    exit_criteria: string
  }>
  install_modes: Array<{
    id: string
    title: string
    buyer: string
    duration: string
    proof_routes: string[]
    acceptance: string
  }>
  risk_register: Array<{
    owner: string
    severity: "high" | "medium" | "low" | string
    risk: string
    route: string
    next_action: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface CommercialOfferStudioResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    offers: number
    pricing_tiers: number
    stakeholder_closers: number
    deal_risks: number
    proposal_sections: number
    procurement_items: number
    approval_roles: number
    close_ready: boolean
    checkout_gates: number
    proof_routes: number
    offer_room_roles: number
    offer_room_proofs: number
    offer_room_steps: number
    offer_room_open_first: number
    first_year_visible_value: number
    currency: string
    trust_score: number
    pilot_score: number
    subscription_break_even_months: number
  }
  offers: Array<{
    id: string
    title: string
    buyer: string
    commercial_frame: string
    route: string
    why_buy: string
    includes: string[]
    proof_routes: string[]
    acceptance: string
  }>
  pricing_ladder: Array<{
    tier: string
    anchor: string
    logic: string
    replaces: string
  }>
  procurement_dossier: {
    headline: string
    recommended_purchase: {
      id: string
      title: string
      route: string
      commercial_frame: string
      acceptance: string
    }
    subscription_escape: {
      annual_ai_rent: string
      three_year_ai_rent: string
      local_value_anchor: string
      local_license_anchor: string
      break_even_months: number
      ai_rent_equivalent_months: number
      line: string
      decision_line: string
      proof_route: string
      guardrails: string[]
      stakeholder_lines: Array<{
        role: string
        line: string
        route: string
      }>
      evidence_files: Array<{
        title: string
        filename: string
        route: string
      }>
    }
    license_model: Array<{
      model: string
      buyer: string
      why: string
    }>
    procurement_pack: Array<{
      owner: string
      artifact: string
      route: string
      why: string
      exit_criteria: string
    }>
    approval_matrix: Array<{
      role: string
      must_accept: string
      artifact: string
      route: string
      blocker_if_missing: string
    }>
    red_lines: string[]
    close_question: string
  }
  subscription_escape_plan: BusinessCaseResponse["subscription_escape_plan"]
  offer_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    recommended_purchase: {
      title: string
      route: string
      commercial_frame: string
      acceptance: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
      close_line?: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  close_packet: {
    ready_to_close: boolean
    close_mode: string
    primary_ask: string
    one_page_order: {
      product: string
      recommended_purchase: string
      commercial_frame: string
      value_anchor: string
      ai_rent_baseline: string
      three_year_ai_rent: string
      local_license_anchor: string
      break_even: string
      first_invoice_trigger: string
      route: string
    }
    mutual_action_plan: Array<{
      window: string
      owner: string
      action: string
      artifact: string
      route: string
      exit: string
    }>
    buyer_commitments: Array<{
      role: string
      commitment: string
      route: string
    }>
    evidence_requirements: Array<{
      artifact: string
      route: string
      why: string
    }>
    checkout: Array<{
      gate: string
      route: string
      evidence: string
    }>
    close_script: string[]
  }
  stakeholder_closers: Array<{
    role: string
    buy_trigger: string
    proof_route: string
    close_line: string
  }>
  deal_risks: Array<{
    risk: string
    route: string
    mitigation: string
  }>
  proposal_sections: Array<{
    title: string
    route: string
    content: string
  }>
  buy_now_path: Array<{
    step: string
    owner: string
    route: string
    exit: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface BoardPackResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    board_minutes: number
    decision_items: number
    committee_roles: number
    risks: number
    severe_risks: number
    proof_items: number
    proof_routes: number
    governance_gates: number
    governance_windows: number
    first_year_visible_value: number
    ai_subscription_year: number
    currency: string
    recommended_offer: string
    evidence_artifacts: number
    close_ready: boolean
    checkout_gates: number
    board_room_roles: number
    board_room_proofs: number
    board_room_steps: number
    board_room_open_first: number
  }
  board_snapshot: {
    one_line: string
    why_now: string
    not_generic_ai: string
    value_anchor: string
    ai_rent_baseline: string
    three_year_ai_rent: string
    local_license_anchor: string
    break_even: string
    subscription_escape_line: string
    recommended_motion: string
    commercial_frame: string
    default_route: string
    trust_position: string
  }
  board_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    board_question: string
  }
  decision_brief: Array<{
    question: string
    answer: string
    owner: string
    route: string
  }>
  committee_map: Array<{
    role: string
    first_question: string
    must_believe: string
    buy_trigger: string
    proof_route: string
    close_line: string
  }>
  recommended_offer: {
    id?: string
    title?: string
    buyer?: string
    commercial_frame?: string
    route?: string
    why_buy?: string
    includes?: string[]
    proof_routes?: string[]
    acceptance?: string
  }
  risk_to_decision: Array<{
    severity: "high" | "medium" | "low" | string
    owner: string
    risk: string
    route: string
    decision: string
  }>
  proof_packet: Array<{
    title: string
    filename: string
    route: string
    reason: string
  }>
  board_close_packet: {
    ready_to_close: boolean
    close_mode: string
    primary_ask: string
    one_page_order: {
      product: string
      recommended_purchase: string
      commercial_frame: string
      value_anchor: string
      ai_rent_baseline: string
      three_year_ai_rent: string
      local_license_anchor: string
      break_even: string
      first_invoice_trigger: string
      route: string
    }
    checkout: Array<{
      gate: string
      route: string
      evidence: string
    }>
    evidence_requirements: Array<{
      artifact: string
      route: string
      why: string
    }>
    buyer_commitments: Array<{
      role: string
      commitment: string
      route: string
    }>
    close_script: string[]
    proof_routes: string[]
    board_line: string
  }
  next_72_hours: Array<{
    window: string
    owner: string
    action: string
    route: string
    output: string
  }>
  objection_answers: Array<{
    objection: string
    answer: string
    route: string
  }>
  board_room_script: Array<{
    minute: string
    speaker: string
    route: string
    line: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface OutcomeLedgerResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    outcome_tiles: number
    adoption_steps: number
    success_metrics: number
    role_scorecards: number
    risk_items: number
    severe_risks: number
    expansion_paths: number
    proof_items: number
    proof_routes: number
    governance_gates: number
    governance_windows: number
    acceptance_rollup_items: number
    acceptance_rollup_ready: boolean
    acceptance_rollup_watch: number
    acceptance_rollup_blocked: number
    post_purchase_ready: boolean
    post_purchase_files: number
    outcome_room_roles: number
    outcome_room_proofs: number
    outcome_room_steps: number
    outcome_room_open_first: number
    first_year_visible_value: number
    ai_subscription_year: number
    currency: string
    recommended_motion: string
  }
  value_realization: {
    first_year_visible_value: number
    currency: string
    value_anchor: string
    ai_subscription_year: number
    ai_subscription_baseline: string
    manual_review_year: number
    manual_review_baseline: string
    release_delay_exposure: number
    release_delay_baseline: string
    risk_exposure: number
    risk_exposure_baseline: string
    recommended_motion: string
    commercial_frame: string
    first_measurement_window: string
    proof_standard: string
  }
  outcome_tiles: Array<{
    id: string
    role: string
    outcome: string
    baseline: string
    target: string
    owner: string
    route: string
    acceptance: string
    evidence: string
  }>
  adoption_timeline: Array<{
    window: string
    owner: string
    route: string
    goal: string
    artifact: string
    exit_criteria: string
  }>
  success_metrics: Array<{
    metric: string
    baseline: string
    target: string
    measurement: string
    route: string
    buyer_line: string
  }>
  role_scorecards: Array<{
    role: string
    spark: string
    adoption_signal: string
    proof_route: string
    owner_action: string
  }>
  risk_burndown: Array<{
    risk: string
    owner: string
    severity: "high" | "medium" | "low" | string
    route: string
    day_7: string
    day_30: string
  }>
  expansion_paths: Array<{
    id: string
    title: string
    route: string
    trigger: string
    offer: string
    proof: string
  }>
  acceptance_rollup: {
    ready_to_claim: boolean
    ready_to_continue: boolean
    owner_line: string
    items: Array<{
      id: string
      role: string
      owner: string
      window: string
      status: "ready" | "watch" | "blocked" | string
      decision: string
      acceptance: string
      evidence_route: string
      evidence_file: string
      outcome_route: string
      outcome_signal: string
      required_routes: string[]
      blocker: string
      next_action: string
    }>
    ready_items: number
    watch_items: number
    blocked_items: number
    next_window: string
    next_owner: string
    proof_routes: string[]
  }
  governance_refresh: {
    ready: boolean
    gates: Array<{
      gate: string
      route: string
      evidence: string
    }>
    windows: Array<{
      window: string
      owner: string
      route: string
      acceptance: string
    }>
    proof_routes: string[]
    refresh_line: string
  }
  post_purchase_proof_spine: {
    status: string
    ready_to_measure: boolean
    ready_to_claim: boolean
    buyer_line: string
    measurement_rule: string
    files: Array<{
      title: string
      filename: string
      route: string
      owner: string
      purpose: string
    }>
    required_routes: string[]
    buyer_room_packet: {
      title: string
      filename: string
      route: string
      endpoint: string
      hash_header: string
      check: string
    }
    archive_receipt: {
      title: string
      filename: string
      route: string
      check: string
    }
    verification_packet: {
      title: string
      filename: string
      route: string
      hash_header: string
      check: string
    }
    activation_gate: {
      ready: boolean
      source: string
      invoice_trigger: string
    }
  }
  outcome_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    outcome_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
      value_anchor: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
      owner_action?: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    outcome_question: string
  }
  proof_packet: Array<{
    title: string
    filename: string
    route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface LaunchRoomResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    phases: number
    ready_phases: number
    risk_phases: number
    role_paths: number
    meeting_modes: number
    route_health_items: number
    proof_items: number
    proof_routes: number
    journey_steps: number
    journey_ready: number
    checkout_gates: number
    activation_gates: number
    governance_gates: number
    acceptance_items: number
    acceptance_watch: number
    acceptance_blocked: number
    claim_ready: boolean
    purchase_spine_status: string
    procurement_handoff_steps: number
    buyer_room_roles: number
    buyer_room_proofs: number
    buyer_room_steps: number
  }
  launch_summary: {
    one_line: string
    current_truth: string
    first_year_visible_value: number
    currency: string
    value_anchor: string
    trust_status: string
    board_status: string
    outcome_status: string
    persona_cards: number
    recommended_motion: string
  }
  next_best_action: {
    label: string
    route: string
    reason: string
  }
  purchase_spine: {
    status: string
    headline: string
    buyer_line: string
    value_anchor: string
    monthly_ai_rent: string
    annual_ai_rent: string
    three_year_ai_rent: string
    local_license_anchor: string
    break_even: string
    ai_rent_equivalent_months: number
    recommended_purchase: string
    commercial_frame: string
    first_invoice_trigger: string
    route: string
    proof_routes: string[]
    evidence_files: Array<{
      title: string
      filename: string
      route: string
    }>
    procurement_handoff: {
      status: string
      title: string
      owner_line: string
      acceptance: string
      open_order: Array<{
        step: number
        label: string
        route: string
        endpoint?: string
        file: string
        hash_header: string
        check: string
      }>
      attachments: Array<{
        title: string
        route: string
        endpoint?: string
        file: string
        hash_header?: string
        why: string
      }>
      routes: string[]
    }
    guardrails: string[]
  }
  buyer_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
  }
  buyer_journey: {
    steps: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      action: string
      proof: string
    }>
    ready_steps: number
    risk_steps: number
    checkout_gates: number
    activation_gates: number
    governance_gates: number
    acceptance_items: number
    acceptance_watch: number
    acceptance_blocked: number
    claim_ready: boolean
    next_route: string
    buyer_line: string
  }
  path_phases: Array<{
    id: string
    title: string
    route: string
    status: string
    score: number
    question: string
    exit_criteria: string
    proof: string
  }>
  role_switchboard: Array<{
    role: string
    first_click: string
    second_click: string
    spark: string
    must_believe: string
    close: string
  }>
  meeting_modes: Array<{
    id: string
    title: string
    audience: string
    minutes: number
    steps: Array<{
      route: string
      label: string
    }>
    close: string
  }>
  route_health: Array<{
    title: string
    route: string
    status: string
    score: number
    headline: string
  }>
  anti_confusion_cards: Array<{
    signal: string
    response: string
    route: string
  }>
  proof_packet: Array<{
    title: string
    filename: string
    route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface KillerDemoResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    stages: number
    demo_modes: number
    role_sparks: number
    proof_moments: number
    close_scripts: number
    proof_routes: number
    proof_files: number
    open_first_steps: number
    role_packets_ready: number
    role_packets_partial: number
    role_packets_missing: number
    role_packet_missing_files: number
    deal_readiness_score: number
    committee_roles: number
    committee_blocked_roles: number
    opening_roles: number
    objection_items: number
    objection_watch: number
    objection_blocked: number
    close_ready: boolean
    close_receipt_ready: boolean
    activation_handoff_ready: boolean
    checkout_gates: number
    total_minutes: number
    test_gaps: number
    trust_status: string
  }
  primary_route: {
    label: string
    route: string
    reason: string
  }
  opening_brief: {
    headline: string
    one_sentence: string
    first_30_seconds: string[]
    first_click: {
      label: string
      route: string
      reason: string
    }
    role_entries: Array<{
      role: string
      route: string
      question: string
      proof: string
    }>
    anti_confusion: Array<{
      signal: string
      response: string
      route: string
    }>
    success_signal: string
  }
  killer_stages: Array<{
    id: string
    title: string
    minutes: number
    route: string
    audience: string
    spark: string
    proof: string
    close_question: string
  }>
  demo_modes: Array<{
    id: string
    title: string
    minutes: number
    steps: Array<{
      route: string
      label: string
    }>
    close: string
  }>
  role_sparks: Array<{
    role: string
    first_route: string
    spark: string
    proof: string
    close: string
  }>
  proof_moments: Array<{
    title: string
    route: string
    signal: string
  }>
  close_scripts: Array<{
    audience: string
    line: string
    route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_packet: {
    bundle_id: string
    bundle_sha256: string
    artifact_count: number
    file_count: number
    ready_to_forward: boolean
    open_first_path: OpenFirstPathItem[]
    role_packet_rollup: {
      status: string
      total: number
      ready: number
      partial: number
      missing: number
      available_files: number
      missing_files: number
      missing_file_names: string[]
      line: string
    }
    close_receipt: {
      ready: boolean
      status: string
      route: string
      filename: string
      json_filename: string
      next_paid_step: string
      why: string
    }
    activation_handoff: {
      ready: boolean
      status: string
      route: string
      filename: string
      json_filename: string
      next_window: string
      why: string
    }
    room_map: {
      ready: boolean
      route: string
      filename: string
      sha256: string
      packet_filename: string
      packet_endpoint: string
      packet_hash_header: string
      plan_ready: boolean
      plan_route: string
      plan_filename: string
      plan_sha256: string
      open_first_path_ready: boolean
      open_first_path_filename: string
      open_first_path_route: string
      open_first_path_sha256: string
      pulse_filename: string
      pulse_sha256: string
      why: string
    }
    archive: {
      ready: boolean
      route: string
      endpoint: string
      filename: string
      sha256_header: string
      why: string
    }
    killer_archive: {
      ready: boolean
      route: string
      endpoint: string
      filename: string
      sha256_header: string
      evidence_sha256_header: string
      manifest: string
      open_first: string
      role_packets: string[]
      why: string
    }
    verification_packet: {
      ready: boolean
      route: string
      endpoint: string
      filename: string
      sha256_header: string
      open_first: string
      contains: string[]
      why: string
    }
    procurement_handoff: {
      present: boolean
      ready: boolean
      status: string
      title: string
      owner_line: string
      acceptance: string
      open_order: Array<{
        step: number
        label: string
        route: string
        endpoint?: string
        file: string
        hash_header: string
        check: string
      }>
      attachments: Array<{
        title: string
        route: string
        endpoint?: string
        file: string
        hash_header?: string
        why: string
      }>
      missing_files: number
      raw_missing_files: number
      blockers: number
      raw_blockers: number
      review_items: number
      risk_review_items: number
      recipients: number
      verification_steps: number
      covered_by_current_demo: string[]
      archive_filename: string
      endpoint: string
      hash_header: string
      verification_packet_filename: string
      verification_packet_endpoint: string
      verification_packet_hash_header: string
      buyer_room_packet_filename: string
      buyer_room_packet_endpoint: string
      buyer_room_packet_hash_header: string
      open_first_file: string
      first_file: string
      buyer_line: string
      why: string
    }
    forwarding_kit: {
      ready: boolean
      source: string
      packets: RoleForwardingPacket[]
      packet_count: number
      first_packet: string
      why: string
    }
    files: Array<{
      id: string
      filename: string
      media_type: string
      sha256: string
      route: string
    }>
    artifacts: Array<{
      id: string
      title: string
      route: string
      filename: string
      status: string
      score?: number | null
      json_sha256: string
      markdown_sha256: string
    }>
    handoff: Array<{
      recipient: string
      role_packet: string
      route: string
      send: string[]
      available_files: string[]
      missing_files: string[]
      availability_status: string
      why: string
    }>
    routes: string[]
    caveat: string
  }
  commercial_close_packet: {
    ready_to_close: boolean
    forward_ready: boolean
    ready_to_ask: boolean
    close_mode: string
    primary_ask: string
    one_page_order: {
      product: string
      recommended_purchase: string
      commercial_frame: string
      value_anchor: string
      ai_rent_baseline: string
      three_year_ai_rent: string
      local_license_anchor: string
      break_even: string
      first_invoice_trigger: string
      route: string
    }
    checkout: Array<{
      gate: string
      route: string
      evidence: string
    }>
    evidence_requirements: Array<{
      artifact: string
      route: string
      why: string
    }>
    mutual_action_plan: Array<{
      window: string
      owner: string
      action: string
      artifact: string
      route: string
      exit: string
    }>
    buyer_commitments: Array<{
      role: string
      commitment: string
      route: string
    }>
    close_script: string[]
    proof_routes: string[]
    buyer_line: string
  }
  deal_readiness: {
    status: string
    score: number
    decision_line: string
    next_paid_step: {
      label: string
      route: string
      owner: string
      acceptance: string
    }
    blockers: Array<{
      id: string
      severity: string
      title: string
      route: string
      action: string
    }>
    role_acceptance: Array<{
      role: string
      status: string
      route: string
      must_hear: string
      proof: string
      close: string
    }>
    committee_close_board: {
      status: string
      accepted_roles: number
      blocked_roles: number
      total_roles: number
      headline: string
      final_question: string
      roles: Array<{
        role: string
        status: string
        route: string
        accepted_proof: string
        send: string[]
        remaining_question: string
        blocker: string
      }>
      handoff: Array<{
        recipient: string
        route: string
        send: string[]
        why: string
      }>
    }
    customer_can_repeat: string[]
    local_asset_case: {
      headline: string
      value_anchor: string
      ai_rent_baseline: string
      three_year_ai_rent: string
      local_license_anchor: string
      break_even: string
      why_it_is_asset: string[]
      proof_routes: string[]
      finance_line: string
      security_line: string
    }
    close_checklist: string[]
  }
  objection_router: {
    status: string
    ready_items: number
    watch_items: number
    blocked_items: number
    presenter_line: string
    primary_objection: {
      id: string
      audience: string
      objection: string
      answer: string
      route: string
      proof_file: string
      owner: string
      status: string
      close_question: string
    }
    items: Array<{
      id: string
      audience: string
      objection: string
      answer: string
      route: string
      proof_file: string
      owner: string
      status: string
      close_question: string
    }>
    proof_routes: string[]
  }
  meeting_close_receipt: {
    schema_version: string
    filename: string
    json_filename: string
    route: string
    client_name: string
    status: string
    ready_to_send: boolean
    ready_to_ask: boolean
    headline: string
    decision: {
      status: string
      score: number
      headline: string
    }
    primary_ask: string
    next_paid_step: {
      label: string
      route: string
      owner: string
      acceptance: string
    }
    proof_packet: {
      forwardable: boolean
      bundle_id: string
      archive_filename: string
      archive_endpoint: string
      archive_hash_header: string
      buyer_room_packet: string
      buyer_room_packet_endpoint: string
      buyer_room_packet_hash_header: string
      verification_packet: string
      verification_packet_endpoint: string
      verification_packet_hash_header: string
      verification_packet_open_first: string
      manifest: string
      open_first: string
      role_packet_rollup: string
      procurement_status: string
      procurement_missing_files: number
      procurement_blockers: number
    }
    committee: {
      status: string
      accepted_roles: number
      blocked_roles: number
      total_roles: number
      final_question: string
      roles: Array<{
        role: string
        status: string
        route: string
        accepted_proof: string
        send: string[]
        remaining_question: string
        blocker: string
      }>
    }
    role_packets: Array<{
      recipient: string
      filename: string
      status: string
      route: string
      missing_files: string[]
    }>
    forwarding_kit: {
      ready: boolean
      source: string
      packets: RoleForwardingPacket[]
      packet_count: number
      first_packet: string
      why: string
    }
    blockers: Array<{
      id: string
      severity: string
      title: string
      route: string
      action: string
    }>
    buyer_commitments: Array<{
      role: string
      commitment: string
      route: string
    }>
    checkout: Array<{
      gate: string
      route: string
      evidence: string
    }>
    customer_can_repeat: string[]
    close_questions: string[]
    send_files: string[]
    why: string
  }
  post_demo_activation_handoff: {
    schema_version: string
    filename: string
    json_filename: string
    route: string
    status: string
    ready_to_start: boolean
    headline: string
    activation_line: string
    next_paid_step: {
      label: string
      route: string
      owner: string
      acceptance: string
    }
    invoice_trigger: string
    route_chain: string[]
    timeline: Array<{
      window: string
      owner: string
      action: string
      route: string
      proof_file: string
      exit: string
      status: string
    }>
    gates: Array<{
      gate: string
      status: string
      route: string
      evidence: string
    }>
    role_packets: Array<{
      recipient: string
      filename: string
      status: string
      route: string
      missing_files: string[]
    }>
    forwarding_kit: {
      ready: boolean
      source: string
      packets: RoleForwardingPacket[]
      packet_count: number
      first_packet: string
      why: string
    }
    proof_files: string[]
    outcome: {
      route: string
      acceptance_rollup_ready: boolean
      acceptance_items: number
      governance_refresh_ready: boolean
      next_window: string
      owner_line: string
    }
    blockers: Array<{
      id: string
      severity: string
      title: string
      route: string
      action: string
    }>
    why: string
  }
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface LaunchRoomHealthResponse {
  status: string
  score: number
  phases: number
  role_paths: number
  journey_steps: number
  journey_ready: number
  governance_gates: number
  purchase_spine_status: string
  three_year_ai_rent: string
  proof_routes: number
  source?: string
}

export interface BuyerConciergeResponse {
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    persona_cards: number
    pain_cards: number
    shortest_paths: number
    guardrails: number
    proof_routes: number
    offer_packages: number
    trust_controls: number
    pilot_offers: number
    purchase_router_status: string
    concierge_room_roles: number
    concierge_room_proofs: number
    concierge_room_steps: number
    concierge_room_open_first: number
  }
  default_next_action: {
    label: string
    route: string
    reason: string
  }
  orientation: {
    not_this: string
    this_is: string
    first_question: string
  }
  persona_cards: Array<{
    id: string
    role: string
    first_question: string
    start_route: string
    second_route: string
    spark: string
    proof: string
    buy_trigger: string
    purchase_route: string
    purchase_ask: string
    proof_file: string
    time_to_value_minutes: number
  }>
  concierge_room_bridge: {
    status: string
    score: number
    source: string
    room_line: string
    primary_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    concierge_motion: {
      label: string
      route: string
      status: string
      ask: string
      reason: string
    }
    role_cards: Array<{
      role: string
      title: string
      route: string
      status: string
      spark: string
      proof_file: string
      purchase_ask?: string
    }>
    proof_readiness: Array<{
      id: string
      title: string
      route: string
      status: string
      signal: string
      file: string
    }>
    meeting_flow: Array<{
      step: number
      label: string
      route: string
      line: string
    }>
    open_first_path: OpenFirstPathItem[]
    files: string[]
    routes: string[]
    close_question: string
  }
  purchase_router: {
    status: string
    headline: string
    buyer_line: string
    primary_route: string
    primary_label: string
    recommended_purchase: string
    recommended_route: string
    commercial_frame: string
    first_invoice_trigger: string
    value_anchor: string
    monthly_ai_rent: string
    annual_ai_rent: string
    three_year_ai_rent: string
    local_license_anchor: string
    break_even: string
    ai_rent_equivalent_months: number
    quick_actions: Array<{
      label: string
      route: string
      why: string
    }>
    role_prompts: Array<{
      role: string
      route: string
      ask: string
      close: string
      proof_file: string
    }>
    close_sequence: Array<{
      window: string
      owner: string
      action: string
      route: string
    }>
    evidence_files: Array<{
      title: string
      filename: string
      route: string
    }>
    guardrails: string[]
    proof_routes: string[]
  }
  pain_picker: Array<{
    scenario_id: string
    title: string
    pain: string
    role: string
    route: string
    why_now: string
    minutes: number
  }>
  shortest_paths: Array<{
    id: string
    title: string
    audience: string
    total_minutes: number
    steps: Array<{
      label: string
      route: string
      minutes: number
      why: string
    }>
    close: string
  }>
  confusion_guardrails: Array<{
    signal: string
    response: string
    route: string
  }>
  exports: Array<{
    title: string
    filename: string
    route: string
  }>
  proof_routes: string[]
  source_signals: Record<string, string | number | boolean | null>
  caveats: string[]
  markdown: string
  download_name: string
}

export interface BuyerConciergeHealthResponse {
  status: string
  score: number
  persona_cards: number
  shortest_paths: number
  purchase_router_status: string
  three_year_ai_rent: string
  source?: string
}

export interface EvidenceArtifact {
  id: string
  title: string
  route: string
  filename: string
  status: string
  score?: number | null
  json_sha256: string
  markdown_sha256: string
  summary: Record<string, unknown>
  caveats: string[]
  json: string
  markdown: string
}

export interface EvidenceProcurementFile {
  id: string
  title: string
  filename: string
  route: string
  role: string
  why: string
  present: boolean
  status: string
  sha256: string
  artifact_status: string
}

export interface EvidenceProcurementReviewItem {
  id: string
  title: string
  status: string
  route: string
  filename: string
}

export interface EvidenceProcurementGate {
  id: string
  label: string
  status: string
  detail: string
  route: string
}

export interface EvidenceProcurementRecipient {
  role: string
  decision: string
  packet_file?: string
  send_files: string[]
  routes: string[]
}

export interface EvidenceRecipientPacket {
  role: string
  filename: string
  markdown_sha256: string
  send_files: string[]
  routes: string[]
  forwarding_subject?: string
  forwarding_filename?: string
  forwarding_body?: string
  attachments?: string[]
  markdown: string
}

export interface RoleForwardingPacket {
  role: string
  filename: string
  forwarding_filename?: string
  forwarding_subject: string
  forwarding_body?: string
  send_files?: string[]
  attachments: string[]
  routes: string[]
}

export interface EvidenceProcurementStep {
  id: string
  owner: string
  action: string
  expected: string
}

export interface EvidenceKillerDemoRecipientOverlay {
  role: string
  source_archive: string
  send_files: string[]
  reason: string
}

export interface EvidenceKillerDemoHandoff {
  id: string
  title: string
  status: string
  available: boolean
  route: string
  archive_endpoint: string
  archive_filename: string
  archive_hash_header: string
  open_first_file: string
  manifest_file: string
  proof_packet_file: string
  files: string[]
  post_demo_files: string[]
  recipient_overlays: EvidenceKillerDemoRecipientOverlay[]
  buyer_line: string
  verification_steps: EvidenceProcurementStep[]
}

export interface EvidenceArchiveBoundary {
  id: string
  title: string
  status: string
  endpoint: string
  filename: string
  hash_header: string
  open_first_file: string
  manifest_file: string
  archive_manifest_file?: string
  contains: string[]
  excludes: string[]
  boundary: string
}

export interface EvidenceArchiveAcceptanceReceipt {
  bundle_id: string
  generated_at: string
  client_name: string
  status: string
  buyer_line: string
  archives: EvidenceArchiveBoundary[]
  role_overlays: EvidenceKillerDemoRecipientOverlay[]
  acceptance_steps: EvidenceProcurementStep[]
  markdown: string
}

export interface EvidenceCommercialAssumptions {
  source: string
  currency: string
  monthly_ai_subscription_cost: number | null
  annual_ai_rent: number | null
  three_year_ai_rent: number | null
  local_license_anchor: number | null
  break_even_months: number | null
  ai_rent_equivalent_months: number | null
  monthly_ai_rent_label: string
  annual_ai_rent_label: string
  three_year_ai_rent_label: string
  local_license_anchor_label: string
  break_even_label: string
  decision_line: string
  evidence_files: Array<{
    title: string
    filename: string
    route: string
  }>
}

export interface EvidenceProcurementHandoff {
  bundle_id: string
  generated_at: string
  client_name: string
  status: string
  ready_to_forward: boolean
  buyer_line: string
  archive_endpoint: string
  archive_filename: string
  bundle_sha256: string
  commercial_assumptions: EvidenceCommercialAssumptions
  archive_hash_header: string
  open_first_file: string
  required_files: EvidenceProcurementFile[]
  missing_files: EvidenceProcurementFile[]
  blockers: string[]
  review_items: EvidenceProcurementReviewItem[]
  gates: EvidenceProcurementGate[]
  recipients: EvidenceProcurementRecipient[]
  recipient_packets?: EvidenceRecipientPacket[]
  killer_demo_handoff?: EvidenceKillerDemoHandoff
  verification_steps: EvidenceProcurementStep[]
  archive_contents: string[]
  markdown: string
}

export interface EvidenceBundleResponse {
  bundle_id: string
  generated_at: string
  client: {
    name: string
    config_path: string
    target_platform_version: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    artifacts: number
    files: number
    risk_artifacts: number
    watch_artifacts: number
    changed_modules: number
    procurement_required_files: number
    procurement_missing_files: number
    procurement_blockers: number
    procurement_recipients: number
    procurement_ready: boolean
    commercial_assumption_source: string
    archive_acceptance_steps: number
  }
  commercial_assumptions: EvidenceCommercialAssumptions
  artifacts: EvidenceArtifact[]
  manifest: {
    bundle_id: string
    generated_at: string
    client_name: string
    files: Array<{
      id: string
      filename: string
      media_type: string
      sha256: string
    }>
    total_files: number
    bundle_sha256: string
  }
  procurement_handoff: EvidenceProcurementHandoff
  archive_acceptance_receipt: EvidenceArchiveAcceptanceReceipt
  caveats: string[]
  markdown: string
  open_first_markdown: string
  download_name: string
}

export interface BuyerRoomPacketVerifyResponse {
  status: string
  archive_type: string
  filename: string
  archive_sha256: string
  checked_files: number
  required_files: string[]
  present_files: string[]
  open_first_file: string
  open_first_status: string
  hash_table_status: string
  expected_headers: Record<string, string>
  summary: {
    findings: number
    high: number
    medium: number
    low: number
  }
  findings: Array<{
    severity: string
    code: string
    message: string
    files?: string[]
  }>
}

export const managementApi = {
  executive: (params?: { governance_limit?: number; hotspot_limit?: number; save_snapshot?: boolean }) =>
    apiClient.get<ExecutiveDashboardResponse>("/api/v1/management/executive", {
      params,
      timeout: 90_000,
    }),
  buyerPulse: (params?: { governance_limit?: number; hotspot_limit?: number; monthly_ai_subscription_cost?: number }) =>
    apiClient.get<BuyerPulseResponse>("/api/v1/management/buyer-pulse", {
      params,
      timeout: 45_000,
    }),
  buyerBrief: (params?: { governance_limit?: number; hotspot_limit?: number; monthly_ai_subscription_cost?: number }) =>
    apiClient.get<BuyerBriefResponse>("/api/v1/management/buyer-brief", {
      params,
      timeout: 45_000,
    }),
  buyerRoomPacket: (params?: { governance_limit?: number; hotspot_limit?: number; monthly_ai_subscription_cost?: number }) =>
    apiClient.get<Blob>("/api/v1/management/buyer-room-packet", {
      params,
      responseType: "blob",
      timeout: 90_000,
    }),
  buyerRoomPacketVerify: (params?: { governance_limit?: number; hotspot_limit?: number; monthly_ai_subscription_cost?: number }) =>
    apiClient.get<BuyerRoomPacketVerifyResponse>("/api/v1/management/buyer-room-packet/verify", {
      params,
      timeout: 90_000,
    }),
  demo: (params?: { governance_limit?: number; hotspot_limit?: number }) =>
    apiClient.get<DemoStoryResponse>("/api/v1/management/demo", {
      params,
      timeout: 90_000,
    }),
  roleReport: (role: string) =>
    apiClient.get<RoleReport>(`/api/v1/management/role-report/${encodeURIComponent(role)}`, {
      timeout: 90_000,
    }),
  intakePlan: (body: { source_path?: string; source_type?: string }) =>
    apiClient.post<IntakePlanResponse>("/api/v1/management/intake/plan", body, {
      timeout: 90_000,
    }),
}

export const platformDoctorApi = {
  analyze: (params?: { config_path?: string; target_platform_version?: string }) =>
    apiClient.get<PlatformDoctorResponse>("/api/v1/platform-doctor/analyze", {
      params,
      timeout: 90_000,
    }),
}

export const vendorPortfolioApi = {
  audit: (params?: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
  }) =>
    apiClient.get<VendorPortfolioResponse>("/api/v1/vendor-portfolio/audit", {
      params,
      timeout: 120_000,
    }),
  portfolio: (body: {
    portfolio_name?: string
    clients?: Array<{
      name?: string
      config_path?: string
      target_platform_version?: string
    }>
    governance_limit?: number
    hotspot_limit?: number
  }) =>
    apiClient.post<VendorPortfolioBookResponse>("/api/v1/vendor-portfolio/portfolio", body, {
      timeout: 180_000,
    }),
}

export const updateWarRoomApi = {
  plan: (body: {
    release_name?: string
    config_path?: string
    target_platform_version?: string
    changed_modules?: string[]
    diff?: string
    include_security?: boolean
  }) =>
    apiClient.post<UpdateWarRoomResponse>("/api/v1/update-war-room/plan", body, {
      timeout: 120_000,
    }),
}

export const safeAutopilotApi = {
  plan: (body: {
    goal?: string
    changed_modules?: string[]
    diff?: string
    allow_write?: boolean
    risk_threshold?: number
    impact_threshold?: number
  }) =>
    apiClient.post<SafeAutopilotResponse>("/api/v1/safe-autopilot/plan", body, {
      timeout: 180_000,
    }),
  requestApproval: (body: {
    goal?: string
    changed_modules?: string[]
    diff?: string
    allow_write?: boolean
    risk_threshold?: number
    impact_threshold?: number
    tool_name?: string
    approval_reason?: string
    approval_ticket?: string
    expires_in_hours?: number
  }) =>
    apiClient.post<SafeAutopilotApprovalResponse>("/api/v1/safe-autopilot/approval-request", body, {
      timeout: 180_000,
    }),
}

export const rightsRlsApi = {
  analyze: (params?: { config_path?: string; baseline_path?: string; role_limit?: number; object_limit?: number }) =>
    apiClient.get<RightsRlsResponse>("/api/v1/rights-rls/analyze", {
      params,
      timeout: 120_000,
    }),
}

export const valuePacksApi = {
  catalog: () =>
    apiClient.get<ValuePacksResponse>("/api/v1/value-packs/catalog", {
      timeout: 90_000,
    }),
}

export const businessCaseApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<BusinessCaseResponse>("/api/v1/business-case/build", body, {
      timeout: 180_000,
    }),
}

export const guidedDemoApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<GuidedDemoResponse>("/api/v1/guided-demo/build", body, {
      timeout: 180_000,
    }),
}

export const scenarioHubApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<ScenarioHubResponse>("/api/v1/scenario-hub/build", body, {
      timeout: 180_000,
    }),
}

export const pilotLaunchpadApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<PilotLaunchpadResponse>("/api/v1/pilot-launchpad/build", body, {
      timeout: 180_000,
    }),
}

export const demoCommandCenterApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<DemoCommandCenterResponse>("/api/v1/demo-command-center/build", body, {
      timeout: 180_000,
    }),
}

export const enterpriseTrustCenterApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    analysis_depth?: "preview" | "standard" | "deep" | string
    governance_limit?: number
    hotspot_limit?: number
    security_limit?: number
    security_module_limit?: number
    rights_role_limit?: number
    rights_object_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<EnterpriseTrustCenterResponse>("/api/v1/enterprise-trust-center/build", body, {
      timeout: 180_000,
    }),
}

export const commercialOfferStudioApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    security_limit?: number
    security_module_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<CommercialOfferStudioResponse>("/api/v1/commercial-offer-studio/build", body, {
      timeout: 180_000,
    }),
}

export const boardPackApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    security_limit?: number
    security_module_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<BoardPackResponse>("/api/v1/board-pack/build", body, {
      timeout: 180_000,
    }),
}

export const outcomeLedgerApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    security_limit?: number
    security_module_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<OutcomeLedgerResponse>("/api/v1/outcome-ledger/build", body, {
      timeout: 180_000,
    }),
}

export const launchRoomApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    security_limit?: number
    security_module_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<LaunchRoomResponse>("/api/v1/launch-room/build", body, {
      timeout: 180_000,
    }),
  health: () => apiClient.get<LaunchRoomHealthResponse>("/api/v1/launch-room/health", { timeout: 90_000 }),
}

export const killerDemoApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    changed_modules?: string[]
    release_name?: string
    evidence_profile?: "buyer" | "enterprise"
    lock_radar_log_path?: string
    include_update?: boolean
    include_rights?: boolean
    include_lock_radar?: boolean
    include_extension_safety?: boolean
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<KillerDemoResponse>("/api/v1/killer-demo/build", body, {
      timeout: 240_000,
    }),
  archive: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    changed_modules?: string[]
    release_name?: string
    evidence_profile?: "buyer" | "enterprise"
    lock_radar_log_path?: string
    include_update?: boolean
    include_rights?: boolean
    include_lock_radar?: boolean
    include_extension_safety?: boolean
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<Blob>("/api/v1/killer-demo/archive", body, {
      responseType: "blob",
      timeout: 300_000,
    }),
  verifyArchive: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    changed_modules?: string[]
    release_name?: string
    evidence_profile?: "buyer" | "enterprise"
    lock_radar_log_path?: string
    include_update?: boolean
    include_rights?: boolean
    include_lock_radar?: boolean
    include_extension_safety?: boolean
    governance_limit?: number
    hotspot_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<ArchiveVerifyResponse>("/api/v1/killer-demo/archive/verify", body, {
      timeout: 300_000,
    }),
}

export const buyerConciergeApi = {
  build: (body: {
    client_name?: string
    config_path?: string
    target_platform_version?: string
    governance_limit?: number
    hotspot_limit?: number
    security_limit?: number
    security_module_limit?: number
    assumptions?: Partial<BusinessCaseAssumptions>
  }) =>
    apiClient.post<BuyerConciergeResponse>("/api/v1/buyer-concierge/build", body, {
      timeout: 180_000,
    }),
  health: () => apiClient.get<BuyerConciergeHealthResponse>("/api/v1/buyer-concierge/health", { timeout: 90_000 }),
}

export const evidenceBundleApi = {
  build: (body: EvidenceBundleRequest) =>
    apiClient.post<EvidenceBundleResponse>("/api/v1/evidence-bundle/build", body, {
      timeout: 180_000,
    }),
  archive: (body: EvidenceBundleRequest) =>
    apiClient.post<Blob>("/api/v1/evidence-bundle/archive", body, {
      responseType: "blob",
      timeout: 240_000,
    }),
  verifyArchive: (body: EvidenceBundleRequest) =>
    apiClient.post<ArchiveVerifyResponse>("/api/v1/evidence-bundle/archive/verify", body, {
      timeout: 240_000,
    }),
  verifyDualArchive: (body: EvidenceBundleRequest) =>
    apiClient.post<DualArchiveVerifyResponse>("/api/v1/evidence-bundle/archive/verify-dual", body, {
      timeout: 360_000,
    }),
  verificationPacketArchive: (body: EvidenceBundleRequest) =>
    apiClient.post<Blob>("/api/v1/evidence-bundle/archive/verification-packet", body, {
      responseType: "blob",
      timeout: 360_000,
    }),
}

export interface ArchiveVerifyFinding {
  severity: "high" | "medium" | "low" | string
  code: string
  filename?: string
  message?: string
  expected?: unknown
  actual?: unknown
}

export interface ArchiveVerifyResponse {
  status: "pass" | "warn" | "fail" | string
  archive_type: string
  filename: string
  archive_sha256: string
  checked_files: number
  required_files: string[]
  expected_headers?: Record<string, string>
  embedded_evidence_verify?: ArchiveVerifyResponse | null
  summary: {
    findings: number
    high: number
    medium: number
    low: number
    [key: string]: number
  }
  findings: ArchiveVerifyFinding[]
  verification_receipt?: ArchiveVerificationReceipt
  verification_receipt_markdown?: string
}

export interface ArchiveVerificationReceipt {
  schema_version: string
  generated_at: string
  status: string
  decision: {
    status: string
    headline: string
    action: string
  }
  archive_type: string
  filename: string
  archive_sha256: string
  checked_files: number
  required_files: string[]
  expected_headers: Record<string, string>
  summary: Record<string, number>
  findings: ArchiveVerifyFinding[]
  embedded_evidence?: {
    status?: string
    archive_type?: string
    filename?: string
    archive_sha256?: string
    checked_files?: number
    summary?: Record<string, number>
  } | null
  receipt_files: {
    json: string
    markdown: string
  }
  acceptance_steps: Array<Record<string, string>>
}

export interface DualArchiveVerifyResponse {
  schema_version: string
  generated_at: string
  status: "pass" | "warn" | "fail" | string
  client_name: string
  summary: {
    archives: number
    pass: number
    warn: number
    fail: number
    findings: number
    high: number
    medium: number
    low: number
  }
  pair: {
    evidence_archive_sha256: string
    killer_archive_sha256: string
    killer_embedded_evidence_sha256: string
    same_evidence_archive_hash: boolean
  }
  receipt_files: {
    json: string
    markdown: string
  }
  evidence: ArchiveVerifyResponse
  killer_demo: ArchiveVerifyResponse
  verification_packet_markdown: string
}

export interface EvidenceBundleRequest {
  client_name?: string
  config_path?: string
  target_platform_version?: string
  release_name?: string
  lock_radar_log_path?: string
  changed_modules?: string[]
  include_demo?: boolean
  include_vendor?: boolean
  include_update?: boolean
  include_rights?: boolean
  include_lock_radar?: boolean
  include_extension_safety?: boolean
  include_test_factory?: boolean
  include_safe_autopilot?: boolean
  include_value_packs?: boolean
  include_business_case?: boolean
  include_board_pack?: boolean
  include_outcome_ledger?: boolean
  include_launch_room?: boolean
  include_killer_demo?: boolean
  include_buyer_concierge?: boolean
  include_commercial_offer_studio?: boolean
  include_demo_command_center?: boolean
  include_enterprise_trust_center?: boolean
  include_guided_demo?: boolean
  include_scenario_hub?: boolean
  include_pilot_launchpad?: boolean
  include_productization?: boolean
  include_governance_proof?: boolean
  assumptions?: Partial<BusinessCaseAssumptions>
}

export interface ProductizationReadinessResponse {
  product: string
  status: string
  release_decision: string
  score: number
  summary: Record<string, number>
  non_ai_value: string[]
  deliverables: Array<Record<string, unknown>>
  review_evidence: Record<string, unknown>
  test_evidence: Record<string, unknown>
  findings: Array<Record<string, unknown>>
}

export interface OfflineBundleManifestResponse {
  schema_version: string
  product: string
  profile: string
  generated_at: string
  root: string
  installer_profile: Record<string, unknown>
  summary: {
    files: number
    missing: number
    total_bytes: number
    by_category: Record<string, number>
    readiness_status: string
    readiness_decision: string
  }
  artifacts: Array<Record<string, unknown>>
  missing: Array<Record<string, unknown>>
  readiness: Record<string, unknown>
  verification: Record<string, unknown>
  manifest_sha256: string
  signature: {
    signed: boolean
    algorithm: string
    key_hint?: string
    value?: string | null
  }
}

export interface OfflineBundleVerifyResponse {
  status: "pass" | "warn" | "fail" | string
  checked_files: number
  archive_path?: string
  archive_sha256?: string
  summary: Record<string, number | string>
  signature: Record<string, unknown>
  delivery_passport?: OfflineDeliveryPassport | null
  findings: Array<Record<string, unknown>>
}

export interface OfflineDeliveryPassport {
  schema_version: string
  product: string
  profile: string
  generated_at: string
  decision: {
    status: string
    headline: string
  }
  package: {
    archive_filename: string
    manifest_sha256: string
    files: number
    missing: number
    total_bytes: number
    signed: boolean
    signature_algorithm: string
    signature_key_hint?: string | null
  }
  install_profile: Record<string, unknown>
  verification_steps: Array<Record<string, unknown>>
  acceptance_gates: Array<Record<string, unknown>>
  handoff_by_role: Array<Record<string, unknown>>
  caveats: string[]
}

export interface OfflineBundleArchiveResponse {
  status: string
  archive_path: string
  archive_sha256: string
  size_bytes: number
  archive_files: string[]
  manifest: OfflineBundleManifestResponse
  delivery_passport: OfflineDeliveryPassport
  delivery_passport_markdown: string
}

export interface SbomResponse {
  bomFormat: string
  specVersion: string
  serialNumber: string
  generated_at: string
  product: string
  summary: {
    components: number
    sources: number
    missing_sources: number
    by_type: Record<string, number>
    by_scope: Record<string, number>
  }
  sources: Array<Record<string, unknown>>
  missing_sources: Array<Record<string, unknown>>
  components: Array<Record<string, unknown>>
}

export const productizationApi = {
  readiness: () =>
    apiClient.get<ProductizationReadinessResponse>("/api/v1/productization/readiness", {
      timeout: 90_000,
    }),
  manifest: (body: {
    profile?: string
    include_paths?: string[]
    include_defaults?: boolean
    output_path?: string
    sign?: boolean
    write?: boolean
  }) =>
    apiClient.post<OfflineBundleManifestResponse>("/api/v1/productization/offline-bundle/manifest", body, {
      timeout: 120_000,
    }),
  verifyManifest: (body?: { manifest_path?: string }) =>
    apiClient.post<OfflineBundleVerifyResponse>("/api/v1/productization/offline-bundle/verify", body ?? {}, {
      timeout: 120_000,
    }),
  archive: (body: {
    profile?: string
    include_paths?: string[]
    include_defaults?: boolean
    output_path?: string
    sign?: boolean
  }) =>
    apiClient.post<OfflineBundleArchiveResponse>("/api/v1/productization/offline-bundle/archive", body, {
      timeout: 180_000,
    }),
  verifyArchive: (archive_path: string) =>
    apiClient.post<OfflineBundleVerifyResponse>("/api/v1/productization/offline-bundle/archive/verify", { archive_path }, {
      timeout: 120_000,
    }),
  sbom: (body: {
    include_paths?: string[]
    include_defaults?: boolean
    output_path?: string
    write?: boolean
  }) =>
    apiClient.post<SbomResponse>("/api/v1/productization/sbom", body, {
      timeout: 120_000,
    }),
}

// === EDT MCP Bridge ===
export interface EdtMcpClassification {
  tool_name: string
  known: boolean
  toolset_id?: string | null
  toolset_title?: string | null
  risk: "read" | "session" | "write" | "execute" | "mixed" | "unknown" | string
  requires_confirmation: boolean
  mutates_configuration: boolean
  executes_runtime: boolean
  safety_note: string
}

export interface EdtMcpToolset {
  id: string
  title: string
  purpose: string
  tools: string[]
  risk: string
  preconditions?: string[]
}

export interface EdtMcpCatalogResponse {
  generated_at: string
  source: string
  license: Record<string, string>
  summary: {
    toolsets: number
    tools: number
    write_or_execute_toolsets: number
  }
  toolsets: EdtMcpToolset[]
  presets: Array<Record<string, unknown>>
  high_value_for_1cai: string[]
}

export interface EdtMcpPlanResponse {
  generated_at: string
  task: string
  matched_workflows: string[]
  toolsets_to_enable: string[]
  edt_tools: string[]
  one_cai_tools: string[]
  risk_levels: string[]
  requires_confirmation: boolean
  recommended_preset: string
  progressive_disclosure_calls: Array<Record<string, unknown>>
  safety: string[]
  bridge_notes: string[]
}

export interface EdtMcpStatusResponse {
  checked_at: string
  available: boolean
  status: string
  base_url: string
  mcp_url: string
  auth_required: boolean
  authenticated: boolean
  health?: Record<string, unknown> | null
  server_info?: Record<string, unknown> | null
  errors?: string[]
}

export interface EdtMcpLiveTool {
  name: string
  description?: string
  inputSchema?: Record<string, unknown>
  annotations?: Record<string, unknown>
  classification: EdtMcpClassification
}

export interface EdtMcpLiveToolsResponse {
  available: boolean
  status: string
  generated_at?: string
  mcp_url?: string
  session_id?: string | null
  server?: Record<string, unknown>
  summary?: {
    tools: number
    by_risk: Record<string, number>
    requires_confirmation: number
  }
  tools: EdtMcpLiveTool[]
  error?: unknown
}

export interface EdtMcpCallResponse {
  available: boolean
  status: string
  blocked: boolean
  tool_name: string
  classification: EdtMcpClassification
  policy?: {
    mode: string
    requires_confirmation: boolean
    requires_actor: boolean
    requires_reason: boolean
    requires_approval_record: boolean
    minimum_reason_length: number
    actor?: string | null
    approval_ticket?: string | null
    approval_reason_length: number
    missing: string[]
    audit_action: string
  }
  message?: string
  result?: unknown
  error?: unknown
}

const edtMcpHeaders = (authToken?: string) =>
  authToken ? { "X-EDT-MCP-Token": authToken } : undefined

export interface ApprovalRecord {
  id: string
  kind: string
  status: string
  tool_name: string
  risk: string
  actor: string
  approval_reason: string
  approval_ticket?: string | null
  requested_by?: string | null
  approved_by?: string | null
  decision_reason?: string | null
  linked_record?: {
    type?: string | null
    id?: string | null
  }
  argument_constraints?: Record<string, unknown>
  created_at: string
  updated_at: string
  expires_at: string
  used_at?: string | null
}

export interface ApprovalCreateResponse {
  record: ApprovalRecord
  classification: EdtMcpClassification
}

export const edtMcpApi = {
  catalog: () => apiClient.get<EdtMcpCatalogResponse>("/api/v1/edt-mcp/toolsets"),
  plan: (body: { task: string; intent?: string }) =>
    apiClient.post<EdtMcpPlanResponse>("/api/v1/edt-mcp/plan", body),
  connectionConfig: (baseUrl: string) =>
    apiClient.get<Record<string, unknown>>("/api/v1/edt-mcp/connection-config", {
      params: { base_url: baseUrl },
    }),
  status: (baseUrl: string, authToken?: string) =>
    apiClient.get<EdtMcpStatusResponse>("/api/v1/edt-mcp/status", {
      params: { base_url: baseUrl },
      headers: edtMcpHeaders(authToken),
      timeout: 15_000,
    }),
  liveTools: (baseUrl: string, authToken?: string) =>
    apiClient.get<EdtMcpLiveToolsResponse>("/api/v1/edt-mcp/live-tools", {
      params: { base_url: baseUrl },
      headers: edtMcpHeaders(authToken),
      timeout: 30_000,
    }),
  call: (body: {
    tool_name: string
    arguments?: Record<string, unknown>
    base_url?: string
    confirm?: boolean
    actor?: string
    approval_reason?: string
    approval_ticket?: string
    approval_id?: string
    timeout_s?: number
  }, authToken?: string) =>
    apiClient.post<EdtMcpCallResponse>("/api/v1/edt-mcp/call", body, {
      headers: edtMcpHeaders(authToken),
      timeout: Math.max(30_000, Math.min((body.timeout_s ?? 30) * 1000, 300_000)),
    }),
}

export const approvalsApi = {
  createEdtMcp: (body: {
    tool_name: string
    actor?: string
    approval_reason: string
    approval_ticket?: string
    linked_record_type?: string
    linked_record_id?: string
    argument_constraints?: Record<string, unknown>
    expires_in_hours?: number
  }) => apiClient.post<ApprovalCreateResponse>("/api/v1/approvals/edt-mcp", body),
  approve: (approvalId: string, body: { actor?: string; decision_reason?: string }) =>
    apiClient.post<{ record: ApprovalRecord }>(`/api/v1/approvals/${approvalId}/approve`, body),
  reject: (approvalId: string, body: { actor?: string; decision_reason?: string }) =>
    apiClient.post<{ record: ApprovalRecord }>(`/api/v1/approvals/${approvalId}/reject`, body),
  list: (params?: { status?: string; kind?: string; limit?: number }) =>
    apiClient.get<{ items: ApprovalRecord[]; total: number; path: string }>("/api/v1/approvals", { params }),
  get: (approvalId: string) => apiClient.get<ApprovalRecord>(`/api/v1/approvals/${approvalId}`),
}

// ── Code Review ──
export const codeReviewApi = {
  analyze: (code: string, language?: string) =>
    apiClient.post("/api/v1/analyze", { code, language: language ?? "bsl" }),
  autoFix: (code: string, suggestion_id: string) =>
    apiClient.post("/api/v1/auto-fix", { code, suggestion_id }),
}

// ── Copilot ──
export const copilotApi = {
  complete: (code: string, cursor_position?: number) =>
    apiClient.post("/api/v1/complete", { code, cursor_position }),
  generate: (prompt: string) =>
    apiClient.post("/api/v1/generate", { prompt }),
  generateGrounded: (body: {
    prompt: string
    type?: string
    module_path?: string
    metadata_identifier?: string
    include_its_context?: boolean
    include_requirement_impact?: boolean
  }) =>
    apiClient.post<GroundedGenerationResponse>("/api/v1/generate-grounded", body),
  optimize: (code: string) =>
    apiClient.post("/api/v1/optimize", { code }),
  generateTests: (code: string) =>
    apiClient.post("/api/v1/generate-tests", { code }),
}

export interface GroundedGenerationResponse {
  code: string
  grounding: Record<string, unknown>
  diagnostics: Record<string, unknown>
  caveats: string[]
  plan?: Array<Record<string, unknown>>
  risk_controls?: Array<Record<string, unknown>>
  test_actions?: Array<Record<string, unknown>>
  artifact?: Record<string, unknown>
}

// ── Marketplace ──
export const marketplaceApi = {
  search: (params?: { query?: string; category?: string; page?: number }) =>
    apiClient.get("/api/v1/marketplace/plugins", { params }),
  getPlugin: (id: string) =>
    apiClient.get(`/api/v1/marketplace/plugins/${id}`),
  featured: () => apiClient.get("/api/v1/marketplace/featured"),
  trending: () => apiClient.get("/api/v1/marketplace/trending"),
  categories: () => apiClient.get("/api/v1/marketplace/categories"),
}

// ── Admin ──
export const adminApi = {
  stats: () => apiClient.get("/api/v1/stats"),
  auditLog: (params?: { actor?: string; action?: string; limit?: number; offset?: number }) =>
    apiClient.get("/api/v1/admin/audit", { params }),
}

// ── Wiki ──
export const wikiApi = {
  list: () => apiClient.get("/api/v1/wiki"),
  get: (id: string) => apiClient.get(`/api/v1/wiki/${id}`),
}

// ── BPMN ──
export const bpmnApi = {
  list: () => apiClient.get("/api/v1/diagrams"),
  get: (id: string) => apiClient.get(`/api/v1/diagrams/${id}`),
  save: (data: { name: string; xml: string }) =>
    apiClient.post("/api/v1/diagrams", data),
  update: (id: string, data: { name: string; xml: string }) =>
    apiClient.put(`/api/v1/diagrams/${id}`, data),
  delete: (id: string) => apiClient.delete(`/api/v1/diagrams/${id}`),
}

// ── Health ──
export const healthApi = {
  check: () => apiClient.get("/health"),
}

// === ITS RAG Search ===
export const itsApi = {
  search: (question: string, limit = 5) =>
    apiClient.post<{ results: Array<{ text: string; section_title: string; source_file: string; score: number }>; total: number }>(
      '/api/v1/its/search', { question, limit }
    ),
  context: (question: string, limit = 3) =>
    apiClient.post<{ context: string; query: string }>(
      '/api/v1/its/context', { question, limit }
    ),
};

// === Swarm BSL Review ===
export const swarmApi = {
  review: (code: string) =>
    apiClient.post<{ decision: string; scores: Record<string, number>; response: string | null; confidence: number }>(
      '/api/v1/swarm/review', { code }
    ),
};

// === Рентген качества (Quality Scoring) ===
export interface ModuleScore {
  module_path: string
  module_type: string
  domain: string
  loc: number
  complexity_score: number
  documentation_score: number
  maintainability_score: number
  has_n_plus_one?: boolean
  has_select_star?: boolean
  has_empty_catch?: boolean
  has_deep_nesting?: boolean
  has_magic_numbers?: boolean
  num_todo_fixme?: number
  code_quality: number
}

export interface HotspotReason {
  factor: string
  detail: string
  weight: number
}

export interface Hotspot extends ModuleScore {
  risk: number
  quality_risk: number
  fan_in: number
  fan_out: number
  reasons: HotspotReason[]
}

export interface GraphModuleMatch {
  name: string
  object_name: string
  module_kind: string
  fan_in: number
  fan_out: number
  n_subs: number
  n_export?: number
  max_complexity: number
}

export interface ImpactModuleSummary {
  module: string
  edges: number
}

export interface PerformanceRisk {
  module_path: string
  factor: string
  severity: string
  detail: string
}

export interface ChangeImpactItem {
  module_path: string
  canonical: { object_name: string; module_kind: string; source: string }
  graph_modules: GraphModuleMatch[]
  entry_subroutines: number
  impact_total: number
  impacted_modules: ImpactModuleSummary[]
  impacted_hotspots: Hotspot[]
  quality: Hotspot | null
  changed_hotspot: Hotspot | null
  performance_risks: PerformanceRisk[]
  covering_tests: Array<{ status: string; detail: string }>
  impact_measured: boolean
  coverage: string
  coverage_caveat?: string | null
}

export interface ChangeImpactResponse {
  changed_modules: string[]
  modules: ChangeImpactItem[]
  total_impact_edges: number
  total_impacted_modules: number
  caveats: string[]
  unmeasured_modules: string[]
}

export interface StandardsFinding {
  module_path: string
  source: string
  severity: string
  message: string
  rule_id?: string
  standard?: string
  code?: string
  line?: number
  details: Record<string, unknown>
  autofix?: Record<string, unknown> | null
}

export interface ReviewDiffItem {
  module_path: string
  canonical: { object_name: string; module_kind: string; source: string }
  graph_modules: GraphModuleMatch[]
  quality: Hotspot | null
  changed_hotspot: Hotspot | null
  impact_total: number
  impacted_modules: ImpactModuleSummary[]
  impacted_hotspots: Hotspot[]
  standards_findings: StandardsFinding[]
  impact_measured?: boolean
  coverage?: string
  coverage_caveat?: string | null
}

export interface ReviewDiffResponse {
  changed_modules: string[]
  modules: ReviewDiffItem[]
  total_impact_edges: number
  total_findings: number
  caveats: string[]
}

export interface ReviewDiffRequest {
  changed_modules?: string[]
  diff?: string
  max_depth?: number
  max_edges?: number
  hotspot_limit?: number
}

export interface StandardsReviewResponse {
  generated_at: string
  module_path?: string | null
  engine: string
  bsl_language_server: {
    available: boolean
    home: string
    detected_paths: string[]
    mode: string
  }
  catalog: Array<Record<string, unknown>>
  findings: StandardsFinding[]
  diagnostics: Record<string, unknown>
  summary: {
    findings: number
    by_severity: Record<string, number>
    by_standard: Record<string, number>
    autofixable: number
    loc: number
    functions: number
    procedures: number
    metadata_refs: number
  }
  caveats: string[]
  markdown: string
  stored?: Record<string, unknown>
}

export interface StandardsFindingsList {
  items: Array<{
    module_path: string
    updated_at: string
    summary: StandardsReviewResponse["summary"]
    findings: StandardsFinding[]
    markdown: string
  }>
  total: number
  path: string
}

export interface TestSelectorResponse {
  changed_modules: string[]
  modules: Array<{
    module_path: string
    risk?: number
    impact_total: number
    covering_tests: Array<Record<string, unknown>>
  }>
  caveats: string[]
}

export interface TestCoverageMatrixResponse {
  changed_modules: string[]
  summary: {
    changed_modules: number
    covered: number
    planned: number
    gaps: number
    high_priority: number
    exact_tests: number
    planned_tests: number
    total_impact_edges: number
    total_impacted_modules: number
    unmeasured_impact: number
  }
  inventory: TestInventorySummary
  modules: Array<{
    module_path: string
    canonical: Record<string, string>
    risk: number
    impact_total: number
    impact_measured: boolean
    coverage: string
    coverage_caveat?: string | null
    coverage_status: "covered" | "planned" | "gap"
    priority: "high" | "medium" | "low"
    exact_tests: Array<Record<string, unknown>>
    planned_tests: Array<Record<string, unknown>>
    commands: string[]
    test_data_blueprint: Array<Record<string, unknown>>
    gaps: Array<Record<string, unknown>>
  }>
  change_plan: ChangeImpactResponse
  caveats: string[]
  markdown: string
}

export interface TestFactoryResponse {
  generated_at: string
  client: {
    name: string
  }
  release: {
    name: string
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    headline: string
  }
  summary: {
    changed_modules: number
    run_now: number
    regression_tests: number
    manual_checks: number
    generation_tasks: number
    test_data_items: number
    gaps: number
    unmeasured_impact: number
    exact_tests: number
    planned_tests: number
    commands: number
  }
  run_now: Array<{
    module_path: string
    object_name: string
    priority: string
    coverage_status: string
    command: string
    reason: string
    route: string
  }>
  regression_pack: Array<{
    module_path: string
    object_name: string
    exact_tests: number
    planned_tests: number
    commands: string[]
    acceptance: string
    route: string
  }>
  manual_checks: Array<{
    module_path: string
    title: string
    owner: string
    reason: string
    steps: string[]
    route: string
  }>
  generation_tasks: Array<{
    module_path: string
    object_name: string
    priority: string
    frameworks: string[]
    reason: string
    yaxunit_skeleton: string
    vanessa_scenario: string
    route: string
  }>
  test_data_plan: Array<Record<string, unknown>>
  commands: string[]
  evidence_packet: Array<{
    title: string
    filename: string
    route: string
  }>
  matrix: TestCoverageMatrixResponse
  proof_routes: string[]
  caveats: string[]
  markdown: string
  download_name: string
}

export interface TestInventorySummary {
  root: string
  framework_available: boolean
  summary: {
    test_files: number
    test_cases: number
    by_framework: Record<string, number>
    yaxunit_available: boolean
  }
}

export interface CIGateResponse {
  status: string
  violations: Array<Record<string, unknown>>
  summary: Record<string, number>
  markdown?: string
}

export interface ReleaseReadinessRequest {
  release_name?: string
  changed_modules?: string[]
  diff?: string
  snapshot_id?: string
  include_security?: boolean
  include_forms?: boolean
  form_object_limit?: number
  security_limit?: number
  max_depth?: number
  max_edges?: number
  hotspot_limit?: number
  risk_threshold?: number
  impact_threshold?: number
  fail_on_high?: boolean
}

export interface ReleaseReadinessResponse {
  release_name: string
  generated_at: string
  decision: {
    status: "pass" | "warn" | "fail"
    score: number
    blockers: string[]
    warnings: string[]
  }
  summary: {
    changed_modules: number
    total_impact_edges: number
    total_impacted_modules: number
    unmeasured_impact_modules: number
    gate_violations: number
    standards_findings: number
    form_findings: number
    security_findings: number
    test_actions: number
    metadata_objects: number
  }
  gate: CIGateResponse
  change_plan: ChangeImpactResponse
  standards: {
    summary: Record<string, number>
    findings: StandardsFinding[]
  }
  metadata: {
    surface: {
      objects: Array<Record<string, unknown>>
      summary: Record<string, number>
    }
    snapshot_diff?: MetadataDiffResponse | null
    form_reviews: {
      included: boolean
      items: Array<Record<string, unknown>>
      summary: Record<string, number>
    }
    security_review: MetadataSecurityReview | { included: false }
  }
  tests: {
    total: number
    high_priority: number
    mapped: number
    by_status: Record<string, number>
    items: Array<Record<string, unknown>>
  }
  personas: Record<string, Record<string, unknown>>
  recommended_actions: Array<{
    owner: string
    severity: string
    kind: string
    title: string
    target?: string | null
    details: Record<string, unknown>
  }>
  caveats: string[]
  markdown: string
}

export interface RequirementImpactResponse {
  requirement: string
  candidate_modules: Array<Record<string, unknown>>
  change_plan: ChangeImpactResponse
  its_context: Array<Record<string, unknown>>
  caveats: string[]
}

export interface RequirementTraceRequest {
  title?: string
  text: string
  acceptance_criteria?: string[]
  limit?: number
  max_depth?: number
  max_edges?: number
  include_its_context?: boolean
  save?: boolean
}

export interface RequirementTraceRecord {
  id: string
  title: string
  requirement: string
  acceptance_criteria: string[]
  status: string
  created_at: string
  updated_at: string
  candidate_modules: Array<Record<string, unknown>>
  change_plan: ChangeImpactResponse
  trace_matrix: Array<{
    requirement: string
    module_path: string
    metadata_object: string
    module_kind: string
    match_terms: string[]
    match_score: number
    impact_edges: number
    risk: number
    tests: string[]
    coverage: string
  }>
  links: {
    modules: Array<Record<string, unknown>>
    metadata_objects: Array<Record<string, unknown>>
    tests: Array<Record<string, unknown>>
    its: Array<Record<string, unknown>>
  }
  risk_summary: {
    modules: number
    metadata_objects: number
    total_impact_edges: number
    total_impacted_modules: number
    max_risk: number
    high_risk_modules: number
    test_actions: number
    mapped_tests: number
  }
  next_actions: Array<{
    owner: string
    severity: string
    title: string
    target?: string | null
  }>
  caveats: string[]
  markdown: string
}

export interface RequirementTraceList {
  items: Array<{
    id: string
    title: string
    status: string
    updated_at: string
    risk_summary: Record<string, unknown>
    next_actions: Array<Record<string, unknown>>
  }>
  total: number
  path: string
}

export interface QualitySummary {
  total_modules: number
  avg_complexity: number
  avg_documentation: number
  avg_maintainability: number
  modules_with_issues: number
  by_domain: Array<{ domain: string; count: number; avg_maintainability: number }>
}

export interface QualityStats {
  subroutines: number
  functions: number
  procedures: number
  exported: number
  modules: number
  call_edges: number
  module_edges: number
  quality_modules: number
  avg_complexity: number
  max_complexity: number
  top_fan_in: Array<{ name: string; object_name: string; module_kind: string; fan_in: number; fan_out: number; n_subs: number }>
  top_complex: Array<{ name: string; module: string; complexity: number; line: number }>
  meta: Record<string, string>
}

export const qualityApi = {
  stats: () => apiClient.get<QualityStats>('/api/v1/quality/stats'),
  summary: () => apiClient.get<QualitySummary>('/api/v1/quality/summary'),
  hotspots: (params?: { limit?: number; domain?: string; min_fan_in?: number }) =>
    apiClient.get<Hotspot[]>('/api/v1/quality/hotspots', { params }),
  worst: (limit = 30) =>
    apiClient.get<ModuleScore[]>('/api/v1/quality/worst', { params: { limit } }),
  search: (q: string, limit = 30) =>
    apiClient.get<ModuleScore[]>('/api/v1/quality/search', { params: { q, limit } }),
  module: (path: string) =>
    apiClient.get<ModuleScore | null>('/api/v1/quality/module', { params: { path } }),
  reviewDiff: (body: ReviewDiffRequest) =>
    apiClient.post<ReviewDiffResponse>('/api/v1/quality/review-diff', body),
  standardsReview: (body: { code: string; module_path?: string; save?: boolean; max_nesting_threshold?: number }) =>
    apiClient.post<StandardsReviewResponse>('/api/v1/quality/standards-review', body),
  standardsFindings: (params?: { module_path?: string; limit?: number }) =>
    apiClient.get<StandardsFindingsList>('/api/v1/quality/standards-findings', { params }),
  standardsCatalog: () =>
    apiClient.get<{ items: Record<string, Record<string, unknown>>; total: number }>('/api/v1/quality/standards-catalog'),
};

// === Рентген (Call Graph) ===
export interface FlowEdge {
  caller: string
  caller_module: string
  callee: string
  callee_module: string
  line?: number
  depth: number
}

export interface DeadCodeItem {
  name: string
  kind: string
  module: string
  module_path: string
  line: number
  complexity: number
}

export const rentgenApi = {
  build: (configPath: string) =>
    apiClient.get<{ built: boolean; meta?: Record<string, string | number>; hint?: string }>(
      '/api/v1/rentgen/build',
      { params: configPath ? { config_path: configPath } : undefined },
    ),
  flow: (entryPoint: string, maxDepth = 10) =>
    apiClient.post<{ entry_point: string; edges: FlowEdge[]; total: number }>(
      '/api/v1/rentgen/flow', { entry_point: entryPoint, max_depth: maxDepth }
    ),
  impact: (entryPoint: string, maxDepth = 5) =>
    apiClient.post<{ target: string; callers: FlowEdge[]; total: number }>(
      '/api/v1/rentgen/impact', { entry_point: entryPoint, max_depth: maxDepth }
    ),
  deadCode: (params?: { limit?: number; scope?: string }) =>
    apiClient.get<{ candidates: DeadCodeItem[]; total: number; shown: number; scope: string }>(
      '/api/v1/rentgen/dead-code', { params }
    ),
  moduleNeighbors: (module: string, limit = 15) =>
    apiClient.get<{
      module: string
      info: { name: string; object_name: string; module_kind: string; fan_in: number; fan_out: number; n_subs: number; max_complexity: number }
      calls: Array<{ module: string; weight: number }>
      called_by: Array<{ module: string; weight: number }>
    }>('/api/v1/rentgen/module-neighbors', { params: { module, limit } }),
  changeImpact: (changedModules: string[], maxDepth = 5) =>
    apiClient.post<ChangeImpactResponse>(
      '/api/v1/rentgen/change-impact',
      { changed_modules: changedModules, max_depth: maxDepth }
    ),
  testSelector: (body: ReviewDiffRequest) =>
    apiClient.post<TestSelectorResponse>('/api/v1/rentgen/test-selector', body),
  testCoverageMatrix: (body: ReviewDiffRequest & { match_limit?: number }) =>
    apiClient.post<TestCoverageMatrixResponse>('/api/v1/rentgen/test-coverage-matrix', body),
  testInventory: () =>
    apiClient.get<TestInventorySummary>('/api/v1/rentgen/test-inventory'),
  testInventoryMatch: (body: { module_path: string; object_name?: string; limit?: number }) =>
    apiClient.post<{ module_path: string; object_name?: string; matches: Array<Record<string, unknown>> }>(
      '/api/v1/rentgen/test-inventory/match',
      body,
    ),
  ciGate: (body: ReviewDiffRequest & { risk_threshold?: number; impact_threshold?: number; fail_on_high?: boolean }) =>
    apiClient.post<CIGateResponse>('/api/v1/rentgen/ci-gate', body),
  stats: () => apiClient.get<Record<string, number>>('/api/v1/rentgen/stats'),
};

export const testFactoryApi = {
  build: (body: ReviewDiffRequest & { client_name?: string; release_name?: string; match_limit?: number }) =>
    apiClient.post<TestFactoryResponse>('/api/v1/test-factory/build', body, {
      timeout: 180_000,
    }),
}

// === Release Readiness ===
export const releaseReadinessApi = {
  analyze: (body: ReleaseReadinessRequest) =>
    apiClient.post<ReleaseReadinessResponse>('/api/v1/release-readiness/analyze', body, {
      timeout: body.include_security ? 240_000 : 60_000,
    }),
};

// === Architecture Review ===
export interface ArchitectureReviewRequest {
  changed_modules?: string[]
  diff?: string
  limit?: number
  min_weight?: number
  dense_threshold?: number
  include_cycles?: boolean
  finding_limit?: number
}

export interface ArchitectureFinding {
  rule: string
  severity: "high" | "medium" | "low" | "info"
  src: string
  dst: string
  weight: number
  src_layer: string
  dst_layer: string
  message: string
  recommendation: string
  details: Record<string, unknown>
}

export interface ArchitectureReviewResponse {
  scope: {
    mode: string
    changed_modules: string[]
    focus_graph_modules: string[]
    limit: number
    min_weight: number
    dense_threshold: number
  }
  summary: {
    edges_reviewed: number
    findings: number
    by_severity: Record<string, number>
    by_rule: Record<string, number>
    layer_edges: Record<string, number>
    score: number
  }
  findings: ArchitectureFinding[]
  hubs: Array<{ module: string; out_weight: number; edges: number; layer: string }>
  top_edges: Array<{
    src: string
    dst: string
    weight: number
    src_layer: string
    dst_layer: string
    src_path?: string | null
    dst_path?: string | null
  }>
  caveats: string[]
}

export const architectureApi = {
  review: (body: ArchitectureReviewRequest) =>
    apiClient.post<ArchitectureReviewResponse>('/api/v1/architecture/review', body, {
      timeout: 90_000,
    }),
};

// === Offline Readiness ===
export interface OfflineReadinessCheck {
  id: string
  title: string
  status: "pass" | "warn" | "fail"
  severity: "high" | "medium" | "low"
  evidence: Record<string, unknown> | string | number | boolean | null
}

export interface OfflineReadinessResponse {
  strict: boolean
  root: string
  decision: {
    status: "pass" | "warn" | "fail"
    score: number
    fails: number
    warnings: number
  }
  summary: {
    checks: number
    passes: number
    warnings: number
    fails: number
    external_env: number
    metadata_objects: number
    its_docs: number
  }
  checks: OfflineReadinessCheck[]
  external_env: string[]
  runtime: Record<string, string>
  caveats: string[]
  markdown: string
}

export const offlineReadinessApi = {
  analyze: (strict = false) =>
    apiClient.get<OfflineReadinessResponse>('/api/v1/offline-readiness/analyze', {
      params: { strict },
      timeout: 90_000,
    }),
  health: () => apiClient.get('/api/v1/offline-readiness/health'),
};

// === Team Governance ===
export interface TeamGovernanceResponse {
  available: boolean
  generated_at: string
  summary: {
    areas: number
    red_areas: number
    yellow_areas: number
    review_queue: number
    total_modules: number
    modules_with_issues: number
    avg_maintainability: number
  }
  areas: Array<{
    domain: string
    owner: { id: string; name: string; lead: string; source: string }
    modules: number
    avg_maintainability: number
    hotspots: number
    max_risk: number
    status: string
    risk_sla: string
    top_hotspots: Array<Record<string, unknown>>
  }>
  release_board: {
    status_counts: Record<string, number>
    review_queue: Array<Record<string, unknown>>
    sla_policy: Record<string, string>
  }
  trend: {
    path: string
    snapshots: Array<Record<string, unknown>>
    total: number
  }
  recommendations: Array<{
    owner: string
    severity: string
    title: string
    details: Record<string, unknown>
  }>
  caveats: string[]
  markdown: string
  stored_snapshot?: Record<string, unknown>
}

export const teamGovernanceApi = {
  board: (params?: { limit?: number; save_snapshot?: boolean }) =>
    apiClient.get<TeamGovernanceResponse>('/api/v1/team-governance/board', {
      params,
      timeout: 90_000,
    }),
  snapshot: (limit = 40) =>
    apiClient.post<Record<string, unknown>>('/api/v1/team-governance/snapshots', null, {
      params: { limit },
      timeout: 90_000,
    }),
};

// === 1C Metadata Graph ===
export interface MetadataCounts {
  modules: number
  forms: number
  commands: number
  attributes: number
  tabular_sections: number
  dimensions?: number
  resources?: number
  rights_objects: number
  rights: number
}

export interface MetadataPreview {
  type: string
  name: string
  synonym?: string | null
  ref: string
  path: string
  uuid?: string | null
  counts: MetadataCounts
}

export interface MetadataSummaryResponse {
  available: boolean
  config_path: string
  configuration: Record<string, string | null>
  summary: {
    total_objects: number
    by_type: Record<string, number>
    total_forms: number
    total_modules: number
    total_roles: number
    total_rights: number
    roles_with_dangerous_rights: number
  }
}

export interface MetadataObject extends MetadataPreview {
  comment?: string | null
  folder: string
  modules: Array<{ path: string; name: string; type: string; size: number }>
  forms: Array<{ name: string; synonym?: string | null; form_type?: string | null; path: string; module_path?: string | null }>
  commands: Array<{ name: string; path: string }>
  attributes: Array<Record<string, string>>
  tabular_sections: Array<Record<string, string>>
  dimensions?: Array<Record<string, string>>
  resources?: Array<Record<string, string>>
  references: string[]
  rights?: {
    path: string
    objects: number
    rights: number
    dangerous: Array<{ object: string; right: string }>
  } | null
}

export interface MetadataImpactResponse {
  object: MetadataPreview
  modules: string[]
  rentgen_available: boolean
  total_impact_edges: number
  impacts: Array<Record<string, unknown>>
  caveats: string[]
}

export interface MetadataSecurityReview {
  summary: {
    roles: number
    roles_with_rights: number
    total_rights: number
    dangerous_rights: number
    findings: number
    by_right: Record<string, number>
  }
  findings: Array<{
    role: string
    severity: string
    code: string
    message: string
    details: Record<string, unknown>
  }>
  caveats: string[]
}

export interface MetadataSecurityPosture {
  available: boolean
  generated_at: string
  config_path: string
  decision: {
    status: "pass" | "warn" | "fail"
    score: number
    high: number
    medium: number
    low: number
  }
  summary: {
    metadata_objects?: number
    roles?: number
    roles_with_rights?: number
    dangerous_rights?: number
    role_findings?: number
    privileged_code_paths?: number
    dynamic_execute_paths?: number
    integration_code_paths?: number
    exchange_objects?: number
    external_exposure?: number
    scanned_modules?: number
    findings: number
    by_severity: Record<string, number>
  }
  role_review: MetadataSecurityReview
  role_diff: Record<string, unknown>
  privileged_code_paths: Array<Record<string, unknown>>
  dynamic_execute_paths: Array<Record<string, unknown>>
  integration_exposure: {
    metadata_objects: Array<Record<string, unknown>>
    code_paths: Array<Record<string, unknown>>
    by_type: Record<string, number>
  }
  code_scan: {
    scanned_modules: number
    scan_limit?: number
    truncated: boolean
    max_file_bytes?: number
    skipped_large?: number
    by_rule?: Record<string, number>
  }
  recommendations: Array<{
    owner: string
    severity: string
    title: string
    details: Record<string, unknown>
  }>
  caveats: string[]
  markdown: string
}

export interface MetadataDataGovernance {
  available: boolean
  config_path: string
  summary: {
    total_objects: number
    data_objects: number
    registers: number
    exchange_objects: number
    roles: number
    dangerous_rights: number
    migration_findings: number
    by_group: Record<string, number>
    by_type: Record<string, number>
  }
  objects: Array<Record<string, unknown>>
  exchanges: Array<Record<string, unknown>>
  rights: {
    summary: Record<string, unknown>
    findings: Array<Record<string, unknown>>
  }
  migration_findings: Array<{
    severity: string
    code: string
    ref: string
    message: string
    details: Record<string, unknown>
  }>
  caveats: string[]
}

export interface MetadataFormReview {
  object: { type: string; name: string; ref: string; path: string }
  forms: Array<{
    form: { name: string; path: string; module_path?: string | null }
    ext_path: string
    metrics: Record<string, unknown>
    diagnostics?: Record<string, unknown> | null
    findings: Array<{
      severity: string
      code: string
      message: string
      details: Record<string, unknown>
    }>
  }>
  summary: { forms_reviewed: number; findings: number }
  caveats: string[]
}

export interface MetadataFormBlueprint {
  generated_at: string
  config_path: string
  identifier: string
  intent: string
  object: {
    type: string
    name: string
    ref: string
    path: string
    synonym?: string | null
  }
  form_kind: "object" | "list" | "choice"
  summary: {
    fields: number
    tabular_sections: number
    commands: number
    existing_forms: number
    review_findings: number
    ux_rules: number
    readiness: string
  }
  layout: Record<string, unknown>
  commands: Array<Record<string, string>>
  ux_rules: Array<{
    severity: string
    code: string
    message: string
    details?: Record<string, unknown>
  }>
  review?: MetadataFormReview | null
  generated_assets: {
    form_xml: string
    form_module_bsl: string
    import_ready: boolean
  }
  acceptance_checks: string[]
  caveats: string[]
  markdown: string
}

export interface MetadataSnapshot {
  id: string
  path: string
  created_at?: string
  summary: Record<string, unknown>
}

export interface MetadataDiffResponse {
  snapshot: MetadataSnapshot
  current: { created_at: string; summary: Record<string, unknown> }
  summary: { added: number; removed: number; changed: number }
  added: MetadataPreview[]
  removed: MetadataPreview[]
  changed: Array<Record<string, unknown>>
  caveats: string[]
}

export const metadataApi = {
  summary: () => apiClient.get<MetadataSummaryResponse>('/api/v1/metadata/summary'),
  search: (params?: { q?: string; type?: string; limit?: number }) =>
    apiClient.get<{ items: MetadataPreview[] }>('/api/v1/metadata/search', { params }),
  object: (identifier: string) =>
    apiClient.get<MetadataObject>('/api/v1/metadata/object', { params: { identifier } }),
  objectImpact: (identifier: string) =>
    apiClient.get<MetadataImpactResponse>('/api/v1/metadata/object-impact', { params: { identifier } }),
  securityReview: (limit = 200) =>
    apiClient.get<MetadataSecurityReview>('/api/v1/metadata/security-review', {
      params: { limit },
      timeout: 240_000,
    }),
  securityPosture: (params?: { limit?: number; module_limit?: number; snapshot_id?: string }) =>
    apiClient.get<MetadataSecurityPosture>('/api/v1/metadata/security-posture', {
      params,
      timeout: 240_000,
    }),
  dataGovernance: (limit = 120) =>
    apiClient.get<MetadataDataGovernance>('/api/v1/metadata/data-governance', {
      params: { limit },
      timeout: 240_000,
    }),
  formReview: (body: { identifier: string; form_name?: string }) =>
    apiClient.post<MetadataFormReview>('/api/v1/metadata/form-review', body),
  formBlueprint: (body: { identifier: string; form_kind?: string; intent?: string; include_review?: boolean }) =>
    apiClient.post<MetadataFormBlueprint>('/api/v1/metadata/form-blueprint', body, {
      timeout: 120_000,
    }),
  snapshots: () =>
    apiClient.get<{ items: MetadataSnapshot[]; total: number }>('/api/v1/metadata/snapshots'),
  canonicalSnapshots: () =>
    apiClient.get<{ items: Array<Record<string, unknown>>; total: number }>('/api/v1/metadata/canonical-snapshots'),
  canonicalObjects: (params?: { type?: string; group?: string; q?: string; limit?: number }) =>
    apiClient.get<{ items: Array<Record<string, unknown>>; total: number }>('/api/v1/metadata/objects', { params }),
  createSnapshot: (name?: string) =>
    apiClient.post<MetadataSnapshot>('/api/v1/metadata/snapshots', { name }),
  diff: (snapshot_id: string, limit = 100) =>
    apiClient.post<MetadataDiffResponse>('/api/v1/metadata/diff', { snapshot_id, limit }),
  refresh: () => apiClient.post<MetadataSummaryResponse>('/api/v1/metadata/refresh'),
};

// === Internal ALM / Enterprise Workbench ===
export interface ArtifactHealthResponse {
  status: string
  artifacts: number
  links: number
  by_type: Record<string, number>
}

export interface ArtifactMatrixResponse {
  summary: {
    rows: number
    covered: number
    partial: number
    gaps: number
    suspect_rows: number
    artifacts: number
    links: number
  }
  rows: Array<Record<string, unknown>>
}

export interface ListResponse<T = Record<string, unknown>> {
  items: T[]
  total: number
  path?: string
}

export interface PolicyEvaluationList extends ListResponse {
  items: Array<{
    id: string
    status: string
    scope_id?: string | null
    generated_at?: string
    summary: Record<string, number>
  }>
}

export interface TestRunList extends ListResponse {
  items: Array<{
    id: string
    title: string
    framework: string
    status: string
    change_set_id?: string | null
    summary: Record<string, number>
    created_at: string
  }>
}

export interface EnterpriseReadiness {
  status: string
  summary: {
    providers: number
    enabled_providers: number
    boundaries: number
    high: number
    medium: number
    low: number
  }
  findings: Array<Record<string, string>>
}

export const artifactsApi = {
  health: () => apiClient.get<ArtifactHealthResponse>('/api/v1/artifacts/health'),
  matrix: () => apiClient.get<ArtifactMatrixResponse>('/api/v1/artifacts/matrix'),
}

export const changeSetsApi = {
  list: (params?: { status?: string; owner?: string; limit?: number }) =>
    apiClient.get<ListResponse>('/api/v1/change-sets', { params }),
}

export const policiesApi = {
  evaluations: (limit = 20) => apiClient.get<PolicyEvaluationList>('/api/v1/policies/evaluations', { params: { limit } }),
  waivers: (params?: { status?: string; limit?: number }) =>
    apiClient.get<ListResponse>('/api/v1/policies/waivers', { params }),
}

export const testingEvidenceApi = {
  runs: (params?: { status?: string; change_set_id?: string; limit?: number }) =>
    apiClient.get<TestRunList>('/api/v1/testing/runs', { params }),
  runners: () => apiClient.get<Record<string, unknown>>('/api/v1/testing/runners'),
}

export interface AuditEvent {
  id: string
  timestamp: string
  actor: string
  action: string
  target?: string | null
  category: string
  outcome: string
  correlation_id?: string | null
  metadata?: Record<string, unknown>
  prev_hash?: string
}

export interface AuditEventList {
  items: AuditEvent[]
  total: number
  path: string
}

export interface AuditVerifyReport {
  valid: boolean
  total: number
  chained: number
  legacy: number
  broken: Array<{
    index: number
    id: string
    actor?: string | null
    action?: string | null
    reasons: string[]
  }>
  path: string
}

export interface AuditExportResponse {
  format: string
  events: number
  content: string
  path: string
}

export interface AuditSiemExportResponse extends AuditExportResponse {
  schema: string
  content_sha256: string
  chain: AuditVerifyReport
  ingestion: {
    recommended_filename: string
    format: string
    time_field: string
    event_id_field: string
    chain_valid_field: string
    message: string
  }
}

export const auditApi = {
  events: (params?: { actor?: string; action?: string; category?: string; target?: string; limit?: number }) =>
    apiClient.get<AuditEventList>('/api/v1/audit/events', { params }),
  verify: () => apiClient.get<AuditVerifyReport>('/api/v1/audit/verify'),
  export: (format: "jsonl" | "json" = "jsonl") =>
    apiClient.get<AuditExportResponse>('/api/v1/audit/export', { params: { format } }),
  siemExport: (format: "jsonl" | "json" = "jsonl", limit = 1000) =>
    apiClient.get<AuditSiemExportResponse>('/api/v1/audit/siem-export', { params: { format, limit } }),
}

export const enterpriseApi = {
  readiness: () => apiClient.get<EnterpriseReadiness>('/api/v1/enterprise/iam/readiness'),
  boundaries: (tenant_id?: string) =>
    apiClient.get<ListResponse>('/api/v1/enterprise/projects/boundaries', { params: { tenant_id } }),
}

// === Requirements / BA impact ===
export const requirementsApi = {
  impact: (text: string, limit = 6) =>
    apiClient.post<RequirementImpactResponse>(
      '/api/v1/requirements/impact',
      { text, limit }
    ),
  trace: (body: RequirementTraceRequest) =>
    apiClient.post<RequirementTraceRecord>('/api/v1/requirements/trace', body, {
      timeout: 90_000,
    }),
  traces: (limit = 20) =>
    apiClient.get<RequirementTraceList>('/api/v1/requirements/traces', { params: { limit } }),
  traceDetails: (traceId: string) =>
    apiClient.get<RequirementTraceRecord>(`/api/v1/requirements/traces/${traceId}`),
};

// === Перформер (Performance) ===
export interface PerformerHotspot {
  module: string
  line: number
  code_fragment: string
  sdbl: string
  total_calls: number
  total_duration_ms: number
  max_duration_us: number
  avg_rows: number
  is_in_loop: boolean
}

export interface PerformerReport {
  total_events: number
  total_duration_ms: number
  hotspots: PerformerHotspot[]
  n_plus_one: PerformerHotspot[]
  lock_waits_count: number
  deadlocks_count: number
}

export interface PerformerHotspotImpact {
  hotspot: PerformerHotspot
  canonical: Record<string, string>
  graph_modules: GraphModuleMatch[]
  impact_total: number
  impacted_modules: ImpactModuleSummary[]
}

export interface PerformerImpactReport extends PerformerReport {
  hotspot_impacts: PerformerHotspotImpact[]
}

export const performerApi = {
  analyze: (logPath: string, minDurationMs = 100, topN = 20) =>
    apiClient.post<PerformerReport>(
      '/api/v1/performer/analyze', { log_path: logPath, min_duration_ms: minDurationMs, top_n: topN }
    ),
  impact: (logPath: string, minDurationMs = 100, topN = 20) =>
    apiClient.post<PerformerImpactReport>(
      '/api/v1/performer/impact', { log_path: logPath, min_duration_ms: minDurationMs, top_n: topN }
    ),
};

// === Operations / Incident Response ===
export interface IncidentReportRequest {
  incident_title?: string
  description?: string
  symptoms?: string[]
  log_path?: string
  changed_modules?: string[]
  min_duration_ms?: number
  top_n?: number
  module_limit?: number
  max_depth?: number
  max_edges?: number
  include_team?: boolean
}

export interface IncidentReportResponse {
  generated_at: string
  incident: {
    title: string
    description: string
    symptoms: string[]
    log_path?: string | null
  }
  decision: {
    status: "critical" | "high" | "medium" | "low"
    severity_score: number
    max_module_risk: number
    total_impact_edges: number
    test_gaps: number
  }
  summary: {
    tj_events: number
    tj_duration_ms: number
    hotspots: number
    n_plus_one: number
    lock_waits: number
    deadlocks: number
    modules: number
    owner_areas: number
    total_impact_edges: number
    test_actions: number
    test_gaps: number
  }
  signals: Array<{
    kind: string
    severity: string
    title: string
    evidence: Record<string, unknown>
  }>
  tj_report: {
    available: boolean
    error?: string | null
    total_events: number
    total_duration_ms: number
    hotspots: PerformerHotspot[]
    n_plus_one: PerformerHotspot[]
    lock_waits_count: number
    deadlocks_count: number
  }
  module_plan: Array<{
    module_ref: string
    sources: string[]
    canonical: Record<string, string>
    graph_modules: GraphModuleMatch[]
    entry_subroutines: number
    impact_total: number
    impacted_modules: ImpactModuleSummary[]
    quality?: (Hotspot & { domain?: string }) | null
    owner?: { id?: string; name?: string; lead?: string; source?: string } | null
    tj_hotspots: PerformerHotspot[]
    impacted_hotspots: Hotspot[]
  }>
  test_matrix?: TestCoverageMatrixResponse | null
  team_governance: {
    included: boolean
    summary: Record<string, unknown>
    owner_counts: Record<string, number>
  }
  recommended_actions: Array<{
    owner: string
    severity: string
    kind: string
    title: string
    target?: string | null
    details: Record<string, unknown>
  }>
  runbook: Array<{
    phase: string
    owner: string
    action: string
  }>
  caveats: string[]
  markdown: string
}

export const operationsApi = {
  incidentReport: (body: IncidentReportRequest) =>
    apiClient.post<IncidentReportResponse>('/api/v1/operations/incident-report', body, {
      timeout: 120_000,
    }),
};

// === Lock Radar / Technology Journal locks ===
export interface LockRadarRequest {
  log_path?: string
  changed_modules?: string[]
  module_limit?: number
  max_depth?: number
  max_edges?: number
}

export interface LockRadarEvent {
  timestamp: string
  kind: "TLOCK" | "TTIMEOUT" | "TDEADLOCK" | string
  severity: string
  duration_ms: number
  user: string
  process: string
  module_refs: string[]
  top_module: string
  context: string[]
  extra: Record<string, unknown>
}

export interface LockRadarModule {
  module_ref: string
  sources: string[]
  lock_events: number
}

export interface LockRadarResponse {
  generated_at: string
  source: {
    path: string
    available: boolean
    changed_modules: string[]
  }
  decision: {
    status: "ready" | "watch" | "risk" | "critical" | string
    score: number
    risk_score: number
    headline: string
    max_duration_ms: number
    max_module_risk: number
    test_gaps: number
  }
  summary: {
    total_events: number
    lock_waits: number
    timeouts: number
    deadlocks: number
    modules: number
    module_plan: number
    test_gaps: number
  }
  modules: LockRadarModule[]
  events: LockRadarEvent[]
  module_plan: Array<Record<string, unknown>>
  test_matrix?: TestCoverageMatrixResponse | null
  recommended_actions: Array<{
    owner: string
    severity: string
    kind: string
    title: string
    target?: string | null
    details: Record<string, unknown>
  }>
  runbook: Array<{
    phase: string
    owner: string
    action: string
  }>
  caveats: string[]
  markdown: string
}

export const lockRadarApi = {
  analyze: (body: LockRadarRequest) =>
    apiClient.post<LockRadarResponse>('/api/v1/lock-radar/analyze', body, {
      timeout: 120_000,
    }),
};

// === Extension Safety / 1C extensions ===
export interface ExtensionSafetyRequest {
  config_path?: string
  changed_modules?: string[]
  extension_limit?: number
  max_files_per_extension?: number
  max_depth?: number
  max_edges?: number
}

export interface ExtensionSafetyExtension {
  name: string
  path: string
  kind: string
  files: number
  files_truncated: boolean
  bsl_files: number
  xml_files: number
  rights_files: number
  borrowed_objects: number
  modules: string[]
  objects: string[]
  signals: Array<{
    id: string
    severity: string
    title: string
    path: string
  }>
  severity_counts: Record<string, number>
  signal_counts: Record<string, number>
}

export interface ExtensionSafetyResponse {
  generated_at: string
  source: {
    path: string
    exists: boolean
  }
  decision: {
    status: "ready" | "watch" | "risk" | string
    score: number
    risk_score: number
    headline: string
    signals?: Record<string, number>
    max_module_risk?: number
    impact_total?: number
    test_gaps?: number
  }
  summary: {
    extensions: number
    modules: number
    objects: number
    signals: number
    high: number
    medium: number
    rights_files: number
    borrowed_objects: number
    impact_modules: number
    test_gaps: number
  }
  extensions: ExtensionSafetyExtension[]
  modules: string[]
  impact: Array<Record<string, unknown>>
  test_matrix?: TestCoverageMatrixResponse | null
  recommended_actions: Array<{
    owner: string
    severity: string
    kind: string
    title: string
    target?: string | null
    details: Record<string, unknown>
  }>
  checklist: string[]
  caveats: string[]
  markdown: string
}

export const extensionSafetyApi = {
  analyze: (body: ExtensionSafetyRequest) =>
    apiClient.post<ExtensionSafetyResponse>('/api/v1/extension-safety/analyze', body, {
      timeout: 120_000,
    }),
};

// === 1C Copilot Coverage Map ===
export type CoverageStatus = "done" | "partial" | "planned"

export interface CoverageStage {
  id: string
  title: string
  description: string
}

export interface CoveragePersona {
  id: string
  title: string
}

export interface CoverageItem {
  id: string
  stage: string
  title: string
  personas: string[]
  naparnik: string
  ours: string
  target: string
  status: CoverageStatus
  priority: string
  moat: string
  enterprise_value: string
  next_build: string
  implementation_refs: string[]
}

export interface CoverageResponse {
  product: string
  positioning: string
  stages: CoverageStage[]
  personas: CoveragePersona[]
  competitor: {
    name: string
    observed_strengths: string[]
    observed_gaps: string[]
    sources: Array<{ title: string; url: string; signal: string }>
  }
  runtime: Record<string, string | number | boolean>
  summary: {
    total_items: number
    by_status: Record<string, number>
    by_stage: Record<string, number>
    by_priority: Record<string, number>
    coverage_score: number
    p0_coverage_score: number
    done: number
    partial: number
    planned: number
  }
  items: CoverageItem[]
  next_actions: Array<{
    id: string
    title: string
    priority: string
    stage: string
    next_build: string
  }>
}

export const copilotCoverageApi = {
  get: () => apiClient.get<CoverageResponse>('/api/v1/copilot-coverage'),
};

export default apiClient
