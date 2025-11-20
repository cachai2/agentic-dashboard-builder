import type { MetricSummary } from '@/types/orchestrator'
import styles from './MetricsGrid.module.css'

type Props = {
  metrics: MetricSummary[]
}

const deltaColor = (trend: MetricSummary['trend']) => {
  if (trend === 'up') return 'var(--color-success)'
  if (trend === 'down') return 'var(--color-error)'
  return 'var(--color-text-secondary)'
}

export const MetricsGrid = ({ metrics }: Props) => {
  if (!metrics.length) return null
  return (
    <div className={styles.grid}>
      {metrics.map((metric) => (
        <article key={metric.label} className={styles.card}>
          <div className={styles.label}>{metric.label}</div>
          <div className={styles.value}>{metric.value}</div>
          {metric.delta ? (
            <div className={styles.delta} style={{ color: deltaColor(metric.trend) }}>
              {metric.delta}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  )
}
