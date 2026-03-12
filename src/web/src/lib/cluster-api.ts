import { clusterBySlug, mockClusters, type FramingGroup, type StoryCluster } from './mock-clusters'
import { loadLiveStoryBySlug } from './live-feed'
import { getNewsSectionKey } from './news-sections'
import { inferSourceAccessTier } from './source-access'
import type { StoryBrief } from './story-brief-types'
import { getSupabaseServerClient, hasSupabaseServerConfig, type JsonObject } from './supabase/server'

export type ClusterSummary = {
  slug: string
  topic: string
  title: string
  dek: string
  updatedAt: string
  status: string
  heroImage: string
  heroAlt: string
  heroCredit: string
  outletCount: number
  reliabilityRange: string
  coverageCounts: StoryCluster['coverageCounts']
  latestEventAt: string
  storyOrigin: string
  qualityScore: number
  homepageEligible: boolean
}

function toClusterSummary(cluster: StoryCluster): ClusterSummary {
  return {
    slug: cluster.slug,
    topic: cluster.topic,
    title: cluster.title,
    dek: cluster.dek,
    updatedAt: cluster.updatedAt,
    status: cluster.status,
    heroImage: cluster.heroImage,
    heroAlt: cluster.heroAlt,
    heroCredit: cluster.heroCredit,
    outletCount: cluster.outletCount,
    reliabilityRange: cluster.reliabilityRange,
    coverageCounts: cluster.coverageCounts,
    latestEventAt: new Date().toISOString(),
    storyOrigin: 'mock',
    qualityScore: 0,
    homepageEligible: true,
  }
}

function normalizeCoverageCounts(value: unknown): Record<FramingGroup, number> {
  if (value && typeof value === 'object') {
    const counts = value as Partial<Record<FramingGroup, number>>
    return {
      left: Number(counts.left ?? 0),
      center: Number(counts.center ?? 0),
      right: Number(counts.right ?? 0),
    }
  }

  return {
    left: 0,
    center: 0,
    right: 0,
  }
}

function formatStatusLabel(status: string | null | undefined, metadata?: JsonObject | null) {
  if (typeof metadata?.display_status === 'string' && metadata.display_status.trim().length > 0) {
    return metadata.display_status
  }

  if (!status) {
    return 'Developing'
  }

  return status
    .split('_')
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ')
}

function formatUpdatedAt(value: string | null | undefined) {
  if (!value) {
    return 'Updated recently'
  }

  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return 'Updated recently'
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000))

  if (diffMinutes < 60) {
    return `Updated ${diffMinutes}m ago`
  }

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `Updated ${diffHours}h ago`
  }

  const diffDays = Math.round(diffHours / 24)
  return `Updated ${diffDays}d ago`
}

function fallbackClusterSummary(cluster: StoryCluster): ClusterSummary {
  return toClusterSummary(cluster)
}

async function fallbackClusterDetail(slug: string) {
  return clusterBySlug[slug] ?? (await loadLiveStoryBySlug(slug))
}

function clusterFallbackImage(slug: string) {
  return `https://picsum.photos/seed/${slug}/1600/900`
}

function looksClippedText(value: string) {
  const trimmed = value.trim()
  if (trimmed.length < 80) {
    return false
  }

  if (trimmed.endsWith('...') || trimmed.endsWith('…')) {
    return true
  }

  if (!/[.!?]$/.test(trimmed)) {
    return true
  }

  const words = trimmed.match(/[A-Za-z']+/g) ?? []
  if (words.length < 2) {
    return false
  }

  const lastWord = words[words.length - 1] ?? ''
  const previousWord = (words[words.length - 2] ?? '').toLowerCase()
  return (
    lastWord.length <= 2 &&
    ['a', 'an', 'the', 'to', 'of', 'in', 'on', 'for', 'with', 'from', 'at'].includes(previousWord)
  )
}

function clampSnippet(value: string, maxChars: number) {
  if (value.length <= maxChars) {
    return value
  }

  const sentenceMatches = Array.from(value.matchAll(/.+?[.!?](?:\s|$)/g))
  for (let index = sentenceMatches.length - 1; index >= 0; index -= 1) {
    const match = sentenceMatches[index]
    if (!match) {
      continue
    }

    const sentence = match[0].trim()
    const endIndex = value.indexOf(sentence) + sentence.length
    if (endIndex <= maxChars && endIndex >= Math.floor(maxChars * 0.55)) {
      return value.slice(0, endIndex).trim()
    }
  }

  const shortened = value.slice(0, maxChars).trim().replace(/\s+\S*$/, '')
  return shortened ? `${shortened}...` : value.slice(0, maxChars).trim()
}

function normalizeSnippet(
  value: string | null | undefined,
  options?: {
    maxChars?: number
    fallback?: string
  },
) {
  const trimmed = value?.trim() ?? ''
  const maxChars = options?.maxChars ?? 280
  const fallback = options?.fallback ?? 'No summary available yet.'

  if (!trimmed) {
    return fallback
  }

  const clamped = clampSnippet(trimmed.replace(/\s+/g, ' '), maxChars)
  if (looksClippedText(clamped)) {
    const firstSentence = trimmed.match(/^(.+?[.!?])(?:\s|$)/)?.[1]?.trim()
    if (firstSentence && firstSentence.length >= 60) {
      return firstSentence
    }
    return fallback
  }

  return clamped
}

function normalizeKeyFact(fact: string, outletCount: number, articleCount: number) {
  if (/^Prism currently sees /i.test(fact)) {
    if (outletCount <= 1) {
      return `Prism has one linked report in this story so far, so the comparison view is still early.`
    }
    return `Prism has ${articleCount} linked reports across ${outletCount} publishers in this story so far.`
  }

  if (/^The newest linked coverage came from /i.test(fact)) {
    return fact.replace(/^The newest linked coverage came from /i, 'The latest linked reporting came from ')
  }

  return fact
}

function publicArticleUrl(value: string | null | undefined) {
  const trimmed = value?.trim()
  if (!trimmed || trimmed.startsWith('https://seed.prism.local/')) {
    return undefined
  }

  const cleaned = trimmed.replace(/[)>.,]+$/, '')
  if (!/^https?:\/\//i.test(cleaned)) {
    return undefined
  }

  try {
    return new URL(cleaned).toString()
  } catch {
    return undefined
  }
}

type StoryClusterRow = {
  id: string
  slug: string
  topic_label: string
  canonical_headline: string
  summary: string
  status: string
  latest_event_at: string
  hero_media_url: string | null
  hero_media_alt: string | null
  hero_media_credit: string | null
  outlet_count: number
  coverage_counts: unknown
  reliability_range: string | null
  metadata: JsonObject | null
}

type StoryBriefRevisionRow = {
  label: string
  title: string
  status: string
  paragraphs: string[] | null
  why_it_matters: string
  where_sources_agree: string
  where_coverage_differs: string
  what_to_watch: string
  supporting_points: string[] | null
  metadata: JsonObject | null
}

function mapStoredBrief(row: StoryBriefRevisionRow | null | undefined): StoryBrief | undefined {
  if (!row) {
    return undefined
  }

  const metadata = row.metadata || {}
  const paragraphs = Array.isArray(row.paragraphs)
    ? row.paragraphs.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    : []
  const supportingPoints = Array.isArray(row.supporting_points)
    ? row.supporting_points.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    : []

  return {
    label: row.label,
    title: row.title,
    paragraphs,
    whyItMatters: row.why_it_matters,
    whereSourcesAgree: row.where_sources_agree,
    whereCoverageDiffers: row.where_coverage_differs,
    whatToWatch: row.what_to_watch,
    supportingPoints,
    substantiveSourceCount:
      typeof metadata.substantive_source_count === 'number'
        ? metadata.substantive_source_count
        : Number(metadata.substantive_source_count ?? 0),
    isEarlyBrief: row.status !== 'full',
  }
}

function mapSummaryRow(row: StoryClusterRow): ClusterSummary {
  const metadata = row.metadata || {}
  const qualityScore =
    typeof metadata.quality_score === 'number'
      ? metadata.quality_score
      : Number(metadata.quality_score ?? 0)
  const homepageEligible =
    typeof metadata.homepage_eligible === 'boolean'
      ? metadata.homepage_eligible
      : (row.outlet_count ?? 0) >= 2
  const storyOrigin =
    typeof metadata.story_origin === 'string' ? metadata.story_origin : 'database'
  const fallbackDek =
    storyOrigin === 'automated_feed_ingestion'
      ? `${row.canonical_headline.replace(/[?!.]+$/, '')} is drawing live coverage as Prism tracks what changes next.`
      : 'No summary available yet.'

  return {
    slug: row.slug,
    topic: row.topic_label,
    title: row.canonical_headline,
    dek: normalizeSnippet(row.summary, { maxChars: 280, fallback: fallbackDek }),
    updatedAt: formatUpdatedAt(row.latest_event_at),
    status: formatStatusLabel(row.status, row.metadata),
    heroImage: row.hero_media_url || clusterFallbackImage(row.slug),
    heroAlt:
      row.hero_media_alt ||
      `Editorial image for the ${row.canonical_headline} story.`,
    heroCredit: row.hero_media_credit || 'Editorial preview image',
    outletCount: row.outlet_count ?? 0,
    reliabilityRange:
      row.reliability_range ||
      (typeof metadata.reliability_range === 'string'
        ? metadata.reliability_range
        : 'Not enough data'),
    coverageCounts: normalizeCoverageCounts(row.coverage_counts),
    latestEventAt: row.latest_event_at,
    storyOrigin,
    qualityScore: Number.isFinite(qualityScore) ? qualityScore : 0,
    homepageEligible,
  }
}

function isReaderVisibleStoryOrigin(origin: string) {
  return origin !== 'editorial_seed'
}

type ClusterSortMode = 'frontpage' | 'latest'

function coverageDiversityScore(counts: StoryCluster['coverageCounts']) {
  return [counts.left, counts.center, counts.right].filter((value) => value > 0).length
}

function freshnessBonus(value: string) {
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return 0
  }

  const ageMinutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000))

  if (ageMinutes <= 30) return 12
  if (ageMinutes <= 90) return 9
  if (ageMinutes <= 240) return 6
  if (ageMinutes <= 720) return 3
  return 0
}

function frontPagePriority(summary: ClusterSummary) {
  let score = summary.qualityScore
  score += Math.min(summary.outletCount, 4) * 14
  score += coverageDiversityScore(summary.coverageCounts) * 6
  score += freshnessBonus(summary.latestEventAt)
  score += getNewsSectionKey(summary.topic) === 'more' ? -14 : 10

  if (summary.storyOrigin === 'editorial_seed') {
    score -= 8
  }

  if (summary.storyOrigin === 'automated_feed_ingestion') {
    score += 10
  }

  if (summary.homepageEligible) {
    score += 18
  } else {
    score -= 18
  }

  if (summary.status === 'Live intake' && summary.outletCount === 1) {
    score -= 16
  }

  return score
}

function sortClusterSummaries(clusters: ClusterSummary[], mode: ClusterSortMode) {
  const sorted = [...clusters]

  if (mode === 'latest') {
    return sorted.sort((left, right) => {
      const recency = new Date(right.latestEventAt).getTime() - new Date(left.latestEventAt).getTime()
      if (recency !== 0) return recency
      return frontPagePriority(right) - frontPagePriority(left)
    })
  }

  return sorted.sort((left, right) => {
    const priority = frontPagePriority(right) - frontPagePriority(left)
    if (priority !== 0) return priority
    return new Date(right.latestEventAt).getTime() - new Date(left.latestEventAt).getTime()
  })
}

function mapLensName(lens: string) {
  switch (lens) {
    case 'balanced_framing':
      return 'Balanced Framing'
    case 'evidence_first':
      return 'Evidence-First'
    case 'local_impact':
      return 'Local Impact'
    case 'international_comparison':
      return 'International Comparison'
    default:
      return lens
  }
}

export function isSupabaseConfigured() {
  return hasSupabaseServerConfig()
}

export async function getClusterSummaries(options?: {
  sort?: ClusterSortMode
}): Promise<ClusterSummary[]> {
  const sortMode = options?.sort ?? 'frontpage'
  const client = getSupabaseServerClient()
  if (!client) {
    return sortClusterSummaries(mockClusters.map(fallbackClusterSummary), sortMode)
  }

  try {
    const { data, error } = await client
      .from('story_clusters')
      .select(
        'id, slug, topic_label, canonical_headline, summary, status, latest_event_at, hero_media_url, hero_media_alt, hero_media_credit, outlet_count, coverage_counts, reliability_range, metadata',
      )
      .order('latest_event_at', { ascending: false })
      .limit(24)

    if (error) {
      throw error
    }

    if (!data || data.length === 0) {
      return []
    }

    return sortClusterSummaries(
      (data as StoryClusterRow[])
        .map(mapSummaryRow)
        .filter((summary) => isReaderVisibleStoryOrigin(summary.storyOrigin)),
      sortMode,
    )
  } catch (error) {
    console.error('Unable to load Supabase cluster summaries', error)
    return []
  }
}

export async function getClusterDetail(slug: string): Promise<StoryCluster | null> {
  const client = getSupabaseServerClient()
  if (!client) {
    return fallbackClusterDetail(slug)
  }

  try {
    const { data: clusterRow, error: clusterError } = await client
      .from('story_clusters')
      .select(
        'id, slug, topic_label, canonical_headline, summary, status, latest_event_at, hero_media_url, hero_media_alt, hero_media_credit, outlet_count, coverage_counts, reliability_range, metadata',
      )
      .eq('slug', slug)
      .maybeSingle()

    if (clusterError) {
      throw clusterError
    }

    if (!clusterRow) {
      return (await loadLiveStoryBySlug(slug)) ?? null
    }

    const [
      { data: keyFacts },
      { data: clusterArticles },
      { data: contextPackItems },
      { data: evidenceItems },
      { data: correctionEvents },
      { data: briefRevision },
    ] =
      await Promise.all([
        client
          .from('cluster_key_facts')
          .select('fact_text, sort_order')
          .eq('cluster_id', clusterRow.id)
          .order('sort_order', { ascending: true }),
        client
          .from('cluster_articles')
          .select(
            'rank_in_cluster, is_primary, framing_group, selection_reason, articles!inner(headline, dek, summary, body_text, published_at, preview_image_url, original_url, canonical_url, metadata, outlets(canonical_name))',
          )
          .eq('cluster_id', clusterRow.id)
          .order('rank_in_cluster', { ascending: true }),
        client
          .from('context_pack_items')
          .select(
            'lens, rank, title_override, why_included, articles!inner(headline, original_url, canonical_url, metadata, outlets(canonical_name))',
          )
          .eq('cluster_id', clusterRow.id)
          .order('rank', { ascending: true }),
        client
          .from('evidence_items')
          .select('label, source_name, source_type, sort_order')
          .eq('cluster_id', clusterRow.id)
          .order('sort_order', { ascending: true }),
        client
          .from('correction_events')
          .select('event_type, display_summary, notes, created_at')
          .eq('cluster_id', clusterRow.id)
          .order('created_at', { ascending: false })
          .limit(8),
        client
          .from('story_brief_revisions')
          .select(
            'label, title, status, paragraphs, why_it_matters, where_sources_agree, where_coverage_differs, what_to_watch, supporting_points, metadata',
          )
          .eq('cluster_id', clusterRow.id)
          .eq('is_current', true)
          .maybeSingle(),
      ])

    const normalizedCluster = mapSummaryRow(clusterRow as StoryClusterRow)
    if (!isReaderVisibleStoryOrigin(normalizedCluster.storyOrigin)) {
      return null
    }

    const articles =
      (clusterArticles as Array<{
        framing_group?: FramingGroup | null
        selection_reason?: string | null
        articles?: {
          headline?: string | null
          dek?: string | null
          summary?: string | null
          body_text?: string | null
          published_at?: string | null
          preview_image_url?: string | null
          original_url?: string | null
          canonical_url?: string | null
          metadata?: JsonObject | null
          outlets?: { canonical_name?: string | null } | null
        } | null
      }> | null)?.map((item, index) => {
        const articleMetadata = item.articles?.metadata || {}
        const namedEntities = Array.isArray(articleMetadata.named_entities)
          ? articleMetadata.named_entities.filter((value): value is string => typeof value === 'string')
          : []

        return {
        outlet: item.articles?.outlets?.canonical_name || 'Unknown outlet',
        title: item.articles?.headline || 'Untitled article',
        summary: normalizeSnippet(item.articles?.summary || item.articles?.dek, {
          maxChars: 220,
          fallback: `${
            item.articles?.outlets?.canonical_name || 'This outlet'
          } is covering this development from its own reporting angle.`,
        }),
        published: formatUpdatedAt(item.articles?.published_at),
        framing: (item.framing_group as FramingGroup | null) || 'center',
        image:
          item.articles?.preview_image_url ||
          `https://picsum.photos/seed/${normalizedCluster.slug}-article-${index + 1}/640/420`,
        reason:
          item.selection_reason ||
          'Included because it materially adds reporting or framing context to the story.',
        url: publicArticleUrl(item.articles?.original_url || item.articles?.canonical_url),
        accessTier: inferSourceAccessTier({
          outlet: item.articles?.outlets?.canonical_name,
          url: item.articles?.original_url || item.articles?.canonical_url,
          signal:
            typeof articleMetadata.access_signal === 'string'
              ? articleMetadata.access_signal
              : undefined,
        }),
        feedSummary:
          typeof articleMetadata.feed_summary === 'string' ? articleMetadata.feed_summary : undefined,
        bodyText: item.articles?.body_text || undefined,
        namedEntities,
        extractionQuality:
          typeof articleMetadata.extraction_quality === 'string'
            ? articleMetadata.extraction_quality
            : undefined,
      }
      }) ?? []

    const contextPacks = Object.fromEntries(
      ((contextPackItems as Array<{
        lens: string
        title_override?: string | null
        why_included: string
        articles?: {
          headline?: string | null
          original_url?: string | null
          canonical_url?: string | null
          metadata?: JsonObject | null
          outlets?: { canonical_name?: string | null } | null
        } | null
      }> | null) ?? []).reduce<Array<[string, StoryCluster['contextPacks'][string]]>>(
        (accumulator, item) => {
          const lensLabel = mapLensName(item.lens)
          const existing = accumulator.find(([label]) => label === lensLabel)
          const contextMetadata = item.articles?.metadata || {}
          const entry = {
            outlet: item.articles?.outlets?.canonical_name || 'Unknown outlet',
            title: item.title_override || item.articles?.headline || 'Untitled article',
            why: item.why_included,
            url: publicArticleUrl(item.articles?.original_url || item.articles?.canonical_url),
            accessTier: inferSourceAccessTier({
              outlet: item.articles?.outlets?.canonical_name,
              url: item.articles?.original_url || item.articles?.canonical_url,
              signal:
                typeof contextMetadata.access_signal === 'string' ? contextMetadata.access_signal : undefined,
            }),
          }

          if (existing) {
            existing[1].push(entry)
            return accumulator
          }

          accumulator.push([lensLabel, [entry]])
          return accumulator
        },
        [],
      ),
    ) as StoryCluster['contextPacks']

    const corrections =
      (correctionEvents as Array<{
        event_type: string
        display_summary: string
        notes: string
        created_at: string
      }> | null)?.map((item) => ({
        eventType: item.event_type,
        detail: item.notes,
        timestamp: new Date(item.created_at).toLocaleString('en-US', {
          hour: 'numeric',
          minute: '2-digit',
          month: 'short',
          day: 'numeric',
        }),
        note: item.display_summary || item.notes,
      })) ?? []

    const changeTimeline = corrections.map((item) => ({
      timestamp: item.timestamp,
      kind:
        item.eventType === 'summary_update'
          ? ('summary' as const)
          : item.eventType === 'evidence_update'
            ? ('evidence' as const)
            : item.eventType === 'article_remap' ||
                item.eventType === 'merge' ||
                item.eventType === 'split'
              ? ('coverage' as const)
              : ('correction' as const),
      label: item.note,
      detail: item.detail,
    }))

    return {
      slug: normalizedCluster.slug,
      topic: normalizedCluster.topic,
      title: normalizedCluster.title,
      dek: normalizedCluster.dek,
      updatedAt: normalizedCluster.updatedAt,
      status: normalizedCluster.status,
      heroImage: normalizedCluster.heroImage,
      heroAlt: normalizedCluster.heroAlt,
      heroCredit: normalizedCluster.heroCredit,
      outletCount: normalizedCluster.outletCount,
      reliabilityRange: normalizedCluster.reliabilityRange,
      coverageCounts: normalizedCluster.coverageCounts,
      keyFacts:
        (keyFacts as Array<{ fact_text: string }> | null)?.map((item) =>
          normalizeKeyFact(item.fact_text, normalizedCluster.outletCount, articles.length),
        ) ?? [],
      whatChanged: changeTimeline.slice(0, 3).map((item) => item.label),
      changeTimeline,
      articles,
      evidence:
        (evidenceItems as Array<{
          label: string
          source_name: string
          source_type: string
        }> | null)?.map((item) => ({
          label: item.label,
          source: item.source_name,
          type: item.source_type,
        })) ?? [],
      corrections,
      contextPacks,
      generatedBrief: mapStoredBrief(briefRevision as StoryBriefRevisionRow | null | undefined),
    }
  } catch (error) {
    console.error(`Unable to load Supabase cluster detail for ${slug}`, error)
    return (await loadLiveStoryBySlug(slug)) ?? null
  }
}
