import { SavedStoriesClient, type TrackedStoryCandidate } from '../../components/saved-stories-client'
import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'
import { getClusterSummaries } from '../../lib/cluster-api'
import { clusterBySlug } from '../../lib/mock-clusters'
import { loadLiveFeed, mapLiveClusterToStoryCluster } from '../../lib/live-feed'

export default async function SavedStoriesPage() {
  const summaries = await getClusterSummaries()
  const liveFeed = await loadLiveFeed()

  const summaryStories: TrackedStoryCandidate[] = summaries.map((story) => ({
    clusterId: story.clusterId,
    slug: story.slug,
    topic: story.topic,
    title: story.title,
    dek: story.dek,
    updatedAt: story.updatedAt,
    heroImage: story.heroImage,
    heroAlt: story.heroAlt,
    latestChange: clusterBySlug[story.slug]?.whatChanged[0],
    changeCount: clusterBySlug[story.slug]?.whatChanged.length ?? 0,
  }))

  const liveStories: TrackedStoryCandidate[] = (liveFeed?.clusters ?? []).map((cluster) => {
    const story = mapLiveClusterToStoryCluster(cluster)

    return {
      slug: story.slug,
      topic: story.topic,
      title: story.title,
      dek: story.dek,
      updatedAt: story.updatedAt,
      heroImage: story.heroImage,
      heroAlt: story.heroAlt,
      latestChange: story.whatChanged[0],
      changeCount: story.changeTimeline.length,
    }
  })

  const stories = Array.from(
    new Map([...summaryStories, ...liveStories].map((story) => [story.slug, story])).values(),
  )

  return (
    <main className="page-shell saved-page">
      <SiteNav />
      <header className="masthead">
        <div>
          <p className="eyebrow">Saved stories</p>
          <h1>Your tracked working set for follow-up reading and change review.</h1>
          <p className="hero-dek">
            Save and follow still work instantly in this browser. Prism now shows the latest
            narrative and Perspective deltas for each tracked story, with optional sign-in only
            if you want that working set synced across devices.
          </p>
        </div>
      </header>
      <SavedStoriesClient stories={stories} />
      <SiteFooter />
    </main>
  )
}
