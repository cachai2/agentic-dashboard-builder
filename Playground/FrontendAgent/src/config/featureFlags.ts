export type FeatureFlags = {
  useMockPlanner: boolean
  enableAgentFramework: boolean
  enableAppInsights: boolean
}

const toBool = (value: string | undefined, defaultValue: boolean) => {
  if (value === undefined) return defaultValue
  return value.toLowerCase() === 'true'
}

export const featureFlags: FeatureFlags = {
  useMockPlanner: toBool(import.meta.env.VITE_USE_MOCK, true),
  enableAgentFramework: toBool(import.meta.env.VITE_ENABLE_AGENT_FRAMEWORK, false),
  enableAppInsights: toBool(import.meta.env.VITE_ENABLE_APP_INSIGHTS, false),
}
