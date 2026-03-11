import Fastify from 'fastify'

import { registerClusterRoutes } from './routes/clusters.js'
import { registerHealthRoute } from './routes/health.js'

const app = Fastify({
  logger: true,
})

const start = async () => {
  await registerHealthRoute(app)
  await registerClusterRoutes(app)

  await app.listen({
    host: '0.0.0.0',
    port: Number(process.env.PORT || 4000),
  })
}

start().catch((error) => {
  app.log.error(error)
  process.exit(1)
})
