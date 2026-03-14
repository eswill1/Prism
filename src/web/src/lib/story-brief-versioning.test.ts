import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildStoryBriefHistory,
  type StoryBriefRevisionSnapshot,
} from './story-brief-versioning'

function createBriefSnapshot(
  overrides: Partial<StoryBriefRevisionSnapshot> = {},
): StoryBriefRevisionSnapshot {
  return {
    revisionTag: 'brief-v2',
    createdAt: '2026-03-13T12:00:00Z',
    status: 'full',
    title: 'Prism brief',
    paragraphs: [
      'Paragraph one.',
      'Paragraph two.',
      'Paragraph three.',
    ],
    whyItMatters: 'Why it matters.',
    whereSourcesAgree: 'Where sources agree.',
    whereCoverageDiffers: 'Where coverage differs.',
    whatToWatch: 'What to watch.',
    supportingPoints: ['Point one', 'Point two', 'Point three'],
    metadata: {
      substantive_source_count: 3,
    },
    ...overrides,
  }
}

test('buildStoryBriefHistory flags a mature update since last check', () => {
  const previous = createBriefSnapshot({
    revisionTag: 'brief-v1',
    status: 'early',
    paragraphs: ['Paragraph one.', 'Paragraph two.'],
    supportingPoints: ['Point one'],
    metadata: {
      substantive_source_count: 1,
    },
  })

  const current = createBriefSnapshot()

  const history = buildStoryBriefHistory(current, previous, {
    mode: 'since_last_check',
  })

  assert.equal(history.state, 'updated')
  assert.equal(history.title, 'Narrative changed since you last checked')
  assert.equal(history.currentRevisionTag, 'brief-v2')
  assert.equal(history.comparedToTag, 'brief-v1')
  assert.match(history.changeSummary[0] || '', /matured from an early brief to a full brief/i)
})

test('buildStoryBriefHistory reports unchanged revisions cleanly', () => {
  const current = createBriefSnapshot()
  const history = buildStoryBriefHistory(current, current, {
    mode: 'since_last_check',
  })

  assert.equal(history.state, 'current')
  assert.equal(history.title, 'Narrative unchanged since you last checked')
  assert.equal(history.changeSummary.length, 1)
  assert.match(history.changeSummary[0] || '', /same full brief revision/i)
})

test('buildStoryBriefHistory handles missing stored revisions', () => {
  const history = buildStoryBriefHistory(null, null)

  assert.equal(history.state, 'pending')
  assert.equal(history.title, 'Stored narrative revision pending')
  assert.match(history.changeSummary[0] || '', /does not have a stored brief revision/i)
})
