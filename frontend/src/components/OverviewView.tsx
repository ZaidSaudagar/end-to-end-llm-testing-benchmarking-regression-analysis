import React, { useMemo } from 'react'
import { ArrowRight, Database } from 'lucide-react'
import type { OverviewResponse, RunSummary } from '../api'

interface OverviewViewProps {
  overview: OverviewResponse | null
  runs: RunSummary[]
  onSelectRun: (runId: string) => void
  onNavigateToBenchmark: () => void
}

interface ModelRow {
  key: string
  modelId: string
  provider: string
  latest: RunSummary
  passRate: number
  previousPassRate: number | null
  delta: number | null
  avgLatencyMs: number
  regressed: boolean
}

const passRateOf = (run: RunSummary): number =>
  run.total_cases > 0 ? (run.passed_cases / run.total_cases) * 100 : 0

const avgLatencyOf = (run: RunSummary): number =>
  run.completed_cases > 0 ? run.total_latency_ms / run.completed_cases : 0

const formatLatency = (ms: number): string =>
  ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(0)} ms`

const formatDelta = (delta: number): string =>
  `${delta > 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)}`

const formatWhen = (iso: string): string => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  overview,
  runs,
  onSelectRun,
  onNavigateToBenchmark,
}) => {
  const metrics = overview?.metrics ?? {
    total_runs: 0,
    models_evaluated: 0,
    test_cases_executed: 0,
  }

  const modelRows = useMemo<ModelRow[]>(() => {
    const byModel = new Map<string, RunSummary[]>()
    for (const run of runs) {
      const key = `${run.provider}::${run.model_id}`
      const bucket = byModel.get(key)
      if (bucket) bucket.push(run)
      else byModel.set(key, [run])
    }

    const rows: ModelRow[] = []
    for (const [key, bucket] of byModel) {
      const ordered = [...bucket].sort(
        (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
      )
      const latest = ordered[0]
      const previous = ordered[1] ?? null
      const passRate = passRateOf(latest)
      const previousPassRate = previous ? passRateOf(previous) : null
      const delta = previousPassRate === null ? null : passRate - previousPassRate

      rows.push({
        key,
        modelId: latest.model_id,
        provider: latest.provider,
        latest,
        passRate,
        previousPassRate,
        delta,
        avgLatencyMs: avgLatencyOf(latest),
        regressed: delta !== null && delta < 0,
      })
    }

    return rows.sort((a, b) => {
      if (a.regressed !== b.regressed) return a.regressed ? -1 : 1
      return a.passRate - b.passRate
    })
  }, [runs])

  const regressions = modelRows.filter((row) => row.regressed)
  const comparable = modelRows.filter((row) => row.delta !== null)
  const worst = regressions.length > 0 ? regressions[0] : null

  const ledger = useMemo(
    () =>
      [...runs]
        .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
        .slice(0, 8),
    [runs],
  )

  const verdict = (() => {
    if (runs.length === 0) {
      return {
        headline: 'No runs recorded yet',
        detail:
          'Run a benchmark to establish a baseline. Regressions appear here once a model has two runs to compare.',
      }
    }
    if (comparable.length === 0) {
      return {
        headline: 'No model has two runs yet',
        detail:
          'A regression needs a previous run to compare against. Run the same model again to start tracking drift.',
      }
    }
    if (regressions.length === 0) {
      return {
        headline: `No regressions across ${comparable.length} ${comparable.length === 1 ? 'model' : 'models'}`,
        detail:
          'Pass rate held or improved against the previous run for every model with a comparable baseline.',
      }
    }
    return {
      headline: `${regressions.length} ${regressions.length === 1 ? 'regression' : 'regressions'} across ${comparable.length} ${comparable.length === 1 ? 'model' : 'models'}`,
      detail: worst
        ? `${worst.modelId} dropped ${formatDelta(worst.delta as number)} points of pass rate, from ${(worst.previousPassRate as number).toFixed(1)}% to ${worst.passRate.toFixed(1)}%.`
        : '',
    }
  })()

  return (
    <div className="overview">
      <section className="overview-verdict" aria-labelledby="overview-verdict-heading">
        <h1
          id="overview-verdict-heading"
          className={`overview-verdict-headline${regressions.length > 0 ? ' is-regressed' : ''}`}
        >
          {verdict.headline}
        </h1>
        <p className="overview-verdict-detail">{verdict.detail}</p>
        <button type="button" className="overview-verdict-action" onClick={onNavigateToBenchmark}>
          Run a benchmark
          <ArrowRight size={15} aria-hidden="true" />
        </button>
      </section>

      <section className="overview-matrix" aria-labelledby="overview-matrix-heading">
        <div className="overview-section-head">
          <h2 id="overview-matrix-heading">Pass rate by model</h2>
          <p>
            Latest run against the previous run of the same model. A negative delta is a regression.
          </p>
        </div>

        {modelRows.length === 0 ? (
          <div className="overview-empty">
            <Database size={28} aria-hidden="true" />
            <p>No model has been evaluated yet.</p>
            <p className="overview-empty-hint">
              Results appear here as soon as the first benchmark run completes.
            </p>
          </div>
        ) : (
          <div className="overview-matrix-scroll">
            <table className="overview-matrix-table">
              <caption className="overview-visually-hidden">
                Pass rate for each evaluated model, compared with its previous run
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="col-model">
                    Model
                  </th>
                  <th scope="col" className="col-num">
                    Pass rate
                  </th>
                  <th scope="col" className="col-num">
                    Previous
                  </th>
                  <th scope="col" className="col-num">
                    Delta
                  </th>
                  <th scope="col" className="col-num">
                    Avg latency
                  </th>
                  <th scope="col" className="col-num">
                    Cases
                  </th>
                  <th scope="col" className="col-when">
                    Last run
                  </th>
                </tr>
              </thead>
              <tbody>
                {modelRows.map((row) => (
                  <tr
                    key={row.key}
                    className={row.regressed ? 'is-regressed' : undefined}
                    onClick={() => onSelectRun(row.latest.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        onSelectRun(row.latest.id)
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Inspect latest run for ${row.modelId}`}
                  >
                    <th scope="row" className="col-model">
                      <span className="overview-model-id">{row.modelId}</span>
                      <span className="overview-model-provider">{row.provider}</span>
                    </th>
                    <td className="col-num overview-num">{row.passRate.toFixed(1)}%</td>
                    <td className="col-num overview-num overview-num-quiet">
                      {row.previousPassRate === null ? '—' : `${row.previousPassRate.toFixed(1)}%`}
                    </td>
                    <td className="col-num overview-num">
                      {row.delta === null ? (
                        <span className="overview-num-quiet">no baseline</span>
                      ) : (
                        <span className={row.regressed ? 'overview-delta-bad' : 'overview-delta-ok'}>
                          {formatDelta(row.delta)}
                        </span>
                      )}
                    </td>
                    <td className="col-num overview-num overview-num-quiet">
                      {formatLatency(row.avgLatencyMs)}
                    </td>
                    <td className="col-num overview-num overview-num-quiet">
                      {row.latest.passed_cases}/{row.latest.total_cases}
                    </td>
                    <td className="col-when overview-num-quiet">{formatWhen(row.latest.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="overview-ledger" aria-labelledby="overview-ledger-heading">
        <div className="overview-section-head">
          <h2 id="overview-ledger-heading">Recent runs</h2>
          <p>
            {metrics.total_runs} {metrics.total_runs === 1 ? 'run' : 'runs'} recorded across{' '}
            {metrics.models_evaluated} {metrics.models_evaluated === 1 ? 'model' : 'models'} and{' '}
            {metrics.test_cases_executed.toLocaleString()} test cases.
          </p>
        </div>

        {ledger.length === 0 ? (
          <div className="overview-empty">
            <p>Nothing has run yet.</p>
            <p className="overview-empty-hint">
              Start in the Benchmark Studio to produce the first result.
            </p>
          </div>
        ) : (
          <ul className="overview-ledger-list">
            {ledger.map((run) => {
              const rate = passRateOf(run)
              return (
                <li key={run.id}>
                  <button
                    type="button"
                    className="overview-ledger-row"
                    onClick={() => onSelectRun(run.id)}
                  >
                    <span className="overview-ledger-model">
                      <span className="overview-model-id">{run.model_id}</span>
                      <span className="overview-model-provider">{run.provider}</span>
                    </span>
                    <span className="overview-ledger-dataset">
                      {run.dataset_name}
                      <span className="overview-model-provider">v{run.dataset_version}</span>
                    </span>
                    <span className="overview-ledger-status" data-status={run.status}>
                      {run.status.replace(/_/g, ' ')}
                    </span>
                    <span className="overview-ledger-rate overview-num">
                      {rate.toFixed(1)}%
                      <span className="overview-num-quiet">
                        {run.passed_cases}/{run.total_cases}
                      </span>
                    </span>
                    <span className="overview-ledger-when overview-num-quiet">
                      {formatWhen(run.started_at)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
