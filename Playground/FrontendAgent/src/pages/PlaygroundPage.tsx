import { copy } from '@/config/ui'
import { usePlannerSession } from '@/hooks/usePlannerSession'
import {
  DashboardViewer,
  ErrorBanner,
  MetricsGrid,
  Panel,
  StatusTimeline,
  Uploader,
} from '@/components'
import styles from './PlaygroundPage.module.css'

export const PlaygroundPage = () => {
  const { uploadCsv, statusEntries, dashboard, isUploading, error } = usePlannerSession()

  return (
    <div className={styles.layout}>
      <div className={styles.column}>
        <Panel title={copy.uploader.title} helper={copy.uploader.helper}>
          <Uploader isUploading={isUploading} onUpload={uploadCsv} />
        </Panel>

        <Panel title={copy.status.title} helper={copy.status.helper}>
          {error ? <ErrorBanner message={error} /> : null}
          <StatusTimeline entries={statusEntries} emptyLabel={copy.status.empty} />
        </Panel>
      </div>

      <div className={styles.column}>
        <Panel title={copy.dashboard.title} helper={copy.dashboard.helper}>
          <MetricsGrid metrics={dashboard?.metrics ?? []} />
          <DashboardViewer
            iframeUrl={dashboard?.iframeUrl}
            charts={dashboard?.charts ?? []}
            isLoading={isUploading && !dashboard}
            placeholder={copy.dashboard.placeholder}
          />
        </Panel>
      </div>
    </div>
  )
}
