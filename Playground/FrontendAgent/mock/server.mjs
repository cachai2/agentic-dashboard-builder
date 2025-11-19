import express from 'express'
import cors from 'cors'
import multer from 'multer'

const app = express()
const upload = multer()
const PORT = process.env.PORT ?? 8800

app.use(cors())
app.use(express.json())

const sessions = new Map()

const toolchain = ['CSVProfiler', 'SignalSelector', 'VisualizationPlanner', 'CopilotRenderer']

app.post('/upload', upload.single('file'), (req, res) => {
  const sessionId = Math.random().toString(36).slice(2, 10)
  const startedAt = Date.now()
  sessions.set(sessionId, { startedAt })
  res.json({ sessionId, uploadedAt: new Date(startedAt).toISOString(), nextPollInMs: 1200 })
})

app.get('/dashboard/status', (req, res) => {
  const { sessionId } = req.query
  const record = sessions.get(sessionId)
  if (!record) return res.status(404).json({ message: 'Unknown session' })
  const elapsed = Date.now() - record.startedAt
  const stepDuration = 2000
  const entries = toolchain.map((tool, index) => {
    const start = record.startedAt + index * stepDuration
    const end = start + stepDuration
    let state = 'idle'
    if (elapsed >= (index + 1) * stepDuration) state = 'success'
    else if (elapsed >= index * stepDuration) state = 'running'
    return {
      id: `${sessionId}-${tool}`,
      toolName: tool,
      reasoning: `Mock reasoning for ${tool}`,
      state,
      startedAt: new Date(start).toISOString(),
      finishedAt: state === 'success' ? new Date(end).toISOString() : undefined,
      durationMs: state === 'success' ? stepDuration : undefined,
    }
  })
  const isComplete = entries.every((entry) => entry.state === 'success')
  res.json({ entries, isComplete, nextPollInMs: isComplete ? 0 : 1500 })
})

app.get('/dashboard/view', (req, res) => {
  const { sessionId } = req.query
  if (!sessions.has(sessionId)) return res.status(404).json({ message: 'Unknown session' })
  res.json({
    iframeUrl: 'http://localhost:5173/sample-dashboard.html',
    metrics: [
      { label: 'North America Lift', value: '42%', delta: '+6% vs LY', trend: 'up' },
      { label: 'EMEA Lift', value: '37%', delta: '-2% vs LY', trend: 'down' },
    ],
    charts: [
      { id: 'mock', title: 'Demo chart', description: 'Mock chart output' },
    ],
  })
})

app.listen(PORT, () => {
  console.log(`Mock API ready on http://localhost:${PORT}`)
})
