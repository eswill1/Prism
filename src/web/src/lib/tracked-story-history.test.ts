import assert from 'node:assert/strict'
import test from 'node:test'

import type { PerspectiveRevisionSnapshot } from './perspective-versioning'
import type { StoryBriefRevisionSnapshot } from './story-brief-versioning'
import { buildTrackedStoryHistory } from './tracked-story-history'

function createBriefSnapshot(
  overrides: Partial<StoryBriefRevisionSnapshot> = {},
): StoryBriefRevisionSnapshot {
  return {
    revisionTag: 'brief-v2',
    status: 'full',
    title: 'Prism brief',
    paragraphs: ['Paragraph one.', 'Paragraph two.', 'Paragraph three.'],
    whyItMatters: 'Why it matters.',
    whereSourcesAgree: 'Where sources agree.',
    whereCoverageDiffers: 'Where coverage differs.',
    whatToWatch: 'Watch for the next update.',
    supportingPoints: ['Point one', 'Point two'],
    metadata: {
      substantive_source_count: 3,
    },
    ...overrides,
  }
}

function createPerspectiveSnapshot(
  overrides: Partial<PerspectiveRevisionSnapshot> = {},
): PerspectiveRevisionSnapshot {
  return {
    revisionTag: 'perspective-v2',
    createdAt: '2026-03-13T12:00:00Z',
    generationMethod: 'stored_generator_v1',
    status: 'ready',
    summary: 'Perspective summary.',
    takeaways: ['Takeaway one', 'Takeaway two'],
    metadata: {
      substantive_source_count: 3,
      substantive_outlet_count: 2,
      lens_counts: {
        balanced_framing: 2,
      },
    },
    ...overrides,
  }
}

test('buildTrackedStoryHistory compares against last seen revisions when available', () => {
  const history = buildTrackedStoryHistory({
    currentBrief: createBriefSnapshot(),
    seenBrief: createBriefSnapshot({
      revisionTag: 'brief-v1',
      status: 'early',
      paragraphs: ['Paragraph one.', 'Paragraph two.'],
      supportingPoints: ['Point one'],
      metadata: {
        substantive_source_count: 1,
      },
    }),
    lastSeenBriefRevisionTag: 'brief-v1',
    currentPerspective: createPerspectiveSnapshot(),
    seenPerspective: createPerspectiveSnapshot({
      revisionTag: 'perspective-v1',
      status: 'early',
      metadata: {
        substantive_source_count: 1,
        substantive_outlet_count: 1,
        lens_counts: {},
      },
    }),
    lastSeenPerspectiveRevisionTag: 'perspective-v1',
  })

  assert.equal(history.hasUpdates, true)
  assert.equal(history.narrative.title, 'Narrative changed since you last checked')
  assert.equal(history.perspective.title, 'Perspective changed since you last checked')
  assert.equal(history.narrative.comparedToTag, 'brief-v1')
  assert.equal(history.perspective.comparedToTag, 'perspective-v1')
})

test('buildTrackedStoryHistory falls back to latest revision when no last-seen tags exist', () => {
  const currentBrief = createBriefSnapshot()
  const currentPerspective = createPerspectiveSnapshot()
  const history = buildTrackedStoryHistory({
    currentBrief,
    previousBrief: createBriefSnapshot({
      revisionTag: 'brief-v1',
      paragraphs: ['Paragraph one.', 'Paragraph two.'],
    }),
    currentPerspective,
    previousPerspective: createPerspectiveSnapshot({
      revisionTag: 'perspective-v1',
      summary: 'Older summary.',
    }),
  })

  assert.equal(history.hasUpdates, true)
  assert.equal(history.narrative.title, 'Latest narrative revision is different')
  assert.equal(history.perspective.title, 'Latest Perspective revision is different')
})

test('buildTrackedStoryHistory reports pending state when stored revisions are missing', () => {
  const history = buildTrackedStoryHistory({})

  assert.equal(history.hasUpdates, false)
  assert.equal(history.narrative.state, 'pending')
  assert.equal(history.perspective.state, 'pending')
})
