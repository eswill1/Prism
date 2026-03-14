import type { ReaderTrackingState } from './reader-tracking-types'

export type StoryTrackingRecord = ReaderTrackingState

type StoryTrackingStore = Record<string, StoryTrackingRecord>

const STORAGE_KEY = 'prism.story_tracking.v1'

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function sanitizeRecord(slug: string, value: Partial<StoryTrackingRecord> | null | undefined) {
  return {
    slug,
    clusterId: typeof value?.clusterId === 'string' ? value.clusterId : undefined,
    title: typeof value?.title === 'string' ? value.title : undefined,
    topic: typeof value?.topic === 'string' ? value.topic : undefined,
    saved: value?.saved === true,
    followed: value?.followed === true,
    savedAt: typeof value?.savedAt === 'string' ? value.savedAt : undefined,
    followedAt: typeof value?.followedAt === 'string' ? value.followedAt : undefined,
    lastViewedAt: typeof value?.lastViewedAt === 'string' ? value.lastViewedAt : undefined,
    lastSeenBriefRevisionTag:
      typeof value?.lastSeenBriefRevisionTag === 'string'
        ? value.lastSeenBriefRevisionTag
        : undefined,
    lastSeenPerspectiveRevisionTag:
      typeof value?.lastSeenPerspectiveRevisionTag === 'string'
        ? value.lastSeenPerspectiveRevisionTag
        : undefined,
  } satisfies StoryTrackingRecord
}

export function readStoryTrackingStore(): StoryTrackingStore {
  if (!canUseStorage()) {
    return {}
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return {}
    }

    const parsed = JSON.parse(raw) as Record<string, Partial<StoryTrackingRecord>>
    return Object.fromEntries(
      Object.entries(parsed).map(([slug, record]) => [slug, sanitizeRecord(slug, record)]),
    )
  } catch {
    return {}
  }
}

export function listTrackedStoryRecords() {
  return Object.values(readStoryTrackingStore()).filter(
    (record) => record.saved || record.followed || record.lastViewedAt,
  )
}

function writeStoryTrackingStore(store: StoryTrackingStore) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store))
}

export function writeStoryTrackingRecord(record: StoryTrackingRecord) {
  const store = readStoryTrackingStore()
  store[record.slug] = sanitizeRecord(record.slug, record)
  writeStoryTrackingStore(store)
  return store[record.slug]
}

export function mergeStoryTrackingRecords(records: StoryTrackingRecord[]) {
  const store = readStoryTrackingStore()

  for (const record of records) {
    store[record.slug] = sanitizeRecord(record.slug, record)
  }

  writeStoryTrackingStore(store)
  return store
}

function upsertStoryTracking(
  slug: string,
  update: (existing: StoryTrackingRecord) => StoryTrackingRecord,
) {
  const store = readStoryTrackingStore()
  const nextRecord = update(sanitizeRecord(slug, store[slug]))

  if (!nextRecord.saved && !nextRecord.followed && !nextRecord.lastViewedAt) {
    delete store[slug]
  } else {
    store[slug] = nextRecord
  }

  writeStoryTrackingStore(store)
  return store[slug] ?? sanitizeRecord(slug, null)
}

export function getStoryTracking(slug: string) {
  return sanitizeRecord(slug, readStoryTrackingStore()[slug])
}

export function toggleSavedStory(
  story: Pick<StoryTrackingRecord, 'clusterId' | 'slug' | 'title' | 'topic'>,
) {
  return upsertStoryTracking(story.slug, (existing) => {
    const nextSaved = !existing.saved

    return {
      ...existing,
      clusterId: story.clusterId || existing.clusterId,
      title: story.title || existing.title,
      topic: story.topic || existing.topic,
      saved: nextSaved,
      savedAt: nextSaved ? new Date().toISOString() : undefined,
    }
  })
}

export function toggleFollowedStory(
  story: Pick<StoryTrackingRecord, 'clusterId' | 'slug' | 'title' | 'topic'>,
) {
  return upsertStoryTracking(story.slug, (existing) => {
    const nextFollowed = !existing.followed

    return {
      ...existing,
      clusterId: story.clusterId || existing.clusterId,
      title: story.title || existing.title,
      topic: story.topic || existing.topic,
      saved: nextFollowed ? true : existing.saved,
      savedAt: nextFollowed && !existing.saved ? new Date().toISOString() : existing.savedAt,
      followed: nextFollowed,
      followedAt: nextFollowed ? new Date().toISOString() : undefined,
    }
  })
}

export function markStoryViewed(
  story: Pick<StoryTrackingRecord, 'clusterId' | 'slug' | 'title' | 'topic'>,
) {
  return upsertStoryTracking(story.slug, (existing) => ({
    ...existing,
    clusterId: story.clusterId || existing.clusterId,
    title: story.title || existing.title,
    topic: story.topic || existing.topic,
    lastViewedAt: new Date().toISOString(),
  }))
}
