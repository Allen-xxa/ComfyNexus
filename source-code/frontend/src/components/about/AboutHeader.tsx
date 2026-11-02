import { useState, useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { RefreshCw, Download, Github } from 'lucide-react'
import { toast } from '@/utils/toast'
import { Button } from '@/components/ui/Button'
import { useAppUpdateStore, LocalFileInfo } from '@/stores/useAppUpdateStore'

import { UpdateDialog } from './UpdateDialog'

interface AboutHeaderProps {
  version: string
}

export function AboutHeader({ version }: AboutHeaderProps) {
  const { t } = useTranslation()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const hasAutoOpenedRef = useRef(false)
  const { hasUpdate, hasViewed, setChecking, setHasUpdate, markAsViewed, setLocalFileInfo } = useAppUpdateStore()

  const showBadge = hasUpdate && !hasViewed

  useEffect(() => {
    if (hasUpdate && !hasViewed && !hasAutoOpenedRef.current) {
      hasAutoOpenedRef.current = true
      setDialogOpen(true)
    }
  }, [hasUpdate, hasViewed])

  const handleCheckUpdate = useCallback(async () => {
    if (isChecking) return

    const { updateInfo } = useAppUpdateStore.getState()
    
    if (hasUpdate && updateInfo) {
      setDialogOpen(true)
      return
    }

    setIsChecking(true)
    setChecking(true)

    try {
      const api = (window as any).pywebview?.api
      if (!api) {
        toast.error(t('update.networkError'))
        return
      }

      const result = await api.check_for_update()
      setChecking(false)

      if (!result.success) {
        toast.error(result.error || t('update.updateError'))
        return
      }

      if (result.has_update) {
        setHasUpdate(true, {
          currentVersion: result.current_version,
          latestVersion: result.latest_version,
          downloadUrl: result.download_url,
          releaseNotes: result.release_notes,
          publishedAt: result.published_at,
          fileSize: result.file_size,
          fileHash: result.file_hash
        })
        
        const localResult = await api.check_local_update()
        if (localResult.success) {
          const localInfo: LocalFileInfo = {
            exists: localResult.has_local_file,
            filePath: localResult.file_path,
            hashMatch: localResult.hash_match,
            fileSize: localResult.file_size,
            partialDownload: localResult.partial_download
          }
          setLocalFileInfo(localInfo)
        }
        
        setDialogOpen(true)
      } else {
        setHasUpdate(false, null)
        setLocalFileInfo(null)
        toast.success(t('update.noUpdate'))
      }
    } catch (err) {
      setChecking(false)
      toast.error(err instanceof Error ? err.message : t('update.networkError'))
    } finally {
      setIsChecking(false)
    }
  }, [isChecking, hasUpdate, setChecking, setHasUpdate, setLocalFileInfo, t])

  const handleDialogOpenChange = useCallback((open: boolean) => {
    setDialogOpen(open)
    if (!open && hasUpdate) {
      markAsViewed()
    }
  }, [hasUpdate, markAsViewed])

  return (
    <>
      <header className="flex flex-col justify-between gap-4 border-b border-border pb-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-4">
          <img
            src="/app-icon.png"
            alt="ComfyNexus"
            className="size-14"
          />
          <div className="flex flex-col">
            <div className="mb-1 flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-wide text-foreground">
                ComfyNexus
              </h1>
              <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 font-mono text-xs text-primary">
                {version}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => window.open('https://github.com/qiqStrong/ComfyNexus', '_blank', 'noopener,noreferrer')}
                className="size-7 rounded-md"
                title="GitHub"
              >
                <Github className="size-4" />
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {t('about.subtitle')}
            </p>
          </div>
        </div>
        <div className="relative">
          {hasUpdate ? (
            <Button 
              onClick={handleCheckUpdate} 
              size="sm" 
              className="text-success-foreground flex items-center gap-2 bg-success hover:bg-success/90"
            >
              <Download className="size-4" />
              {t('update.updateNow') || '立即更新'}
            </Button>
          ) : (
            <Button 
              onClick={handleCheckUpdate} 
              size="sm" 
              variant="outline" 
              className="flex items-center gap-2"
              disabled={isChecking}
            >
              <RefreshCw className={cn("w-4 h-4", isChecking && "animate-spin")} />
              {isChecking ? t('update.checking') : t('update.checkUpdate')}
            </Button>
          )}
          {showBadge && (
            <span className="absolute -right-1 -top-1 size-2.5 animate-pulse rounded-full border-2 border-background bg-success" />
          )}
        </div>
      </header>

      <UpdateDialog 
        open={dialogOpen} 
        onOpenChange={handleDialogOpenChange}
        currentVersion={version}
      />
    </>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}

export default AboutHeader
