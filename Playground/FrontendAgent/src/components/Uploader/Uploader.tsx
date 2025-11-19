import { useMemo, useState } from 'react'
import clsx from 'clsx'
import type { UploadMetadata } from '@/types/orchestrator'
import styles from './Uploader.module.css'

type Props = {
  isUploading: boolean
  onUpload: (file: File, metadata: UploadMetadata) => Promise<void> | void
}

const createDefaultMetadata = (): UploadMetadata => ({
  scenarioName: 'Q4 Ignite demo dataset',
  objective: 'Highlight where the agent sees the biggest conversion unlock',
  notes: '',
})

export const Uploader = ({ isUploading, onUpload }: Props) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [metadata, setMetadata] = useState<UploadMetadata>(createDefaultMetadata)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFile = (file: File | null) => {
    if (!file) return
    if (!file.name.endsWith('.csv')) {
      setError('Please choose a .csv file')
      return
    }
    setError(null)
    setSelectedFile(file)
  }

  const onInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files?.length) return
    handleFile(event.target.files[0])
  }

  const onDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDragActive(false)
    const file = event.dataTransfer.files?.[0]
    handleFile(file ?? null)
  }

  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault()
    setDragActive(true)
  }

  const onDragLeave = (event: React.DragEvent) => {
    event.preventDefault()
    setDragActive(false)
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedFile) {
      setError('Upload a CSV to get started')
      return
    }
    setError(null)
    await onUpload(selectedFile, metadata)
  }

  const reset = () => {
    setSelectedFile(null)
    setMetadata(createDefaultMetadata())
    setError(null)
  }

  const fileLabel = useMemo(() => {
    if (!selectedFile) return 'Drag & drop or browse for a CSV file'
    return `${selectedFile.name} · ${(selectedFile.size / 1024).toFixed(1)} KB`
  }, [selectedFile])

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label
        className={clsx(styles.dropZone, dragActive && styles.dropZoneActive)}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <input type="file" accept=".csv" onChange={onInputChange} />
        <strong>{fileLabel}</strong>
        <span>{selectedFile ? 'Ready to orchestrate' : 'Max 5MB · secure upload'}</span>
      </label>

      <div className={styles.fields}>
        <div className={styles.input}>
          <label htmlFor="scenarioName">Scenario name</label>
          <input
            id="scenarioName"
            name="scenarioName"
            value={metadata.scenarioName}
            onChange={(event) =>
              setMetadata((prev) => ({ ...prev, scenarioName: event.target.value }))
            }
            required
          />
        </div>
        <div className={styles.input}>
          <label htmlFor="objective">Objective</label>
          <input
            id="objective"
            name="objective"
            value={metadata.objective}
            onChange={(event) =>
              setMetadata((prev) => ({ ...prev, objective: event.target.value }))
            }
            required
          />
        </div>
        <div className={styles.input}>
          <label htmlFor="notes">Notes (optional)</label>
          <textarea
            id="notes"
            name="notes"
            rows={3}
            value={metadata.notes}
            onChange={(event) => setMetadata((prev) => ({ ...prev, notes: event.target.value }))}
          />
        </div>
      </div>

      {error ? <span className={styles.error}>{error}</span> : null}

      <div className={styles.actions}>
        <button type="button" className={styles.secondaryButton} onClick={reset}>
          Reset
        </button>
        <button type="submit" className={styles.primaryButton} disabled={isUploading}>
          {isUploading ? 'Uploading…' : 'Upload & plan'}
        </button>
      </div>

      {selectedFile ? (
        <span className={styles.fileMeta}>
          Last modified: {new Date(selectedFile.lastModified).toLocaleString()}
        </span>
      ) : null}
    </form>
  )
}
