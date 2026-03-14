import { NextResponse } from 'next/server'

import {
  listTrackedStories,
  ReaderAuthError,
  requireAuthenticatedReader,
} from '../../../../lib/reader-persistence'

export const runtime = 'nodejs'

function toErrorResponse(error: unknown) {
  if (error instanceof ReaderAuthError) {
    return NextResponse.json({ error: error.message }, { status: error.status })
  }

  console.error('Tracked stories route failed', error)
  return NextResponse.json({ error: 'Reader sync is unavailable right now.' }, { status: 500 })
}

export async function GET(request: Request) {
  try {
    const { client, reader } = await requireAuthenticatedReader(request)
    const stories = await listTrackedStories(client, reader.profileId)

    return NextResponse.json({
      stories,
      count: stories.length,
    })
  } catch (error) {
    return toErrorResponse(error)
  }
}
