import { NextResponse } from 'next/server'

import { getClusterSummaries } from '../../../lib/cluster-api'

export const runtime = 'nodejs'

export async function GET() {
  const clusters = await getClusterSummaries()

  return NextResponse.json({
    clusters,
    count: clusters.length,
  })
}
