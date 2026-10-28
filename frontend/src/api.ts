export interface ProviderInfo {
  name: string
  configured: boolean
  default_model: string
  available_models: string[]
}

export interface ProviderConfigResponse {
  providers: Record<string, ProviderInfo>
  custom_models: Array<{
    id: string
    name: string
    model_id: string
    base_url: string
    has_api_key: boolean
  }>
  judge_enabled: boolean
  judge_provider: string
  environment: string
}

export interface OverviewMetrics {
  total_runs: number
  models_evaluated: number
  test_cases_executed: number
}

export interface OverviewResponse {
  project: string
  status: string
  metrics: OverviewMetrics
}

export interface DatasetItem {
  dataset_file: string
  dataset_name: string
  dataset_version: string
  case_count: number
  sha256: string
}

export interface DatasetCaseDetail {
  test_case_id: string
  task_category: string
  input_prompt: string
  reference_answer?: string | null
  reference_context?: string | null
  evaluation_method: string
  difficulty?: string | null
  expected_output_schema?: Record<string, any> | null
  tags?: string[]
}

export interface DatasetCasesResponse {
  dataset_file: string
  dataset_name: string
  dataset_version: string
  sha256: string
  total_cases: number
  cases: DatasetCaseDetail[]
}

export interface RunSummary {
  id: string
  dataset_file: string
  dataset_name: string
  dataset_version: string
  dataset_sha256: string
  provider: string
  model_id: string
  status: string
  judge_enabled: boolean
  started_at: string
  completed_at: string | null
  total_cases: number
  completed_cases: number
  passed_cases: number
  errored_cases: number
  total_input_tokens: number | null
  total_output_tokens: number | null
  total_latency_ms: number
  total_estimated_cost_usd: number | null
  error_message: string | null
}

export interface CaseResultItem {
  id: string
  ordinal: number
  test_case_id: string
  evaluation_method: string
  status: string
  candidate_text: string | null
  provider: string | null
  model_id: string | null
  input_tokens: number | null
  output_tokens: number | null
  latency_ms: number | null
  estimated_cost_usd: number | null
  deterministic_result: any | null
  semantic_result: any | null
  judge_result: any | null
  evaluation_error: string | null
  error_category: string | null
  error_message: string | null
}

export interface RunDetail extends RunSummary {
  cases: CaseResultItem[]
}

export interface CustomModelItem {
  id: string
  name: string
  model_id: string
  base_url: string
  has_api_key: boolean
  description?: string | null
  created_at: string
  is_active: boolean
}

export interface MetricComparison {
  metric: string
  statistical_test: string
  higher_is_better: boolean
  paired_cases: number
  baseline_mean: number
  candidate_mean: number
  mean_delta: number
  confidence_interval_95: [number, number] | null
  p_value: number | null
  adjusted_p_value: number | null
  regression_detected: boolean
}

export interface RunComparisonResult {
  method_version: string
  baseline_run_id: string
  candidate_run_id: string
  dataset_name: string
  dataset_version: string
  dataset_sha256: string
  alpha: number
  minimum_regression_drop: number
  multiple_testing_correction: string
  confidence_interval_method: string
  metrics: MetricComparison[]
}

export interface ComparisonResponse {
  id: string
  created_at: string
  result: RunComparisonResult
}

export interface AnalysisListItem {
  id: string
  created_at: string
  baseline_run_id: string
  candidate_run_id: string
  method_version: string
  metric_count: number
  regressions_detected: number
}

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '')
const API_BASE = rawBase ? `${rawBase}/api` : '/api'
const API_KEY = (import.meta.env.VITE_BACKEND_API_KEY as string | undefined) || ''

function requestHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY
  }
  return headers
}

export async function fetchOverview(): Promise<OverviewResponse> {
  const res = await fetch(`${API_BASE}/overview`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Overview fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchProviders(): Promise<ProviderConfigResponse> {
  const res = await fetch(`${API_BASE}/config/providers`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Providers fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchDatasets(): Promise<DatasetItem[]> {
  const res = await fetch(`${API_BASE}/datasets`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Datasets fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchDatasetCases(file: string): Promise<DatasetCasesResponse> {
  const res = await fetch(`${API_BASE}/datasets/${file}/cases`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Dataset cases fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_BASE}/runs`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Runs fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchRun(id: string): Promise<RunDetail> {
  const res = await fetch(`${API_BASE}/runs/${id}`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Run detail fetch failed: ${res.statusText}`)
  return res.json()
}

export async function createRun(payload: {
  dataset_file: string
  provider: string
  model_id?: string
  include_judge?: boolean
}): Promise<RunSummary> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: requestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Run creation failed: ${res.statusText}`)
  }
  return res.json()
}

export async function compareRuns(payload: {
  baseline_run_id: string
  candidate_run_id: string
  alpha?: number
  minimum_regression_drop?: number
}): Promise<ComparisonResponse> {
  const res = await fetch(`${API_BASE}/analyses/compare`, {
    method: 'POST',
    headers: requestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Comparison failed: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchAnalyses(): Promise<AnalysisListItem[]> {
  const res = await fetch(`${API_BASE}/analyses`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Analyses fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchAnalysis(id: string): Promise<ComparisonResponse> {
  const res = await fetch(`${API_BASE}/analyses/${id}`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Analysis fetch failed: ${res.statusText}`)
  return res.json()
}

export async function fetchCustomModels(): Promise<CustomModelItem[]> {
  const res = await fetch(`${API_BASE}/custom-models`, { headers: requestHeaders() })
  if (!res.ok) throw new Error(`Custom models fetch failed: ${res.statusText}`)
  return res.json()
}

export async function createCustomModel(payload: {
  name: string
  model_id: string
  base_url: string
  api_key?: string
  description?: string
}): Promise<CustomModelItem> {
  const res = await fetch(`${API_BASE}/custom-models`, {
    method: 'POST',
    headers: requestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create custom model`)
  }
  return res.json()
}

export async function deleteCustomModel(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/custom-models/${id}`, {
    method: 'DELETE',
    headers: requestHeaders(),
  })
  if (!res.ok) throw new Error(`Delete custom model failed`)
}

export async function testCustomModel(payload: {
  base_url: string
  model_id: string
  api_key?: string
  prompt?: string
}): Promise<{ success: boolean; latency_ms: number; reply?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/custom-models/test`, {
    method: 'POST',
    headers: requestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return res.json()
}
