import type { TrackedStoryHistoryEntry } from './reader-tracking-types'
import type { JsonObject } from './supabase/server'

type StoryBriefRevisionStatus = 'early' | 'full'
type StoryBriefComparisonMode = 'since_last_check' | 'latest_revision'

export type StoryBriefRevisionSnapshot = {
  revisionTag: string
  createdAt?: string | null
  status: StoryBriefRevisionStatus
  title: string
  paragraphs: string[]
  whyItMatters: string
  whereSourcesAgree: string
  whereCoverageDiffers: string
  whatToWatch: string
  supportingPoints: string[]
  metadata?: JsonObject | null
}

function readNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }

  return undefined
}

function normalizeTokens(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, ' ')
}

function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return count === 1 ? singular : plural
}

function describeSourceCount(sourceCount: number | undefined) {
  if (!sourceCount || sourceCount <= 0) {
    return 'the current linked reporting mix'
  }

  return `${sourceCount} substantive ${pluralize(sourceCount, 'source')}`
}

function joinLabels(labels: string[]) {
  if (labels.length === 0) {
    return ''
  }

  if (labels.length === 1) {
    return labels[0]
  }

  if (labels.length === 2) {
    return `${labels[0]} and ${labels[1]}`
  }

  return `${labels.slice(0, -1).join(', ')}, and ${labels.at(-1)}`
}

function changedSectionLabels(
  current: StoryBriefRevisionSnapshot,
  previous: StoryBriefRevisionSnapshot,
) {
  const labels: string[] = []

  if (normalizeTokens(current.whyItMatters) !== normalizeTokens(previous.whyItMatters)) {
    labels.push('Why it matters')
  }
  if (normalizeTokens(current.whereSourcesAgree) !== normalizeTokens(previous.whereSourcesAgree)) {
    labels.push('Where sources agree')
  }
  if (
    normalizeTokens(current.whereCoverageDiffers) !==
    normalizeTokens(previous.whereCoverageDiffers)
  ) {
    labels.push('Where coverage differs')
  }
  if (normalizeTokens(current.whatToWatch) !== normalizeTokens(previous.whatToWatch)) {
    labels.push('What to watch')
  }

  return labels
}

function buildPendingBriefHistory(): TrackedStoryHistoryEntry {
  return {
    state: 'pending',
    title: 'Stored narrative revision pending',
    changeSummary: [
      'Prism does not have a stored brief revision for this saved story yet.',
      'Open the story page again after the next brief generation pass if you want tracked narrative deltas here.',
    ],
  }
}

export function buildStoryBriefHistory(
  current: StoryBriefRevisionSnapshot | null | undefined,
  previous?: StoryBriefRevisionSnapshot | null,
  options?: {
    mode?: StoryBriefComparisonMode
  },
): TrackedStoryHistoryEntry {
  if (!current) {
    return buildPendingBriefHistory()
  }

  const mode = options?.mode ?? 'latest_revision'
  const currentMetadata = current.metadata || {}
  const previousMetadata = previous?.metadata || {}
  const currentSourceCount = readNumber(currentMetadata.substantive_source_count)
  const previousSourceCount = readNumber(previousMetadata.substantive_source_count)
  const currentParagraphCount = current.paragraphs.length
  const previousParagraphCount = previous?.paragraphs.length ?? 0
  const currentSupportingPoints = current.supportingPoints.length
  const previousSupportingPoints = previous?.supportingPoints.length ?? 0

  if (!previous) {
    const changeSummary = [
      `Prism now has a stored ${current.status === 'full' ? 'full' : 'early'} brief grounded in ${describeSourceCount(currentSourceCount)}.`,
      `The current narrative runs ${currentParagraphCount} ${pluralize(currentParagraphCount, 'paragraph')} with ${currentSupportingPoints} supporting ${pluralize(currentSupportingPoints, 'point')}.`,
    ]

    return {
      state: 'updated',
      title:
        mode === 'since_last_check'
          ? 'Narrative available since you last checked'
          : 'First stored narrative revision is live',
      currentRevisionTag: current.revisionTag,
      changeSummary,
    }
  }

  if (current.revisionTag === previous.revisionTag) {
    return {
      state: 'current',
      title:
        mode === 'since_last_check'
          ? 'Narrative unchanged since you last checked'
          : 'Narrative unchanged from the latest revision',
      currentRevisionTag: current.revisionTag,
      comparedToTag: previous.revisionTag,
      changeSummary: [
        `Prism is still serving the same ${current.status === 'full' ? 'full' : 'early'} brief revision for this story.`,
      ],
    }
  }

  const changeSummary: string[] = []

  if (current.status !== previous.status) {
    changeSummary.push(
      current.status === 'full'
        ? `Narrative matured from an early brief to a full brief after source breadth grew to ${describeSourceCount(currentSourceCount)}.`
        : `Narrative moved from a full brief back to an early brief because the current story mix narrowed to ${describeSourceCount(currentSourceCount)}.`,
    )
  }

  if (
    changeSummary.length < 3 &&
    currentSourceCount !== undefined &&
    previousSourceCount !== undefined &&
    currentSourceCount !== previousSourceCount
  ) {
    changeSummary.push(
      currentSourceCount > previousSourceCount
        ? `Substantive source breadth expanded from ${describeSourceCount(previousSourceCount)} to ${describeSourceCount(currentSourceCount)}.`
        : `Substantive source breadth narrowed from ${describeSourceCount(previousSourceCount)} to ${describeSourceCount(currentSourceCount)}.`,
    )
  }

  if (
    changeSummary.length < 3 &&
    currentParagraphCount !== previousParagraphCount
  ) {
    changeSummary.push(
      currentParagraphCount > previousParagraphCount
        ? `The narrative summary expanded from ${previousParagraphCount} to ${currentParagraphCount} paragraphs.`
        : `The narrative summary tightened from ${previousParagraphCount} to ${currentParagraphCount} paragraphs.`,
    )
  }

  const sectionsChanged = changedSectionLabels(current, previous)
  if (changeSummary.length < 3 && sectionsChanged.length > 0) {
    changeSummary.push(`Prism refreshed ${joinLabels(sectionsChanged)} in the current brief.`)
  }

  if (
    changeSummary.length < 3 &&
    currentSupportingPoints !== previousSupportingPoints
  ) {
    changeSummary.push(
      `Supporting points shifted from ${previousSupportingPoints} to ${currentSupportingPoints} highlighted ${pluralize(currentSupportingPoints, 'item')}.`,
    )
  }

  if (changeSummary.length === 0) {
    changeSummary.push(
      'Prism refreshed the narrative brief copy while keeping the same brief stage and source breadth.',
    )
  }

  return {
    state: 'updated',
    title:
      mode === 'since_last_check'
        ? 'Narrative changed since you last checked'
        : 'Latest narrative revision is different',
    currentRevisionTag: current.revisionTag,
    comparedToTag: previous.revisionTag,
    changeSummary: changeSummary.slice(0, 3),
  }
}
