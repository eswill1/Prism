'use client'

import type {
  ReaderTrackingMutation,
  ReaderTrackingState,
  RemoteTrackedStory,
} from './reader-tracking-types'

async function readJsonResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => null)) as { error?: string } | T | null
  if (!response.ok) {
    const message =
      payload && typeof payload === 'object' && 'error' in payload && typeof payload.error === 'string'
        ? payload.error
        : 'Reader sync is unavailable right now.'
    throw new Error(message)
  }

  return payload as T
}

function withReaderHeaders(accessToken: string | undefined, init?: RequestInit) {
  if (!accessToken) {
    throw new Error('Sign in to sync saved stories across devices.')
  }

  return {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(init?.headers || {}),
      Authorization: `Bearer ${accessToken}`,
    },
  } satisfies RequestInit
}

export async function syncReaderTrackingMutation(
  accessToken: string | undefined,
  mutation: ReaderTrackingMutation,
) {
  const response = await fetch('/api/reader/tracking', withReaderHeaders(accessToken, {
    method: 'POST',
    body: JSON.stringify(mutation),
  }))

  return readJsonResponse<{
    tracking: ReaderTrackingState
  }>(response)
}

export async function loadReaderTrackingState(
  accessToken: string | undefined,
  clusterIds: string[],
) {
  const params = new URLSearchParams()
  for (const clusterId of clusterIds) {
    params.append('clusterId', clusterId)
  }

  const response = await fetch(
    `/api/reader/tracking?${params.toString()}`,
    withReaderHeaders(accessToken),
  )

  return readJsonResponse<{
    tracking: ReaderTrackingState[]
  }>(response)
}

export async function importLocalTrackingState(
  accessToken: string | undefined,
  records: ReaderTrackingState[],
) {
  if (records.length === 0) {
    return {
      importedCount: 0,
    }
  }

  const response = await fetch('/api/reader/tracking/import', withReaderHeaders(accessToken, {
    method: 'POST',
    body: JSON.stringify({ records }),
  }))

  return readJsonResponse<{
    importedCount: number
  }>(response)
}

export async function loadTrackedStories(accessToken: string | undefined) {
  const response = await fetch('/api/reader/tracked-stories', withReaderHeaders(accessToken))
  return readJsonResponse<{
    stories: RemoteTrackedStory[]
  }>(response)
}
