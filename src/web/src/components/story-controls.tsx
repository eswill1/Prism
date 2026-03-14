'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'

import { syncReaderTrackingMutation } from '../lib/reader-tracking-client'
import {
  emptyStoryTrackingRecord,
  markStoryViewed,
  toggleFollowedStory,
  toggleSavedStory,
  writeStoryTrackingRecord,
  type StoryTrackingRecord,
} from '../lib/story-tracking'
import { useReaderSession } from '../lib/use-reader-session'

type StoryControlsProps = {
  clusterId?: string
  slug: string
  title: string
  topic: string
  updatedAt: string
  changeCount: number
  briefRevisionTag?: string
  perspectiveRevisionTag?: string
}

function formatTrackedTimestamp(value?: string) {
  if (!value) {
    return 'Viewed here after you start tracking this story.'
  }

  return `Last opened ${new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}.`
}

function mergeTrackedRecord(
  record: StoryTrackingRecord,
  fallback: Pick<StoryTrackingRecord, 'clusterId' | 'slug' | 'title' | 'topic'>,
) {
  return writeStoryTrackingRecord({
    ...record,
    clusterId: record.clusterId || fallback.clusterId,
    slug: record.slug || fallback.slug,
    title: record.title || fallback.title,
    topic: record.topic || fallback.topic,
  })
}

export function StoryControls({
  clusterId,
  slug,
  title,
  topic,
  updatedAt,
  changeCount,
  briefRevisionTag,
  perspectiveRevisionTag,
}: StoryControlsProps) {
  const session = useReaderSession()
  const storyIdentity = { clusterId, slug, title, topic }
  const [tracking, setTracking] = useState<StoryTrackingRecord>(() => emptyStoryTrackingRecord(slug))
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  const [isSyncing, setIsSyncing] = useState(false)
  const lastViewSyncKeyRef = useRef<string | null>(null)

  useEffect(() => {
    setTracking(markStoryViewed({
      ...storyIdentity,
      lastSeenBriefRevisionTag: briefRevisionTag,
      lastSeenPerspectiveRevisionTag: perspectiveRevisionTag,
    }))
  }, [briefRevisionTag, clusterId, perspectiveRevisionTag, slug, title, topic])

  useEffect(() => {
    if (session.status !== 'signed_in' || !clusterId || !session.accessToken) {
      lastViewSyncKeyRef.current = null
      return
    }

    const syncKey = [
      session.userId,
      clusterId,
      briefRevisionTag || '',
      perspectiveRevisionTag || '',
    ].join(':')

    if (lastViewSyncKeyRef.current === syncKey) {
      return
    }

    lastViewSyncKeyRef.current = syncKey
    setIsSyncing(true)
    setSyncMessage(null)

    syncReaderTrackingMutation(session.accessToken, {
      clusterId,
      slug,
      title,
      topic,
      markViewed: true,
      lastSeenBriefRevisionTag: briefRevisionTag,
      lastSeenPerspectiveRevisionTag: perspectiveRevisionTag,
    })
      .then(({ tracking: remoteTracking }) => {
        setTracking(mergeTrackedRecord(remoteTracking, storyIdentity))
      })
      .catch((error) => {
        setSyncMessage(error instanceof Error ? error.message : 'Reader sync is unavailable right now.')
      })
      .finally(() => {
        setIsSyncing(false)
      })
  }, [
    briefRevisionTag,
    clusterId,
    perspectiveRevisionTag,
    session.accessToken,
    session.status,
    session.userId,
    slug,
    title,
    topic,
  ])

  const onToggleSaved = async () => {
    const localTracking = toggleSavedStory(storyIdentity)
    setTracking(localTracking)

    if (session.status !== 'signed_in' || !clusterId || !session.accessToken) {
      setSyncMessage(
        session.status === 'signed_out'
          ? 'Tracked here only. Sign in to keep it across devices.'
          : null,
      )
      return
    }

    setIsSyncing(true)
    setSyncMessage(null)

    try {
      const { tracking: remoteTracking } = await syncReaderTrackingMutation(session.accessToken, {
        clusterId,
        slug,
        title,
        topic,
        saved: localTracking.saved,
      })
      setTracking(mergeTrackedRecord(remoteTracking, storyIdentity))
    } catch (error) {
      setSyncMessage(error instanceof Error ? error.message : 'Unable to sync saved-story state.')
    } finally {
      setIsSyncing(false)
    }
  }

  const onToggleFollowed = async () => {
    const localTracking = toggleFollowedStory(storyIdentity)
    setTracking(localTracking)

    if (session.status !== 'signed_in' || !clusterId || !session.accessToken) {
      setSyncMessage(
        session.status === 'signed_out'
          ? 'Tracked here only. Sign in to keep follow state across devices.'
          : null,
      )
      return
    }

    setIsSyncing(true)
    setSyncMessage(null)

    try {
      const { tracking: remoteTracking } = await syncReaderTrackingMutation(session.accessToken, {
        clusterId,
        slug,
        title,
        topic,
        saved: localTracking.saved,
        followed: localTracking.followed,
      })
      setTracking(mergeTrackedRecord(remoteTracking, storyIdentity))
    } catch (error) {
      setSyncMessage(error instanceof Error ? error.message : 'Unable to sync follow state.')
    } finally {
      setIsSyncing(false)
    }
  }

  const syncStatusLabel =
    session.status === 'signed_in'
      ? isSyncing
        ? 'Syncing account state'
        : `Synced as ${session.email || 'reader'}`
      : session.status === 'unavailable'
        ? 'Local tracking only'
        : 'Local tracking only'

  return (
    <article className="tracking-card panel">
      <div className="section-heading">
        <div>
          <p className="panel-label">Tracking</p>
          <h3>Keep this story in your working set.</h3>
        </div>
        <span className="cluster-badge">{changeCount} visible changes</span>
      </div>
      <p>
        {session.status === 'signed_in'
          ? 'Save and follow now sync to your account while still staying lightweight.'
          : 'Save and follow still work immediately in this browser. Sign in only if you want sync across devices.'}{' '}
        The story last moved {updatedAt.replace('Updated ', '')}.
      </p>
      <div className="tracking-chip-row">
        <span className={`tracking-chip ${tracking.saved ? 'active' : ''}`}>
          {tracking.saved ? 'Saved' : 'Not saved'}
        </span>
        <span className={`tracking-chip ${tracking.followed ? 'active' : ''}`}>
          {tracking.followed ? 'Following updates' : 'Not following'}
        </span>
        <span className="tracking-chip">{syncStatusLabel}</span>
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
        {session.status !== 'signed_in' ? (
          <Link className="secondary-link" href="/sync">
            Sync across devices
          </Link>
        ) : null}
      </div>
      <p className="tracking-footnote">
        {syncMessage || formatTrackedTimestamp(tracking.lastViewedAt)}
      </p>
    </article>
  )
}
