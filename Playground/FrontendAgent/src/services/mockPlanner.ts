import type {
  AgentStatusEntry,
  ChartConfig,
  DashboardResponse,
  MetricSummary,
  StatusResponse,
  ToolState,
  UploadMetadata,
  UploadSession,
} from '@/types/orchestrator'
import type { PlannerClient } from './types'

const TOOLCHAIN = [
  {
    toolName: 'CSVProfiler',
    reasoning: 'Profiling the dataset to detect schema drift and gaps.',
    durationMs: 1500,
  },
  {
    toolName: 'SignalSelector',
    reasoning: 'Ranking candidate metrics that align with the stated objective.',
    durationMs: 1600,
  },
  {
    toolName: 'VisualizationPlanner',
    reasoning: 'Selecting the best chart types for each prioritized metric.',
    durationMs: 2000,
  },
  {
    toolName: 'CopilotRenderer',
    reasoning: 'Generating dashboard markup + updating the live preview.',
    durationMs: 1800,
  },
] as const

type MockStep = (typeof TOOLCHAIN)[number] & {
  id: string
  metadata?: Record<string, string>
}

type MockSession = {
  session: UploadSession
  startedAt: number
  steps: MockStep[]
  metrics: MetricSummary[]
  charts: ChartConfig[]
  iframeUrl: string
}

const sessions = new Map<string, MockSession>()

const nowIso = () => new Date().toISOString()

const generateId = () => crypto.randomUUID().slice(0, 8)

const summarizeCsv = (text: string) => {
  const rows = text
    .split(/\r?\n/)
    .map((row) => row.trim())
    .filter(Boolean)

  if (!rows.length) {
    return {
      headers: [],
      previewRows: [],
    }
  }
  const [headerRow, ...dataRows] = rows
  const headers = headerRow.split(',').map((h) => h.trim())
  return {
    headers,
    previewRows: dataRows.slice(0, 5).map((row) => row.split(',').map((cell) => cell.trim())),
  }
}

const deriveMetrics = (objective: string, headers: string[]): MetricSummary[] => {
  const fallback = ['North America', 'EMEA', 'APAC']
  const dimension = headers[0] ?? 'Segment'
  const valueLabel = headers[headers.length - 1] ?? 'Metric'
  const polarity = objective.length % 2 === 0 ? 'up' : 'down'

  return fallback.slice(0, 3).map((region, idx) => ({
    label: `${region} ${dimension}`,
    value: `${(Math.random() * 100).toFixed(1)} ${valueLabel}`,
    delta: `${idx % 2 === 0 ? '+' : '-'}${(Math.random() * 6 + 1).toFixed(1)}% vs goal`,
    trend: idx === 0 ? polarity : idx % 2 === 0 ? 'up' : 'down',
  }))
}

const deriveCharts = (objective: string, headers: string[]): ChartConfig[] => {
  const dimension = headers[0] ?? 'Segment'
  const measure = headers[headers.length - 1] ?? 'Value'
  const baseTrace = {
    type: 'bar',
    x: ['North America', 'EMEA', 'APAC', 'LATAM'],
    y: [42, 55, 38, 33].map((value) => value + Math.round(Math.random() * 10 - 5)),
    marker: { color: ['#38bdf8', '#a855f7', '#f97316', '#facc15'] },
  }

  return [
    {
      id: 'chart-1',
      title: `Impact by ${dimension}`,
      description: `Measuring ${measure} uplift to support "${objective}"`,
      plotlySpec: {
        data: [baseTrace],
        layout: {
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: { color: '#f8fafc', family: 'Inter, sans-serif' },
          margin: { t: 40, l: 50, r: 12, b: 40 },
        },
      },
    },
    {
      id: 'chart-2',
      title: 'Forecast vs Actual',
      description: 'Stacking orchestrator-picked scenarios for the next 6 weeks.',
      plotlySpec: {
        data: [
          {
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Actual',
            x: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
            y: [72, 76, 74, 81, 84, 87],
          },
          {
            type: 'scatter',
            mode: 'lines',
            name: 'Forecast',
            x: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
            y: [70, 73, 75, 79, 83, 90],
            line: { dash: 'dot' },
          },
        ],
        layout: {
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: { color: '#f8fafc', family: 'Inter, sans-serif' },
          legend: { orientation: 'h' },
          margin: { t: 40, l: 50, r: 12, b: 40 },
        },
      },
    },
  ]
}

const registerDashboardHook = (sessionId: string, metrics: MetricSummary[], charts: ChartConfig[]) => {
  if (typeof window === 'undefined') return
  window.DashboardDemo = {
    sessionId,
    lastPlan: {
      metrics,
      charts,
    },
    note: 'mock-planner',
  }
}

const createMockSession = (
  file: File,
  metadata: UploadMetadata,
  csvText: string,
): MockSession => {
  const headers = summarizeCsv(csvText).headers
  const sessionId = generateId()
  const uploadedAt = nowIso()
  const session: UploadSession = {
    sessionId,
    uploadedAt,
    nextPollInMs: 1200,
  }

  const steps: MockStep[] = TOOLCHAIN.map((step, index) => ({
    ...step,
    id: `${sessionId}-${index}`,
    metadata: {
      objective: metadata.objective,
      fileName: file.name,
    },
  }))

  const metrics = deriveMetrics(metadata.objective, headers)
  const charts = deriveCharts(metadata.objective, headers)
  const sessionRecord: MockSession = {
    session,
    startedAt: Date.now(),
    steps,
    metrics,
    charts,
    iframeUrl: '/sample-dashboard.html',
  }

  registerDashboardHook(sessionId, metrics, charts)
  sessions.set(sessionId, sessionRecord)
  return sessionRecord
}

const summarizeStepState = (session: MockSession): AgentStatusEntry[] => {
  const currentTime = Date.now()
  let timeCursor = 0
  return session.steps.map((step) => {
    const start = session.startedAt + timeCursor
    const end = start + step.durationMs
    timeCursor += step.durationMs

    let state: ToolState = 'idle'
    if (currentTime >= end) state = 'success'
    else if (currentTime >= start) state = 'running'

    const durationMs = state === 'success' ? step.durationMs : undefined

    return {
      id: step.id,
      toolName: step.toolName,
      reasoning: step.reasoning,
      state,
      startedAt: new Date(start).toISOString(),
      finishedAt: state === 'success' ? new Date(end).toISOString() : undefined,
      durationMs,
      metadata: step.metadata,
    }
  })
}

const ensureSession = (sessionId: string): MockSession => {
  const session = sessions.get(sessionId)
  if (!session) {
    throw new Error('Mock session expired')
  }
  return session
}

const uploadCsv = async (file: File, metadata: UploadMetadata): Promise<UploadSession> => {
  const text = await file.text()
  const session = createMockSession(file, metadata, text)
  return session.session
}

const getStatus = async (sessionId: string): Promise<StatusResponse> => {
  const session = ensureSession(sessionId)
  const entries = summarizeStepState(session)
  const isComplete = entries.every((entry) => entry.state === 'success')
  return {
    entries,
    isComplete,
    nextPollInMs: isComplete ? 0 : 1500,
  }
}

const getDashboard = async (sessionId: string): Promise<DashboardResponse> => {
  const session = ensureSession(sessionId)
  return {
    iframeUrl: session.iframeUrl,
    metrics: session.metrics,
    charts: session.charts,
  }
}

export const mockPlannerClient: PlannerClient = {
  uploadCsv,
  getStatus,
  getDashboard,
}
