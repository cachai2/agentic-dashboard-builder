import type { ChartConfig, MetricSummary } from './orchestrator'

declare global {
  interface Window {
    DashboardDemo?: {
      sessionId: string
      lastPlan: {
        metrics: MetricSummary[]
        charts: ChartConfig[]
      }
      note?: string
    }
  }
}

export {}
