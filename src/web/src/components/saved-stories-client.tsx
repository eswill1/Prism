'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { loadTrackedStories, previewTrackedStories } from '../lib/reader-tracking-client'
import type { RemoteTrackedStory } from '../lib/reader-tracking-types'
import {
  readStoryTrackingStore,
  type StoryTrackingRecord,
} from '../lib/story-tracking'
import { useLocalTrackingImport } from '../lib/use-local-tracking-import'
import { useReaderSession } from '../lib/use-reader-session'

export type TrackedStoryCandidate = {
  clusterId?: string
  slug: string
  topic: string
  title: string
  dek: string
  updatedAt: string
  heroImage: string
  heroAlt: string
  latestChange?: string
  changeCount: number
}

type SavedStoriesClientProps = {
  stories: TrackedStoryCandidate[]
}

type RenderTrackedStory = TrackedStoryCandidate & {
  tracking?: StoryTrackingRecord
  history?: RemoteTrackedStory['history']
}

function formatTrackedDate(value?: string) {
  if (!value) {
    return 'Not opened recently'
  }

  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function toSortedLocalStories(
  stories: TrackedStoryCandidate[],
  store: Record<string, StoryTrackingRecord>,
) {
  return stories
    .map((story) => ({
      ...story,
      tracking: store[story.slug],
    }))
    .filter((story) => story.tracking?.saved || story.tracking?.followed)
    .sort((left, right) => {
      const leftTimestamp =
        left.tracking?.followedAt || left.tracking?.savedAt || left.tracking?.lastViewedAt || ''
      const rightTimestamp =
        right.tracking?.followedAt ||
        right.tracking?.savedAt ||
        right.tracking?.lastViewedAt ||
        ''

      return rightTimestamp.localeCompare(leftTimestamp)
    })
}

function toRenderedRemoteStories(stories: RemoteTrackedStory[]) {
  return stories.map((story) => ({
    clusterId: story.clusterId,
    slug: story.slug,
    topic: story.topic,
    title: story.title,
    dek: story.dek,
    updatedAt: story.updatedAt,
    heroImage: story.heroImage,
    heroAlt: story.heroAlt,
    latestChange: story.latestChange,
    changeCount: story.changeCount,
    tracking: story.tracking,
    history: story.history,
  }))
}

function renderHistoryEntry(
  label: string,
  entry: RemoteTrackedStory['history']['narrative'],
) {
  return (
    <article className={`saved-history-card saved-history-card-${entry.state}`}>
      <div className="saved-history-header">
        <p className="panel-label">{label}</p>
        {entry.currentRevisionTag ? (
          <span className="saved-history-tag">{entry.currentRevisionTag}</span>
        ) : null}
      </div>
      <p className="saved-history-title">{entry.title}</p>
      {entry.comparedToTag ? (
        <p className="saved-history-compare">Compared with {entry.comparedToTag}</p>
      ) : null}
      <ul className="simple-list saved-history-list">
        {entry.changeSummary.map((item) => (
          <li key={`${label}-${entry.currentRevisionTag || entry.title}-${item}`}>{item}</li>
        ))}
      </ul>
    </article>
  )
}

export function SavedStoriesClient({ stories }: SavedStoriesClientProps) {
  const session = useReaderSession()
  const [trackedStories, setTrackedStories] = useState<RenderTrackedStory[]>([])
  const [syncError, setSyncError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const importState = useLocalTrackingImport({
    enabled: session.status === 'signed_in',
    onImported: () => {
      if (session.status !== 'signed_in' || !session.accessToken) {
        return
      }

      loadTrackedStories(session.accessToken)
        .then(({ stories: remoteStories }) => {
          setTrackedStories(toRenderedRemoteStories(remoteStories))
          setSyncError(null)
        })
        .catch((error) => {
          setSyncError(
            error instanceof Error ? error.message : 'Unable to load synced saved stories.',
          )
        })
    },
  })

  useEffect(() => {
    const localStories = toSortedLocalStories(stories, readStoryTrackingStore())
    if (session.status !== 'signed_in' || !session.accessToken) {
      const localRecords = localStories.flatMap((story) => (story.tracking ? [story.tracking] : []))
      setTrackedStories(localStories)
      setSyncError(null)
      if (localStories.length === 0) {
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      previewTrackedStories(localRecords)
        .then(({ stories: previewStories }) => {
          if (previewStories.length > 0) {
            setTrackedStories(toRenderedRemoteStories(previewStories))
          }
        })
        .catch((error) => {
          setSyncError(
            error instanceof Error
              ? error.message
              : 'Unable to load saved-story history right now.',
          )
        })
        .finally(() => {
          setIsLoading(false)
        })
      return
    }

    if (localStories.length > 0) {
      setTrackedStories((existing) => (existing.length > 0 ? existing : localStories))
    }

    setIsLoading(true)
    setSyncError(null)

    loadTrackedStories(session.accessToken)
      .then(({ stories: remoteStories }) => {
        if (remoteStories.length > 0) {
          setTrackedStories(toRenderedRemoteStories(remoteStories))
          return
        }

        setTrackedStories(localStories)
      })
      .catch((error) => {
        setTrackedStories(localStories)
        setSyncError(error instanceof Error ? error.message : 'Unable to load synced saved stories.')
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [session.accessToken, session.status, stories])

  if (trackedStories.length === 0) {
    return (
      <section className="panel empty-state-panel">
        <p className="panel-label">Saved stories</p>
        <h1>
          {session.status === 'signed_in'
            ? 'Nothing is synced to this account yet.'
            : 'Nothing is tracked in this browser yet.'}
        </h1>
        <p className="hero-dek">
          {session.status === 'signed_in'
            ? 'Save or follow a story from the story page and it will stay with this account across devices.'
            : 'Save or follow a story from the story page to build a working set here, then sign in only if you want it synced.'}
        </p>
        <div className="tracking-actions">
          <Link className="primary-link" href="/">
            Browse stories
          </Link>
          {session.status !== 'signed_in' ? (
            <Link className="secondary-link" href="/sync">
              Sync across devices
            </Link>
          ) : null}
        </div>
        {importState.isImporting ? (
          <p className="tracking-footnote">Syncing browser-tracked stories into this account...</p>
        ) : null}
        {syncError || importState.error ? (
          <p className="tracking-footnote">{syncError || importState.error}</p>
        ) : null}
      </section>
    )
  }

  return (
    <>
      {isLoading ? (
        <p className="tracking-footnote">
          {session.status === 'signed_in'
            ? 'Refreshing synced saved stories...'
            : 'Refreshing saved-story history...'}
        </p>
      ) : null}
      {importState.isImporting ? (
        <p className="tracking-footnote">Syncing browser-tracked stories into this account...</p>
      ) : null}
      {syncError || importState.error ? (
        <p className="tracking-footnote">{syncError || importState.error}</p>
      ) : null}
      <section className="saved-story-grid">
        {trackedStories.map((story) => (
          <article className="saved-story-card panel" key={story.slug}>
            <img
              src={story.heroImage}
              alt={story.heroAlt}
              className="saved-story-image"
            />
            <div className="saved-story-copy">
              <div className="saved-story-meta">
                <span className="panel-label">{story.topic}</span>
                <div className="tracking-chip-row">
                  {story.tracking?.saved ? <span className="tracking-chip active">Saved</span> : null}
                  {story.tracking?.followed ? (
                    <span className="tracking-chip active">Following</span>
                  ) : null}
                </div>
              </div>
              <h2>{story.title}</h2>
              <p>{story.dek}</p>
              <div className="saved-story-note">
                <strong>{story.changeCount} visible changes</strong>
                <span>{story.latestChange || 'Return to the story page for the latest change log.'}</span>
              </div>
              {story.history ? (
                <div className="saved-history-grid">
                  {renderHistoryEntry('Narrative delta', story.history.narrative)}
                  {renderHistoryEntry('Perspective delta', story.history.perspective)}
                </div>
              ) : null}
              <div className="saved-story-footer">
                <span>{story.updatedAt}</span>
                <span>Last opened {formatTrackedDate(story.tracking?.lastViewedAt)}</span>
                <Link className="secondary-link" href={`/stories/${story.slug}`}>
                  Open story
                </Link>
              </div>
            </div>
          </article>
        ))}
      </section>
    </>
  )
}
