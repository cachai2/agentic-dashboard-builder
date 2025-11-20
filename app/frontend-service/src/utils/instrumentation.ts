type TelemetryPayload = Record<string, string | number | boolean | undefined>

const logLocally = (name: string, payload?: TelemetryPayload) => {
  if (import.meta.env.DEV) {
    // Helpful when demoing locally without App Insights configured.
    console.debug(`[telemetry] ${name}`, payload)
  }
}

export const trackEvent = (name: string, payload?: TelemetryPayload) => {
  if (!import.meta.env.VITE_APP_INSIGHTS_CONNECTION_STRING) {
    logLocally(name, payload)
    return
  }
  try {
    // Placeholder: integrate the real Application Insights JS SDK when the key is ready.
    logLocally(name, payload)
  } catch (error) {
    logLocally('telemetry-error', { message: (error as Error).message })
  }
}
