import type { FastifyInstance } from 'fastify'

const sampleClusters = [
  {
    slug: 'federal-budget-deadline',
    topic: 'US Policy',
    title: 'Federal budget talks enter a new deadline cycle',
    summary:
      'Lawmakers moved toward a short-term funding patch while both parties hardened messaging around spending cuts, border provisions, and shutdown risk.',
    outletCount: 18,
    perspective: {
      reliabilityRange: 'Established to high',
      framingGroups: ['left', 'center', 'right'],
    },
  },
  {
    slug: 'europe-tech-regulation-push',
    topic: 'Global Tech',
    title: 'European regulators tighten pressure on major AI platforms',
    summary:
      'A new round of European scrutiny focused on disclosure, training-data transparency, and compliance pacing.',
    outletCount: 11,
    perspective: {
      reliabilityRange: 'Established to high',
      framingGroups: ['left', 'center', 'right'],
    },
  },
]

export async function registerClusterRoutes(app: FastifyInstance) {
  app.get('/api/clusters', async () => {
    return {
      items: sampleClusters,
      total: sampleClusters.length,
    }
  })

  app.get('/api/clusters/:slug', async (request, reply) => {
    const cluster = sampleClusters.find(
      (item) => item.slug === (request.params as { slug: string }).slug,
    )

    if (!cluster) {
      return reply.status(404).send({
        message: 'Cluster not found',
      })
    }

    return {
      item: cluster,
    }
  })
}
