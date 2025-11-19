import type {
  DashboardResponse,
  StatusResponse,
  UploadMetadata,
  UploadSession,
} from '@/types/orchestrator'

export type PlannerClient = {
  uploadCsv: (file: File, metadata: UploadMetadata) => Promise<UploadSession>
  getStatus: (sessionId: string) => Promise<StatusResponse>
  getDashboard: (sessionId: string) => Promise<DashboardResponse>
}
