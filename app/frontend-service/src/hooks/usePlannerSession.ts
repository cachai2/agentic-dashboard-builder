import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  AgentStatusEntry,
  DashboardResponse,
  StatusResponse,
  UploadMetadata,
  UploadSession,
  WorkflowEventEntry,
} from '@/types/orchestrator'
import { plannerClient as defaultPlannerClient, plannerClientMode as defaultPlannerMode } from '@/services/plannerClient'
import type { PlannerClient } from '@/services/types'
import { trackEvent } from '@/utils/instrumentation'

const getErrorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'Unexpected orchestrator error'

type PlannerErrors = {
  upload: string | null
  status: string | null
  dashboard: string | null
  events: string | null
}

const createDefaultErrors = (): PlannerErrors => ({
  upload: null,
  status: null,
  dashboard: null,
  events: null,
})

type PlannerMode = 'mock' | 'live' | 'custom'

export const usePlannerSession = (
  client: PlannerClient = defaultPlannerClient,
  clientMode: PlannerMode = defaultPlannerMode,
) => {
  const [session, setSession] = useState<UploadSession | null>(null)
  const [statusEntries, setStatusEntries] = useState<AgentStatusEntry[]>([])
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [events, setEvents] = useState<WorkflowEventEntry[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [errors, setErrors] = useState<PlannerErrors>(createDefaultErrors)

  const pollTimerRef = useRef<number | null>(null)

  const resetErrors = useCallback(() => {
    setErrors(createDefaultErrors())
  }, [])

  const setErrorField = useCallback((field: keyof PlannerErrors, value: string | null) => {
    setErrors((prev) => ({
      ...prev,
      [field]: value,
    }))
  }, [])

  const clearExistingTimer = useCallback(() => {
    if (pollTimerRef.current) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  useEffect(() => clearExistingTimer, [clearExistingTimer])

  const pollStatus = useCallback(async () => {
    if (!session) return

    let status: StatusResponse | null = null
    try {
      status = await client.getStatus(session.sessionId)
      setStatusEntries(status.entries)
      setErrorField('status', null)
    } catch (err) {
      setErrorField('status', getErrorMessage(err))
      clearExistingTimer()
      return
    }

    try {
      const eventsResponse = await client.getEvents(session.sessionId)
      setEvents(eventsResponse.events)
      setErrorField('events', null)
    } catch (err) {
      setErrorField('events', getErrorMessage(err))
    }

    if (status.isComplete) {
      try {
        const dashboardResponse = await client.getDashboard(session.sessionId)
        setDashboard(dashboardResponse)
        setErrorField('dashboard', null)
        clearExistingTimer()
        return
      } catch (err) {
        setErrorField('dashboard', getErrorMessage(err))
        pollTimerRef.current = window.setTimeout(pollStatus, status.nextPollInMs ?? 1500)
        return
      }
    }

    pollTimerRef.current = window.setTimeout(pollStatus, status.nextPollInMs ?? 1500)
  }, [client, clearExistingTimer, session, setErrorField])

  useEffect(() => {
    if (!session) return
    clearExistingTimer()
    pollTimerRef.current = window.setTimeout(pollStatus, session.nextPollInMs ?? 1000)
  }, [clearExistingTimer, pollStatus, session])

  const uploadCsv = useCallback(
    async (file: File, metadata: UploadMetadata) => {
      setIsUploading(true)
      resetErrors()
      setDashboard(null)
      setStatusEntries([])
      setEvents([])
      try {
        const createdSession = await client.uploadCsv(file, metadata)
        setSession(createdSession)
        setErrorField('upload', null)
        trackEvent('upload-submitted', {
          scenarioName: metadata.scenarioName,
        })
      } catch (err) {
        const message = getErrorMessage(err)
        setErrorField('upload', message)
        trackEvent('upload-error', { message: getErrorMessage(err) })
      } finally {
        setIsUploading(false)
      }
    },
    [client, resetErrors, setErrorField],
  )

  return {
    uploadCsv,
    session,
    statusEntries,
    dashboard,
    events,
    isUploading,
    errors,
    isComplete: Boolean(dashboard),
    plannerMode: clientMode,
  }
}
