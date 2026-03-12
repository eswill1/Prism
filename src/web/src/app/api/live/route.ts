import { NextResponse } from 'next/server'

import { loadLiveFeed } from '../../../lib/live-feed'

export const runtime = 'nodejs'

export async function GET() {
  const liveFeed = await loadLiveFeed()

  if (!liveFeed) {
    return NextResponse.json(
      {
        ready: false,
        message: 'No latest snapshot is available yet.',
      },
      { status: 200 },
    )
  }

  return NextResponse.json({
    ready: true,
    ...liveFeed,
  })
}
