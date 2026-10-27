import React, { useMemo, useState } from 'react'
import { AlertCircle, Eye, Play } from 'lucide-react'
import type { DatasetItem, ProviderConfigResponse, RunSummary } from '../api'
import { createRun } from '../api'

interface BenchmarkStudioViewProps {
  datasets: DatasetItem[]
  providers: ProviderConfigResponse | null
  onRunCreated: (run: RunSummary) => void
  onInspectRun: (runId: string) => void
}

interface ProviderOption {
  id: string
  name: string
  models: string[]
}

export const BenchmarkStudioView: React.FC<BenchmarkStudioViewProps> = ({
  datasets,
  providers,
  onRunCreated,
  onInspectRun,
}) => {
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [includeJudge, setIncludeJudge] = useState<boolean>(false)

  const [isRunning, setIsRunning] = useState<boolean>(false)
  const [lastRun, setLastRun] = useState<RunSummary | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Provider and model lists come from the backend so the form cannot drift
  // from what the API actually accepts.
  const providerOptions = useMemo<ProviderOption[]>(() => {
    const options: ProviderOption[] = []
    for (const [id, config] of Object.entries(providers?.providers || {})) {
      if (!config.configured) continue
      options.push({
        id,
        name: config.name || id,
        models: config.available_models || [],
      })
    }
    for (const custom of providers?.custom_models || []) {
      options.push({
        id: custom.id,
        name: custom.name,
        models: [custom.model_id],
      })
    }
    return options
  }, [providers])

  // Selections are derived during render so the form stays valid as the async
  // lists arrive, without an effect that would trigger a second render pass.
  const datasetFile =
    selectedDataset && datasets.some((d) => d.dataset_file === selectedDataset)
      ? selectedDataset
      : datasets[0]?.dataset_file || ''

  const providerId =
    selectedProvider && providerOptions.some((p) => p.id === selectedProvider)
      ? selectedProvider
      : providerOptions[0]?.id || ''

  const activeProvider = providerOptions.find((p) => p.id === providerId)

  const modelId =
    selectedModel && activeProvider?.models.includes(selectedModel)
      ? selectedModel
      : activeProvider?.models[0] || ''

  const handleLaunch = async () => {
    if (!datasetFile) {
      setErrorMessage('Select a dataset before running a benchmark.')
      return
    }
    if (!providerId || !modelId) {
      setErrorMessage('Select a provider and a model before running a benchmark.')
      return
    }

    setIsRunning(true)
    setErrorMessage(null)
    setLastRun(null)

    try {
      const summary = await createRun({
        dataset_file: datasetFile,
        provider: providerId,
        model_id: modelId,
        include_judge: includeJudge,
      })
      setLastRun(summary)
      onRunCreated(summary)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'The benchmark run failed to start.')
    } finally {
      setIsRunning(false)
    }
  }

  const currentDatasetMeta = datasets.find((d) => d.dataset_file === datasetFile)
  const noProviders = providerOptions.length === 0

  return (
    <div className="view" style={{ maxWidth: 900 }}>
      <div className="view-head">
        <h2>Benchmark studio</h2>
        <p>
          Pick a dataset, a provider, and a model, then run the suite. Each case is scored with the
          evaluation method declared in the dataset.
        </p>
      </div>

      {errorMessage && (
        <div className="notice notice-error" role="alert">
          <AlertCircle size={17} aria-hidden="true" />
          <span>{errorMessage}</span>
        </div>
      )}

      {lastRun && (
        <div className="notice" role="status">
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Run finished</div>
            <div style={{ fontSize: '0.825rem', marginTop: 2 }}>
              {lastRun.model_id} · {lastRun.passed_cases}/{lastRun.total_cases} passed ·{' '}
              {(lastRun.total_latency_ms / 1000).toFixed(2)} s total
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '7px 14px', fontSize: '0.825rem' }}
            onClick={() => onInspectRun(lastRun.id)}
          >
            <Eye size={15} aria-hidden="true" />
            Inspect cases
          </button>
        </div>
      )}

      {noProviders && (
        <div className="notice" role="status">
          <AlertCircle size={17} aria-hidden="true" />
          <span>
            No provider is configured. Add an API key to <code>.env</code> or register a custom
            model in the Model &amp; Provider Studio.
          </span>
        </div>
      )}

      <div className="glass-panel" style={{ padding: '24px 26px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <label className="field-label" htmlFor="benchmark-dataset">
            Dataset
          </label>
          <select
            id="benchmark-dataset"
            className="input-field"
            value={datasetFile}
            onChange={(e) => setSelectedDataset(e.target.value)}
            disabled={isRunning}
          >
            {datasets.length === 0 && <option value="">No datasets available</option>}
            {datasets.map((d) => (
              <option key={d.dataset_file} value={d.dataset_file}>
                {d.dataset_name} ({d.dataset_file}) — {d.case_count} cases
              </option>
            ))}
          </select>
          {currentDatasetMeta && (
            <p className="field-hint">
              v{currentDatasetMeta.dataset_version} · sha256{' '}
              <code>{currentDatasetMeta.sha256.slice(0, 16)}…</code>
            </p>
          )}
        </div>

        <div>
          <span className="field-label">Provider</span>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
              gap: 10,
            }}
          >
            {providerOptions.map((p) => {
              const selected = providerId === p.id
              return (
                <button
                  key={p.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setSelectedProvider(p.id)}
                  disabled={isRunning}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: `1px solid ${selected ? 'var(--text-primary)' : 'var(--border-subtle)'}`,
                    background: selected ? 'var(--bg-surface-elevated)' : 'transparent',
                    cursor: isRunning ? 'not-allowed' : 'pointer',
                    textAlign: 'left',
                    font: 'inherit',
                    color: 'inherit',
                  }}
                >
                  <span className="row-title">{p.name}</span>
                  <span className="row-meta">
                    {p.models.length} {p.models.length === 1 ? 'model' : 'models'}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <div>
          <label className="field-label" htmlFor="benchmark-model">
            Model
          </label>
          <select
            id="benchmark-model"
            className="input-field"
            value={modelId}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={isRunning || !activeProvider}
          >
            {(activeProvider?.models || []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div
          style={{
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>Run the LLM judge</div>
            <p className="field-hint" style={{ marginTop: 2 }}>
              Adds a rubric-based scorecard per case. Slower and costs extra tokens.
            </p>
          </div>
          <label
            style={{
              position: 'relative',
              display: 'inline-block',
              width: 42,
              height: 24,
              flexShrink: 0,
              cursor: isRunning ? 'not-allowed' : 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={includeJudge}
              onChange={(e) => setIncludeJudge(e.target.checked)}
              disabled={isRunning}
              style={{ opacity: 0, width: 0, height: 0 }}
            />
            <span
              style={{
                position: 'absolute',
                inset: 0,
                backgroundColor: includeJudge ? 'var(--text-primary)' : 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-strong)',
                borderRadius: 24,
                transition: 'background-color 0.15s ease',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  height: 16,
                  width: 16,
                  left: includeJudge ? 22 : 3,
                  top: 3,
                  backgroundColor: includeJudge ? '#0b0c0e' : 'var(--text-muted)',
                  borderRadius: '50%',
                  transition: 'left 0.15s ease',
                }}
              />
            </span>
          </label>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleLaunch}
          disabled={isRunning || noProviders || !datasetFile}
          style={{ width: '100%', padding: '13px 20px' }}
        >
          <Play size={16} aria-hidden="true" />
          {isRunning ? 'Running benchmark…' : 'Run benchmark'}
        </button>
      </div>
    </div>
  )
}
