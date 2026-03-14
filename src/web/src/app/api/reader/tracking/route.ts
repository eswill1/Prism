import { NextResponse } from 'next/server'

import {
  applyReaderTrackingMutation,
  loadReaderTrackingState,
  ReaderAuthError,
  requireAuthenticatedReader,
} from '../../../../lib/reader-persistence'
import type { ReaderTrackingMutation } from '../../../../lib/reader-tracking-types'

export const runtime = 'nodejs'

function toErrorResponse(error: unknown) {
  if (error instanceof ReaderAuthError) {
    return NextResponse.json({ error: error.message }, { status: error.status })
  }

  console.error('Reader tracking route failed', error)
  return NextResponse.json({ error: 'Reader sync is unavailable right now.' }, { status: 500 })
}

export async function GET(request: Request) {
  try {
    const { client, reader } = await requireAuthenticatedReader(request)
    const { searchParams } = new URL(request.url)
    const clusterIds = searchParams.getAll('clusterId').filter(Boolean)
    const trackingMap = await loadReaderTrackingState(client, reader.profileId, clusterIds)

    return NextResponse.json({
      tracking: Object.values(trackingMap),
    })
  } catch (error) {
    return toErrorResponse(error)
  }
}

export async function POST(request: Request) {
  try {
    const { client, reader } = await requireAuthenticatedReader(request)
    const mutation = (await request.json()) as ReaderTrackingMutation

    if (!mutation || typeof mutation.slug !== 'string' || mutation.slug.trim().length === 0) {
      return NextResponse.json({ error: 'A story slug is required for synced tracking.' }, { status: 400 })
    }

    const tracking = await applyReaderTrackingMutation(client, reader.profileId, mutation)

    return NextResponse.json({ tracking })
  } catch (error) {
    return toErrorResponse(error)
  }
}
