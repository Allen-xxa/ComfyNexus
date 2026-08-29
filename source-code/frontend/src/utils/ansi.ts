/**
 * ANSI 转义序列解析工具
 *
 * ComfyUI 及部分插件（如 Crystools）的日志输出携带 ANSI SGR 颜色序列
 * （如 \u001b[32m[INFO]\u001b[0m）。本模块将日志文本解析为带颜色/加粗
 * 属性的片段，供终端页面按真实颜色渲染；同时提供 stripAnsi 用于复制、
 * AI 分析等需要纯文本的场景。
 *
 * 支持的 SGR 参数：0（重置）、1（加粗）、22（取消加粗）、30-37（标准
 * 前景色）、39（恢复默认前景色）、90-97（亮前景色）。38（扩展前景色）
 * 与 48（扩展背景色）按 5;n / 2;r;g;b 形式正确跳过参数但不着色，其余
 * 参数一律忽略。非 SGR 的 CSI 序列（光标控制等）直接剥离。
 */

// CSI 序列: ESC [ 参数字节 中间字节 终止字节
// eslint-disable-next-line no-control-regex
const CSI_PATTERN = /\u001b\[([0-9;]*)([\u0020-\u002f]*[\u0040-\u007e])/g

// 孤立的 ESC 字符（未构成完整 CSI 序列）
// eslint-disable-next-line no-control-regex
const LONE_ESC_PATTERN = /\u001b/g

export interface AnsiSegment {
  text: string
  /** ANSI 16 色索引: 0-7 标准色, 8-15 亮色 */
  colorIndex?: number
  bold?: boolean
}

interface SgrState {
  colorIndex?: number
  bold: boolean
}

/**
 * 应用一条 SGR 序列的参数列表到当前状态
 */
function applySgrParams(params: string, state: SgrState): SgrState {
  const next: SgrState = { ...state }
  // 空参数串等价于 0（重置）
  const codes = (params === '' ? '0' : params).split(';').map(p => (p === '' ? 0 : parseInt(p, 10)))

  let i = 0
  while (i < codes.length) {
    const code = codes[i]
    if (code === 0) {
      next.colorIndex = undefined
      next.bold = false
    } else if (code === 1) {
      next.bold = true
    } else if (code === 22) {
      next.bold = false
    } else if (code >= 30 && code <= 37) {
      next.colorIndex = code - 30
    } else if (code === 39) {
      next.colorIndex = undefined
    } else if (code >= 90 && code <= 97) {
      next.colorIndex = code - 90 + 8
    } else if (code === 38 || code === 48) {
      // 扩展色: 38;5;n 跳 2 个参数, 38;2;r;g;b 跳 4 个参数（不着色，只保证后续参数不被误读）
      const mode = codes[i + 1]
      if (mode === 5) {
        i += 2
      } else if (mode === 2) {
        i += 4
      }
    }
    // 其余参数（背景色、反显等）忽略
    i += 1
  }
  return next
}

/**
 * 将含 ANSI 序列的文本解析为带样式属性的片段数组。
 * 相邻的同样式片段会被合并；不含 ANSI 序列时返回单片段。
 */
export function parseAnsi(text: string): AnsiSegment[] {
  const segments: AnsiSegment[] = []
  let state: SgrState = { bold: false }

  const pushText = (chunk: string) => {
    if (!chunk) {
      return
    }
    const last = segments[segments.length - 1]
    if (last && last.colorIndex === state.colorIndex && (last.bold ?? false) === state.bold) {
      last.text += chunk
      return
    }
    const segment: AnsiSegment = { text: chunk }
    if (state.colorIndex !== undefined) {
      segment.colorIndex = state.colorIndex
    }
    if (state.bold) {
      segment.bold = true
    }
    segments.push(segment)
  }

  let lastIndex = 0
  CSI_PATTERN.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = CSI_PATTERN.exec(text)) !== null) {
    pushText(text.slice(lastIndex, match.index))
    lastIndex = match.index + match[0].length

    const [, params, finalByte] = match
    if (finalByte === 'm') {
      state = applySgrParams(params, state)
    }
    // 非 SGR 的 CSI 序列（光标控制等）直接丢弃
  }
  pushText(text.slice(lastIndex))

  // 剥离残留的孤立 ESC 字符
  for (const segment of segments) {
    segment.text = segment.text.replace(LONE_ESC_PATTERN, '')
  }

  const result = segments.filter(segment => segment.text !== '')
  return result.length > 0 ? result : [{ text: '' }]
}

/**
 * 剥离文本中的全部 ANSI 序列，返回纯文本
 */
export function stripAnsi(text: string): string {
  return text.replace(CSI_PATTERN, '').replace(LONE_ESC_PATTERN, '')
}

/**
 * 判断文本是否包含 ANSI 转义序列（渲染快速路径用）
 */
export function hasAnsi(text: string): boolean {
  return text.includes('\u001b')
}
