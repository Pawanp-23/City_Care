import { useRef } from 'react'

export function useTilt() {
  const ref = useRef(null)

  const onMouseMove = (event) => {
    const card = ref.current
    if (!card || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const bounds = card.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width - 0.5
    const y = (event.clientY - bounds.top) / bounds.height - 0.5
    card.style.setProperty('--tilt-x', `${(y * -5).toFixed(2)}deg`)
    card.style.setProperty('--tilt-y', `${(x * 5).toFixed(2)}deg`)
  }

  const onMouseLeave = () => {
    ref.current?.style.setProperty('--tilt-x', '0deg')
    ref.current?.style.setProperty('--tilt-y', '0deg')
  }

  return { ref, onMouseMove, onMouseLeave }
}

