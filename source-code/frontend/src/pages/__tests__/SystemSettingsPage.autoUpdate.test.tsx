/**
 * SystemSettingsPage - 「启动时检查更新」开关渲染与交互测试
 *
 * 验证：
 * - 一般设置卡片中存在该开关
 * - 开关状态来自 systemSettings.autoUpdate
 * - 切换后点击保存，会把 general.autoUpdate 写入后端
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import SystemSettingsPage from '../SystemSettingsPage'
import { useSettingsStore } from '@/stores/useSettingsStore'

vi.mock('@/components/settings/MirrorSettings', () => ({ MirrorSettings: () => null }))
vi.mock('@/components/settings/PyPIMirrorSettings', () => ({ PyPIMirrorSettings: () => null }))
vi.mock('@/components/settings/ModuleManagement', () => ({ ModuleManagement: () => null }))
vi.mock('@/components/settings/CacheManagement', () => ({ CacheManagement: () => null }))
vi.mock('@/components/settings/LoggingSettings', () => ({ LoggingSettings: () => null }))
vi.mock('@/components/settings/GitHubApiSetting', () => ({ GitHubApiSetting: () => null }))
vi.mock('@/components/settings/TranslationSettings', () => ({ TranslationSettings: () => null }))
vi.mock('@/components/settings/GitConcurrencySetting', () => ({ GitConcurrencySetting: () => null }))

// useWindowStore 的 setSize/loadSize 必须是稳定引用：
// 若每次渲染都返回新函数，页面中依赖 loadSize 的 effect 会不断重跑，导致渲染死循环。
const windowStoreMocks = vi.hoisted(() => ({
  setSize: vi.fn(),
  loadSize: vi.fn(),
}))

vi.mock('@/stores/useWindowStore', () => ({
  useWindowStore: (selector: any) =>
    selector({ size: '1280x720', setSize: windowStoreMocks.setSize, loadSize: windowStoreMocks.loadSize }),
}))

vi.mock('@/stores/useWarningStore', () => ({
  useWarningStore: () => ({ resetAllWarnings: vi.fn() }),
}))

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ setTheme: vi.fn() }),
}))

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const getSettingsMock = vi.fn()
const updateSettingsMock = vi.fn()

function mockBackend(autoUpdate: boolean) {
  getSettingsMock.mockResolvedValue({
    success: true,
    settings: {
      version: '1.0.0',
      general: { autoUpdate, comfyuiStartupAction: 'workspace', selectedBrowser: '' },
      appearance: { theme: 'light', windowSize: '1280x720' },
      language: { current: 'zh-CN' },
      proxy: { enabled: false, host: '', port: '' },
    },
  })

  ;(window as any).pywebview = {
    api: {
      get_settings: getSettingsMock,
      update_settings: updateSettingsMock,
      get_installed_browsers: vi.fn().mockResolvedValue({ success: true, browsers: [] }),
    },
  }
}

describe('SystemSettingsPage - 启动时检查更新开关', () => {
  beforeEach(() => {
    getSettingsMock.mockReset()
    updateSettingsMock.mockReset()
    updateSettingsMock.mockResolvedValue({ success: true })
    mockBackend(false)
  })

  afterEach(() => {
    delete (window as any).pywebview
  })

  it('渲染出「启动时检查更新」开关，且默认关闭', async () => {
    render(<SystemSettingsPage />)

    const toggle = await screen.findByRole('switch', { name: '启动时检查更新' })
    expect(toggle).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  it('后端配置为开启时，开关显示为开启', async () => {
    mockBackend(true)
    render(<SystemSettingsPage />)

    await waitFor(() => {
      expect(useSettingsStore.getState().systemSettings.autoUpdate).toBe(true)
    })

    const toggle = await screen.findByRole('switch', { name: '启动时检查更新' })
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'))
  })

  it('切换开关并保存后，向后端写入 general.autoUpdate = true', async () => {
    render(<SystemSettingsPage />)

    const toggle = await screen.findByRole('switch', { name: '启动时检查更新' })
    fireEvent.click(toggle)
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'))

    fireEvent.click(screen.getByRole('button', { name: /保存/ }))

    await waitFor(() => {
      expect(updateSettingsMock).toHaveBeenCalled()
    })

    const payload = updateSettingsMock.mock.calls[0][0]
    expect(payload.general.autoUpdate).toBe(true)
  })
})
