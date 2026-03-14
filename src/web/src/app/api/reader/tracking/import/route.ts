import { NextResponse } from 'next/server'

import {
  importReaderTrackingRecords,
  ReaderAuthError,
  requireAuthenticatedReader,
} from '../../../../../lib/reader-persistence'
import type { ReaderTrackingState } from '../../../../../lib/reader-tracking-types'

export const runtime = 'nodejs'

function toErrorResponse(error: unknown) {
  if (error instanceof ReaderAuthError) {
    return NextResponse.json({ error: error.message }, { status: error.status })
  }

  console.error('Reader tracking import route failed', error)
  return NextResponse.json({ error: 'Reader sync is unavailable right now.' }, { status: 500 })
}

export async function POST(request: Request) {
  try {
    const { client, reader } = await requireAuthenticatedReader(request)
    const payload = (await request.json()) as { records?: ReaderTrackingState[] }
    const records = Array.isArray(payload?.records) ? payload.records : []

    await importReaderTrackingRecords(client, reader.profileId, records)

    return NextResponse.json({
      importedCount: records.length,
    })
  } catch (error) {
    return toErrorResponse(error)
  }
}
