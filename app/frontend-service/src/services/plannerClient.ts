import { featureFlags } from '@/config/featureFlags'
import { apiPlannerClient } from './restPlanner'
import { mockPlannerClient } from './mockPlanner'
import type { PlannerClient } from './types'

export type PlannerClientMode = 'mock' | 'live'

const selectClient = (): PlannerClient =>
  featureFlags.useMockPlanner ? mockPlannerClient : apiPlannerClient

export const plannerClientMode: PlannerClientMode = featureFlags.useMockPlanner ? 'mock' : 'live'

export const plannerClient = selectClient()
