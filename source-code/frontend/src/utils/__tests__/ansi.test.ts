/**
 * ANSI 转义序列解析工具单元测试
 *
 * 样本取自 ComfyUI 与 Crystools 的真实日志输出
 */

import { describe, it, expect } from 'vitest'
import { parseAnsi, stripAnsi, hasAnsi } from '../ansi'

const ESC = '\u001b'

describe('parseAnsi', () => {
  it('不含 ANSI 序列时返回单个无样式片段', () => {
    const text = 'Total VRAM 16304 MB, total RAM 48741 MB'
    expect(parseAnsi(text)).toEqual([{ text }])
  })

  it('解析 ComfyUI INFO 级别标签（绿色）', () => {
    const text = `${ESC}[32m[INFO]${ESC}[0m Adding extra search path llm`
    expect(parseAnsi(text)).toEqual([
      { text: '[INFO]', colorIndex: 2 },
      { text: ' Adding extra search path llm' },
    ])
  })

  it('解析 ComfyUI WARNING 级别标签（加粗黄色）', () => {
    const text = `${ESC}[1m${ESC}[33m[WARNING]${ESC}[0m Some warning`
    expect(parseAnsi(text)).toEqual([
      { text: '[WARNING]', colorIndex: 3, bold: true },
      { text: ' Some warning' },
    ])
  })

  it('解析 Crystools 的组合参数序列 [0;32m', () => {
    const text = `[Crystools ${ESC}[0;32mINFO${ESC}[0m] Crystools version: 1.27.4`
    expect(parseAnsi(text)).toEqual([
      { text: '[Crystools ' },
      { text: 'INFO', colorIndex: 2 },
      { text: '] Crystools version: 1.27.4' },
    ])
  })

  it('解析亮色（90-97）', () => {
    const text = `${ESC}[92mok${ESC}[0m done`
    expect(parseAnsi(text)).toEqual([
      { text: 'ok', colorIndex: 10 },
      { text: ' done' },
    ])
  })

  it('空参数序列等价于重置', () => {
    const text = `${ESC}[31mred${ESC}[mplain`
    expect(parseAnsi(text)).toEqual([
      { text: 'red', colorIndex: 1 },
      { text: 'plain' },
    ])
  })

  it('39 恢复默认前景色, 22 取消加粗', () => {
    const text = `${ESC}[1;31mbold red${ESC}[39m still bold${ESC}[22m plain`
    expect(parseAnsi(text)).toEqual([
      { text: 'bold red', colorIndex: 1, bold: true },
      { text: ' still bold', bold: true },
      { text: ' plain' },
    ])
  })

  it('跳过 256 色扩展参数且不误读后续参数', () => {
    const text = `${ESC}[38;5;196mextended${ESC}[0m`
    expect(parseAnsi(text)).toEqual([{ text: 'extended' }])
  })

  it('跳过真彩色扩展参数', () => {
    const text = `${ESC}[38;2;255;0;0mrgb${ESC}[0m`
    expect(parseAnsi(text)).toEqual([{ text: 'rgb' }])
  })

  it('剥离非 SGR 的 CSI 序列（如清行）', () => {
    const text = `${ESC}[2KProgress 50%`
    expect(parseAnsi(text)).toEqual([{ text: 'Progress 50%' }])
  })

  it('剥离孤立的 ESC 字符', () => {
    const text = `before${ESC}after`
    expect(parseAnsi(text)).toEqual([{ text: 'beforeafter' }])
  })

  it('合并相邻同样式片段', () => {
    const text = `${ESC}[32mgreen1${ESC}[32mgreen2${ESC}[0m`
    expect(parseAnsi(text)).toEqual([{ text: 'green1green2', colorIndex: 2 }])
  })

  it('多行消息（Traceback 合并日志）保持换行', () => {
    const text = `${ESC}[31mError line 1\nline 2${ESC}[0m`
    expect(parseAnsi(text)).toEqual([{ text: 'Error line 1\nline 2', colorIndex: 1 }])
  })

  it('纯 ANSI 序列无文本时返回单个空片段', () => {
    expect(parseAnsi(`${ESC}[32m${ESC}[0m`)).toEqual([{ text: '' }])
  })
})

describe('stripAnsi', () => {
  it('剥离全部 SGR 序列', () => {
    const text = `${ESC}[1m${ESC}[33m[WARNING]${ESC}[0m Some warning`
    expect(stripAnsi(text)).toBe('[WARNING] Some warning')
  })

  it('剥离非 SGR 序列与孤立 ESC', () => {
    const text = `${ESC}[2Kline${ESC}`
    expect(stripAnsi(text)).toBe('line')
  })

  it('纯文本原样返回', () => {
    expect(stripAnsi('plain text')).toBe('plain text')
  })
})

describe('hasAnsi', () => {
  it('含 ESC 字符时为 true', () => {
    expect(hasAnsi(`${ESC}[32mgreen${ESC}[0m`)).toBe(true)
  })

  it('纯文本为 false', () => {
    expect(hasAnsi('[INFO] plain')).toBe(false)
  })
})
