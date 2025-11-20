import type {
  DashboardResponse,
  StatusResponse,
  UploadMetadata,
  UploadSession,
  WorkflowEventsResponse,
} from '@/types/orchestrator'

export type PlannerClient = {
  uploadCsv: (file: File, metadata: UploadMetadata) => Promise<UploadSession>
  getStatus: (sessionId: string) => Promise<StatusResponse>
  getDashboard: (sessionId: string) => Promise<DashboardResponse>
  getEvents: (sessionId: string) => Promise<WorkflowEventsResponse>
}
