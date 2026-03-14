import {
  buildPerspectiveRevisionInfo,
  type PerspectiveRevisionSnapshot,
} from './perspective-versioning'
import type {
  TrackedStoryHistory,
  TrackedStoryHistoryEntry,
} from './reader-tracking-types'
import {
  buildStoryBriefHistory,
  type StoryBriefRevisionSnapshot,
} from './story-brief-versioning'

type ComparisonMode = 'since_last_check' | 'latest_revision'

type TrackedStoryHistoryInput = {
  currentBrief?: StoryBriefRevisionSnapshot | null
  seenBrief?: StoryBriefRevisionSnapshot | null
  previousBrief?: StoryBriefRevisionSnapshot | null
  lastSeenBriefRevisionTag?: string
  currentPerspective?: PerspectiveRevisionSnapshot | null
  seenPerspective?: PerspectiveRevisionSnapshot | null
  previousPerspective?: PerspectiveRevisionSnapshot | null
  lastSeenPerspectiveRevisionTag?: string
}

function buildPendingPerspectiveHistory(): TrackedStoryHistoryEntry {
  return {
    state: 'pending',
    title: 'Stored Perspective revision pending',
    changeSummary: [
      'Prism does not have a stored Perspective revision for this saved story yet.',
      'Open the story page again after the next Perspective generation pass if you want tracked framing deltas here.',
    ],
  }
}

function selectComparisonSnapshot<T extends { revisionTag: string }>(
  current: T | null | undefined,
  seen: T | null | undefined,
  previous: T | null | undefined,
  lastSeenRevisionTag?: string,
) {
  if (lastSeenRevisionTag && seen) {
    return {
      mode: 'since_last_check' as const,
      snapshot: seen,
    }
  }

  if (previous && previous.revisionTag !== current?.revisionTag) {
    return {
      mode: 'latest_revision' as const,
      snapshot: previous,
    }
  }

  return {
    mode: (lastSeenRevisionTag ? 'since_last_check' : 'latest_revision') as ComparisonMode,
    snapshot: undefined,
  }
}

function buildPerspectiveHistory(
  current: PerspectiveRevisionSnapshot | null | undefined,
  previous?: PerspectiveRevisionSnapshot | null,
  options?: {
    mode?: ComparisonMode
  },
): TrackedStoryHistoryEntry {
  if (!current) {
    return buildPendingPerspectiveHistory()
  }

  const mode = options?.mode ?? 'latest_revision'

  if (!previous) {
    return {
      state: 'updated',
      title:
        mode === 'since_last_check'
          ? 'Perspective available since you last checked'
          : 'First stored Perspective revision is live',
      currentRevisionTag: current.revisionTag,
      changeSummary: buildPerspectiveRevisionInfo(current).changeSummary,
    }
  }

  if (current.revisionTag === previous.revisionTag) {
    return {
      state: 'current',
      title:
        mode === 'since_last_check'
          ? 'Perspective unchanged since you last checked'
          : 'Perspective unchanged from the latest revision',
      currentRevisionTag: current.revisionTag,
      comparedToTag: previous.revisionTag,
      changeSummary: [
        `Prism is still serving the same ${current.status} Perspective revision for this story.`,
      ],
    }
  }

  const revisionInfo = buildPerspectiveRevisionInfo(current, previous)
  return {
    state: 'updated',
    title:
      mode === 'since_last_check'
        ? 'Perspective changed since you last checked'
        : 'Latest Perspective revision is different',
    currentRevisionTag: current.revisionTag,
    comparedToTag: previous.revisionTag,
    changeSummary: revisionInfo.changeSummary.slice(0, 3),
  }
}

export function buildTrackedStoryHistory(input: TrackedStoryHistoryInput): TrackedStoryHistory {
  const briefComparison = selectComparisonSnapshot(
    input.currentBrief,
    input.seenBrief,
    input.previousBrief,
    input.lastSeenBriefRevisionTag,
  )
  const perspectiveComparison = selectComparisonSnapshot(
    input.currentPerspective,
    input.seenPerspective,
    input.previousPerspective,
    input.lastSeenPerspectiveRevisionTag,
  )

  const narrative = buildStoryBriefHistory(input.currentBrief, briefComparison.snapshot, {
    mode: briefComparison.mode,
  })
  const perspective = buildPerspectiveHistory(
    input.currentPerspective,
    perspectiveComparison.snapshot,
    {
      mode: perspectiveComparison.mode,
    },
  )

  return {
    hasUpdates: narrative.state === 'updated' || perspective.state === 'updated',
    narrative,
    perspective,
  }
}
