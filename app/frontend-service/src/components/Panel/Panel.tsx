import clsx from 'clsx'
import type { PropsWithChildren, ReactNode } from 'react'
import styles from './Panel.module.css'

export type PanelProps = PropsWithChildren<{
  title: string
  helper?: string
  actions?: ReactNode
  className?: string
}>

export const Panel = ({ title, helper, actions, className, children }: PanelProps) => (
  <section className={clsx(styles.panel, className)}>
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
