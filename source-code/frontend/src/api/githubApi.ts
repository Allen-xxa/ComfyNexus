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

export async function fetchReleases(): Promise<GitHubRelease[]> {
  const result = await window.pywebview.api.get_github_releases(
    'qiqStrong',
    'ComfyNexus',
    MAX_RELEASES
  )
  
  if (!result.success || !result.releases) {
    throw new Error(result.message || '获取 GitHub Releases 失败')
  }
  
  return result.releases.filter((release: GitHubRelease) => !release.draft)
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

export const GITHUB_RELEASES_URL = 'https://github.com/qiqStrong/ComfyNexus/releases'
