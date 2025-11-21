import { useEffect, useState } from 'react'
import './App.css'
import { featureFlags } from './config/featureFlags'
import { ComponentGallery } from './pages/ComponentGallery'
import { PlaygroundPage } from './pages/PlaygroundPage'

type Mode = 'playground' | 'gallery'

const App = () => {
  const [mode, setMode] = useState<Mode>('playground')

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (params.get('gallery') === '1') {
      setMode('gallery')
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (mode === 'gallery') {
      params.set('gallery', '1')
    } else {
      params.delete('gallery')
    }
    const query = params.toString()
    const newUrl = `${window.location.pathname}${query ? `?${query}` : ''}`
    window.history.replaceState({}, '', newUrl)
  }, [mode])

  const toggleMode = () => {
    setMode((previous) => (previous === 'playground' ? 'gallery' : 'playground'))
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Agentic Dashboard Generator</p>
          <h1>Describe the brief. Let the agent design.</h1>
          <p className="subtitle">
            Upload a CSV, and let the agent plan,
            prioritize, and render the full dashboard narrative in real time.
          </p>
        </div>
        <div className="hero-controls">
          <div className="hero-pill">
            <span>{featureFlags.useMockPlanner ? 'Mock planner' : 'Live planner'}</span>
            <span>{featureFlags.enableAgentFramework ? 'Agent Framework' : 'REST bridge'}</span>
          </div>
          <button className="hero-toggle" onClick={toggleMode}>
            {mode === 'gallery' ? 'Back to playground' : 'Component gallery'}
          </button>
        </div>
      </header>
      {mode === 'gallery' ? <ComponentGallery /> : <PlaygroundPage />}
    </main>
  )
}

export default App
