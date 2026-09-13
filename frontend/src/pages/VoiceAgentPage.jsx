import { Link } from 'react-router-dom'
import ErrorBanner from '../components/ErrorBanner'
import { useAuth } from '../context/AuthContext'
import { useHospitalVoiceAgent } from '../hooks/useHospitalVoiceAgent'

export default function VoiceAgentPage() {
  const { user } = useAuth()
  const agent = useHospitalVoiceAgent(user)
  const active = agent.status === 'connected' || agent.status === 'connecting'
  const home = user.role === 'PATIENT' ? '/dashboard' : '/doctor'

  return (
    <main className="voice-agent-page">
      <section className="voice-agent-shell">
        <header className="voice-agent-header">
          <div>
            <p className="eyebrow">Realtime hospital voice agent</p>
            <h1>CityCare Compass Live</h1>
            <p>Natural, interruption-aware voice assistance grounded in your authorized CityCare data.</p>
          </div>
          <Link to={home} className="voice-back-link">Back to dashboard</Link>
        </header>

        <div className="voice-agent-grid">
          <section className="voice-stage" aria-live="polite">
            <div className={`voice-orbit voice-orbit--${agent.voiceState}${active ? ' voice-orbit--active' : ''}`}>
              <span /><span /><span />
              <div className="voice-orbit-core">+</div>
            </div>
            <p className="voice-state-label">
              {agent.status === 'connecting' ? 'Creating secure session…'
                : agent.voiceState === 'speaking' ? 'Compass is speaking'
                  : agent.status === 'connected' ? 'Listening — speak naturally'
                    : 'Ready when you are'}
            </p>
            <button type="button" className={active ? 'voice-end-button' : 'voice-start-button'} onClick={active ? agent.stop : agent.connect}>
              {agent.status === 'connecting' ? 'Cancel' : agent.status === 'connected' ? 'End voice session' : 'Start live voice'}
            </button>
            <small>Microphone audio streams only during an active session. Say “stop” or use End session at any time.</small>
          </section>

          <section className="voice-transcript-card">
            <div className="voice-transcript-heading">
              <div><p className="eyebrow">Live transcript</p><h2>Your conversation</h2></div>
              <span className={`voice-status-pill voice-status-pill--${agent.status}`}>{agent.status}</span>
            </div>
            {agent.error && <ErrorBanner message={agent.error} />}
            <div className="voice-transcript" aria-live="polite">
              {agent.transcript.length ? agent.transcript.map((line) => (
                <article key={line.key} className={`voice-line voice-line--${line.speaker}`}>
                  <span>{line.speaker === 'user' ? 'You' : 'Compass'}</span>
                  <p>{line.text}</p>
                </article>
              )) : (
                <div className="voice-empty">
                  <strong>What you can ask</strong>
                  <p>{user.role === 'PATIENT'
                    ? 'Find a doctor, check facilities, review appointments or prescriptions, find slots, and book after confirmation.'
                    : 'Review your schedule, patient load, clinic statistics, doctors, or hospital facilities.'}</p>
                </div>
              )}
            </div>
          </section>
        </div>

        <aside className="voice-safety-note">
          <strong>Clinical safety:</strong> Compass provides administrative help and general information. It does not diagnose, prescribe, or replace emergency care. For an emergency, call 108.
        </aside>
      </section>
    </main>
  )
}
