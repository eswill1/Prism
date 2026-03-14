export type ReaderTrackingState = {
  clusterId?: string
  slug: string
  title?: string
  topic?: string
  saved: boolean
  followed: boolean
  savedAt?: string
  followedAt?: string
  lastViewedAt?: string
  lastSeenBriefRevisionTag?: string
  lastSeenPerspectiveRevisionTag?: string
}

export type ReaderTrackingMutation = {
  clusterId?: string
  slug: string
  title?: string
  topic?: string
  saved?: boolean
  followed?: boolean
  markViewed?: boolean
  lastSeenBriefRevisionTag?: string
  lastSeenPerspectiveRevisionTag?: string
}

export type TrackedStoryHistoryEntry = {
  state: 'updated' | 'current' | 'pending'
  title: string
  currentRevisionTag?: string
  comparedToTag?: string
  changeSummary: string[]
}

export type TrackedStoryHistory = {
  hasUpdates: boolean
  narrative: TrackedStoryHistoryEntry
  perspective: TrackedStoryHistoryEntry
}

export type RemoteTrackedStory = {
  clusterId: string
  slug: string
  topic: string
  title: string
  dek: string
  updatedAt: string
  heroImage: string
  heroAlt: string
  latestChange?: string
  changeCount: number
  tracking: ReaderTrackingState
  history: TrackedStoryHistory
}
