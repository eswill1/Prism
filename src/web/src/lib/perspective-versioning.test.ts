import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildFallbackPerspectiveRevision,
  buildPerspectiveRevisionInfo,
} from './perspective-versioning.js'

test('buildFallbackPerspectiveRevision exposes pending stored state', () => {
  const revision = buildFallbackPerspectiveRevision()

  assert.equal(revision.stage, 'fallback')
  assert.equal(revision.revisionTag, 'pending-stored-perspective')
  assert.equal(revision.generationMethod, 'page_heuristic_fallback')
  assert.equal(revision.changeSummary.length, 2)
})

test('buildPerspectiveRevisionInfo summarizes initial stored revision', () => {
  const revision = buildPerspectiveRevisionInfo({
    revisionTag: 'perspective-20260313003000',
    createdAt: '2026-03-13T00:30:00Z',
    generationMethod: 'deterministic_presence_v1',
    status: 'early',
    summary: 'Perspective is still early here.',
    takeaways: ['Source set is still narrow.'],
    metadata: {
      substantive_source_count: 2,
      substantive_outlet_count: 2,
      lens_statuses: {
        balanced_framing: { status: 'ready', count: 2 },
        evidence_first: { status: 'ready', count: 2 },
        local_impact: { status: 'unavailable', count: 0 },
        international_comparison: { status: 'unavailable', count: 0 },
      },
    },
  })

  assert.equal(revision.stage, 'stored')
  assert.equal(revision.revisionTag, 'perspective-20260313003000')
  assert.match(revision.changeSummary[0] || '', /first stored Perspective revision/i)
  assert.match(revision.changeSummary[1] || '', /Balanced Framing and Evidence-First/i)
})

test('buildPerspectiveRevisionInfo highlights status and lens changes against prior revision', () => {
  const revision = buildPerspectiveRevisionInfo(
    {
      revisionTag: 'perspective-20260313004500',
      createdAt: '2026-03-13T00:45:00Z',
      generationMethod: 'deterministic_presence_v1',
      status: 'ready',
      summary: 'Perspective now has a broader comparison set.',
      takeaways: ['Multiple outlet families are represented.'],
      metadata: {
        substantive_source_count: 4,
        substantive_outlet_count: 3,
        lens_statuses: {
          balanced_framing: { status: 'ready', count: 3 },
          evidence_first: { status: 'ready', count: 2 },
          local_impact: { status: 'ready', count: 1 },
          international_comparison: { status: 'unavailable', count: 0 },
        },
      },
    },
    {
      revisionTag: 'perspective-20260313001500',
      createdAt: '2026-03-13T00:15:00Z',
      generationMethod: 'deterministic_presence_v1',
      status: 'early',
      summary: 'Perspective is still early here.',
      takeaways: ['Source set is still narrow.'],
      metadata: {
        substantive_source_count: 2,
        substantive_outlet_count: 2,
        lens_statuses: {
          balanced_framing: { status: 'ready', count: 2 },
          evidence_first: { status: 'unavailable', count: 0 },
          local_impact: { status: 'unavailable', count: 0 },
          international_comparison: { status: 'unavailable', count: 0 },
        },
      },
    },
  )

  assert.equal(revision.comparedToTag, 'perspective-20260313001500')
  assert.match(revision.changeSummary[0] || '', /moved from early to ready/i)
  assert.ok(
    revision.changeSummary.some((item) => /Evidence-First and Local Impact|Local Impact and Evidence-First/i.test(item)),
  )
})
