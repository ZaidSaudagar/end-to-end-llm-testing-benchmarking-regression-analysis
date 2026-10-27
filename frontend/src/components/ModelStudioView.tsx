import React, { useState } from 'react'
import { AlertCircle, CheckCircle2, Cpu, Plus, Trash2, Wifi } from 'lucide-react'
import type { CustomModelItem, ProviderConfigResponse } from '../api'
import { createCustomModel, deleteCustomModel, testCustomModel } from '../api'

interface ModelStudioViewProps {
  providers: ProviderConfigResponse | null
  customModels: CustomModelItem[]
  onRefresh: () => void
}

type PresetKey = 'ollama' | 'openrouter' | 'vllm' | 'groq'

interface Preset {
  key: PresetKey
  label: string
  name: string
  modelId: string
  baseUrl: string
  description: string
}

const PRESETS: Preset[] = [
  {
    key: 'ollama',
    label: 'Ollama (local)',
    name: 'Ollama Llama 3.2',
    modelId: 'llama3.2',
    baseUrl: 'http://localhost:11434/v1',
    description: 'Local model served by Ollama',
  },
  {
    key: 'openrouter',
    label: 'OpenRouter',
    name: 'OpenRouter DeepSeek R1',
    modelId: 'deepseek/deepseek-r1:free',
    baseUrl: 'https://openrouter.ai/api/v1',
    description: 'OpenRouter free-tier reasoning model',
  },
  {
    key: 'vllm',
    label: 'vLLM (local)',
    name: 'Local vLLM server',
    modelId: 'meta-llama/Llama-3-8B-Instruct',
    baseUrl: 'http://localhost:8000/v1',
    description: 'Self-hosted vLLM endpoint',
  },
  {
    key: 'groq',
    label: 'Groq',
    name: 'Groq DeepSeek R1',
    modelId: 'deepseek-r1-distill-llama-70b',
    baseUrl: 'https://api.groq.com/openai/v1',
    description: 'Groq-hosted reasoning model',
  },
]

interface TestResult {
  success: boolean
  latency_ms: number
  reply?: string
  error?: string
}

export const ModelStudioView: React.FC<ModelStudioViewProps> = ({
  providers,
  customModels,
  onRefresh,
}) => {
  const [name, setName] = useState<string>('')
  const [modelId, setModelId] = useState<string>('')
  const [baseUrl, setBaseUrl] = useState<string>('http://localhost:11434/v1')
  const [apiKey, setApiKey] = useState<string>('')
  const [description, setDescription] = useState<string>('')

  const [isTesting, setIsTesting] = useState<boolean>(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [isSaving, setIsSaving] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const applyPreset = (preset: Preset) => {
    setName(preset.name)
    setModelId(preset.modelId)
    setBaseUrl(preset.baseUrl)
    setApiKey('')
    setDescription(preset.description)
    setTestResult(null)
  }

  const handleTestConnection = async () => {
    if (!baseUrl || !modelId) {
      setError('Enter a base URL and a model ID before testing the connection.')
      return
    }

    setIsTesting(true)
    setError(null)
    setTestResult(null)

    try {
      const result = await testCustomModel({
        base_url: baseUrl,
        model_id: modelId,
        api_key: apiKey || undefined,
      })
      setTestResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The connection test failed.')
    } finally {
      setIsTesting(false)
    }
  }

  const handleSaveModel = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !modelId || !baseUrl) {
      setError('Name, model ID, and base URL are required.')
      return
    }

    setIsSaving(true)
    setError(null)
    setSuccessMsg(null)

    try {
      await createCustomModel({
        name,
        model_id: modelId,
        base_url: baseUrl,
        api_key: apiKey || undefined,
        description: description || undefined,
      })
      setSuccessMsg(`Registered "${name}". It is now selectable in Benchmark Studio.`)
      setName('')
      setModelId('')
      setApiKey('')
      setDescription('')
      setTestResult(null)
      onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The model could not be registered.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this custom model? Runs already recorded with it are kept.')) return
    try {
      await deleteCustomModel(id)
      onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The model could not be deleted.')
    }
  }

  const builtInProviders = Object.entries(providers?.providers || {})

  return (
    <div className="view" style={{ maxWidth: 1180 }}>
      <div className="view-head">
        <h2>Model &amp; provider studio</h2>
        <p>
          Register any OpenAI-compatible endpoint — local Ollama, LM Studio, vLLM, or a hosted
          gateway — and test it before you benchmark against it.
        </p>
      </div>

      {error && (
        <div className="notice notice-error" role="alert">
          <AlertCircle size={17} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="notice" role="status">
          <CheckCircle2 size={17} aria-hidden="true" />
          <span>{successMsg}</span>
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: 20,
          alignItems: 'start',
        }}
      >
        <div className="glass-panel" style={{ padding: '24px 26px' }}>
          <div className="view-section-head">
            <h3>Register a model</h3>
            <span className="badge">OpenAI-compatible</span>
          </div>

          <div style={{ marginBottom: 20 }}>
            <span className="field-label">Start from a preset</span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '5px 11px', fontSize: '0.78rem' }}
                  onClick={() => applyPreset(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSaveModel} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label className="field-label" htmlFor="model-name">
                Display name
              </label>
              <input
                id="model-name"
                type="text"
                className="input-field"
                placeholder="Ollama Llama 3.2 3B"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="field-label" htmlFor="model-id">
                Model ID
              </label>
              <input
                id="model-id"
                type="text"
                className="input-field"
                placeholder="llama3.2"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                required
              />
              <p className="field-hint">The identifier the endpoint expects in the request body.</p>
            </div>

            <div>
              <label className="field-label" htmlFor="model-base-url">
                Base URL
              </label>
              <input
                id="model-base-url"
                type="text"
                className="input-field"
                placeholder="http://localhost:11434/v1"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="field-label" htmlFor="model-api-key">
                API key
              </label>
              <input
                id="model-api-key"
                type="password"
                className="input-field"
                placeholder="Leave blank for local endpoints"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="field-hint">Stored with the model record and never returned by the API.</p>
            </div>

            <div>
              <label className="field-label" htmlFor="model-description">
                Notes
              </label>
              <input
                id="model-description"
                type="text"
                className="input-field"
                placeholder="Quantized 4-bit local run"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            {testResult && (
              <div className="notice" role="status">
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {testResult.success ? 'Connection succeeded' : 'Connection failed'}
                  </div>
                  {testResult.success && (
                    <div style={{ fontSize: '0.8rem', marginTop: 2 }}>
                      Responded in {testResult.latency_ms.toFixed(0)} ms
                    </div>
                  )}
                  {testResult.reply && (
                    <div style={{ fontSize: '0.8rem', marginTop: 4, color: 'var(--text-secondary)' }}>
                      Reply: “{testResult.reply}”
                    </div>
                  )}
                  {testResult.error && (
                    <div style={{ fontSize: '0.8rem', marginTop: 4 }}>{testResult.error}</div>
                  )}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleTestConnection}
                disabled={isTesting}
                style={{ flex: 1 }}
              >
                <Wifi size={15} aria-hidden="true" />
                {isTesting ? 'Testing…' : 'Test connection'}
              </button>

              <button type="submit" className="btn btn-primary" disabled={isSaving} style={{ flex: 1 }}>
                <Plus size={15} aria-hidden="true" />
                {isSaving ? 'Registering…' : 'Register model'}
              </button>
            </div>
          </form>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="glass-panel" style={{ padding: '24px 26px' }}>
            <div className="view-section-head">
              <h3>Built-in providers</h3>
            </div>
            {builtInProviders.length === 0 ? (
              <p className="field-hint">No built-in providers are reported by the backend.</p>
            ) : (
              <div className="row-list">
                {builtInProviders.map(([id, info]) => (
                  <div key={id} className="row-button" style={{ cursor: 'default' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span className="row-title">{info.name || id}</span>
                      <span className="row-meta">
                        {info.available_models.length} models · default {info.default_model}
                      </span>
                    </div>
                    <span className="badge">{info.configured ? 'Configured' : 'No API key'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="glass-panel" style={{ padding: '24px 26px' }}>
            <div className="view-section-head">
              <h3>Custom models</h3>
              <span className="badge">{customModels.length} registered</span>
            </div>

            {customModels.length === 0 ? (
              <div style={{ padding: '28px 8px', textAlign: 'center' }}>
                <Cpu size={26} style={{ opacity: 0.35, marginBottom: 8 }} aria-hidden="true" />
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  No custom models yet. Pick a preset or fill in the form to add one.
                </p>
              </div>
            ) : (
              <div className="row-list">
                {customModels.map((cm) => (
                  <div key={cm.id} className="row-button" style={{ cursor: 'default' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span className="row-title">{cm.name}</span>
                      <span className="row-meta">
                        {cm.model_id} · {cm.base_url}
                      </span>
                      {cm.description && (
                        <span className="row-meta">{cm.description}</span>
                      )}
                    </div>
                    <button
                      type="button"
                      className="btn btn-danger"
                      style={{ padding: '6px 9px' }}
                      onClick={() => handleDelete(cm.id)}
                      aria-label={`Delete ${cm.name}`}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
