import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

const INPUT_SAMPLE_RATE = 16000
const OUTPUT_SAMPLE_RATE = 24000
const LIVE_SOCKET = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained'

const PUBLIC_TOOLS = [
  {
    name: 'get_doctors',
    description: 'List currently available CityCare doctors, specialties, qualifications, and consultation hours.',
    parameters: { type: 'OBJECT', properties: {} },
  },
  {
    name: 'get_clinic_facilities',
    description: 'Get current public CityCare clinic details, hours, services, facilities, and contact information.',
    parameters: { type: 'OBJECT', properties: {} },
  },
]

const PATIENT_TOOLS = [
  {
    name: 'get_my_appointments',
    description: "Read only the signed-in patient's appointments and confirmation status.",
    parameters: { type: 'OBJECT', properties: {} },
  },
  {
    name: 'get_my_prescriptions',
    description: "Read only the signed-in patient's prescriptions. Never infer a diagnosis or change medicine instructions.",
    parameters: { type: 'OBJECT', properties: {} },
  },
  {
    name: 'get_available_slots',
    description: 'Get available appointment slots for an exact doctor id and ISO date returned by get_doctors.',
    parameters: {
      type: 'OBJECT',
      properties: {
        doctor_id: { type: 'STRING' },
        date: { type: 'STRING', description: 'ISO date YYYY-MM-DD, no more than seven days ahead.' },
      },
      required: ['doctor_id', 'date'],
    },
  },
  {
    name: 'book_appointment',
    description: 'Book after the patient explicitly confirms the repeated doctor, date, slot, and reason. Never call on an implied confirmation.',
    parameters: {
      type: 'OBJECT',
      properties: {
        doctor_id: { type: 'STRING' },
        appointment_date: { type: 'STRING' },
        slot: { type: 'STRING' },
        reason: { type: 'STRING' },
        confirmed: { type: 'BOOLEAN', description: 'True only after the patient explicitly said yes to the full summary.' },
      },
      required: ['doctor_id', 'appointment_date', 'slot', 'reason', 'confirmed'],
    },
  },
  {
    name: 'open_booking_page',
    description: 'Open the signed-in patient booking page when the patient asks to see or complete booking visually.',
    parameters: { type: 'OBJECT', properties: {} },
  },
]

const DOCTOR_TOOLS = [
  {
    name: 'get_my_schedule',
    description: "Get the signed-in doctor's authorized schedule for an ISO date.",
    parameters: {
      type: 'OBJECT',
      properties: { date: { type: 'STRING', description: 'ISO date YYYY-MM-DD.' } },
      required: ['date'],
    },
  },
  {
    name: 'get_clinic_statistics',
    description: "Get the signed-in doctor's clinic workload statistics.",
    parameters: { type: 'OBJECT', properties: {} },
  },
]

function bytesToBase64(bytes) {
  let binary = ''
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, Math.min(index + 0x8000, bytes.length)))
  }
  return btoa(binary)
}

function pcm16Base64(samples, sourceRate) {
  const ratio = sourceRate / INPUT_SAMPLE_RATE
  const targetLength = Math.max(1, Math.round(samples.length / ratio))
  const buffer = new ArrayBuffer(targetLength * 2)
  const view = new DataView(buffer)
  for (let index = 0; index < targetLength; index += 1) {
    const sourceIndex = index * ratio
    const low = Math.floor(sourceIndex)
    const high = Math.min(low + 1, samples.length - 1)
    const blend = sourceIndex - low
    const value = Math.max(-1, Math.min(1, samples[low] * (1 - blend) + samples[high] * blend))
    view.setInt16(index * 2, value < 0 ? value * 0x8000 : value * 0x7fff, true)
  }
  return bytesToBase64(new Uint8Array(buffer))
}

function pcm24kFromBase64(data) {
  const binary = atob(data)
  const samples = new Float32Array(Math.floor(binary.length / 2))
  for (let index = 0; index < samples.length; index += 1) {
    const raw = binary.charCodeAt(index * 2) | (binary.charCodeAt(index * 2 + 1) << 8)
    samples[index] = (raw >= 0x8000 ? raw - 0x10000 : raw) / 0x8000
  }
  return samples
}

function joinTranscript(previous, incoming) {
  const before = previous.trim()
  const next = incoming.trim()
  if (!before) return next
  if (!next || before.endsWith(next)) return before
  if (next.startsWith(before)) return next
  return `${before} ${next}`
}

export function useHospitalVoiceAgent(user) {
  const [status, setStatus] = useState('idle')
  const [voiceState, setVoiceState] = useState('idle')
  const [transcript, setTranscript] = useState([])
  const [error, setError] = useState('')
  const socketRef = useRef(null)
  const streamRef = useRef(null)
  const contextRef = useRef(null)
  const processorRef = useRef(null)
  const inputRef = useRef(null)
  const silenceRef = useRef(null)
  const playbackRef = useRef(new Set())
  const nextPlaybackRef = useRef(0)
  const manualCloseRef = useRef(false)
  const activeRef = useRef({ user: null, assistant: null })

  const addTranscript = useCallback((speaker, text, streaming = false) => {
    if (!text?.trim()) return
    setTranscript((previous) => {
      const key = streaming ? activeRef.current[speaker] : null
      const index = key ? previous.findIndex((line) => line.key === key) : -1
      if (index >= 0) {
        return previous.map((line, itemIndex) => itemIndex === index
          ? { ...line, text: joinTranscript(line.text, text) }
          : line)
      }
      const next = [...previous, { speaker, text: text.trim(), key: `${speaker}-${Date.now()}-${Math.random()}` }]
      if (streaming) activeRef.current[speaker] = next.at(-1).key
      return next
    })
  }, [])

  const finishTranscript = useCallback((speaker) => { activeRef.current[speaker] = null }, [])

  const clearPlayback = useCallback(() => {
    playbackRef.current.forEach((source) => { try { source.stop() } catch { /* finished */ } })
    playbackRef.current.clear()
    if (contextRef.current) nextPlaybackRef.current = contextRef.current.currentTime
  }, [])

  const releaseAudio = useCallback(() => {
    clearPlayback()
    if (processorRef.current?.port) processorRef.current.port.onmessage = null
    processorRef.current?.disconnect()
    inputRef.current?.disconnect()
    silenceRef.current?.disconnect()
    processorRef.current = null
    inputRef.current = null
    silenceRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    const context = contextRef.current
    contextRef.current = null
    if (context && context.state !== 'closed') context.close().catch(() => {})
  }, [clearPlayback])

  const stop = useCallback(async () => {
    manualCloseRef.current = true
    const socket = socketRef.current
    socketRef.current = null
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'Voice session ended')
    releaseAudio()
    setStatus('idle')
    setVoiceState('idle')
  }, [releaseAudio])

  const runTool = useCallback(async (name, args = {}) => {
    if (name === 'get_doctors') return api.get('/api/v1/doctors')
    if (name === 'get_clinic_facilities') return api.get('/api/v1/clinic')
    if (name === 'get_my_appointments') return api.get('/api/v1/appointments/mine', { auth: true })
    if (name === 'get_my_prescriptions') {
      const items = await api.get('/api/v1/prescriptions/mine', { auth: true })
      return items.map(({ diagnosis, medicines, instructions, created_at }) => ({ diagnosis, medicines, instructions, created_at }))
    }
    if (name === 'get_available_slots') {
      return api.get(`/api/v1/appointments/free-slots?date=${encodeURIComponent(args.date || '')}&doctor_id=${encodeURIComponent(args.doctor_id || '')}`)
    }
    if (name === 'book_appointment') {
      if (args.confirmed !== true) return { error: 'Booking blocked because explicit confirmation was not received.' }
      if (String(args.reason || '').trim().length < 10) return { error: 'Ask for a clearer visit reason of at least 10 characters.' }
      return api.post('/api/v1/appointments', {
        doctor_id: args.doctor_id,
        appointment_date: args.appointment_date,
        slot: args.slot,
        reason: String(args.reason).trim(),
        temperature_f: null,
        symptoms: [],
      }, { auth: true })
    }
    if (name === 'open_booking_page') {
      setTimeout(() => window.location.assign('/book'), 500)
      return { opened: true }
    }
    if (name === 'get_my_schedule') return api.get(`/api/v1/doctor/schedule?date=${encodeURIComponent(args.date || '')}`, { auth: true })
    if (name === 'get_clinic_statistics') return api.get('/api/v1/doctor/stats', { auth: true })
    return { error: 'Unsupported CityCare tool.' }
  }, [])

  const playAudio = useCallback((base64Audio) => {
    const context = contextRef.current
    if (!context || !base64Audio) return
    const samples = pcm24kFromBase64(base64Audio)
    const buffer = context.createBuffer(1, samples.length, OUTPUT_SAMPLE_RATE)
    buffer.copyToChannel(samples, 0)
    const source = context.createBufferSource()
    source.buffer = buffer
    source.connect(context.destination)
    const startAt = Math.max(context.currentTime + 0.03, nextPlaybackRef.current)
    source.start(startAt)
    nextPlaybackRef.current = startAt + buffer.duration
    playbackRef.current.add(source)
    source.onended = () => playbackRef.current.delete(source)
    setVoiceState('speaking')
  }, [])

  const connect = useCallback(async () => {
    await stop()
    manualCloseRef.current = false
    setStatus('connecting')
    setVoiceState('idle')
    setError('')
    setTranscript([])
    activeRef.current = { user: null, assistant: null }

    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('This browser does not support microphone access. Use current Chrome or Edge.')
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (!AudioContextClass) throw new Error('This browser does not support live audio playback.')

      const session = await api.get('/api/v1/assistant/live-session', { auth: true })
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      streamRef.current = stream
      const context = new AudioContextClass()
      contextRef.current = context
      await context.resume()

      const input = context.createMediaStreamSource(stream)
      const silence = context.createGain()
      silence.gain.value = 0
      inputRef.current = input
      silenceRef.current = silence

      const socket = new WebSocket(`${LIVE_SOCKET}?access_token=${encodeURIComponent(session.token)}`)
      socketRef.current = socket
      let setupReady = false
      const sendAudio = (samples) => {
        if (!setupReady || socket.readyState !== WebSocket.OPEN || !samples?.length) return
        socket.send(JSON.stringify({ realtimeInput: { audio: { data: pcm16Base64(samples, context.sampleRate), mimeType: 'audio/pcm;rate=16000' } } }))
      }

      let microphoneNode
      try {
        if (!context.audioWorklet || typeof AudioWorkletNode === 'undefined') throw new Error('AudioWorklet unavailable')
        await context.audioWorklet.addModule(new URL('../audio/citycare-microphone-processor.js', import.meta.url))
        microphoneNode = new AudioWorkletNode(context, 'citycare-microphone-processor', { channelCount: 1, channelCountMode: 'explicit' })
        microphoneNode.port.onmessage = ({ data }) => sendAudio(new Float32Array(data))
      } catch {
        microphoneNode = context.createScriptProcessor(4096, 1, 1)
        microphoneNode.onaudioprocess = ({ inputBuffer }) => sendAudio(inputBuffer.getChannelData(0))
      }
      processorRef.current = microphoneNode
      input.connect(microphoneNode)
      microphoneNode.connect(silence)
      silence.connect(context.destination)

      const tools = [...PUBLIC_TOOLS, ...(session.role === 'PATIENT' ? PATIENT_TOOLS : DOCTOR_TOOLS)]
      socket.onopen = () => socket.send(JSON.stringify({
        setup: {
          model: `models/${session.model}`,
          generationConfig: {
            responseModalities: ['AUDIO'],
            speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } } },
          },
          systemInstruction: { parts: [{ text: session.instructions }] },
          inputAudioTranscription: {},
          outputAudioTranscription: {},
          tools: [{ functionDeclarations: tools }],
        },
      }))

      socket.onmessage = async ({ data }) => {
        try {
          const raw = typeof data === 'string' ? data : await data.text()
          const message = JSON.parse(raw)
          if (message.error) { setError(message.error.message || 'Gemini Live reported a session problem.'); return }
          if (message.setupComplete) {
            setupReady = true
            setStatus('connected')
            setVoiceState('listening')
            socket.send(JSON.stringify({ clientContent: { turns: [{ role: 'user', parts: [{ text: 'Start with the required opening line, then wait for the user.' }] }], turnComplete: true } }))
            return
          }
          const content = message.serverContent
          if (content?.interrupted) { clearPlayback(); finishTranscript('assistant'); setVoiceState('listening') }
          if (content?.inputTranscription?.text) { finishTranscript('assistant'); addTranscript('user', content.inputTranscription.text, true) }
          content?.modelTurn?.parts?.forEach((part) => { if (part.inlineData?.data) playAudio(part.inlineData.data) })
          if (content?.outputTranscription?.text) { finishTranscript('user'); addTranscript('assistant', content.outputTranscription.text, true) }
          if (content?.turnComplete) { finishTranscript('assistant'); setVoiceState('listening') }

          const calls = message.toolCall?.functionCalls || []
          if (calls.length) {
            const functionResponses = await Promise.all(calls.map(async (call) => {
              try {
                return { name: call.name, id: call.id, response: { result: await runTool(call.name, call.args || {}) } }
              } catch (toolError) {
                return { name: call.name, id: call.id, response: { result: { error: toolError?.message || 'CityCare tool failed.' } } }
              }
            }))
            if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ toolResponse: { functionResponses } }))
          }
        } catch {
          setError('A live voice event could not be processed. Reconnect if the conversation stops.')
        }
      }
      socket.onerror = () => setError('The Gemini Live connection failed. Check API access, quota, and your internet connection.')
      socket.onclose = (event) => {
        if (manualCloseRef.current) return
        socketRef.current = null
        releaseAudio()
        setStatus('disconnected')
        setVoiceState('idle')
        setError(event.reason || 'The live voice connection ended. Reconnect to continue.')
      }
    } catch (connectError) {
      await stop()
      const denied = connectError?.name === 'NotAllowedError' || /permission|not.allowed/i.test(connectError?.message || '')
      setError(denied
        ? 'Microphone access is blocked. Allow it in browser site settings, reload, then reconnect.'
        : (connectError?.message || 'Could not start CityCare Compass Live.'))
      setStatus('disconnected')
    }
  }, [addTranscript, clearPlayback, finishTranscript, playAudio, releaseAudio, runTool, stop])

  useEffect(() => () => { stop() }, [stop])

  return { status, voiceState, transcript, error, connect, stop, user }
}
