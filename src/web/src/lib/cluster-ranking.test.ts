import assert from 'node:assert/strict'
import test from 'node:test'

import { buildClusterRankingFixture } from './cluster-ranking-regression-fixtures.js'
import { frontPagePriority, sortClusterSummaries } from './cluster-ranking.js'

function isoMinutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

test('front-page ranking ignores framing mix and reliability labels', () => {
  const baseline = buildClusterRankingFixture({
    slug: 'baseline',
    coverageCounts: { left: 1, center: 2, right: 1 },
    reliabilityRange: 'Established to high',
  })
  const prohibitedVariant = buildClusterRankingFixture({
    slug: 'prohibited-variant',
    coverageCounts: { left: 4, center: 0, right: 0 },
    reliabilityRange: 'Early source set',
  })

  assert.equal(frontPagePriority(baseline), frontPagePriority(prohibitedVariant))

  const sorted = sortClusterSummaries([prohibitedVariant, baseline], 'frontpage')
  assert.deepEqual(sorted.map((story) => story.slug), ['prohibited-variant', 'baseline'])
})

test('front-page ranking still rewards fresher reporting when allowed signals change', () => {
  const older = buildClusterRankingFixture({
    slug: 'older',
    latestEventAt: isoMinutesAgo(14 * 60),
  })
  const fresher = buildClusterRankingFixture({
    slug: 'fresher',
    latestEventAt: isoMinutesAgo(20),
  })

  const sorted = sortClusterSummaries([older, fresher], 'frontpage')
  assert.deepEqual(sorted.map((story) => story.slug), ['fresher', 'older'])
})

test('front-page ranking still rewards broader source breadth when allowed signals change', () => {
  const narrow = buildClusterRankingFixture({
    slug: 'narrow',
    outletCount: 1,
    qualityScore: 28,
    homepageEligible: false,
    status: 'Live intake',
  })
  const broad = buildClusterRankingFixture({
    slug: 'broad',
    outletCount: 4,
    qualityScore: 28,
    homepageEligible: true,
    status: 'Developing',
  })

  const sorted = sortClusterSummaries([narrow, broad], 'frontpage')
  assert.deepEqual(sorted.map((story) => story.slug), ['broad', 'narrow'])
})

test('latest mode stays recency-first even when prohibited fields differ', () => {
  const older = buildClusterRankingFixture({
    slug: 'older',
    latestEventAt: '2026-03-13T17:30:00Z',
    coverageCounts: { left: 4, center: 0, right: 0 },
    reliabilityRange: 'Early source set',
  })
  const newer = buildClusterRankingFixture({
    slug: 'newer',
    latestEventAt: '2026-03-13T18:30:00Z',
    coverageCounts: { left: 0, center: 0, right: 4 },
    reliabilityRange: 'Established to high',
  })

  const sorted = sortClusterSummaries([older, newer], 'latest')
  assert.deepEqual(sorted.map((story) => story.slug), ['newer', 'older'])
})
