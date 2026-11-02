import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Clock, ExternalLink, RefreshCw } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import {
  fetchReleases,
  fetchLocalRelease,
  parseReleaseBody,
  formatReleaseDate,
  GITHUB_RELEASES_URL,
  GitHubRelease,
} from '@/api/githubApi'

interface ChangelogSectionProps {
  className?: string
}

export function ChangelogSection({ className }: ChangelogSectionProps) {
  const { t } = useTranslation()
  const [releases, setReleases] = useState<GitHubRelease[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  /**
   * 先用本地 version.json 秒开，再尝试拉远端 Release。
   * GitHub 不可达时后端要等 15 秒超时，不能让用户一直看加载中。
   */
  const loadReleases = async () => {
    setIsLoading(true)
    setError(null)

    const local = await fetchLocalRelease()
    if (local) {
      setReleases([local])
      setIsLoading(false)
    }

    try {
      const remote = await fetchReleases()
      if (remote.length > 0) {
        setReleases(remote)
      } else if (!local) {
        setReleases([])
      }
    } catch (err) {
      if (!local) {
        setError(err instanceof Error ? err : new Error('Unknown error'))
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadReleases()
  }, [])

  const renderLoading = () => (
    <div className="flex items-center justify-center py-8">
      <RefreshCw className="size-5 animate-spin text-muted-foreground" />
      <span className="ml-2 text-sm text-muted-foreground">
        {t('about.changelog.loading')}
      </span>
    </div>
  )

  const renderError = () => (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <p className="text-sm text-muted-foreground">{t('about.changelog.error')}</p>
      <Button variant="outline" size="sm" onClick={loadReleases}>
        <RefreshCw className="mr-2 size-4" />
        {t('about.changelog.retry')}
      </Button>
    </div>
  )

  const renderEmpty = () => (
    <div className="flex items-center justify-center py-8">
      <p className="text-sm text-muted-foreground">{t('about.changelog.noData')}</p>
    </div>
  )

  const renderReleases = () => (
    <div className="relative ml-2 space-y-4 border-l border-border">
      {releases.map((release, index) => {
        const changes = parseReleaseBody(release.body)
        // id 为 0 表示来自本地 version.json 的兜底数据，不声称是"最新"
        const isLatest = index === 0 && release.id !== 0

        return (
          <div key={release.id} className="relative pl-4">
            <div
              className={`absolute -left-[5px] top-1.5 size-2.5 rounded-full ring-4 ring-card ${
                isLatest ? 'bg-primary' : 'bg-muted-foreground'
              }`}
            />
            <h3 className="text-sm font-bold text-foreground">
              {release.tag_name}
              {isLatest && (
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {t('about.latest')}
                </span>
              )}
            </h3>
            {changes.length > 0 ? (
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-muted-foreground">
                {changes.map((change, i) => (
                  <li key={i}>{change}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">
                {formatReleaseDate(release.published_at)}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )

  return (
    <Card className={cn("p-5 h-full flex flex-col", className)}>
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-foreground">
        <Clock className="size-4 text-primary" />
        {t('about.changelog.title')}
      </h2>

      <div className="min-h-0 flex-1">
        {isLoading && renderLoading()}
        {!isLoading && error && renderError()}
        {!isLoading && !error && releases.length === 0 && renderEmpty()}
        {!isLoading && !error && releases.length > 0 && renderReleases()}
      </div>

      <div className="mt-4 border-t border-border/50 pt-3">
        <a
          href={GITHUB_RELEASES_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
        >
          {t('about.viewFullLog')}
          <ExternalLink className="size-3" />
        </a>
      </div>
    </Card>
  )
}

export default ChangelogSection
