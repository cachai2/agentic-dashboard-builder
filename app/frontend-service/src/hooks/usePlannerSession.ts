import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  AgentStatusEntry,
  DashboardResponse,
  UploadMetadata,
  UploadSession,
  WorkflowEventEntry,
} from '@/types/orchestrator'
import { plannerClient as defaultPlannerClient } from '@/services/plannerClient'
import type { PlannerClient } from '@/services/types'
import { trackEvent } from '@/utils/instrumentation'

const getErrorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'Unexpected orchestrator error'

export const usePlannerSession = (client: PlannerClient = defaultPlannerClient) => {
  const [session, setSession] = useState<UploadSession | null>(null)
  const [statusEntries, setStatusEntries] = useState<AgentStatusEntry[]>([])
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [events, setEvents] = useState<WorkflowEventEntry[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pollTimerRef = useRef<number | null>(null)

  const clearExistingTimer = useCallback(() => {
    if (pollTimerRef.current) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  useEffect(() => clearExistingTimer, [clearExistingTimer])

  const pollStatus = useCallback(async () => {
    if (!session) return
    try {
      const status = await client.getStatus(session.sessionId)
      setStatusEntries(status.entries)
      const eventsResponse = await client.getEvents(session.sessionId)
      setEvents(eventsResponse.events)
      if (status.isComplete) {
        const dashboardResponse = await client.getDashboard(session.sessionId)
        setDashboard(dashboardResponse)
        clearExistingTimer()
        return
      }
      pollTimerRef.current = window.setTimeout(pollStatus, status.nextPollInMs ?? 1500)
    } catch (err) {
      setError(getErrorMessage(err))
      clearExistingTimer()
    }
  }, [client, clearExistingTimer, session])

  useEffect(() => {
    if (!session) return
    clearExistingTimer()
    pollTimerRef.current = window.setTimeout(pollStatus, session.nextPollInMs ?? 1000)
  }, [clearExistingTimer, pollStatus, session])

  const uploadCsv = useCallback(
    async (file: File, metadata: UploadMetadata) => {
      setIsUploading(true)
      setError(null)
      setDashboard(null)
      setStatusEntries([])
      setEvents([])
      try {
        const createdSession = await client.uploadCsv(file, metadata)
        setSession(createdSession)
        trackEvent('upload-submitted', {
          scenarioName: metadata.scenarioName,
        })
      } catch (err) {
        setError(getErrorMessage(err))
        trackEvent('upload-error', { message: getErrorMessage(err) })
      } finally {
        setIsUploading(false)
      }
    },
    [client],
  )

  return {
    uploadCsv,
    session,
    statusEntries,
    dashboard,
    events,
    isUploading,
    error,
    isComplete: Boolean(dashboard),
  }
}
