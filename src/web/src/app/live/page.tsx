import Link from 'next/link'

import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'
import { getClusterDetail, getClusterSummaries } from '../../lib/cluster-api'
import { loadLiveFeed, mapLiveClusterToStoryCluster } from '../../lib/live-feed'
import type { StoryCluster } from '../../lib/mock-clusters'

function formatTimestamp(value: string) {
  const date = new Date(value)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default async function LiveFeedPage() {
  const liveFeed = await loadLiveFeed()
  const liveSummaries = (await getClusterSummaries({ sort: 'latest' })).filter(
    (cluster) => cluster.status === 'Live intake',
  )
  const dbBackedStories = (
    await Promise.all(liveSummaries.map((story) => getClusterDetail(story.slug)))
  ).filter((story): story is StoryCluster => Boolean(story))
  const visibleStories =
    dbBackedStories.length > 0
      ? dbBackedStories
      : liveFeed?.clusters.map((cluster) => mapLiveClusterToStoryCluster(cluster)) ?? []

  if (!liveFeed && visibleStories.length === 0) {
    return (
      <main className="page-shell live-page">
        <SiteNav />
        <header className="masthead">
          <div>
            <p className="eyebrow">Secondary queue</p>
            <h1>No fast-moving story intake is available yet.</h1>
          </div>
        </header>
        <section className="panel empty-state-panel">
          <p>
            Run `npm run ingest:feeds` to poll the configured feeds and refresh the secondary
            intake queue that powers story movement on the homepage.
          </p>
          <Link href="/" className="secondary-link">
            Back to homepage
          </Link>
        </section>
        <SiteFooter />
      </main>
    )
  }

  return (
    <main className="page-shell live-page">
      <SiteNav />
      <header className="masthead">
        <div>
          <p className="eyebrow">Secondary queue</p>
          <h1>Fast-moving intake behind the homepage.</h1>
          <p className="hero-dek">
            {liveFeed
              ? `Generated from ${liveFeed.source_count} feeds and ${liveFeed.article_count} discovered articles.`
              : `Showing ${visibleStories.length} automated live stories currently synced into Supabase.`}{' '}
            This route remains available as a secondary intake view, but the homepage is the
            actual reader-facing news surface.
          </p>
        </div>
        <div className="live-meta-card">
          <span className="metric-label">Secondary queue</span>
          <strong>{liveFeed ? formatTimestamp(liveFeed.generated_at) : 'Live DB state'}</strong>
          <Link href="/" className="secondary-link">
            Return to homepage
          </Link>
        </div>
      </header>

      {liveFeed ? (
        <section className="briefing-band panel">
          <div>
            <p className="panel-label">Source coverage</p>
            <h2>Feeds currently powering the secondary intake queue</h2>
          </div>
          <ul className="briefing-list">
            {liveFeed.sources.map((source) => (
              <li key={source.feed_url}>
                {source.source} · <span className="muted-inline">{source.feed_url}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section className="briefing-band panel">
          <div>
            <p className="panel-label">Automated intake</p>
            <h2>This secondary queue is being read from the Supabase-backed intake layer.</h2>
          </div>
          <p className="hero-dek">
            The visible cards below reflect the current automated story set stored in Prism,
            even if the temporary JSON snapshot is not present on disk.
          </p>
        </section>
      )}

      {liveFeed && liveFeed.errors.length > 0 ? (
        <section className="panel warning-panel">
          <p className="panel-label">Feed warnings</p>
          <ul className="simple-list">
            {liveFeed.errors.map((error) => (
              <li key={`${error.source}-${error.feed_url}`}>
                {error.source}: {error.error}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="live-cluster-stack">
        {visibleStories.map((story) => (
          <article className="live-cluster panel" key={story.slug}>
            <div className="live-cluster-hero">
              <div className="live-cluster-copy">
                <div className="hero-meta-line">
                  <span className="status-chip">{story.status}</span>
                  <span>{story.updatedAt}</span>
                  <span>{story.articles.length} related articles</span>
                </div>
                <p className="panel-label">{story.topic}</p>
                <h2>{story.title}</h2>
                <p className="hero-dek">{story.dek}</p>
                <div className="source-chip-row">
                  {Array.from(new Set(story.articles.map((article) => article.outlet))).map(
                    (source) => (
                      <span className="source-chip" key={`${story.slug}-${source}`}>
                        {source}
                      </span>
                    ),
                  )}
                </div>
                <div className="live-cluster-actions">
                  <Link className="primary-link" href={`/stories/${story.slug}`}>
                    Open story view
                  </Link>
                  <p className="live-cluster-note">
                    This queue helps surface fast-moving intake, but the story page is still the
                    full Prism view.
                  </p>
                </div>
              </div>

              <div className="live-cluster-media">
                {story.heroImage ? (
                  <>
                    <img src={story.heroImage} alt={story.heroAlt} className="hero-image" />
                    <span className="media-credit">{story.heroCredit}</span>
                  </>
                ) : (
                  <div className="generated-visual">
                    <span>{story.topic}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="live-article-grid">
              {story.articles.map((article) => {
                const cardContent = (
                  <>
                    {article.image ? (
                      <img
                        src={article.image}
                        alt={`${article.outlet} preview`}
                        className="live-article-image"
                      />
                    ) : (
                      <div className="generated-visual small">
                        <span>{article.outlet}</span>
                      </div>
                    )}
                    <div className="live-article-copy">
                      <div className="article-card-meta">
                        <span>{article.outlet}</span>
                        <span>{article.published}</span>
                      </div>
                      <h3>{article.title}</h3>
                      <p>{article.summary}</p>
                    </div>
                  </>
                )

                if (!article.url) {
                  return (
                    <div
                      className="live-article-card"
                      key={`${story.slug}-${article.outlet}-${article.title}`}
                    >
                      {cardContent}
                    </div>
                  )
                }

                return (
                  <a
                    className="live-article-card"
                    key={`${story.slug}-${article.outlet}-${article.url}`}
                    href={article.url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {cardContent}
                  </a>
                )
              })}
            </div>
          </article>
        ))}
      </section>
      <SiteFooter />
    </main>
  )
}
