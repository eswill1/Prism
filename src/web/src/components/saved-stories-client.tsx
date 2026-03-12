'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import {
  readStoryTrackingStore,
  type StoryTrackingRecord,
} from '../lib/story-tracking'

export type TrackedStoryCandidate = {
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

function formatTrackedDate(value?: string) {
  if (!value) {
    return 'Not opened recently on this browser'
  }

  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function toSortedStories(
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

export function SavedStoriesClient({ stories }: SavedStoriesClientProps) {
  const [trackedStories, setTrackedStories] = useState<
    Array<TrackedStoryCandidate & { tracking?: StoryTrackingRecord }>
  >([])

  useEffect(() => {
    setTrackedStories(toSortedStories(stories, readStoryTrackingStore()))
  }, [stories])

  if (trackedStories.length === 0) {
    return (
      <section className="panel empty-state-panel">
        <p className="panel-label">Saved stories</p>
        <h1>Nothing is tracked in this browser yet.</h1>
        <p className="hero-dek">
          Save or follow a story from the story page to build a working set here before
          full account sync is online.
        </p>
        <Link className="primary-link" href="/">
          Browse stories
        </Link>
      </section>
    )
  }

  return (
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
            <div className="saved-story-footer">
              <span>{story.updatedAt}</span>
              <span>Last opened here {formatTrackedDate(story.tracking?.lastViewedAt)}</span>
              <Link className="secondary-link" href={`/stories/${story.slug}`}>
                Open story
              </Link>
            </div>
          </div>
        </article>
      ))}
    </section>
  )
}
