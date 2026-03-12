import { readFile } from 'node:fs/promises'
import path from 'node:path'

import type {
  ClusterArticle,
  ContextItem,
  FramingGroup,
  StoryChangeItem,
  StoryCluster,
} from './mock-clusters'

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

const framingBySource: Record<string, FramingGroup> = {
  BBC: 'center',
  NPR: 'left',
  'PBS NewsHour': 'center',
  'WSJ World': 'right',
}

function formatRelativeTimestamp(value: string) {
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return 'recently'
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000))

  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`
  }

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `${diffHours}h ago`
  }

  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatTimelineTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return 'Just now'
  }

  return timestamp.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function inferDeskLabel(title: string, dek: string) {
  const haystack = `${title} ${dek}`.toLowerCase()
  const sectionScores: Record<string, number> = {
    World: 0,
    'US Politics': 0,
    Business: 0,
    'Climate and Infrastructure': 0,
    Technology: 0,
  }

  const signalMap: Record<string, Array<[RegExp, number]>> = {
    World: [
      [/\b(iran|ukraine|gaza|israel|europe|european|foreign|war|missile|refugee|china|chinese|beijing)\b/, 4],
      [/\b(britain|british|uk|u\.k\.|parliament|london)\b|house of lords/, 4],
      [/\b(international|global|diplomacy)\b|strait of hormuz/, 3],
    ],
    'US Politics': [
      [/\b(congress|senate|house|election|campaign|governor|policy|lawmakers|administration)\b|white house/, 4],
      [/\b(trump|biden|federal|court|budget)\b|supreme court|title ix/, 3],
    ],
    Business: [
      [/\b(market|markets|economy|economic|jobs|trade|business|inflation|consumer|fed)\b/, 5],
      [/\b(oil|reserve|bank|banks|prices|shipping|tariff|sanction|sanctions)\b/, 4],
    ],
    'Climate and Infrastructure': [
      [/\b(storm|grid|climate|energy|weather|wildfire|flood|hurricane|disaster)\b/, 4],
      [/\b(outage|recovery|infrastructure|utility|utilities)\b/, 3],
    ],
    Technology: [
      [/\b(ai|technology|tech|software|platform|chip|cyber)\b|artificial intelligence/, 4],
      [/\b(regulation|antitrust|semiconductor)\b|data center/, 3],
    ],
  }

  for (const [section, patterns] of Object.entries(signalMap)) {
    for (const [pattern, points] of patterns) {
      if (pattern.test(haystack)) {
        sectionScores[section] += points
      }
    }
  }

  const [bestSection, bestScore] = Object.entries(sectionScores).sort((left, right) => right[1] - left[1])[0]

  return bestScore > 0 ? bestSection : 'General News'
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values))
}

function joinSourceNames(sources: string[]) {
  if (sources.length <= 2) {
    return sources.join(' and ')
  }

  return `${sources.slice(0, 2).join(', ')}, and ${sources.length - 2} more`
}

function framingForSource(source: string): FramingGroup {
  return framingBySource[source] || 'center'
}

function buildCoverageCounts(sources: string[]) {
  return uniqueStrings(sources).reduce<Record<FramingGroup, number>>(
    (counts, source) => {
      counts[framingForSource(source)] += 1
      return counts
    },
    {
      left: 0,
      center: 0,
      right: 0,
    },
  )
}

function buildArticleReason(source: string, framing: FramingGroup) {
  switch (framing) {
    case 'left':
      return `${source} adds a more accountability-forward framing to the comparison set.`
    case 'right':
      return `${source} adds a more skeptical or leverage-focused framing to the comparison set.`
    default:
      return `${source} is useful as a baseline reporting anchor for the story stack.`
  }
}

function sortLiveArticles(articles: LiveClusterArticle[]) {
  return [...articles].sort(
    (left, right) =>
      new Date(right.published_at).getTime() - new Date(left.published_at).getTime(),
  )
}

function mapLiveArticles(cluster: LiveCluster): ClusterArticle[] {
  return sortLiveArticles(cluster.articles).map((article, index) => {
    const framing = framingForSource(article.source)

    return {
      outlet: article.source,
      title: article.title,
      summary: article.summary || article.domain,
      published: formatRelativeTimestamp(article.published_at),
      framing,
      image:
        article.image || cluster.hero_image || `https://picsum.photos/seed/${cluster.slug}-${index + 1}/640/420`,
      reason: buildArticleReason(article.source, framing),
      url: article.url,
    }
  })
}

function fillToCount<T>(items: T[], backup: T[], count: number) {
  const seen = new Set(items)
  const filled = [...items]

  for (const candidate of backup) {
    if (filled.length >= count) {
      break
    }

    if (seen.has(candidate)) {
      continue
    }

    seen.add(candidate)
    filled.push(candidate)
  }

  return filled
}

function buildContextPacks(cluster: LiveCluster, articles: ClusterArticle[]): StoryCluster['contextPacks'] {
  const byFraming: Record<FramingGroup, ClusterArticle[]> = {
    left: [],
    center: [],
    right: [],
  }

  for (const article of articles) {
    byFraming[article.framing].push(article)
  }

  const balancedCandidates = fillToCount(
    [byFraming.left[0], byFraming.center[0], byFraming.right[0]].filter(
      (item): item is ClusterArticle => Boolean(item),
    ),
    articles,
    Math.min(3, articles.length),
  )

  const evidenceFirst = [...articles]
    .sort((left, right) => right.summary.length - left.summary.length)
    .slice(0, Math.min(3, articles.length))

  const localImpact = articles.filter((article) =>
    /(local|state|city|school|community|jobs|families|residents|agency|operations|market)/i.test(
      `${article.title} ${article.summary}`,
    ),
  )

  const internationalComparison = articles.filter((article) =>
    /(bbc|world)/i.test(article.outlet),
  )

  const toContextItem = (article: ClusterArticle, why: string): ContextItem => ({
    outlet: article.outlet,
    title: article.title,
    why,
  })

  return {
    'Balanced Framing': balancedCandidates.map((article) =>
      toContextItem(
        article,
        'Included because it changes the reader’s frame without collapsing the story into a single verdict.',
      ),
    ),
    'Evidence-First': evidenceFirst.map((article) =>
      toContextItem(
        article,
        'Selected because the reporting is dense with direct detail, named sourcing, or concrete sequence.',
      ),
    ),
    'Local Impact': (localImpact.length > 0 ? localImpact : articles.slice(-1)).map((article) =>
      toContextItem(
        article,
        'Useful for understanding who is affected operationally, financially, or civically if the story keeps moving.',
      ),
    ),
    'International Comparison': (
      internationalComparison.length > 0
        ? internationalComparison
        : articles.filter((article) => article.outlet !== cluster.sources[0]).slice(0, 2)
    ).map((article) =>
      toContextItem(
        article,
        'Shows how the story looks when it is framed outside the most immediate domestic source context.',
      ),
    ),
  }
}

function buildKeyFacts(cluster: LiveCluster) {
  const sourceLabel = joinSourceNames(cluster.sources)
  const newestArticle = sortLiveArticles(cluster.articles)[0]

  return [
    `Prism currently sees ${cluster.article_count} linked pieces across ${cluster.sources.length} publishers in this story.`,
    newestArticle
      ? `The newest linked coverage came from ${newestArticle.source} ${formatRelativeTimestamp(newestArticle.published_at)}.`
      : 'The story shell is waiting for the first linked article payload.',
    cluster.article_count > 2
      ? `The comparison set is already broad enough to inspect framing differences across ${sourceLabel}.`
      : `The comparison set is still thin, so this story may move quickly as additional publishers enter the frame.`,
  ]
}

function buildChangeTimeline(cluster: LiveCluster): StoryChangeItem[] {
  const sortedArticles = sortLiveArticles(cluster.articles)
  const newestArticle = sortedArticles[0]
  const secondArticle = sortedArticles[1]
  const sourceLabel = joinSourceNames(cluster.sources)

  const timeline: StoryChangeItem[] = [
    {
      timestamp: formatTimelineTimestamp(cluster.latest_at),
      kind: 'summary',
      label: `Story shell refreshed from ${cluster.sources.length} publisher signals`,
      detail: `Prism regenerated the story summary, comparison stack, and context pack using ${cluster.article_count} linked inputs across ${sourceLabel}.`,
    },
  ]

  if (newestArticle) {
    timeline.push({
      timestamp: formatTimelineTimestamp(newestArticle.published_at),
      kind: 'coverage',
      label: `${newestArticle.source} added the latest visible turn`,
      detail: newestArticle.title,
    })
  }

  if (secondArticle) {
    timeline.push({
      timestamp: formatTimelineTimestamp(secondArticle.published_at),
      kind: 'coverage',
      label: `Comparison set widened beyond a single-source read`,
      detail: `${cluster.article_count} linked articles now give the story enough breadth for side-by-side framing inspection.`,
    })
  }

  if (cluster.hero_image) {
    timeline.push({
      timestamp: formatTimelineTimestamp(cluster.latest_at),
      kind: 'evidence',
      label: 'Representative publisher media attached to the story shell',
      detail: 'The current hero image comes from linked publisher metadata and is shown as a preview rather than a definitive visual claim.',
    })
  }

  return timeline
}

export function mapLiveClusterToStoryCluster(cluster: LiveCluster): StoryCluster {
  const articles = mapLiveArticles(cluster)
  const changeTimeline = buildChangeTimeline(cluster)
  const sourceLabel = joinSourceNames(cluster.sources)

  return {
    slug: cluster.slug,
    topic: inferDeskLabel(cluster.title, cluster.dek),
    title: cluster.title,
    dek: cluster.dek,
    updatedAt: `Updated ${formatRelativeTimestamp(cluster.latest_at)}`,
    status: 'Live intake',
    heroImage:
      cluster.hero_image || articles[0]?.image || `https://picsum.photos/seed/${cluster.slug}/1600/900`,
    heroAlt: `${cluster.title} preview image from linked publisher metadata.`,
    heroCredit: cluster.hero_credit || 'Publisher preview image',
    outletCount: cluster.sources.length,
    reliabilityRange: cluster.sources.length >= 3 ? 'Mixed source set' : 'Early source set',
    coverageCounts: buildCoverageCounts(cluster.sources),
    keyFacts: buildKeyFacts(cluster),
    whatChanged: changeTimeline.slice(0, 3).map((item) => item.label),
    changeTimeline,
    articles,
    evidence: [
      {
        label: 'Primary linked reporting set',
        source: sourceLabel,
        type: 'Publisher articles',
      },
      {
        label: 'Latest refresh in the live intake queue',
        source: formatTimelineTimestamp(cluster.latest_at),
        type: 'Live feed metadata',
      },
      {
        label: 'Current source breadth',
        source: `${cluster.article_count} linked articles across ${cluster.sources.length} publishers`,
        type: 'Coverage signal',
      },
    ],
    corrections: changeTimeline.slice(0, 2).map((item) => ({
      timestamp: item.timestamp,
      note: item.label,
    })),
    contextPacks: buildContextPacks(cluster, articles),
  }
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

export async function loadLiveStoryBySlug(slug: string): Promise<StoryCluster | null> {
  const liveFeed = await loadLiveFeed()
  const liveCluster = liveFeed?.clusters.find((cluster) => cluster.slug === slug)

  if (!liveCluster) {
    return null
  }

  return mapLiveClusterToStoryCluster(liveCluster)
}
