import styles from './ErrorBanner.module.css'

type Props = {
  message: string
}

export const ErrorBanner = ({ message }: Props) => <div className={styles.banner}>{message}</div>
