import { Panel, StatusTimeline, MetricsGrid, DashboardViewer, ErrorBanner } from '@/components'
import type { AgentStatusEntry, MetricSummary } from '@/types/orchestrator'
import styles from './ComponentGallery.module.css'

const sampleStatuses: AgentStatusEntry[] = [
  {
    id: 'gallery-1',
    toolName: 'CSVProfiler',
    state: 'success',
    reasoning: 'Column profiling complete · 12 columns detected',
    startedAt: new Date(Date.now() - 4000).toISOString(),
    finishedAt: new Date(Date.now() - 2000).toISOString(),
    durationMs: 2000,
  },
  {
    id: 'gallery-2',
    toolName: 'SignalSelector',
    state: 'running',
    reasoning: 'Scoring dimensions against objective weightings',
    startedAt: new Date(Date.now() - 1000).toISOString(),
  },
]

const sampleMetrics: MetricSummary[] = [
  { label: 'North America Lift', value: '42%', delta: '+7% vs LY', trend: 'up' },
  { label: 'EMEA Lift', value: '36%', delta: '-3% vs LY', trend: 'down' },
]

const sampleCharts = [
  {
    id: 'gallery-chart-1',
    title: 'Gallery Chart',
    description: 'Minimal Plotly spec rendered inline.',
    plotlySpec: {
      data: [
        {
          type: 'bar',
          x: ['A', 'B', 'C'],
          y: [12, 18, 10],
          marker: { color: ['#38bdf8', '#a855f7', '#f97316'] },
        },
      ],
    },
  },
]

export const ComponentGallery = () => (
  <div className={styles.gallery}>
    <Panel title="Status Timeline" helper="Documented component" actions={<span>#StatusTimeline</span>}>
      <StatusTimeline entries={sampleStatuses} />
    </Panel>
    <Panel title="Metrics Grid" helper="Use for quick KPIs" actions={<span>#MetricsGrid</span>}>
      <MetricsGrid metrics={sampleMetrics} />
    </Panel>
    <Panel title="Dashboard Viewer" helper="Embedding Plotly + iframe">
      <DashboardViewer
        iframeUrl={undefined}
        charts={sampleCharts}
        isLoading={false}
        placeholder="Plotly spec renders inline when provided."
      />
    </Panel>
    <Panel title="Error Banner" helper="Surface errors from hooks">
      <ErrorBanner message="Example: Upload validation failed" />
    </Panel>
  </div>
)
