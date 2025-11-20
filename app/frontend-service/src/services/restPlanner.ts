import type {
  DashboardResponse,
  StatusResponse,
  UploadMetadata,
  UploadSession,
  WorkflowEventsResponse,
} from '@/types/orchestrator'
import type { PlannerClient } from './types'

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8800'

const throwIfNotOk = async (response: Response) => {
  if (response.ok) return response
  const text = await response.text()
  throw new Error(text || 'Planner API request failed')
}

const uploadCsv = async (file: File, metadata: UploadMetadata): Promise<UploadSession> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('scenarioName', metadata.scenarioName)
  formData.append('objective', metadata.objective)
  formData.append('notes', metadata.notes ?? '')

  const response = await throwIfNotOk(
    await fetch(`${baseUrl}/upload`, {
      method: 'POST',
      body: formData,
    }),
  )
  return (await response.json()) as UploadSession
}

const getStatus = async (sessionId: string): Promise<StatusResponse> => {
  const response = await throwIfNotOk(
    await fetch(`${baseUrl}/dashboard/status?sessionId=${encodeURIComponent(sessionId)}`),
  )
  return (await response.json()) as StatusResponse
}

const getDashboard = async (sessionId: string): Promise<DashboardResponse> => {
  const response = await throwIfNotOk(
    await fetch(`${baseUrl}/dashboard/view?sessionId=${encodeURIComponent(sessionId)}`),
  )
  return (await response.json()) as DashboardResponse
}

const getEvents = async (sessionId: string): Promise<WorkflowEventsResponse> => {
  const response = await throwIfNotOk(
    await fetch(`${baseUrl}/dashboard/events?sessionId=${encodeURIComponent(sessionId)}`),
  )
  return (await response.json()) as WorkflowEventsResponse
}

export const apiPlannerClient: PlannerClient = {
  uploadCsv,
  getStatus,
  getDashboard,
  getEvents,
}
