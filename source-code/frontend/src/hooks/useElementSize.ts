import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

interface ElementSize {
  width: number
  height: number
}

/**
 * 监听元素内容区尺寸，供 react-window 等需要明确像素的虚拟列表使用。
 */
export function useElementSize<T extends HTMLElement>(): [RefObject<T | null>, ElementSize] {
  const ref = useRef<T>(null)
  const [size, setSize] = useState<ElementSize>({ width: 0, height: 0 })

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      setSize({
        width: entry.contentRect.width,
        height: entry.contentRect.height
      })
    })

    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return [ref, size]
}
