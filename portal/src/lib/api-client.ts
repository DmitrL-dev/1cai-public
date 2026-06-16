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
  me: () => apiClient.get("/api/v1/auth/me"),
}

// ── Dashboard ──
export const dashboardApi = {
  developer: () => apiClient.get("/api/v1/developer"),
  executive: () => apiClient.get("/api/v1/executive"),
  pm: () => apiClient.get("/api/v1/pm"),
  owner: () => apiClient.get("/api/v1/owner"),
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
  markdown: string
}

export const managementApi = {
  executive: (params?: { governance_limit?: number; hotspot_limit?: number; save_snapshot?: boolean }) =>
    apiClient.get<ExecutiveDashboardResponse>("/api/v1/management/executive", {
      params,
      timeout: 90_000,
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
}

export interface ChangeImpactResponse {
  changed_modules: string[]
  modules: ChangeImpactItem[]
  total_impact_edges: number
  total_impacted_modules: number
  caveats: string[]
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
  }
  inventory: TestInventorySummary
  modules: Array<{
    module_path: string
    canonical: Record<string, string>
    risk: number
    impact_total: number
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
    apiClient.post<{ modules: number; functions: number; procedures: number; calls: number; subscriptions: number; queries: number }>(
      '/api/v1/rentgen/build', { config_path: configPath }
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

export interface AuditEventList extends ListResponse {
  items: Array<{
    id: string
    timestamp: string
    actor: string
    action: string
    target?: string | null
    category: string
    outcome: string
    metadata: Record<string, unknown>
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

export const auditApi = {
  events: (params?: { actor?: string; action?: string; category?: string; target?: string; limit?: number }) =>
    apiClient.get<AuditEventList>('/api/v1/audit/events', { params }),
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
