import clsx from 'clsx'
import { copy } from '@/config/ui'
import { usePlannerSession } from '@/hooks/usePlannerSession'
import {
  DashboardViewer,
  ErrorBanner,
  MetricsGrid,
  Panel,
  StatusTimeline,
  StepIndicator,
  Uploader,
} from '@/components'
import type { Step } from '@/components'
import styles from './PlaygroundPage.module.css'

export const PlaygroundPage = () => {
  const { uploadCsv, statusEntries, dashboard, session, isUploading, error } = usePlannerSession()

  const hasUploadStarted = Boolean(session) || isUploading
  const hasDashboard = Boolean(dashboard)
  const isGeneratingDashboard = Boolean(session) && !dashboard

  const steps: Step[] = [
    {
      id: 'upload',
      label: 'Upload data',
      description: 'CSV + objective + notes',
      status: hasUploadStarted ? 'complete' : 'active',
    },
    {
      id: 'plan',
      label: 'Agent planning',
      description: 'Tool calls & retries',
      status: hasDashboard ? 'complete' : isGeneratingDashboard ? 'active' : 'upcoming',
    },
    {
      id: 'dashboard',
      label: 'Dashboard ready',
      description: 'KPIs + charts render',
      status: hasDashboard ? 'active' : 'upcoming',
    },
  ] as const

  return (
    <div>
      <StepIndicator steps={steps} />
      <div className={styles.layout}>
        <div className={clsx(styles.column, styles.inputColumn)}>
          <Panel title={copy.uploader.title} helper={copy.uploader.helper}>
            <Uploader isUploading={isUploading} onUpload={uploadCsv} />
          </Panel>
        </div>

        <div className={clsx(styles.column, styles.outputColumn)}>
          <Panel title={copy.status.title} helper={copy.status.helper}>
            {error ? <ErrorBanner message={error} /> : null}
            <StatusTimeline entries={statusEntries} emptyLabel={copy.status.empty} />
          </Panel>

          <Panel title={copy.dashboard.title} helper={copy.dashboard.helper}>
            <MetricsGrid metrics={dashboard?.metrics ?? []} />
            <DashboardViewer
              iframeUrl={dashboard?.iframeUrl}
              charts={dashboard?.charts ?? []}
              isGenerating={isGeneratingDashboard}
              placeholder={copy.dashboard.placeholder}
            />
          </Panel>
        </div>
      </div>
    </div>
  )
}
