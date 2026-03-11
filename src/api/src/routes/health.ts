import type { FastifyInstance } from 'fastify'

export async function registerHealthRoute(app: FastifyInstance) {
  app.get('/api/health', async () => {
    return {
      ok: true,
      service: 'prism-wire-api',
      timestamp: new Date().toISOString(),
    }
  })
}
