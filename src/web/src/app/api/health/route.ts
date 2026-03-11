import { NextResponse } from 'next/server'

import { loadLiveFeed } from '../../../lib/live-feed'

export const runtime = 'nodejs'

export async function GET() {
  const liveFeed = await loadLiveFeed()

  return NextResponse.json({
    ok: true,
    service: 'prism-web',
    liveFeedReady: Boolean(liveFeed),
    liveFeedGeneratedAt: liveFeed?.generated_at ?? null,
  })
}
