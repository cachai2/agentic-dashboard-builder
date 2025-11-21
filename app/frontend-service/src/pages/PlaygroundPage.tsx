import clsx from 'clsx'
import { useMemo, useState } from 'react'
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

type DownloadState = 'idle' | 'ready' | 'downloading' | 'downloaded'

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
  const [downloadStateMap, setDownloadStateMap] = useState<Record<string, DownloadState>>({})
  const [downloadErrorMap, setDownloadErrorMap] = useState<Record<string, string | null>>({})

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

  const downloadFilename = useMemo(() => {
    if (!dashboard?.iframeUrl) {
      return 'dashboard.html'
    }
    try {
      const parsed = new URL(dashboard.iframeUrl)
      const segments = parsed.pathname.split('/')
      const lastSegment = segments.pop() || 'dashboard'
      const safeSegment = lastSegment.replace(/[<>:"/\\|?*]+/g, '-')
      return safeSegment.toLowerCase().endsWith('.html') ? safeSegment : `${safeSegment || 'dashboard'}.html`
    } catch {
      return 'dashboard.html'
    }
  }, [dashboard])

  const downloadKey = dashboard?.iframeUrl ?? ''
  const downloadState: DownloadState = downloadKey ? downloadStateMap[downloadKey] ?? 'ready' : 'idle'
  const downloadError = downloadKey ? downloadErrorMap[downloadKey] ?? null : null

  const handleDownloadDashboard = () => {
    if (!downloadKey || !dashboard?.iframeUrl) return
    setDownloadErrorMap((prev) => ({ ...prev, [downloadKey]: null }))
    setDownloadStateMap((prev) => ({ ...prev, [downloadKey]: 'downloading' }))
    try {
      const anchor = document.createElement('a')
      anchor.href = dashboard.iframeUrl
      anchor.target = '_blank'
      anchor.rel = 'noopener noreferrer'
      anchor.download = downloadFilename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      setDownloadStateMap((prev) => ({ ...prev, [downloadKey]: 'downloaded' }))
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to open dashboard download.'
      setDownloadErrorMap((prev) => ({ ...prev, [downloadKey]: message }))
      setDownloadStateMap((prev) => ({ ...prev, [downloadKey]: 'ready' }))
    }
  }

  const downloadLabel =
    downloadState === 'downloaded'
      ? 'Downloaded'
      : downloadState === 'downloading'
        ? 'Opening…'
        : 'Download HTML'

  const dashboardActions = dashboard?.iframeUrl ? (
    <div className={styles.dashboardActions}>
      <button
        type="button"
        className={styles.downloadButton}
        onClick={handleDownloadDashboard}
        disabled={downloadState === 'downloading'}
      >
        {downloadLabel}
      </button>
      <span className={styles.downloadFilename}>{downloadFilename}</span>
      {downloadError ? (
        <span className={styles.downloadError}>{downloadError}</span>
      ) : downloadState === 'downloaded' ? (
        <span className={styles.downloadHint}>HTML opened in a new tab</span>
      ) : (
        <span className={styles.downloadHint}>Opens the rendered HTML in a new tab</span>
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
