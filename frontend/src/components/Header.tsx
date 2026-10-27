import React from 'react'
import { Activity, Cpu, Database, GitCompare, Sparkles } from 'lucide-react'
import type { ProviderConfigResponse } from '../api'

interface HeaderProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  providers: ProviderConfigResponse | null
  isOnline: boolean
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  providers,
  isOnline,
}) => {
  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'benchmark', label: 'Benchmark Studio', icon: Sparkles },
    { id: 'datasets', label: 'Dataset Explorer', icon: Database },
    { id: 'regression', label: 'Regression Matrix', icon: GitCompare },
    { id: 'models', label: 'Model & Provider Studio', icon: Cpu },
  ]

  const customCount = providers?.custom_models?.length || 0
  const configured = providers?.providers
    ? Object.values(providers.providers).filter((p) => p.configured).length
    : 0

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="app-brand">
          <h1>LLM Evaluation Platform</h1>
          <p>
            Benchmark runs, statistical regression analysis, and dataset inspection against a
            self-hosted FastAPI backend.
          </p>
        </div>

        <div className="app-status">
          <span className="app-status-item">
            <span
              className="pulse-dot"
              style={{ backgroundColor: isOnline ? 'var(--text-secondary)' : 'var(--accent-rose)' }}
              aria-hidden="true"
            />
            {isOnline ? 'Backend connected' : 'Backend unreachable'}
          </span>
          <span className="app-status-item">
            {configured} {configured === 1 ? 'provider' : 'providers'} configured
          </span>
          <span className="app-status-item">
            {customCount} custom {customCount === 1 ? 'model' : 'models'}
          </span>
        </div>
      </div>

      <nav className="app-nav" aria-label="Sections">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const active = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className="app-nav-tab"
              aria-current={active ? 'page' : undefined}
            >
              <Icon size={15} aria-hidden="true" />
              {tab.label}
            </button>
          )
        })}
      </nav>
    </header>
  )
}
