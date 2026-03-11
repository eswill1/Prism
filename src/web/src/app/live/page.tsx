import Link from 'next/link'

import { loadLiveFeed } from '../../lib/live-feed'

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

  if (!liveFeed) {
    return (
      <main className="page-shell live-page">
        <header className="masthead">
          <div>
            <p className="eyebrow">Temporary live feed</p>
            <h1>No generated live feed found yet.</h1>
          </div>
        </header>
        <section className="panel empty-state-panel">
          <p>
            Run `python3 tooling/generate_temporary_live_feed.py` to fetch a temporary set
            of live publisher headlines and cluster them for the Prism prototype.
          </p>
          <Link href="/" className="secondary-link">
            Back to homepage
          </Link>
        </section>
      </main>
    )
  }

  return (
    <main className="page-shell live-page">
      <header className="masthead">
        <div>
          <p className="eyebrow">Temporary live feed</p>
          <h1>Live source input, clustered into a Prism-style prototype view.</h1>
          <p className="hero-dek">
            Generated from {liveFeed.source_count} feeds and {liveFeed.article_count}{' '}
            discovered articles. This is a temporary clustering preview, not a production
            ranking or rights-cleared media pipeline.
          </p>
        </div>
        <div className="live-meta-card">
          <span className="metric-label">Generated</span>
          <strong>{formatTimestamp(liveFeed.generated_at)}</strong>
          <Link href="/" className="secondary-link">
            Back to homepage
          </Link>
        </div>
      </header>

      <section className="briefing-band panel">
        <div>
          <p className="panel-label">Source coverage</p>
          <h2>Feeds currently feeding the prototype</h2>
        </div>
        <ul className="briefing-list">
          {liveFeed.sources.map((source) => (
            <li key={source.feed_url}>
              {source.source} · <span className="muted-inline">{source.feed_url}</span>
            </li>
          ))}
        </ul>
      </section>

      {liveFeed.errors.length > 0 ? (
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
        {liveFeed.clusters.map((cluster) => (
          <article className="live-cluster panel" key={cluster.slug}>
            <div className="live-cluster-hero">
              <div className="live-cluster-copy">
                <div className="hero-meta-line">
                  <span className="status-chip">Live prototype</span>
                  <span>{formatTimestamp(cluster.latest_at)}</span>
                  <span>{cluster.article_count} related articles</span>
                </div>
                <p className="panel-label">{cluster.topic_label}</p>
                <h2>{cluster.title}</h2>
                <p className="hero-dek">{cluster.dek}</p>
                <div className="source-chip-row">
                  {cluster.sources.map((source) => (
                    <span className="source-chip" key={source}>
                      {source}
                    </span>
                  ))}
                </div>
              </div>

              <div className="live-cluster-media">
                {cluster.hero_image ? (
                  <>
                    <img
                      src={cluster.hero_image}
                      alt={`${cluster.title} preview`}
                      className="hero-image"
                    />
                    <span className="media-credit">{cluster.hero_credit}</span>
                  </>
                ) : (
                  <div className="generated-visual">
                    <span>{cluster.topic_label}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="live-article-grid">
              {cluster.articles.map((article) => (
                <a
                  className="live-article-card"
                  key={`${article.source}-${article.url}`}
                  href={article.url}
                  rel="noreferrer"
                  target="_blank"
                >
                  {article.image ? (
                    <img
                      src={article.image}
                      alt={`${article.source} preview`}
                      className="live-article-image"
                    />
                  ) : (
                    <div className="generated-visual small">
                      <span>{article.source}</span>
                    </div>
                  )}
                  <div className="live-article-copy">
                    <div className="article-card-meta">
                      <span>{article.source}</span>
                      <span>{formatTimestamp(article.published_at)}</span>
                    </div>
                    <h3>{article.title}</h3>
                    <p>{article.summary || article.domain}</p>
                  </div>
                </a>
              ))}
            </div>
          </article>
        ))}
      </section>
    </main>
  )
}
