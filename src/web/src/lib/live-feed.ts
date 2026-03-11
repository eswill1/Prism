import { readFile } from 'node:fs/promises'
import path from 'node:path'

export type LiveClusterArticle = {
  source: string
  title: string
  url: string
  published_at: string
  summary: string
  image?: string | null
  domain: string
}

export type LiveCluster = {
  slug: string
  topic_label: string
  title: string
  dek: string
  latest_at: string
  article_count: number
  sources: string[]
  hero_image?: string | null
  hero_credit?: string
  articles: LiveClusterArticle[]
}

export type LiveFeedPayload = {
  generated_at: string
  source_count: number
  article_count: number
  sources: Array<{ source: string; feed_url: string }>
  errors: Array<{ source: string; feed_url: string; error: string }>
  clusters: LiveCluster[]
}

export async function loadLiveFeed(): Promise<LiveFeedPayload | null> {
  const candidatePaths = [
    path.join(process.cwd(), 'public', 'data', 'temporary-live-feed.json'),
    path.join(process.cwd(), 'src', 'web', 'public', 'data', 'temporary-live-feed.json'),
    path.join(process.cwd(), 'data', 'temporary-live-feed.json'),
    path.join(process.cwd(), '..', '..', 'data', 'temporary-live-feed.json'),
  ]

  for (const candidatePath of candidatePaths) {
    try {
      const raw = await readFile(candidatePath, 'utf-8')
      return JSON.parse(raw) as LiveFeedPayload
    } catch {
      continue
    }
  }

  return null
}
