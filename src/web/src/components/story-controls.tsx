'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import {
  getStoryTracking,
  markStoryViewed,
  toggleFollowedStory,
  toggleSavedStory,
  type StoryTrackingRecord,
} from '../lib/story-tracking'

type StoryControlsProps = {
  slug: string
  title: string
  topic: string
  updatedAt: string
  changeCount: number
}

function formatLocalTimestamp(value?: string) {
  if (!value) {
    return 'Viewed on this browser after you start tracking.'
  }

  return `Last opened here ${new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}.`
}

export function StoryControls({
  slug,
  title,
  topic,
  updatedAt,
  changeCount,
}: StoryControlsProps) {
  const [tracking, setTracking] = useState<StoryTrackingRecord>({
    slug,
    title,
    topic,
    saved: false,
    followed: false,
  })

  useEffect(() => {
    setTracking(markStoryViewed({ slug, title, topic }))
  }, [slug, title, topic])

  const onToggleSaved = () => {
    setTracking(toggleSavedStory({ slug, title, topic }))
  }

  const onToggleFollowed = () => {
    setTracking(toggleFollowedStory({ slug, title, topic }))
  }

  return (
    <article className="tracking-card">
      <div className="section-heading">
        <div>
          <p className="panel-label">Tracking</p>
          <h3>Keep this story in your working set.</h3>
        </div>
        <span className="cluster-badge">{changeCount} visible changes</span>
      </div>
      <p>
        Save and follow live in this browser for now while account sync comes online. The
        story last moved {updatedAt.replace('Updated ', '')}.
      </p>
      <div className="tracking-chip-row">
        <span className={`tracking-chip ${tracking.saved ? 'active' : ''}`}>
          {tracking.saved ? 'Saved here' : 'Not saved'}
        </span>
        <span className={`tracking-chip ${tracking.followed ? 'active' : ''}`}>
          {tracking.followed ? 'Following updates' : 'Not following'}
        </span>
      </div>
      <div className="tracking-actions">
        <button className="action-pill" onClick={onToggleSaved} type="button">
          {tracking.saved ? 'Unsave story' : 'Save story'}
        </button>
        <button className="action-pill" onClick={onToggleFollowed} type="button">
          {tracking.followed ? 'Unfollow updates' : 'Follow updates'}
        </button>
        <Link className="secondary-link" href="/saved">
          Review saved stories
        </Link>
      </div>
      <p className="tracking-footnote">{formatLocalTimestamp(tracking.lastViewedAt)}</p>
    </article>
  )
}
