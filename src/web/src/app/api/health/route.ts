import { NextResponse } from 'next/server'

import { loadLiveFeed } from '../../../lib/live-feed'
import { isSupabaseConfigured } from '../../../lib/cluster-api'

export const runtime = 'nodejs'

export async function GET() {
  const liveFeed = await loadLiveFeed()

  return NextResponse.json({
    ok: true,
    service: 'prism-web',
    supabaseConfigured: isSupabaseConfigured(),
    liveFeedReady: Boolean(liveFeed),
    liveFeedGeneratedAt: liveFeed?.generated_at ?? null,
  })
}
