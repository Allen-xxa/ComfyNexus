/**
 * ANSI 日志消息渲染组件
 *
 * 将携带 ANSI 颜色序列的日志文本渲染为带颜色/加粗样式的 span 片段，
 * 用于终端页面还原 ComfyUI 等进程输出的真实终端配色。
 * 不含 ANSI 序列的消息走快速路径，直接按纯文本渲染。
 */

import { parseAnsi, hasAnsi } from '@/utils/ansi'
import { cn } from '@/lib/utils'

// ANSI 16 色 -> Tailwind 类（深浅主题各自取可读的色阶）
const ANSI_COLOR_CLASSES: Record<number, string> = {
  0: 'text-neutral-500',
  1: 'text-red-600 dark:text-red-400',
  2: 'text-green-600 dark:text-green-400',
  3: 'text-yellow-600 dark:text-yellow-300',
  4: 'text-blue-600 dark:text-blue-400',
  5: 'text-fuchsia-600 dark:text-fuchsia-400',
  6: 'text-cyan-600 dark:text-cyan-400',
  7: 'text-neutral-400 dark:text-neutral-300',
  8: 'text-neutral-500',
  9: 'text-red-500 dark:text-red-300',
  10: 'text-green-500 dark:text-green-300',
  11: 'text-yellow-500 dark:text-yellow-200',
  12: 'text-blue-500 dark:text-blue-300',
  13: 'text-fuchsia-500 dark:text-fuchsia-300',
  14: 'text-cyan-500 dark:text-cyan-300',
  15: 'text-neutral-600 dark:text-white'
}

interface AnsiLogMessageProps {
  message: string
}

export function AnsiLogMessage({ message }: AnsiLogMessageProps) {
  if (!hasAnsi(message)) {
    return message
  }
  return parseAnsi(message).map((segment, index) => {
    if (segment.colorIndex === undefined && !segment.bold) {
      return <span key={index}>{segment.text}</span>
    }
    return (
      <span
        key={index}
        className={cn(
          segment.colorIndex !== undefined && ANSI_COLOR_CLASSES[segment.colorIndex],
          segment.bold && 'font-bold'
        )}
      >
        {segment.text}
      </span>
    )
  })
}
