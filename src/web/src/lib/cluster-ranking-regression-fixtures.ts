import type { ClusterSummaryRankInput, CoverageCounts } from './cluster-ranking.js'

const baseCoverageCounts: CoverageCounts = {
  left: 1,
  center: 2,
  right: 1,
}

export function buildClusterRankingFixture(
  overrides: Partial<ClusterSummaryRankInput> = {},
): ClusterSummaryRankInput {
  return {
    slug: 'fixture-story',
    topic: 'World',
    title: 'Fixture story',
    dek: 'Fixture dek',
    updatedAt: 'Updated 1h ago',
    status: 'Developing',
    heroImage: 'https://example.com/hero.jpg',
    heroAlt: 'Fixture hero image',
    heroCredit: 'Fixture credit',
    outletCount: 3,
    reliabilityRange: 'Mixed source set',
    coverageCounts: { ...baseCoverageCounts },
    latestEventAt: '2026-03-13T18:00:00Z',
    storyOrigin: 'database',
    qualityScore: 42,
    homepageEligible: true,
    ...overrides,
  }
}
