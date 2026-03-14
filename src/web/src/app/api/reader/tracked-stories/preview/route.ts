import { NextResponse } from 'next/server'

import type { ReaderTrackingState } from '../../../../../lib/reader-tracking-types'
import {
  listTrackedStoriesPreview,
  ReaderAuthError,
  requireReaderServiceClient,
} from '../../../../../lib/reader-persistence'

export const runtime = 'nodejs'

function toErrorResponse(error: unknown) {
  if (error instanceof ReaderAuthError) {
    return NextResponse.json({ error: error.message }, { status: error.status })
  }

  console.error('Tracked story preview route failed', error)
  return NextResponse.json({ error: 'Reader sync is unavailable right now.' }, { status: 500 })
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json().catch(() => null)) as
      | {
          records?: ReaderTrackingState[]
        }
      | null
    const records = Array.isArray(payload?.records) ? payload.records : []
    const client = requireReaderServiceClient()
    const stories = await listTrackedStoriesPreview(client, records)

    return NextResponse.json({
      stories,
      count: stories.length,
    })
  } catch (error) {
    return toErrorResponse(error)
  }
}
