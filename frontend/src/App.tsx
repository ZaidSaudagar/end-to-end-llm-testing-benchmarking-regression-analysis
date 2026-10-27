import React, { useCallback, useEffect, useState } from 'react'
import type {
  CustomModelItem,
  DatasetItem,
  OverviewResponse,
  ProviderConfigResponse,
  RunSummary,
} from './api'
import {
  fetchCustomModels,
  fetchDatasets,
  fetchOverview,
  fetchProviders,
  fetchRuns,
} from './api'
import { Header } from './components/Header'
import { OverviewView } from './components/OverviewView'
import { BenchmarkStudioView } from './components/BenchmarkStudioView'
import { DatasetExplorerView } from './components/DatasetExplorerView'
import { RegressionMatrixView } from './components/RegressionMatrixView'
import { ModelStudioView } from './components/ModelStudioView'
import { RunDetailModal } from './components/RunDetailModal'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview')
  const [isOnline, setIsOnline] = useState<boolean>(true)

  const [overview, setOverview] = useState<OverviewResponse | null>(null)
  const [providers, setProviders] = useState<ProviderConfigResponse | null>(null)
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [customModels, setCustomModels] = useState<CustomModelItem[]>([])

  const [inspectRunId, setInspectRunId] = useState<string | null>(null)

  const refreshAllData = useCallback(async () => {
    const [ovData, provData, dsData, runsData, cmData] = await Promise.all([
      fetchOverview().catch(() => null),
      fetchProviders().catch(() => null),
      fetchDatasets().catch(() => []),
      fetchRuns().catch(() => []),
      fetchCustomModels().catch(() => []),
    ])

    if (ovData) setOverview(ovData)
    if (provData) setProviders(provData)
    if (dsData) setDatasets(dsData)
    if (runsData) setRuns(runsData)
    if (cmData) setCustomModels(cmData)
    setIsOnline(Boolean(ovData || provData || runsData))
  }, [])

  useEffect(() => {
    // Polling the backend is exactly the external-system sync effects are for.
    // oxlint-disable-next-line react/set-state-in-effect
    void refreshAllData()
    const interval = setInterval(() => void refreshAllData(), 10000)
    return () => clearInterval(interval)
  }, [refreshAllData])

  const handleRunCreated = (newRun: RunSummary) => {
    setRuns((prev) => [newRun, ...prev])
    fetchOverview().then((ov) => setOverview(ov)).catch(() => {})
  }

  return (
    <div className="app-shell">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        providers={providers}
        isOnline={isOnline}
      />

      <main className="app-main">
        {activeTab === 'overview' && (
          <OverviewView
            overview={overview}
            runs={runs}
            onSelectRun={(id) => setInspectRunId(id)}
            onNavigateToBenchmark={() => setActiveTab('benchmark')}
          />
        )}

        {activeTab === 'benchmark' && (
          <BenchmarkStudioView
            datasets={datasets}
            providers={providers}
            onRunCreated={handleRunCreated}
            onInspectRun={(id) => setInspectRunId(id)}
          />
        )}

        {activeTab === 'datasets' && (
          <DatasetExplorerView datasets={datasets} />
        )}

        {activeTab === 'regression' && (
          <RegressionMatrixView runs={runs} />
        )}

        {activeTab === 'models' && (
          <ModelStudioView
            providers={providers}
            customModels={customModels}
            onRefresh={refreshAllData}
          />
        )}
      </main>

      <RunDetailModal
        runId={inspectRunId}
        onClose={() => setInspectRunId(null)}
      />

      <footer className="app-footer">
        End-to-End LLM Testing, Benchmarking and Regression Analysis · FastAPI backend, React frontend
      </footer>
    </div>
  )
}

export default App
