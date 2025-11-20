import type { AgentStatusEntry, WorkflowEventEntry } from '@/types/orchestrator'
import clsx from 'clsx'
import styles from './StatusTimeline.module.css'

type Props = {
  entries: AgentStatusEntry[]
  emptyLabel?: string
  events?: WorkflowEventEntry[]
}

const stateClass = (state: AgentStatusEntry['state']) => {
  if (state === 'running') return styles.nodeRunning
  if (state === 'success') return styles.nodeSuccess
  if (state === 'error') return styles.nodeError
  return undefined
}

const findEventsForEntry = (entry: AgentStatusEntry, events?: WorkflowEventEntry[]) => {
  if (!events?.length) return []
  const toolName = entry.toolName.toLowerCase()
  return events.filter((event) => {
    const executorId = event.payload?.executorId
    return typeof executorId === 'string' && executorId.toLowerCase().includes(toolName)
  })
}

export const StatusTimeline = ({ entries, events, emptyLabel = 'Awaiting planner activity…' }: Props) => {
  if (!entries.length) {
    return <p>{emptyLabel}</p>
  }

  return (
    <div className={styles.timeline}>
      {entries.map((entry) => {
        const entryEvents = findEventsForEntry(entry, events)

        return (
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
              {entryEvents.length ? (
                <ul className={styles.eventList}>
                  {entryEvents.map((event) => (
                    <li key={event.sequence}>
                      <span className={styles.eventType}>{event.type.replace('Event', '')}</span>
                      <span className={styles.eventDetails}>
                        {event.payload?.data ? JSON.stringify(event.payload.data) : 'no additional details'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        )
      })}
    </div>
  )
}
