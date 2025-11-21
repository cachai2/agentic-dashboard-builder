import clsx from 'clsx'
import { useEffect, useState } from 'react'
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
import { downloadDashboardHtml } from '@/utils/downloadDashboardHtml'
import styles from './PlaygroundPage.module.css'

export const PlaygroundPage = () => {
  const {
    uploadCsv,
    statusEntries,
    dashboard,
    session,
    events,
    isUploading,
    errors,
    plannerMode,
  } = usePlannerSession()
  const [isDownloadingDashboard, setIsDownloadingDashboard] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

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

  const plannerModeLabel =
    plannerMode === 'mock' ? 'Mock planner (local data)' : plannerMode === 'live' ? 'Live planner (API)' : 'Custom planner'

  useEffect(() => {
    if (!dashboard) {
      setDownloadError(null)
      setIsDownloadingDashboard(false)
    }
  }, [dashboard])

  const handleDownloadDashboard = async () => {
    if (!dashboard?.iframeUrl) return
    setIsDownloadingDashboard(true)
    setDownloadError(null)
    try {
      const fallbackName = session ? `dashboard-${session.sessionId}` : 'dashboard'
      await downloadDashboardHtml(dashboard.iframeUrl, { suggestedName: fallbackName })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to download dashboard HTML.'
      setDownloadError(message)
    } finally {
      setIsDownloadingDashboard(false)
    }
  }

  const dashboardActions = dashboard?.iframeUrl ? (
    <div className={styles.dashboardActions}>
      <button
        type="button"
        className={styles.downloadButton}
        onClick={handleDownloadDashboard}
        disabled={isDownloadingDashboard}
      >
        {isDownloadingDashboard ? 'Preparing download…' : 'Download HTML'}
      </button>
      {downloadError ? (
        <span className={styles.downloadError}>{downloadError}</span>
      ) : (
        <span className={styles.downloadHint}>Saves the generated dashboard locally</span>
      )}
    </div>
  ) : null

  return (
    <div>
      <StepIndicator steps={steps} />
      <div className={styles.modeBadge}>{plannerModeLabel}</div>
      <div className={styles.layout}>
        <div className={clsx(styles.column, styles.inputColumn)}>
          <Panel title={copy.uploader.title} helper={copy.uploader.helper}>
            <Uploader isUploading={isUploading} onUpload={uploadCsv} serverError={errors.upload} />
          </Panel>
        </div>

        <div className={clsx(styles.column, styles.statusColumn)}>
          <Panel className={styles.statusPanel} title={copy.status.title} helper={copy.status.helper}>
            {errors.status ? <ErrorBanner message={`Status: ${errors.status}`} /> : null}
            {errors.events ? <ErrorBanner message={`Events: ${errors.events}`} /> : null}
            {errors.dashboard ? <ErrorBanner message={`Dashboard: ${errors.dashboard}`} /> : null}
            <div className={styles.statusBody}>
              <StatusTimeline entries={statusEntries} events={events} emptyLabel={copy.status.empty} />
            </div>
          </Panel>
        </div>

        <div className={clsx(styles.column, styles.dashboardRow)}>
          <Panel
            className={styles.dashboardPanel}
            title={copy.dashboard.title}
            helper={copy.dashboard.helper}
            actions={dashboardActions}
          >
            <div className={styles.dashboardBody}>
              <MetricsGrid metrics={dashboard?.metrics ?? []} />
              <DashboardViewer
                iframeUrl={dashboard?.iframeUrl}
                charts={dashboard?.charts ?? []}
                isGenerating={isGeneratingDashboard}
                placeholder={copy.dashboard.placeholder}
              />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
