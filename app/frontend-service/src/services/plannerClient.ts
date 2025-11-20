import { featureFlags } from '@/config/featureFlags'
import { apiPlannerClient } from './restPlanner'
import { mockPlannerClient } from './mockPlanner'
import type { PlannerClient } from './types'

const selectClient = (): PlannerClient =>
  featureFlags.useMockPlanner ? mockPlannerClient : apiPlannerClient

export const plannerClient = selectClient()
