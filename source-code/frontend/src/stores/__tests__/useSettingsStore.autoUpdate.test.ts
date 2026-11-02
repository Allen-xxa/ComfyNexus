/**
 * useSettingsStore 自动更新开关映射测试
 *
 * 验证后端 general.autoUpdate 能正确加载到前端 systemSettings.autoUpdate，
 * 否则「启动时检查更新」开关在重启后会被重置为默认关闭。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useSettingsStore } from '../useSettingsStore'

describe('useSettingsStore - autoUpdate 映射', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    delete (window as any).pywebview
  })

  it('从后端加载 general.autoUpdate = true 时，前端为 true', async () => {
    ;(window as any).pywebview = {
      api: {
        get_settings: vi.fn().mockResolvedValue({
          success: true,
          settings: { general: { autoUpdate: true } },
        }),
      },
    }

    await useSettingsStore.getState().loadSystemSettings()

    expect(useSettingsStore.getState().systemSettings.autoUpdate).toBe(true)
  })

  it('后端缺少 autoUpdate 字段时，回退为 false', async () => {
    ;(window as any).pywebview = {
      api: {
        get_settings: vi.fn().mockResolvedValue({
          success: true,
          settings: { general: {} },
        }),
      },
    }

    await useSettingsStore.getState().loadSystemSettings()

    expect(useSettingsStore.getState().systemSettings.autoUpdate).toBe(false)
  })

  it('保存 autoUpdate 时写入后端 general 段', async () => {
    const updateSettings = vi.fn().mockResolvedValue({ success: true })
    ;(window as any).pywebview = { api: { update_settings: updateSettings } }

    await useSettingsStore.getState().updateSystemSettings({ autoUpdate: true })

    expect(updateSettings).toHaveBeenCalledWith({ general: { autoUpdate: true } })
    expect(useSettingsStore.getState().systemSettings.autoUpdate).toBe(true)
  })
})
