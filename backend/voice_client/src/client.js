import { PipecatClient } from '@pipecat-ai/client-js'
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport'

export const VOICE_SERVER = import.meta.env.VITE_PIPECAT_WEBRTC_URL || 'http://127.0.0.1:7860/api/offer'
export const voiceClient = new PipecatClient({
  transport: new SmallWebRTCTransport({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    waitForICEGathering: true,
  }),
  enableMic: true,
  enableCam: false,
})
