/**
 * AnsiLogMessage 组件测试
 */

import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { AnsiLogMessage } from '../AnsiLogMessage'

const ESC = '\u001b'

describe('AnsiLogMessage', () => {
  it('纯文本消息原样渲染', () => {
    const { container } = render(<AnsiLogMessage message="Total VRAM 16304 MB" />)
    expect(container.textContent).toBe('Total VRAM 16304 MB')
    expect(container.querySelector('span')).toBeNull()
  })

  it('ANSI 序列渲染为带色 span 且不残留控制码', () => {
    const message = `${ESC}[32m[INFO]${ESC}[0m Adding extra search path`
    const { container } = render(<AnsiLogMessage message={message} />)

    expect(container.textContent).toBe('[INFO] Adding extra search path')

    const colored = container.querySelector('span.text-green-600')
    expect(colored).not.toBeNull()
    expect(colored?.textContent).toBe('[INFO]')
  })

  it('加粗黄色 WARNING 标签', () => {
    const message = `${ESC}[1m${ESC}[33m[WARNING]${ESC}[0m deprecated API`
    const { container } = render(<AnsiLogMessage message={message} />)

    expect(container.textContent).toBe('[WARNING] deprecated API')

    const colored = container.querySelector('span.font-bold')
    expect(colored).not.toBeNull()
    expect(colored?.textContent).toBe('[WARNING]')
    expect(colored?.className).toContain('text-yellow-600')
  })
})
