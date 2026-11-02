/**
 * useAutoUpdateCheck 单元测试
 *
 * 覆盖「系统设置 → 启动时检查更新」开关：
 * - 关闭时不发起任何检查（启动检查 + 定时轮询都不触发）
 * - 开启时在启动延迟后检查一次，并按间隔轮询
 * - 运行中关闭开关后，轮询定时器被清理
 * - 运行中重新开启开关后，可以立即触发一次检查
 */

import { renderHook, act, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAutoUpdateCheck } from '../useAutoUpdateCheck'
import { useSettingsStore } from '@/stores/useSettingsStore'

const checkForUpdateMock = vi.fn()
const setHasUpdateMock = vi.fn()
const setCheckingMock = vi.fn()

vi.mock('@/stores/useAppUpdateStore', () => ({
  useAppUpdateStore: () => ({
    hasUpdate: false,
    updateInfo: null,
    isChecking: false,
    hasViewed: false,
    setHasUpdate: setHasUpdateMock,
    setChecking: setCheckingMock,
  }),
}))

const INITIAL_DELAY = 2000
const CHECK_INTERVAL = 10 * 60 * 1000

function setAutoUpdate(value: boolean) {
  const current = useSettingsStore.getState().systemSettings
  useSettingsStore.setState({ systemSettings: { ...current, autoUpdate: value } })
}

async function advance(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms)
    // 让 checkForUpdate 内部的 await 有机会结算
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('useAutoUpdateCheck', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    checkForUpdateMock.mockReset()
    checkForUpdateMock.mockResolvedValue({ success: true, has_update: false })
    setHasUpdateMock.mockReset()
    setCheckingMock.mockReset()

    ;(window as any).pywebview = {
      api: { check_for_update: checkForUpdateMock },
    }

    setAutoUpdate(false)
  })

  afterEach(() => {
    // 先卸载组件，再改动 store，避免触发未包裹 act 的状态更新
    cleanup()
    vi.useRealTimers()
    delete (window as any).pywebview
    setAutoUpdate(false)
  })

  it('开关关闭时不发起任何检查', async () => {
    setAutoUpdate(false)
    renderHook(() => useAutoUpdateCheck())

    await advance(INITIAL_DELAY + 100)
    await advance(CHECK_INTERVAL * 2)

    expect(checkForUpdateMock).not.toHaveBeenCalled()
  })

  it('开关开启时在启动延迟后检查一次', async () => {
    setAutoUpdate(true)
    renderHook(() => useAutoUpdateCheck())

    await advance(INITIAL_DELAY + 100)

    expect(checkForUpdateMock).toHaveBeenCalledTimes(1)
  })

  it('开关开启时按间隔轮询', async () => {
    setAutoUpdate(true)
    renderHook(() => useAutoUpdateCheck())

    await advance(INITIAL_DELAY + 100)
    expect(checkForUpdateMock).toHaveBeenCalledTimes(1)

    await advance(CHECK_INTERVAL)
    expect(checkForUpdateMock).toHaveBeenCalledTimes(2)

    await advance(CHECK_INTERVAL)
    expect(checkForUpdateMock).toHaveBeenCalledTimes(3)
  })

  it('运行中关闭开关后停止轮询', async () => {
    setAutoUpdate(true)
    renderHook(() => useAutoUpdateCheck())

    await advance(INITIAL_DELAY + 100)
    expect(checkForUpdateMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      setAutoUpdate(false)
    })

    await advance(CHECK_INTERVAL * 2)
    expect(checkForUpdateMock).toHaveBeenCalledTimes(1)
  })

  it('运行中重新开启开关后可以再次检查', async () => {
    setAutoUpdate(false)
    renderHook(() => useAutoUpdateCheck())

    await advance(INITIAL_DELAY + 100)
    expect(checkForUpdateMock).not.toHaveBeenCalled()

    await act(async () => {
      setAutoUpdate(true)
    })

    await advance(INITIAL_DELAY + 100)
    expect(checkForUpdateMock).toHaveBeenCalledTimes(1)
  })
})
