import React, { useEffect, useMemo, useState } from 'react'
import { AlertCircle, Search } from 'lucide-react'
import type { DatasetCaseDetail, DatasetCasesResponse, DatasetItem } from '../api'
import { fetchDatasetCases } from '../api'

interface DatasetExplorerViewProps {
  datasets: DatasetItem[]
}

const PAGE_SIZE = 25

export const DatasetExplorerView: React.FC<DatasetExplorerViewProps> = ({ datasets }) => {
  const [selectedFile, setSelectedFile] = useState<string>('')
  const [datasetData, setDatasetData] = useState<DatasetCasesResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadedFile, setLoadedFile] = useState<string | null>(null)

  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('all')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [page, setPage] = useState<number>(1)

  // Derive the active file during render so no effect is needed to sync it.
  const activeFile = selectedFile || datasets[0]?.dataset_file || ''

  useEffect(() => {
    if (!activeFile) return
    let cancelled = false
    fetchDatasetCases(activeFile)
      .then((data) => {
        if (cancelled) return
        setDatasetData(data)
        setError(null)
        setLoadedFile(activeFile)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load dataset cases')
        setLoadedFile(activeFile)
      })
    return () => {
      cancelled = true
    }
  }, [activeFile])

  // Loading is derived: the request for the active file has not settled yet.
  const isLoading = Boolean(activeFile) && loadedFile !== activeFile

  const categories = useMemo(
    () => Array.from(new Set(datasetData?.cases.map((c) => c.task_category) || [])).sort(),
    [datasetData],
  )

  const filteredCases = useMemo(
    () =>
      (datasetData?.cases || []).filter((c) => {
        if (selectedDifficulty !== 'all' && (c.difficulty || '').toLowerCase() !== selectedDifficulty) {
          return false
        }
        if (selectedCategory !== 'all' && c.task_category !== selectedCategory) return false
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase()
          const matchId = c.test_case_id.toLowerCase().includes(q)
          const matchPrompt = c.input_prompt.toLowerCase().includes(q)
          const matchAnswer = (c.reference_answer || '').toLowerCase().includes(q)
          const matchTags = (c.tags || []).some((t) => t.toLowerCase().includes(q))
          if (!matchId && !matchPrompt && !matchAnswer && !matchTags) return false
        }
        return true
      }),
    [datasetData, selectedDifficulty, selectedCategory, searchQuery],
  )

  // Reset to the first page whenever the result set changes shape. Tracking the
  // filter signature lets the reset happen during render instead of in an effect.
  const filterSignature = `${activeFile}|${selectedDifficulty}|${selectedCategory}|${searchQuery}`
  const [lastSignature, setLastSignature] = useState(filterSignature)
  if (lastSignature !== filterSignature) {
    setLastSignature(filterSignature)
    setPage(1)
  }

  const pageCount = Math.max(1, Math.ceil(filteredCases.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageCases = filteredCases.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  return (
    <div className="view">
      <div className="view-head">
        <h2>Dataset explorer</h2>
        <p>
          Inspect the test suites in <code>datasets/</code>: prompts, reference answers, expected
          schemas, and the evaluation method each case is scored with.
        </p>
      </div>

      <div className="segmented" role="group" aria-label="Dataset file">
        {datasets.map((d) => (
          <button
            key={d.dataset_file}
            type="button"
            aria-pressed={activeFile === d.dataset_file}
            onClick={() => setSelectedFile(d.dataset_file)}
          >
            {d.dataset_file} ({d.case_count})
          </button>
        ))}
      </div>

      {datasetData && (
        <div className="stat-strip">
          <div>
            <div className="stat-label">Dataset</div>
            <div className="stat-value" style={{ fontSize: '0.9rem' }}>
              {datasetData.dataset_name}
            </div>
          </div>
          <div>
            <div className="stat-label">Version</div>
            <div className="stat-value">{datasetData.dataset_version}</div>
          </div>
          <div>
            <div className="stat-label">Cases</div>
            <div className="stat-value">{datasetData.total_cases}</div>
          </div>
          <div style={{ gridColumn: 'span 2' }}>
            <div className="stat-label">SHA-256</div>
            <div className="stat-value" style={{ fontSize: '0.75rem', wordBreak: 'break-all' }}>
              {datasetData.sha256}
            </div>
          </div>
        </div>
      )}

      <section className="view-section">
        <div
          className="glass-panel"
          style={{
            padding: '16px 18px',
            display: 'flex',
            alignItems: 'flex-end',
            flexWrap: 'wrap',
            gap: 14,
          }}
        >
          <div style={{ position: 'relative', flex: '1 1 240px' }}>
            <label className="field-label" htmlFor="dataset-search">
              Search
            </label>
            <Search
              size={15}
              aria-hidden="true"
              style={{ position: 'absolute', left: 11, top: 34, color: 'var(--text-muted)' }}
            />
            <input
              id="dataset-search"
              type="search"
              className="input-field"
              placeholder="Prompt, answer, tag, or case ID"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: 34 }}
            />
          </div>

          <div>
            <label className="field-label" htmlFor="dataset-difficulty">
              Difficulty
            </label>
            <select
              id="dataset-difficulty"
              className="input-field"
              value={selectedDifficulty}
              onChange={(e) => setSelectedDifficulty(e.target.value)}
              style={{ width: 140 }}
            >
              <option value="all">All levels</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>

          <div>
            <label className="field-label" htmlFor="dataset-category">
              Category
            </label>
            <select
              id="dataset-category"
              className="input-field"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{ width: 200 }}
            >
              <option value="all">All categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div style={{ marginLeft: 'auto', fontSize: '0.825rem', color: 'var(--text-muted)' }}>
            {filteredCases.length} of {datasetData?.total_cases || 0} cases
          </div>
        </div>
      </section>

      {isLoading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Loading test cases…</p>
      ) : error ? (
        <div className="notice notice-error" role="alert">
          <AlertCircle size={17} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : filteredCases.length === 0 ? (
        <div className="overview-empty">
          <p>No cases match these filters.</p>
          <p className="overview-empty-hint">
            Clear the search box or set difficulty and category back to all.
          </p>
        </div>
      ) : (
        <>
          <ul className="row-list">
            {pageCases.map((caseItem: DatasetCaseDetail) => (
              <li key={caseItem.test_case_id} style={{ padding: '16px 0' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    flexWrap: 'wrap',
                    marginBottom: 10,
                  }}
                >
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                    }}
                  >
                    {caseItem.test_case_id}
                  </span>
                  <span className="badge">{caseItem.task_category}</span>
                  <span className="badge">{caseItem.difficulty || 'medium'}</span>
                  <span className="badge">{caseItem.evaluation_method}</span>
                  {caseItem.tags?.map((t) => (
                    <span key={t} className="row-meta">
                      #{t}
                    </span>
                  ))}
                </div>

                <div className="stat-label">Input prompt</div>
                <div
                  style={{
                    padding: '10px 13px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-surface-elevated)',
                    fontSize: '0.875rem',
                    color: 'var(--text-primary)',
                  }}
                >
                  {caseItem.input_prompt}
                </div>

                {caseItem.reference_context && (
                  <>
                    <div className="stat-label" style={{ marginTop: 10 }}>
                      Grounding context
                    </div>
                    <div
                      style={{
                        padding: '10px 13px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '0.825rem',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {caseItem.reference_context}
                    </div>
                  </>
                )}

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: caseItem.expected_output_schema ? '1fr 1fr' : '1fr',
                    gap: 12,
                    marginTop: 10,
                  }}
                >
                  {caseItem.reference_answer && (
                    <div>
                      <div className="stat-label">Reference answer</div>
                      <div
                        style={{
                          padding: '10px 13px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--bg-surface-elevated)',
                          fontSize: '0.825rem',
                          color: 'var(--text-primary)',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {caseItem.reference_answer}
                      </div>
                    </div>
                  )}

                  {caseItem.expected_output_schema && (
                    <div>
                      <div className="stat-label">Expected JSON schema</div>
                      <pre
                        style={{
                          padding: '10px 13px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--bg-surface-elevated)',
                          fontSize: '0.75rem',
                          color: 'var(--text-secondary)',
                          overflowX: 'auto',
                          maxHeight: 180,
                        }}
                      >
                        {JSON.stringify(caseItem.expected_output_schema, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>

          {pageCount > 1 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
                Page {currentPage} of {pageCount}
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                  disabled={currentPage === pageCount}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
