import Plot from 'react-plotly.js'
import type { Data, Layout } from 'plotly.js'
import type { ChartConfig } from '@/types/orchestrator'
import styles from './DashboardViewer.module.css'

type Props = {
  iframeUrl?: string
  charts: ChartConfig[]
  isGenerating: boolean
  placeholder: string
}

const Placeholder = ({ message, isGenerating }: { message: string; isGenerating: boolean }) => (
  <div className={styles.placeholder}>
    <div>
      <p className={styles.placeholderTitle}>Dashboard preview</p>
      <p className={styles.placeholderCopy}>{message}</p>
    </div>
    {isGenerating ? (
      <>
        <div className={styles.placeholderGrid} aria-hidden>
          <div className={styles.placeholderCard}>
            <span className={styles.placeholderBar} />
            <span className={styles.placeholderBar} />
            <span className={styles.placeholderBarShort} />
          </div>
          <div className={styles.placeholderCardTall}>
            <span className={styles.placeholderBar} />
            <span className={styles.placeholderChart} />
          </div>
          <div className={styles.placeholderCardTall}>
            <span className={styles.placeholderBar} />
            <span className={styles.placeholderChart} />
          </div>
        </div>
        <span className={styles.placeholderStatus}>Generating dashboard…</span>
      </>
    ) : (
      <p className={styles.placeholderIdle}>Kick off generation to see charts spark to life.</p>
    )}
  </div>
)

export const DashboardViewer = ({ iframeUrl, charts, isGenerating, placeholder }: Props) => {
  if (!charts.length && !iframeUrl) {
    return <Placeholder message={placeholder} isGenerating={isGenerating} />
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

      {!iframeUrl ? (
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
          {isGenerating ? <span className={styles.loadingLabel}>Updating charts…</span> : null}
        </div>
      ) : null}
    </div>
  )
}
