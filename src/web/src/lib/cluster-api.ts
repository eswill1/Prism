import { clusterBySlug, mockClusters, type StoryCluster } from './mock-clusters'

export type ClusterSummary = {
  slug: string
  topic: string
  title: string
  dek: string
  updatedAt: string
  status: string
  heroImage: string
  heroAlt: string
  heroCredit: string
  outletCount: number
  reliabilityRange: string
  coverageCounts: StoryCluster['coverageCounts']
}

function toClusterSummary(cluster: StoryCluster): ClusterSummary {
  return {
    slug: cluster.slug,
    topic: cluster.topic,
    title: cluster.title,
    dek: cluster.dek,
    updatedAt: cluster.updatedAt,
    status: cluster.status,
    heroImage: cluster.heroImage,
    heroAlt: cluster.heroAlt,
    heroCredit: cluster.heroCredit,
    outletCount: cluster.outletCount,
    reliabilityRange: cluster.reliabilityRange,
    coverageCounts: cluster.coverageCounts,
  }
}

export function getClusterSummaries(): ClusterSummary[] {
  return mockClusters.map(toClusterSummary)
}

export function getClusterDetail(slug: string): StoryCluster | null {
  return clusterBySlug[slug] ?? null
}
