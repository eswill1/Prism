'use client'

import { useEffect, useMemo, useRef, useState } from 'react'

import { importLocalTrackingState } from './reader-tracking-client'
import { listTrackedStoryRecords } from './story-tracking'
import { useReaderSession } from './use-reader-session'

type UseLocalTrackingImportOptions = {
  enabled?: boolean
  onImported?: () => void
}

type LocalTrackingImportState = {
  isImporting: boolean
  error: string | null
}

const IMPORT_SIGNATURE_PREFIX = 'prism.reader_sync_import_signature.'

function buildImportSignature() {
  return JSON.stringify(
    listTrackedStoryRecords().map((record) => ({
      clusterId: record.clusterId || '',
      slug: record.slug,
      saved: record.saved,
      followed: record.followed,
      savedAt: record.savedAt || '',
      followedAt: record.followedAt || '',
      lastViewedAt: record.lastViewedAt || '',
      lastSeenBriefRevisionTag: record.lastSeenBriefRevisionTag || '',
      lastSeenPerspectiveRevisionTag: record.lastSeenPerspectiveRevisionTag || '',
    })),
  )
}

export function useLocalTrackingImport(
  options: UseLocalTrackingImportOptions = {},
): LocalTrackingImportState {
  const session = useReaderSession()
  const enabled = options.enabled !== false
  const onImportedRef = useRef(options.onImported)
  const [state, setState] = useState<LocalTrackingImportState>({
    isImporting: false,
    error: null,
  })

  useEffect(() => {
    onImportedRef.current = options.onImported
  }, [options.onImported])

  const storageKey = useMemo(
    () => (session.userId ? `${IMPORT_SIGNATURE_PREFIX}${session.userId}` : null),
    [session.userId],
  )

  useEffect(() => {
    if (
      !enabled ||
      session.status !== 'signed_in' ||
      !session.accessToken ||
      !storageKey ||
      typeof window === 'undefined'
    ) {
      return
    }

    const records = listTrackedStoryRecords()
    if (records.length === 0) {
      return
    }

    const signature = buildImportSignature()
    const lastImportedSignature = window.localStorage.getItem(storageKey)
    if (lastImportedSignature === signature) {
      return
    }

    let cancelled = false
    setState({ isImporting: true, error: null })

    importLocalTrackingState(session.accessToken, records)
      .then(() => {
        if (cancelled) {
          return
        }
        window.localStorage.setItem(storageKey, signature)
        setState({ isImporting: false, error: null })
        onImportedRef.current?.()
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        setState({
          isImporting: false,
          error:
            error instanceof Error
              ? error.message
              : 'Unable to import this browser’s tracked stories right now.',
        })
      })

    return () => {
      cancelled = true
    }
  }, [enabled, session.accessToken, session.status, storageKey])

  return state
}
