import type { PropsWithChildren, ReactNode } from 'react'
import styles from './Panel.module.css'

export type PanelProps = PropsWithChildren<{
  title: string
  helper?: string
  actions?: ReactNode
}>

export const Panel = ({ title, helper, actions, children }: PanelProps) => (
  <section className={styles.panel}>
    <div className={styles.header}>
      <div className={styles.titleBlock}>
        <span className={styles.title}>{title}</span>
        {helper ? <span className={styles.helper}>{helper}</span> : null}
      </div>
      {actions}
    </div>
    {children}
  </section>
)
