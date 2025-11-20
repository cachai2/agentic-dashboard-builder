export type ToolState = 'idle' | 'running' | 'success' | 'error'

export type AgentStatusEntry = {
  id: string
  toolName: string
  state: ToolState
  reasoning: string
  startedAt: string
  finishedAt?: string
  durationMs?: number
  retryCount?: number
  metadata?: Record<string, string>
}

export type UploadMetadata = {
  scenarioName: string
  objective: string
  notes?: string
}

export type UploadSession = {
  sessionId: string
  uploadedAt: string
  nextPollInMs: number
}

export type StatusResponse = {
  entries: AgentStatusEntry[]
  isComplete: boolean
  nextPollInMs: number
}

export type MetricSummary = {
  label: string
  value: string
  delta?: string
  trend?: 'up' | 'down' | 'flat'
}

export type ChartConfig = {
  id: string
  title: string
  description: string
  iframeUrl?: string
  plotlySpec?: Record<string, unknown>
}

export type DashboardResponse = {
  iframeUrl: string
  metrics: MetricSummary[]
  charts: ChartConfig[]
}
