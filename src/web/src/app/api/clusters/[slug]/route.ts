import { NextResponse } from 'next/server'

import { getClusterDetail } from '../../../../lib/cluster-api'

export const runtime = 'nodejs'

type RouteContext = {
  params: Promise<{ slug: string }>
}

export async function GET(_request: Request, context: RouteContext) {
  const { slug } = await context.params
  const cluster = getClusterDetail(slug)

  if (!cluster) {
    return NextResponse.json(
      {
        error: 'Cluster not found',
      },
      { status: 404 },
    )
  }

  return NextResponse.json(cluster)
}
