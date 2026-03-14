import { getNewsSectionKey } from './news-sections'

export type CoverageCounts = {
  left: number
  center: number
  right: number
}

export type ClusterSummaryRankInput = {
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
  coverageCounts: CoverageCounts
  latestEventAt: string
  storyOrigin: string
  qualityScore: number
  homepageEligible: boolean
}

export type ClusterSortMode = 'frontpage' | 'latest'

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

export function frontPagePriority(summary: ClusterSummaryRankInput) {
  let score = summary.qualityScore
  score += Math.min(summary.outletCount, 4) * 14
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

export function sortClusterSummaries<T extends ClusterSummaryRankInput>(
  clusters: T[],
  mode: ClusterSortMode,
) {
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
