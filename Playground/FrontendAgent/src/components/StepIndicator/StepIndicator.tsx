import clsx from 'clsx'
import styles from './StepIndicator.module.css'

export type StepStatus = 'complete' | 'active' | 'upcoming'

export type Step = {
  id: string
  label: string
  description: string
  status: StepStatus
}

type Props = {
  steps: Step[]
}

export const StepIndicator = ({ steps }: Props) => {
  return (
    <ol className={styles.list} aria-label="Agent flow">
      {steps.map((step, index) => (
        <li key={step.id} className={clsx(styles.step, styles[step.status])}>
          <span className={styles.dot} aria-hidden={true}>
            {step.status === 'complete' ? '✓' : index + 1}
          </span>
          <div>
            <p className={styles.label}>{step.label}</p>
            <p className={styles.description}>{step.description}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
