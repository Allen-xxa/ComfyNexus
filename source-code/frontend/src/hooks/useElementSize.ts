import { useCallback, useEffect, useRef, useState } from 'react'

interface ElementSize {
  width: number
  height: number
}

/** 与 ResizeObserver 的 contentRect 同口径：去掉内边距，不含边框与滚动条 */
function readContentSize(node: HTMLElement): ElementSize {
  const style = getComputedStyle(node)
  return {
    width: node.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
    height: node.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
  }
}

/**
 * 监听元素内容区尺寸，供 react-window 等需要明确像素的虚拟列表使用。
 *
 * 返回回调 ref：加载态/空态/就绪态各自渲染不同节点，被测量的元素会被换掉。
 * 只在挂载时 observe 一次的写法会盯住已脱离文档的旧节点，尺寸永远停在 0。
 */
export function useElementSize<T extends HTMLElement>(): [(node: T | null) => void, ElementSize] {
  const [size, setSize] = useState<ElementSize>({ width: 0, height: 0 })
  const observerRef = useRef<ResizeObserver | null>(null)

  const ref = useCallback((node: T | null) => {
    observerRef.current?.disconnect()
    observerRef.current = null
    if (!node) return

    // 首次挂载可能还没有渲染帧（桌面端窗口未显示时），先同步量一次兜底
    setSize(readContentSize(node))

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }))
    })
    observer.observe(node)
    observerRef.current = observer
  }, [])

  useEffect(() => () => observerRef.current?.disconnect(), [])

  return [ref, size]
}
