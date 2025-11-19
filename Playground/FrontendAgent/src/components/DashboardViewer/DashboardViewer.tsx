import Plot from 'react-plotly.js'
import type { Data, Layout } from 'plotly.js'
import type { ChartConfig } from '@/types/orchestrator'
import styles from './DashboardViewer.module.css'

type Props = {
  iframeUrl?: string
  charts: ChartConfig[]
  isLoading: boolean
  placeholder: string
}

export const DashboardViewer = ({ iframeUrl, charts, isLoading, placeholder }: Props) => {
  if (!charts.length && !iframeUrl) {
    return <p>{placeholder}</p>
  }

  return (
    <div className={styles.viewer}>
      {iframeUrl ? (
        <iframe
          title="Dashboard preview"
          src={iframeUrl}
          className={styles.iframe}
          allow="fullscreen"
          loading="lazy"
        />
      ) : null}

      <div className={styles.charts}>
        {charts.map((chart) => (
          <article key={chart.id} className={styles.chartCard}>
            <span className={styles.chartTitle}>{chart.title}</span>
            <span className={styles.chartDescription}>{chart.description}</span>
            {chart.plotlySpec ? (
              <Plot
                data={chart.plotlySpec.data as Data[]}
                layout={{
                  autosize: true,
                  ...(chart.plotlySpec.layout as Partial<Layout>),
                  height: 320,
                  margin:
                    (chart.plotlySpec.layout as Partial<Layout>)?.margin ?? {
                      t: 40,
                      l: 30,
                      r: 16,
                      b: 30,
                    },
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: '100%', height: '320px' }}
              />
            ) : null}
          </article>
        ))}
        {isLoading ? <span>Updating charts…</span> : null}
      </div>
    </div>
  )
}
