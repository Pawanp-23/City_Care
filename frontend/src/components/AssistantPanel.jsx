import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'

// ── Icons ────────────────────────────────────────────────────────────────────
const MicIcon = ({ active }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="2" width="6" height="12" rx="3" fill={active ? 'currentColor' : 'none'} />
    <path d="M5 10a7 7 0 0 0 14 0" />
    <line x1="12" y1="19" x2="12" y2="22" />
    <line x1="8" y1="22" x2="16" y2="22" />
  </svg>
)

// ── Voice helpers ─────────────────────────────────────────────────────────────
// Pre-load voices as soon as possible (Chrome loads them async)
let _cachedVoice = null
function getBestVoice() {
  if (_cachedVoice) return _cachedVoice
  const voices = window.speechSynthesis?.getVoices() ?? []
  // Prefer local English voices: Google UK > Google US > any local en
  _cachedVoice =
    voices.find(v => v.name.includes('Google UK English Female')) ||
    voices.find(v => v.name.includes('Google UK English Male')) ||
    voices.find(v => v.name.includes('Google US English')) ||
    voices.find(v => v.lang.startsWith('en') && v.localService) ||
    voices.find(v => v.lang.startsWith('en')) ||
    null
  return _cachedVoice
}
// Warm up voice list immediately
if (typeof window !== 'undefined' && window.speechSynthesis) {
  window.speechSynthesis.getVoices()
  window.speechSynthesis.addEventListener('voiceschanged', () => {
    _cachedVoice = null
    getBestVoice()
  })
}

const MIC_ERROR_MESSAGES = {
  'not-allowed': 'Microphone access is blocked. Open the site controls beside the address bar, set Microphone to Allow, then reload this page.',
  'service-not-allowed': 'Speech recognition is blocked by this browser. Allow microphone access for this site, then reload the page.',
  'audio-capture': 'No working microphone was found. Connect or enable a microphone, then try again.',
  network: 'The browser speech service could not connect. Check your internet connection, or type your message instead.',
  'language-not-supported': 'This browser cannot recognise English (India). Update Chrome or use the text box.',
  'no-speech': 'I didn\'t hear anything. Tap the microphone and speak after “Listening” appears.',
  aborted: '',
}

function microphoneErrorMessage(code) {
  return MIC_ERROR_MESSAGES[code] || `Voice input stopped (${code || 'unknown error'}). Check the microphone and try again.`
}

function speakText(text, { onStart, onEnd } = {}) {
  if (!('speechSynthesis' in window) || !text) return
  window.speechSynthesis.cancel()
  const utt = new SpeechSynthesisUtterance(text)
  utt.rate = 1.05    // slightly faster = more natural
  utt.pitch = 1.0
  utt.volume = 1
  const voice = getBestVoice()
  if (voice) { utt.voice = voice; utt.lang = voice.lang }
  else utt.lang = 'en-US'
  if (onStart) utt.onstart = onStart
  utt.onend = () => onEnd?.()
  utt.onerror = () => onEnd?.()
  window.speechSynthesis.speak(utt)
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function AssistantPanel() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [speaking, setSpeaking] = useState(false)
  const [voiceMode, setVoiceMode] = useState(false)  // true when last interaction was voice
  const messagesEndRef = useRef(null)
  const recognitionRef = useRef(null)
  const recognitionActiveRef = useRef(false)
  const finalTranscriptSentRef = useRef(false)
  const isPatient = user?.role === 'PATIENT'

  // Voice uses a dedicated low-latency endpoint; text uses the full tool-calling one
  const textEndpoint = isPatient ? '/api/v1/assistant/patient-chat' : '/api/v1/assistant/chat'
  const voiceEndpoint = isPatient ? '/api/v1/assistant/patient-voice' : '/api/v1/assistant/voice-chat'

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel()
    setSpeaking(false)
  }, [])

  const appendVoiceError = useCallback((text) => {
    if (!text) return
    setMessages(prev => {
      if (prev.at(-1)?.voiceError === text) return prev
      return [...prev, { role: 'model', text, error: true, voiceError: text }]
    })
  }, [])

    // Core send — isVoice flag routes to the faster voice endpoint
  const send = useCallback(async (draft, { isVoice = false } = {}) => {
    const message = (draft ?? input).trim()
    if (!message || loading) return

    setVoiceMode(isVoice)
    const history = messages.slice(-4).map(m => ({ role: m.role, text: m.text }))
    setMessages(prev => [...prev, { role: 'user', text: message, voice: isVoice }])
    setInput('')
    setTranscript('')
    setLoading(true)

    const endpoint = isVoice ? voiceEndpoint : textEndpoint

    try {
      const data = await api.post(endpoint, { message, history }, { auth: true })
      const reply = data.response || 'Sorry, I didn\'t get that. Try again?'
      setMessages(prev => [...prev, {
        role: 'model', text: reply,
        tools: data.tools_used || [],
        sources: data.sources || [],
        voice: isVoice,
      }])
      // Speak reply for voice interactions
      if (isVoice) {
        speakText(reply, { onStart: () => setSpeaking(true), onEnd: () => setSpeaking(false) })
      }
    } catch (err) {
      const errText = err instanceof ApiError ? err.message : 'Couldn\'t reach CityCare Compass. Try again!'
      setMessages(prev => [...prev, { role: 'model', text: errText, error: true }])
      if (isVoice) speakText(errText, { onEnd: () => setSpeaking(false) })
    } finally {
      setLoading(false)
    }
  }, [input, loading, messages, textEndpoint, voiceEndpoint])


  const startListening = useCallback(async () => {
    if (recognitionActiveRef.current) return
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Recognition) {
      appendVoiceError('Live voice input is not supported in this browser. Open CityCare in the latest Chrome or Edge, or type your message instead.')
      return
    }
    if (!window.isSecureContext) {
      appendVoiceError('Microphone access requires a secure page. Open CityCare on localhost or HTTPS, then try again.')
      return
    }

    try {
      const permission = await navigator.permissions?.query({ name: 'microphone' })
      if (permission?.state === 'denied') {
        appendVoiceError(MIC_ERROR_MESSAGES['not-allowed'])
        return
      }
    } catch {
      // Some browsers do not expose microphone state; SpeechRecognition will
      // request permission itself and report an actionable error below.
    }

    stopSpeaking()  // stop any TTS before listening

    const rec = new Recognition()
    rec.lang = 'en-IN'
    rec.continuous = false
    rec.interimResults = true
    rec.maxAlternatives = 1

    finalTranscriptSentRef.current = false
    rec.onstart = () => {
      recognitionActiveRef.current = true
      setListening(true)
      setTranscript('')
    }
    rec.onend = () => {
      recognitionActiveRef.current = false
      if (recognitionRef.current === rec) recognitionRef.current = null
      setListening(false)
    }
    rec.onerror = (e) => {
      recognitionActiveRef.current = false
      setListening(false)
      setTranscript('')
      appendVoiceError(microphoneErrorMessage(e.error))
    }
    rec.onresult = (e) => {
      let interimText = ''
      let finalText = ''
      for (let index = e.resultIndex; index < e.results.length; index += 1) {
        const result = e.results[index]
        if (result.isFinal) finalText += result[0].transcript
        else interimText += result[0].transcript
      }
      setTranscript(finalText || interimText)
      if (finalText.trim() && !finalTranscriptSentRef.current) {
        finalTranscriptSentRef.current = true
        setTranscript('')
        void send(finalText, { isVoice: true })
      }
    }
    recognitionRef.current = rec
    try {
      rec.start()
    } catch {
      recognitionRef.current = null
      recognitionActiveRef.current = false
      setListening(false)
      appendVoiceError('The microphone is already busy. Stop any other recording app, then try again.')
    }
  }, [appendVoiceError, send, stopSpeaking])

  const stopListening = useCallback(() => {
    try {
      recognitionRef.current?.stop()
    } catch {
      recognitionRef.current = null
      recognitionActiveRef.current = false
    }
    setListening(false)
  }, [])

  const closePanel = useCallback(() => {
    stopListening()
    stopSpeaking()
    setOpen(false)
  }, [stopListening, stopSpeaking])

  useEffect(() => () => {
    const recognition = recognitionRef.current
    if (recognition) {
      recognition.onstart = null
      recognition.onend = null
      recognition.onerror = null
      recognition.onresult = null
      try { recognition.abort() } catch { /* already stopped */ }
    }
    window.speechSynthesis?.cancel()
  }, [])

  const clearChat = useCallback(() => {
    stopSpeaking()
    setMessages([])
    setInput('')
    setTranscript('')
  }, [stopSpeaking])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(undefined, { isVoice: false }) }
  }

  const roleLabel = isPatient ? 'Prescription & Clinic Assistant' : 'Doctor Assistant'
  const placeholder = listening
    ? 'Listening… speak naturally'
    : isPatient
      ? 'Ask about your prescription, clinic, or anything…'
      : 'Ask about your schedule, patients, or anything…'

  return (
    <div id="assistant">
      <button type="button" className="compass-fab" onClick={() => setOpen(v => !v)} aria-expanded={open} title="CityCare Compass AI Assistant">
        <span aria-hidden>✦</span> CityCare Compass
      </button>

      {open && (
        <section className="assistant-panel" aria-label="CityCare Compass assistant">
          <header>
            <div>
              <p className="eyebrow">{roleLabel}</p>
              <h2>CityCare Compass</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {messages.length > 0 && (
                <button type="button" onClick={clearChat} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: 'var(--text-muted, #888)', padding: '4px 8px' }}>
                  Clear
                </button>
              )}
              <button type="button" onClick={closePanel} aria-label="Close">✕</button>
            </div>
          </header>

          <p className="assistant-note">
            {isPatient ? 'Ask about your prescriptions, clinic, or health info.' : 'Ask about your schedule, patients, or clinic.'}{' '}
            <strong>Tap mic for a quick question</strong> — or{' '}
            <Link className="assistant-live-link" to="/voice" onClick={closePanel}>open realtime voice</Link>.
          </p>

          <div className="assistant-messages">
            {messages.length === 0 ? (
              <div className="assistant-welcome">
                <strong>Hey! Ask me anything 👋</strong>
                <p>Speak or type — I’ll keep the answer clear and useful.</p>
              </div>
            ) : (
              messages.map((m, i) => (
                <article key={`${m.role}-${i}`} className={`assistant-message assistant-${m.role}${m.error ? ' assistant-error' : ''}`}>
                  <p>{m.text}</p>
                  {m.tools?.length > 0 && <small>Used: {m.tools.map(t => t.replaceAll('_', ' ')).join(', ')}</small>}
                  {m.sources?.length > 0 && <small>Sources: {m.sources.join('; ')}</small>}
                </article>
              ))
            )}
            {transcript && (
              <article className="assistant-message assistant-user" style={{ opacity: 0.55, fontStyle: 'italic' }}>
                <p>🎙 {transcript}</p>
              </article>
            )}
            {loading && (
              <article className="assistant-message assistant-model assistant-thinking">
                <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
              </article>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Voice status bar */}
          {(listening || speaking) && (
            <div className="voice-status-bar">
              {listening && <><span className="voice-pulse" />Listening…</>}
              {speaking && !listening && (
                <>
                  <span className="voice-wave">
                    <span /><span /><span /><span /><span />
                  </span>
                  Speaking…
                  <button type="button" onClick={stopSpeaking} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: '11px', color: 'inherit', padding: '2px 6px' }}>
                    Stop ✕
                  </button>
                </>
              )}
            </div>
          )}

          <form onSubmit={(e) => { e.preventDefault(); send(undefined, { isVoice: false }) }}>
            <label className="sr-only" htmlFor="compass-input">Message CityCare Compass</label>
            <div className="assistant-input-wrap">
              <textarea
                id="compass-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                maxLength={1800}
                placeholder={placeholder}
                rows={2}
                disabled={listening}
              />
              <button
                type="button"
                onClick={listening ? stopListening : startListening}
                disabled={loading}
                aria-label={listening ? 'Stop listening' : 'Start voice input'}
                title={listening ? 'Stop' : 'Speak'}
                className={`mic-btn${listening ? ' mic-btn--active' : ''}`}
              >
                <MicIcon active={listening} />
              </button>
            </div>
            <div className="assistant-composer-footer">
              <span>
                {listening ? '🔴 Listening — speak naturally, I\'ll send when you pause' : 'Enter to send · Mic to speak'}
              </span>
              <button type="submit" disabled={loading || (!input.trim() && !listening)}>
                {loading ? 'Thinking…' : 'Send'}
              </button>
            </div>
          </form>
        </section>
      )}
    </div>
  )
}
