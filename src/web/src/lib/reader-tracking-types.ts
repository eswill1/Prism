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
}
