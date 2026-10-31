import { useEffect, useCallback, useRef } from 'react'
import { useAppUpdateStore } from '@/stores/useAppUpdateStore'
import { useSettingsStore } from '@/stores/useSettingsStore'

const CHECK_INTERVAL = 10 * 60 * 1000 // 10 分钟
const INITIAL_DELAY = 2000 // 启动后 2 秒

export function useAutoUpdateCheck() {
  const { 
    hasUpdate, 
    updateInfo, 
    isChecking, 
    setHasUpdate, 
    setChecking,
    hasViewed
  } = useAppUpdateStore()

  // 尊重「系统设置 → 自动更新」开关。
  // 该开关此前只存不读，导致无论是否关闭都会在启动后自动检查更新。
  const autoUpdate = useSettingsStore((state) => state.systemSettings?.autoUpdate ?? false)
  
  const isCheckingRef = useRef(isChecking)
  const hasCheckedRef = useRef(false)

  useEffect(() => {
    isCheckingRef.current = isChecking
  }, [isChecking])

  const checkForUpdate = useCallback(async () => {
    if (isCheckingRef.current) {
      console.log('[AutoUpdateCheck] 正在检查中，跳过')
      return
    }
    
    const api = (window as any).pywebview?.api
    if (!api) {
      console.log('[AutoUpdateCheck] API not available')
      return
    }

    setChecking(true)
    
    try {
      const result = await api.check_for_update()
      
      if (result.success && result.has_update) {
        setHasUpdate(true, {
          currentVersion: result.current_version,
          latestVersion: result.latest_version,
          downloadUrl: result.download_url,
          releaseNotes: result.release_notes,
          publishedAt: result.published_at,
          fileSize: result.file_size
        })
        console.log('[AutoUpdateCheck] 发现新版本:', result.latest_version)
      } else {
        setHasUpdate(false, null)
        console.log('[AutoUpdateCheck] 已是最新版本')
      }
    } catch (error) {
      console.error('[AutoUpdateCheck] 检查更新失败:', error)
      setHasUpdate(false, null)
    } finally {
      setChecking(false)
    }
  }, [setHasUpdate, setChecking])

  useEffect(() => {
    if (!autoUpdate) {
      console.log('[AutoUpdateCheck] 自动更新已关闭，跳过启动检查与定时轮询')
      return
    }

    if (hasCheckedRef.current) {
      return
    }
    hasCheckedRef.current = true

    const api = (window as any).pywebview?.api
    if (!api) {
      console.log('[AutoUpdateCheck] Waiting for API...')
      
      const checkInterval = setInterval(() => {
        if ((window as any).pywebview?.api) {
          clearInterval(checkInterval)
          checkForUpdate()
          startPeriodicCheck()
        }
      }, 500)
      
      const timeout = setTimeout(() => {
        clearInterval(checkInterval)
      }, 10000)
      
      return () => {
        clearInterval(checkInterval)
        clearTimeout(timeout)
      }
    } else {
      const initialTimer = setTimeout(() => {
        checkForUpdate()
        startPeriodicCheck()
      }, INITIAL_DELAY)
      
      return () => clearTimeout(initialTimer)
    }

    function startPeriodicCheck() {
      const intervalId = setInterval(() => {
        console.log('[AutoUpdateCheck] 定时检查更新...')
        checkForUpdate()
      }, CHECK_INTERVAL)
      
      window.addEventListener('beforeunload', () => {
        clearInterval(intervalId)
      })
    }
  }, [checkForUpdate, autoUpdate])

  return {
    hasUpdate,
    updateInfo,
    isChecking,
    hasViewed,
    checkForUpdate
  }
}
