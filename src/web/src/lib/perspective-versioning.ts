import type { JsonObject } from './supabase/server'
import type { StoryPerspectiveRevisionInfo } from './story-perspective-types'

type PerspectiveRevisionStatus = 'early' | 'ready'

export type PerspectiveRevisionSnapshot = {
  revisionTag: string
  createdAt?: string | null
  generationMethod: string
  status: PerspectiveRevisionStatus
  summary: string
  takeaways: string[]
  metadata?: JsonObject | null
}

const perspectiveLensLabels: Record<string, string> = {
  balanced_framing: 'Balanced Framing',
  evidence_first: 'Evidence-First',
  international_comparison: 'International Comparison',
  local_impact: 'Local Impact',
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

function readBoolean(value: unknown) {
  return typeof value === 'boolean' ? value : undefined
}

function readJsonObject(value: unknown): JsonObject | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined
  }

  return value as JsonObject
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

function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return count === 1 ? singular : plural
}

function describeSourceMix(sourceCount: number | undefined, outletCount: number | undefined) {
  const sources = sourceCount ?? 0
  const outlets = outletCount ?? 0
  return `${sources} substantive ${pluralize(sources, 'report')} across ${outlets} ${pluralize(outlets, 'outlet')}`
}

function normalizeTokens(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, ' ')
}

function listReadyLenses(metadata?: JsonObject | null) {
  const lensStatuses = readJsonObject(metadata?.lens_statuses)
  if (lensStatuses) {
    return Object.entries(lensStatuses)
      .filter(([, rawValue]) => readJsonObject(rawValue)?.status === 'ready')
      .map(([key]) => perspectiveLensLabels[key] || key)
      .sort((left, right) => left.localeCompare(right))
  }

  const lensCounts = readJsonObject(metadata?.lens_counts)
  if (!lensCounts) {
    return []
  }

  return Object.entries(lensCounts)
    .filter(([, rawValue]) => (readNumber(rawValue) ?? 0) > 0)
    .map(([key]) => perspectiveLensLabels[key] || key)
    .sort((left, right) => left.localeCompare(right))
}

function formatGeneratedAt(value?: string | null) {
  const trimmed = value?.trim()
  if (!trimmed) {
    return 'Stored revision pending'
  }

  const timestamp = new Date(trimmed)
  if (Number.isNaN(timestamp.getTime())) {
    return 'Stored revision pending'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(timestamp)
}

export function humanizeGenerationMethod(value: string) {
  if (!value.trim()) {
    return 'Unknown method'
  }

  if (value === 'page_heuristic_fallback') {
    return 'Page fallback'
  }

  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((token) => token.slice(0, 1).toUpperCase() + token.slice(1))
    .join(' ')
}

export function buildFallbackPerspectiveRevision(): StoryPerspectiveRevisionInfo {
  return {
    stage: 'fallback',
    revisionTag: 'pending-stored-perspective',
    generatedAtLabel: 'Stored revision pending',
    generationMethod: 'page_heuristic_fallback',
    generationMethodLabel: humanizeGenerationMethod('page_heuristic_fallback'),
    changeSummary: [
      'Prism does not have a stored Perspective revision for this story yet.',
      'The current rail is using page-level fallback heuristics until the next Perspective generation pass runs.',
    ],
  }
}

export function buildPerspectiveRevisionInfo(
  current: PerspectiveRevisionSnapshot,
  previous?: PerspectiveRevisionSnapshot | null,
): StoryPerspectiveRevisionInfo {
  const currentMetadata = current.metadata || {}
  const previousMetadata = previous?.metadata || {}
  const currentSourceCount = readNumber(currentMetadata.substantive_source_count)
  const currentOutletCount = readNumber(currentMetadata.substantive_outlet_count)
  const previousSourceCount = readNumber(previousMetadata.substantive_source_count)
  const previousOutletCount = readNumber(previousMetadata.substantive_outlet_count)
  const currentFramingDiversity = readNumber(currentMetadata.framing_diversity)
  const previousFramingDiversity = readNumber(previousMetadata.framing_diversity)
  const currentFamilyDiversity = readNumber(currentMetadata.source_family_diversity)
  const previousFamilyDiversity = readNumber(previousMetadata.source_family_diversity)
  const currentScopeDiversity = readNumber(currentMetadata.scope_diversity)
  const previousScopeDiversity = readNumber(previousMetadata.scope_diversity)
  const currentManualReview = readBoolean(currentMetadata.manual_review_required)
  const previousManualReview = readBoolean(previousMetadata.manual_review_required)
  const currentReadyLenses = listReadyLenses(currentMetadata)
  const previousReadyLenses = listReadyLenses(previousMetadata)
  const gainedLenses = currentReadyLenses.filter((label) => !previousReadyLenses.includes(label))
  const lostLenses = previousReadyLenses.filter((label) => !currentReadyLenses.includes(label))
  const currentTakeaways = current.takeaways.map(normalizeTokens)
  const previousTakeaways = previous?.takeaways.map(normalizeTokens) ?? []
  const summaryChanged = normalizeTokens(current.summary) !== normalizeTokens(previous?.summary ?? '')
  const takeawaysChanged =
    currentTakeaways.length !== previousTakeaways.length ||
    currentTakeaways.some((item, index) => item !== previousTakeaways[index])

  const changeSummary: string[] = []

  if (!previous) {
    changeSummary.push(
      `This is the first stored Perspective revision for this story, built from ${describeSourceMix(currentSourceCount, currentOutletCount)}.`,
    )
    if (currentReadyLenses.length > 0) {
      changeSummary.push(
        `${joinLabels(currentReadyLenses)} ${currentReadyLenses.length === 1 ? 'is' : 'are'} currently justified by the linked reporting mix.`,
      )
    } else {
      changeSummary.push('Context Packs are still gated until Prism sees stronger source breadth for this story.')
    }
  } else {
    if (current.status !== previous.status) {
      changeSummary.push(
        current.status === 'ready'
          ? `Perspective moved from early to ready after Prism reached ${describeSourceMix(currentSourceCount, currentOutletCount)}.`
          : `Perspective moved from ready back to early because the linked source mix narrowed to ${describeSourceMix(currentSourceCount, currentOutletCount)}.`,
      )
    }

    if (
      currentSourceCount !== undefined &&
      currentOutletCount !== undefined &&
      previousSourceCount !== undefined &&
      previousOutletCount !== undefined &&
      (currentSourceCount !== previousSourceCount || currentOutletCount !== previousOutletCount)
    ) {
      const widened =
        currentSourceCount >= previousSourceCount &&
        currentOutletCount >= previousOutletCount &&
        (currentSourceCount > previousSourceCount || currentOutletCount > previousOutletCount)
      const narrowed =
        currentSourceCount <= previousSourceCount &&
        currentOutletCount <= previousOutletCount &&
        (currentSourceCount < previousSourceCount || currentOutletCount < previousOutletCount)

      changeSummary.push(
        widened
          ? `Source breadth widened from ${describeSourceMix(previousSourceCount, previousOutletCount)} to ${describeSourceMix(currentSourceCount, currentOutletCount)}.`
          : narrowed
            ? `Source breadth narrowed from ${describeSourceMix(previousSourceCount, previousOutletCount)} to ${describeSourceMix(currentSourceCount, currentOutletCount)}.`
            : `The reporting mix shifted from ${describeSourceMix(previousSourceCount, previousOutletCount)} to ${describeSourceMix(currentSourceCount, currentOutletCount)}.`,
      )
    }

    if (gainedLenses.length > 0 || lostLenses.length > 0) {
      if (gainedLenses.length > 0 && lostLenses.length > 0) {
        changeSummary.push(
          `Lens availability shifted: ${joinLabels(gainedLenses)} opened while ${joinLabels(lostLenses)} dropped out.`,
        )
      } else if (gainedLenses.length > 0) {
        changeSummary.push(
          `${joinLabels(gainedLenses)} ${gainedLenses.length === 1 ? 'is' : 'are'} now justified by the current source mix.`,
        )
      } else {
        changeSummary.push(
          `${joinLabels(lostLenses)} ${lostLenses.length === 1 ? 'is no longer' : 'are no longer'} justified by the current source mix.`,
        )
      }
    }

    if (
      changeSummary.length < 3 &&
      currentManualReview !== undefined &&
      previousManualReview !== undefined &&
      currentManualReview !== previousManualReview
    ) {
      changeSummary.push(
        currentManualReview
          ? 'Prism flagged this revision for manual review because the current coverage mix still looks thin or uneven.'
          : 'Manual review is no longer required for the current Perspective revision.',
      )
    }

    if (
      changeSummary.length < 3 &&
      (summaryChanged || takeawaysChanged) &&
      (currentFramingDiversity !== previousFramingDiversity ||
        currentFamilyDiversity !== previousFamilyDiversity ||
        currentScopeDiversity !== previousScopeDiversity)
    ) {
      changeSummary.push(
        'The summary and takeaways were refreshed to match a meaningfully different framing, source-family, or scope mix.',
      )
    }

    if (changeSummary.length === 0 && (summaryChanged || takeawaysChanged)) {
      changeSummary.push('The Perspective summary and takeaways were refreshed against the latest linked reporting.')
    }
  }

  if (changeSummary.length === 0) {
    changeSummary.push('Perspective was regenerated against the latest linked reporting without crossing a new display threshold.')
  }

  return {
    stage: 'stored',
    revisionTag: current.revisionTag,
    comparedToTag: previous?.revisionTag,
    generatedAt: current.createdAt ?? undefined,
    generatedAtLabel: formatGeneratedAt(current.createdAt),
    generationMethod: current.generationMethod,
    generationMethodLabel: humanizeGenerationMethod(current.generationMethod),
    changeSummary: changeSummary.slice(0, 3),
  }
}
