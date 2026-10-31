import '@testing-library/jest-dom'
import { vi, beforeAll } from 'vitest'
import i18n from '@/i18n'

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}

global.localStorage = localStorageMock as any

// 组件断言依赖中文文案，而 jsdom 的 navigator.language 默认为 en-US，
// 必须在每个测试文件执行前强制锁定语言，否则 useTranslation 返回英文资源导致断言失败。
beforeAll(async () => {
  await i18n.changeLanguage('zh-CN')
})

// jsdom 未实现 Pointer Capture / scrollIntoView / ResizeObserver，
// Radix UI 的 Select、Tooltip 等组件在交互时会直接调用这些 API 并抛错，
// 导致下拉选项无法进入 DOM。此处补齐最小实现，仅用于测试环境。
if (typeof Element !== 'undefined') {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {}
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {}
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {}
  }
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as any
}

if (typeof window !== 'undefined' && !window.PointerEvent) {
  class PointerEventPolyfill extends MouseEvent {
    pointerId = 0
    pointerType = 'mouse'
    isPrimary = true
    constructor(type: string, params: any = {}) {
      super(type, params)
      Object.assign(this, params)
    }
  }
  ;(window as any).PointerEvent = PointerEventPolyfill
}

if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as any
}
