/**
 * 应用更新状态管理
 * 
 * 管理应用自动更新检查和徽章显示状态
 */

import { create } from 'zustand'

interface UpdateInfo {
  currentVersion: string
  latestVersion: string
  downloadUrl: string
  releaseNotes: string
  publishedAt: string
  fileSize: number
  fileHash?: string
}

interface PartialDownloadInfo {
  hasPartial: boolean
  downloadedSize: number
  totalSize: number
  percentage: number
  versionMatch: boolean
  hashMatch: boolean
}

interface LocalFileInfo {
  exists: boolean
  filePath: string
  hashMatch: boolean
  fileSize: number
  partialDownload: PartialDownloadInfo | null
}

interface AppUpdateStore {
  hasUpdate: boolean
  updateInfo: UpdateInfo | null
  isChecking: boolean
  lastCheckTime: string | null
  hasViewed: boolean
  localFileInfo: LocalFileInfo | null
  
  setHasUpdate: (hasUpdate: boolean, updateInfo?: UpdateInfo | null) => void
  setChecking: (isChecking: boolean) => void
  markAsViewed: () => void
  setLocalFileInfo: (info: LocalFileInfo | null) => void
  reset: () => void
}

const isDev = import.meta.env.DEV

const DEV_UPDATE_INFO: UpdateInfo = {
  currentVersion: 'RC_0.8.0',
  latestVersion: 'RC_0.8.1',
  downloadUrl: 'https://github.com/qiqStrong/ComfyNexus/releases/latest',
  releaseNotes: '开发环境模拟更新',
  publishedAt: new Date().toISOString(),
  fileSize: 1024 * 1024 * 50,
  fileHash: 'abc123def456'
}

const DEV_LOCAL_FILE_INFO: LocalFileInfo = {
  exists: false,
  filePath: '',
  hashMatch: false,
  fileSize: 0,
  partialDownload: null
}

export const useAppUpdateStore = create<AppUpdateStore>((set) => ({
  hasUpdate: isDev,
  updateInfo: isDev ? DEV_UPDATE_INFO : null,
  isChecking: false,
  lastCheckTime: isDev ? new Date().toISOString() : null,
  hasViewed: false,
  localFileInfo: isDev ? DEV_LOCAL_FILE_INFO : null,
  
  setHasUpdate: (hasUpdate: boolean, updateInfo?: UpdateInfo | null) => {
    set({
      hasUpdate,
      updateInfo: updateInfo || null,
      lastCheckTime: new Date().toISOString(),
      hasViewed: false
    })
  },
  
  setChecking: (isChecking: boolean) => {
    set({ isChecking })
  },
  
  markAsViewed: () => {
    set({ hasViewed: true })
  },
  
  setLocalFileInfo: (info: LocalFileInfo | null) => {
    set({ localFileInfo: info })
  },
  
  reset: () => {
    set({
      hasUpdate: false,
      updateInfo: null,
      isChecking: false,
      lastCheckTime: null,
      hasViewed: false,
      localFileInfo: null
    })
  }
}))

export type { UpdateInfo, LocalFileInfo, PartialDownloadInfo }
