import { useState, useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Github, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useAppUpdateStore } from '@/stores/useAppUpdateStore'
import { GITHUB_RELEASES_URL } from '@/api/githubApi'

import { UpdateDialog } from './UpdateDialog'

interface AboutHeaderProps {
  version: string
}

export function AboutHeader({ version }: AboutHeaderProps) {
  const { t } = useTranslation()
  const [dialogOpen, setDialogOpen] = useState(false)
  const hasAutoOpenedRef = useRef(false)
  const { hasUpdate, hasViewed, markAsViewed } = useAppUpdateStore()

  const showBadge = hasUpdate && !hasViewed

  useEffect(() => {
    if (hasUpdate && !hasViewed && !hasAutoOpenedRef.current) {
      hasAutoOpenedRef.current = true
      setDialogOpen(true)
    }
  }, [hasUpdate, hasViewed])

  const handleDialogOpenChange = useCallback((open: boolean) => {
    setDialogOpen(open)
    if (!open && hasUpdate) {
      markAsViewed()
    }
  }, [hasUpdate, markAsViewed])

  // 本 fork 不发布安装包，本地更新检查没有意义，直接引导到 Releases 页面
  const handleOpenReleases = useCallback(() => {
    window.open(GITHUB_RELEASES_URL, '_blank', 'noopener,noreferrer')
  }, [])

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
          <Button 
            onClick={handleOpenReleases} 
            size="sm" 
            variant="outline" 
            className="flex items-center gap-2"
            title={GITHUB_RELEASES_URL}
          >
            <ExternalLink className="w-4 h-4" />
            {t('update.checkUpdate')}
          </Button>
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

export default AboutHeader
