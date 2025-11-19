import type { AgentStatusEntry } from '@/types/orchestrator'
import clsx from 'clsx'
import styles from './StatusTimeline.module.css'

type Props = {
  entries: AgentStatusEntry[]
  emptyLabel?: string
}

const stateClass = (state: AgentStatusEntry['state']) => {
  if (state === 'running') return styles.nodeRunning
  if (state === 'success') return styles.nodeSuccess
  if (state === 'error') return styles.nodeError
  return undefined
}

export const StatusTimeline = ({ entries, emptyLabel = 'Awaiting planner activity…' }: Props) => {
  if (!entries.length) {
    return <p>{emptyLabel}</p>
  }

  return (
    <div className={styles.timeline}>
      {entries.map((entry) => (
        <div key={entry.id} className={styles.item}>
          <span className={clsx(styles.node, stateClass(entry.state))} />
          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span className={styles.toolName}>{entry.toolName}</span>
              <span className={styles.meta}>
                {entry.state.toUpperCase()} ·{' '}
                {entry.durationMs ? `${(entry.durationMs / 1000).toFixed(1)}s` : 'in progress'}
              </span>
            </div>
            <p className={styles.reasoning}>{entry.reasoning}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
