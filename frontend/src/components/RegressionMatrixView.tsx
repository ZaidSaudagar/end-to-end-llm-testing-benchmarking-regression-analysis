import React, { useMemo, useState } from 'react'
import { AlertCircle, GitCompare } from 'lucide-react'
import type { ComparisonResponse, MetricComparison, RunSummary } from '../api'
import { compareRuns } from '../api'

interface RegressionMatrixViewProps {
  runs: RunSummary[]
}

const METRIC_LABELS: Record<string, string> = {
  deterministic_pass_rate: 'Deterministic pass rate',
  semantic_similarity: 'Semantic similarity',
  judge_overall: 'Judge overall',
  judge_relevance: 'Judge relevance',
  judge_completeness: 'Judge completeness',
  judge_instruction_following: 'Judge instruction following',
  judge_factual_alignment: 'Judge factual alignment',
  judge_clarity: 'Judge clarity',
}

const isRate = (metric: string): boolean =>
  metric === 'deterministic_pass_rate' ||
  metric === 'semantic_similarity' ||
  metric.startsWith('judge_')

const formatMetric = (metric: string, value: number): string =>
  isRate(metric) ? `${(value * 100).toFixed(1)}%` : value.toFixed(4)

const formatDelta = (metric: string, value: number): string => {
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  const magnitude = Math.abs(value)
  return isRate(metric)
    ? `${sign}${(magnitude * 100).toFixed(1)}%`
    : `${sign}${magnitude.toFixed(4)}`
}

const formatPValue = (value: number | null): string =>
  value === null ? '—' : value < 0.0001 ? '<0.0001' : value.toFixed(4)

const passRateOf = (run: RunSummary): number =>
  run.total_cases > 0 ? (run.passed_cases / run.total_cases) * 100 : 0

const runLabel = (run: RunSummary): string =>
  `${run.model_id} · ${run.dataset_name} · ${run.id.slice(0, 8)}`

export const RegressionMatrixView: React.FC<RegressionMatrixViewProps> = ({ runs }) => {
  const [selectedBaselineId, setBaselineId] = useState<string>('')
  const [selectedCandidateId, setCandidateId] = useState<string>('')
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Runs arrive asynchronously, so the selection is derived during render: keep
  // the current choice while it is still present, otherwise fall back to the two
  // most recent runs.
  const baselineId =
    selectedBaselineId && runs.some((r) => r.id === selectedBaselineId)
      ? selectedBaselineId
      : runs[1]?.id ?? runs[0]?.id ?? ''
  const candidateId =
    selectedCandidateId && runs.some((r) => r.id === selectedCandidateId)
      ? selectedCandidateId
      : runs[0]?.id ?? ''

  const baselineRun = runs.find((r) => r.id === baselineId)
  const candidateRun = runs.find((r) => r.id === candidateId)

  const handleCompare = async () => {
    if (!baselineId || !candidateId) {
      setError('Select both a baseline run and a candidate run.')
      return
    }
    if (baselineId === candidateId) {
      setError('Select two different runs. A run cannot be compared with itself.')
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const result = await compareRuns({
        baseline_run_id: baselineId,
        candidate_run_id: candidateId,
      })
      setComparison(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The comparison request failed.')
    } finally {
      setIsLoading(false)
    }
  }

  const metrics: MetricComparison[] = useMemo(
    () => comparison?.result.metrics ?? [],
    [comparison],
  )

  const summary = useMemo(() => {
    const regressions = metrics.filter((m) => m.regression_detected)
    const improvements = metrics.filter(
      (m) =>
        !m.regression_detected &&
        m.mean_delta !== 0 &&
        (m.higher_is_better ? m.mean_delta > 0 : m.mean_delta < 0),
    )
    const passRate = metrics.find((m) => m.metric === 'deterministic_pass_rate')
    return {
      regressions: regressions.length,
      improvements: improvements.length,
      passRate,
      primaryP: passRate?.adjusted_p_value ?? passRate?.p_value ?? null,
    }
  }, [metrics])

  return (
    <div className="view">
      <div className="view-head">
        <h2>Regression matrix</h2>
        <p>
          Compare two runs of the same dataset. Pass rate is tested with an exact McNemar test;
          every other metric uses a paired Wilcoxon signed-rank test, with Holm-Bonferroni
          correction across the metrics compared.
        </p>
      </div>

      {error && (
        <div className="notice notice-error" role="alert">
          <AlertCircle size={17} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <section className="view-section">
        <div className="view-section-head">
          <h3>Select runs</h3>
          <p>Both runs must come from the same dataset version, or the comparison is rejected.</p>
        </div>

        <div className="glass-panel" style={{ padding: '20px 22px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: 18,
              alignItems: 'end',
            }}
          >
            <div>
              <label className="field-label" htmlFor="baseline-run">
                Baseline run
              </label>
              <select
                id="baseline-run"
                className="input-field"
                value={baselineId}
                onChange={(e) => setBaselineId(e.target.value)}
              >
                <option value="">Select a run…</option>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {runLabel(r)}
                  </option>
                ))}
              </select>
              {baselineRun && (
                <p className="field-hint">
                  {passRateOf(baselineRun).toFixed(1)}% pass rate · {baselineRun.provider}
                </p>
              )}
            </div>

            <div>
              <label className="field-label" htmlFor="candidate-run">
                Candidate run
              </label>
              <select
                id="candidate-run"
                className="input-field"
                value={candidateId}
                onChange={(e) => setCandidateId(e.target.value)}
              >
                <option value="">Select a run…</option>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {runLabel(r)}
                  </option>
                ))}
              </select>
              {candidateRun && (
                <p className="field-hint">
                  {passRateOf(candidateRun).toFixed(1)}% pass rate · {candidateRun.provider}
                </p>
              )}
            </div>

            <div>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCompare}
                disabled={isLoading || runs.length < 2}
                style={{ width: '100%' }}
              >
                <GitCompare size={16} aria-hidden="true" />
                {isLoading ? 'Comparing…' : 'Compare runs'}
              </button>
              {runs.length < 2 && (
                <p className="field-hint">At least two runs are needed to compare.</p>
              )}
            </div>
          </div>
        </div>
      </section>

      {comparison && (
        <>
          <section className="view-section">
            <div className="view-section-head">
              <h3>Result</h3>
              <p>
                {comparison.result.dataset_name} v{comparison.result.dataset_version} ·{' '}
                {comparison.result.confidence_interval_method} · α = {comparison.result.alpha} ·{' '}
                {comparison.result.multiple_testing_correction}
              </p>
            </div>

            <div className="stat-strip">
              <div>
                <div className="stat-label">Pass rate delta</div>
                <div
                  className={`stat-value${summary.passRate && summary.passRate.mean_delta < 0 ? ' is-regressed' : ''}`}
                >
                  {summary.passRate ? formatDelta('deterministic_pass_rate', summary.passRate.mean_delta) : '—'}
                </div>
              </div>
              <div>
                <div className="stat-label">Regressed metrics</div>
                <div className={`stat-value${summary.regressions > 0 ? ' is-regressed' : ''}`}>
                  {summary.regressions}
                </div>
              </div>
              <div>
                <div className="stat-label">Improved metrics</div>
                <div className="stat-value">{summary.improvements}</div>
              </div>
              <div>
                <div className="stat-label">Adjusted p (pass rate)</div>
                <div className="stat-value">{formatPValue(summary.primaryP)}</div>
              </div>
            </div>
          </section>

          <section className="view-section">
            <div className="view-section-head">
              <h3>Metric comparison</h3>
              <p>
                A metric is a regression when the adjusted p-value is below α and the mean delta
                falls past the configured minimum drop.
              </p>
            </div>

            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Metric</th>
                    <th scope="col">Test</th>
                    <th scope="col" className="num">Paired</th>
                    <th scope="col" className="num">Baseline</th>
                    <th scope="col" className="num">Candidate</th>
                    <th scope="col" className="num">Delta</th>
                    <th scope="col" className="num">95% CI</th>
                    <th scope="col" className="num">p</th>
                    <th scope="col" className="num">Adjusted p</th>
                    <th scope="col">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((m) => {
                    const improved =
                      !m.regression_detected &&
                      m.mean_delta !== 0 &&
                      (m.higher_is_better ? m.mean_delta > 0 : m.mean_delta < 0)
                    return (
                      <tr key={m.metric}>
                        <th scope="row" className="strong">
                          {METRIC_LABELS[m.metric] || m.metric}
                        </th>
                        <td className="muted">{m.statistical_test}</td>
                        <td className="num muted">{m.paired_cases}</td>
                        <td className="num">{formatMetric(m.metric, m.baseline_mean)}</td>
                        <td className="num">{formatMetric(m.metric, m.candidate_mean)}</td>
                        <td
                          className="num strong"
                          style={
                            m.regression_detected
                              ? { color: 'var(--accent-rose)' }
                              : improved
                                ? { color: 'var(--text-primary)' }
                                : { color: 'var(--text-muted)' }
                          }
                        >
                          {formatDelta(m.metric, m.mean_delta)}
                        </td>
                        <td className="num muted">
                          {m.confidence_interval_95
                            ? `[${formatMetric(m.metric, m.confidence_interval_95[0])}, ${formatMetric(m.metric, m.confidence_interval_95[1])}]`
                            : '—'}
                        </td>
                        <td className="num muted">{formatPValue(m.p_value)}</td>
                        <td className="num muted">{formatPValue(m.adjusted_p_value)}</td>
                        <td>
                          {m.regression_detected ? (
                            <span className="badge badge-rose">Regression</span>
                          ) : improved ? (
                            <span className="badge">Improved</span>
                          ) : (
                            <span className="muted" style={{ fontSize: '0.8125rem' }}>
                              Unchanged
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
