export interface GitHubRelease {
  id: number
  tag_name: string
  name: string
  body: string
  published_at: string
  html_url: string
  prerelease: boolean
  draft: boolean
}

const MAX_RELEASES = 3

export const GITHUB_RELEASES_URL = 'https://github.com/qiqStrong/ComfyNexus/releases'

/**
 * 用随应用分发的 version.json 兜底生成一条更新日志。
 * GitHub API 不可达（国内网络常见）或仓库还没有 Release 时使用。
 */
export async function fetchLocalRelease(): Promise<GitHubRelease | null> {
  const api = (window as { pywebview?: { api?: { get_local_release_info?: () => Promise<{ success: boolean; version?: string; published_at?: string; release_notes?: string }> } } }).pywebview?.api
  if (!api?.get_local_release_info) return null

  try {
    const local = await api.get_local_release_info()
    if (!local?.success || !local.release_notes) return null

    return {
      id: 0,
      tag_name: local.version || '',
      name: local.version || '',
      body: local.release_notes,
      published_at: local.published_at || '',
      html_url: GITHUB_RELEASES_URL,
      prerelease: false,
      draft: false,
    }
  } catch {
    return null
  }
}

export async function fetchReleases(): Promise<GitHubRelease[]> {
  try {
    const result = await window.pywebview.api.get_github_releases(
      'qiqStrong',
      'ComfyNexus',
      MAX_RELEASES
    )

    if (result.success && result.releases) {
      const releases = result.releases.filter((release: GitHubRelease) => !release.draft)
      if (releases.length > 0) return releases
    }
  } catch {
    // 网络异常时继续走本地兜底
  }

  const local = await fetchLocalRelease()
  return local ? [local] : []
}

export function parseReleaseBody(body: string): string[] {
  const lines = body.split('\n')
  const changes: string[] = []
  
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const change = trimmed.substring(2).trim()
      if (change) {
        changes.push(change)
      }
    }
  }
  
  return changes.slice(0, 5)
}

export function formatReleaseDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
