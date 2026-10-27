import React, { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { RunDetail } from '../api'
import { fetchRun } from '../api'

interface RunDetailModalProps {
  runId: string | null
  onClose: () => void
}

type CaseFilter = 'all' | 'passed' | 'failed'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export const RunDetailModal: React.FC<RunDetailModalProps> = ({ runId, onClose }) => {
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<CaseFilter>('all')
  const [loadedRunId, setLoadedRunId] = useState<string | null>(null)

  const panelRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    fetchRun(runId)
      .then((data) => {
        if (cancelled) return
        setDetail(data)
        setError(null)
        setLoadedRunId(runId)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load run details')
        setLoadedRunId(runId)
      })
    return () => {
      cancelled = true
    }
  }, [runId])

  // Move focus into the dialog, trap Tab inside it, close on Escape, and
  // restore focus to whatever opened it.
  useEffect(() => {
    if (!runId) return
    previouslyFocused.current = document.activeElement as HTMLElement | null
    closeButtonRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab') return

      const panel = panelRef.current
      if (!panel) return
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null,
      )
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = overflow
      previouslyFocused.current?.focus()
    }
  }, [runId, onClose])

  if (!runId) return null

  // Loading is derived: the request for this run has not settled yet.
  const isLoading = loadedRunId !== runId

  const cases = detail?.cases || []
  const failedCount = cases.filter((c) => c.deterministic_result?.passed !== true).length
  const filteredCases = cases.filter((c) => {
    const isPassed = c.deterministic_result?.passed === true
    if (filter === 'passed') return isPassed
    if (filter === 'failed') return !isPassed
    return true
  })

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-detail-title"
        ref={panelRef}
      >
        <div className="modal-head">
          <div>
            <h3 id="run-detail-title" style={{ fontSize: '1.05rem', fontWeight: 700 }}>
              Run inspection
            </h3>
            {detail && (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
                {detail.model_id} · {detail.dataset_name} v{detail.dataset_version} ·{' '}
                {detail.provider} · <code>{detail.id}</code>
              </p>
            )}
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            style={{ padding: 8 }}
            aria-label="Close run inspection"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        {isLoading ? (
          <div className="modal-body" style={{ color: 'var(--text-muted)' }}>
            Loading run…
          </div>
        ) : error ? (
          <div className="modal-body">
            <div className="notice notice-error" role="alert">
              {error}
            </div>
          </div>
        ) : detail ? (
          <div className="modal-body">
            <div className="stat-strip">
              <div>
                <div className="stat-label">Status</div>
                <div className="stat-value">{detail.status.replace(/_/g, ' ')}</div>
              </div>
              <div>
                <div className="stat-label">Passed</div>
                <div className="stat-value">
                  {detail.passed_cases} / {detail.total_cases}
                </div>
              </div>
              <div>
                <div className="stat-label">Errored</div>
                <div className={`stat-value${detail.errored_cases > 0 ? ' is-regressed' : ''}`}>
                  {detail.errored_cases}
                </div>
              </div>
              <div>
                <div className="stat-label">Total latency</div>
                <div className="stat-value">{(detail.total_latency_ms / 1000).toFixed(2)} s</div>
              </div>
              <div>
                <div className="stat-label">Tokens</div>
                <div className="stat-value">
                  {((detail.total_input_tokens || 0) + (detail.total_output_tokens || 0)).toLocaleString()}
                </div>
              </div>
            </div>

            {detail.error_message && (
              <div className="notice notice-error" role="alert">
                {detail.error_message}
              </div>
            )}

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <div className="segmented" role="group" aria-label="Filter cases by outcome">
                <button
                  type="button"
                  aria-pressed={filter === 'all'}
                  onClick={() => setFilter('all')}
                >
                  All ({cases.length})
                </button>
                <button
                  type="button"
                  aria-pressed={filter === 'passed'}
                  onClick={() => setFilter('passed')}
                >
                  Passed ({detail.passed_cases})
                </button>
                <button
                  type="button"
                  aria-pressed={filter === 'failed'}
                  onClick={() => setFilter('failed')}
                >
                  Failed ({failedCount})
                </button>
              </div>

              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Showing {filteredCases.length} of {cases.length} cases
              </span>
            </div>

            {filteredCases.length === 0 ? (
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                No cases match this filter.
              </p>
            ) : (
              <ul className="row-list">
                {filteredCases.map((c) => {
                  const passed = c.deterministic_result?.passed === true
                  return (
                    <li key={c.id} style={{ padding: '14px 0' }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 12,
                          flexWrap: 'wrap',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontWeight: 600,
                              fontSize: '0.85rem',
                            }}
                          >
                            {c.test_case_id}
                          </span>
                          <span className="badge">{c.evaluation_method}</span>
                          {passed ? (
                            <span className="badge">Passed</span>
                          ) : (
                            <span className="badge badge-rose">Failed</span>
                          )}
                        </div>

                        <div
                          style={{
                            fontSize: '0.78rem',
                            color: 'var(--text-muted)',
                            display: 'flex',
                            gap: 12,
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          {c.latency_ms != null && <span>{c.latency_ms.toFixed(0)} ms</span>}
                          {c.output_tokens != null && <span>{c.output_tokens} out tokens</span>}
                        </div>
                      </div>

                      {c.candidate_text && (
                        <div style={{ marginTop: 10 }}>
                          <div className="stat-label">Candidate output</div>
                          <pre
                            style={{
                              padding: '10px 14px',
                              borderRadius: 'var(--radius-sm)',
                              background: 'var(--bg-surface-elevated)',
                              fontSize: '0.825rem',
                              color: 'var(--text-primary)',
                              whiteSpace: 'pre-wrap',
                              maxHeight: 160,
                              overflowY: 'auto',
                            }}
                          >
                            {c.candidate_text}
                          </pre>
                        </div>
                      )}

                      {(c.semantic_result || c.judge_result || c.error_message) && (
                        <div
                          style={{
                            display: 'flex',
                            gap: 16,
                            flexWrap: 'wrap',
                            marginTop: 8,
                            fontSize: '0.8rem',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {c.semantic_result?.similarity != null && (
                            <span>
                              Semantic similarity{' '}
                              <b style={{ fontFamily: 'var(--font-mono)' }}>
                                {c.semantic_result.similarity.toFixed(3)}
                              </b>
                            </span>
                          )}
                          {c.judge_result?.aggregate?.overall_mean != null && (
                            <span>
                              Judge rubric mean{' '}
                              <b style={{ fontFamily: 'var(--font-mono)' }}>
                                {c.judge_result.aggregate.overall_mean.toFixed(2)} / 5
                              </b>
                            </span>
                          )}
                          {c.error_message && (
                            <span style={{ color: 'var(--accent-rose)' }}>{c.error_message}</span>
                          )}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
