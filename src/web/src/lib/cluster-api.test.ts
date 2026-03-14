import assert from 'node:assert/strict'
import test from 'node:test'

import { storedBriefShouldRender } from './cluster-api'

test('stored briefs stay hidden when they only contain an opener and Prism scope note', () => {
  const visibility = storedBriefShouldRender(
    [
      'Around 2,500 U.S. Marines are heading for the Middle East, along with a Navy amphibious warship. Their mission is not yet clear, but it signals a marked increase in U.S. forces in the region.',
      "Prism is still treating this as a one-source early brief grounded primarily in PBS NewsHour's reporting. It should already give readers the core story and immediate stakes, but Prism still needs another independent detailed report before coverage differences become useful to compare.",
    ],
    null,
  )

  assert.deepEqual(visibility, {
    visible: false,
    reason: 'no_distinct_grounded_followup',
  })
})

test('stored briefs render when a later paragraph adds grounded detail beyond the opener', () => {
  const visibility = storedBriefShouldRender(
    [
      'Around 2,500 U.S. Marines are heading for the Middle East, along with a Navy amphibious warship. Their mission is not yet clear, but it signals a marked increase in U.S. forces in the region.',
      'The deployment comes as the Pentagon said more than 15,000 targets had been struck in Iran over nearly two weeks of relentless bombing against the regime.',
      "Prism is still treating this as a one-source early brief grounded primarily in PBS NewsHour's reporting. It should already give readers the core story and immediate stakes, but Prism still needs another independent detailed report before coverage differences become useful to compare.",
    ],
    null,
  )

  assert.deepEqual(visibility, {
    visible: true,
    reason: undefined,
  })
})

test('stored brief metadata can force-hide a brief even when paragraphs exist', () => {
  const visibility = storedBriefShouldRender(
    [
      'Opening paragraph.',
      'A distinct-looking second paragraph.',
    ],
    {
      display_visible: false,
      display_hide_reason: 'no_distinct_grounded_followup',
    },
  )

  assert.deepEqual(visibility, {
    visible: false,
    reason: 'no_distinct_grounded_followup',
  })
})
