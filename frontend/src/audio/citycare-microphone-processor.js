class CityCareMicrophoneProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.parts = []
    this.length = 0
    this.chunkLength = Math.max(1, Math.round(sampleRate / 10))
  }

  process(inputs) {
    const samples = inputs[0]?.[0]
    if (!samples?.length) return true
    let offset = 0
    while (offset < samples.length) {
      const available = Math.min(this.chunkLength - this.length, samples.length - offset)
      this.parts.push(samples.slice(offset, offset + available))
      this.length += available
      offset += available
      if (this.length === this.chunkLength) {
        const chunk = new Float32Array(this.length)
        let cursor = 0
        this.parts.forEach((part) => { chunk.set(part, cursor); cursor += part.length })
        this.port.postMessage(chunk.buffer, [chunk.buffer])
        this.parts = []
        this.length = 0
      }
    }
    return true
  }
}

registerProcessor('citycare-microphone-processor', CityCareMicrophoneProcessor)
