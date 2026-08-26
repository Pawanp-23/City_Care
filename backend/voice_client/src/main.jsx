import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { VOICE_SERVER, voiceClient } from './client'
import './style.css'

function App() {
  const [state, setState] = useState('Ready')
  const [error, setError] = useState('')
  useEffect(() => {
    const offConnected = voiceClient.on('connected', () => setState('Listening'))
    const offDisconnected = voiceClient.on('disconnected', () => setState('Ready'))
    return () => { offConnected?.(); offDisconnected?.(); voiceClient.disconnect?.() }
  }, [])
  const toggle = async () => {
    setError('')
    try {
      if (state === 'Ready') { setState('Connecting'); await voiceClient.connect({ webrtcUrl: VOICE_SERVER }) }
      else { await voiceClient.disconnect(); setState('Ready') }
    } catch (err) { setState('Ready'); setError(err?.message || 'Could not connect to the CityCare voice service.') }
  }
  return <main><p>CityCare Clinic</p><h1>Compass Voice</h1><div className={`orb ${state !== 'Ready' ? 'live' : ''}`} /><strong>{state}</strong><button onClick={toggle}>{state === 'Ready' ? 'Start voice session' : 'End session'}</button><small>Voice uses live microphone audio. It cannot create or change appointments.</small>{error && <output>{error}</output>}</main>
}
createRoot(document.getElementById('root')).render(<App />)
