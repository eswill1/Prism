import Link from 'next/link'

import { SiteFooter } from '../components/site-footer'
import { SiteNav } from '../components/site-nav'
import type { ClusterSummary } from '../lib/cluster-api'
import { getClusterSummaries } from '../lib/cluster-api'
import { PRIMARY_NEWS_SECTIONS, getNewsSection, getNewsSectionKey } from '../lib/news-sections'

function pickTopDeckStories(stories: ClusterSummary[]) {
  const [featured, ...rest] = stories
  if (!featured) {
    return {
      featured: null,
      support: [],
    }
  }

  const usedSectionCounts = new Map<string, number>([[getNewsSectionKey(featured.topic), 1]])
  const support: ClusterSummary[] = []

  for (const story of rest) {
    if (support.length >= 5) {
      break
    }

    const sectionKey = getNewsSectionKey(story.topic)
    const currentCount = usedSectionCounts.get(sectionKey) ?? 0
    const limit = support.length < 3 ? 1 : 2

    if (currentCount >= limit) {
      continue
    }

    support.push(story)
    usedSectionCounts.set(sectionKey, currentCount + 1)
  }

  if (support.length < 5) {
    for (const story of rest) {
      if (support.length >= 5) {
        break
      }
      if (support.some((item) => item.slug === story.slug)) {
        continue
      }
      support.push(story)
    }
  }

  return {
    featured,
    support,
  }
}

function buildHomepagePool(stories: ClusterSummary[]) {
  const preferred = stories.filter(
    (story) =>
      story.homepageEligible ||
      story.storyOrigin === 'automated_feed_ingestion' ||
      (story.qualityScore >= 24 && story.outletCount >= 1),
  )

  if (preferred.length >= 10) {
    return preferred
  }

  const supplemented = [...preferred]

  for (const story of stories) {
    if (supplemented.some((item) => item.slug === story.slug)) {
      continue
    }

    supplemented.push(story)

    if (supplemented.length >= 12) {
      break
    }
  }

  return supplemented
}

export default async function HomePage() {
  const clusters = await getClusterSummaries()
  const homepagePool = buildHomepagePool(clusters)
  const { featured: featuredCluster, support } = pickTopDeckStories(homepagePool)
  const homepageDate = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(new Date())

  if (!featuredCluster) {
    return (
      <main className="page-shell home-page">
        <SiteNav />
        <header className="masthead">
          <div>
            <p className="eyebrow">The Prism Wire</p>
            <h1>No stories are available yet.</h1>
          </div>
        </header>
      </main>
    )
  }

  const remainingClusters = clusters.filter((cluster) => cluster.slug !== featuredCluster.slug)
  const leftColumnStories = support.slice(0, 2)
  const centerLeadStory = support[2] ?? null
  const centerColumnStories = support.slice(3, 5)
  const pinnedStorySlugs = new Set([
    featuredCluster.slug,
    ...leftColumnStories.map((story) => story.slug),
    ...(centerLeadStory ? [centerLeadStory.slug] : []),
    ...centerColumnStories.map((story) => story.slug),
  ])
  const latestFeedStories = [...clusters]
    .filter(
      (cluster) => !pinnedStorySlugs.has(cluster.slug),
    )
    .sort(
      (left, right) =>
        new Date(right.latestEventAt).getTime() - new Date(left.latestEventAt).getTime(),
    )
    .slice(0, 8)
  const groupedSections = PRIMARY_NEWS_SECTIONS.map((section) => ({
    ...section,
    stories: homepagePool
      .concat(remainingClusters)
      .filter(
        (cluster, index, collection) =>
          collection.findIndex((item) => item.slug === cluster.slug) === index,
      )
      .filter((cluster) => !pinnedStorySlugs.has(cluster.slug))
      .filter((cluster) => getNewsSection(cluster.topic).key === section.key)
      .slice(0, 4),
  })).filter((section) => section.stories.length > 0)

  return (
    <main className="page-shell home-page">
      <SiteNav />
      <section className="front-page-intro">
        <p className="eyebrow">Top stories</p>
        <span className="front-page-date">{homepageDate}</span>
      </section>

      <section className="home-news-grid">
        <div className="home-news-column home-news-column-left">
          <Link className="home-lead-story home-story-link-card" href={`/stories/${featuredCluster.slug}`}>
            <div className="home-lead-media">
              <img
                src={featuredCluster.heroImage}
                alt={featuredCluster.heroAlt}
                className="hero-image"
              />
              <span className="media-credit">{featuredCluster.heroCredit}</span>
            </div>
            <div className="home-lead-copy">
              <div className="hero-meta-line">
                <span className="status-chip">{featuredCluster.status}</span>
                <span>{featuredCluster.updatedAt}</span>
                <span>{featuredCluster.outletCount} outlets</span>
              </div>
              <p className="panel-label">{featuredCluster.topic}</p>
              <h1>{featuredCluster.title}</h1>
              <p className="hero-dek">{featuredCluster.dek}</p>
              <span className="inline-story-link">
                Open story
              </span>
            </div>
          </Link>

          {leftColumnStories.length > 0 ? (
            <div className="home-secondary-stack">
              {leftColumnStories.map((story) => (
                <Link className="home-secondary-story" href={`/stories/${story.slug}`} key={story.slug}>
                  <span className="headline-link-kicker">
                    {story.topic} · {story.updatedAt}
                  </span>
                  <strong>{story.title}</strong>
                  <span className="headline-link-dek">{story.dek}</span>
                </Link>
              ))}
            </div>
          ) : null}
        </div>

        <div className="home-news-column home-news-column-center">
          {centerLeadStory ? (
            <Link className="home-center-feature home-story-link-card" href={`/stories/${centerLeadStory.slug}`}>
              <img
                src={centerLeadStory.heroImage}
                alt={centerLeadStory.heroAlt}
                className="home-center-feature-image"
              />
              <div className="home-center-feature-copy">
                <span className="headline-link-kicker">
                  {centerLeadStory.topic} · {centerLeadStory.updatedAt}
                </span>
                <h2>{centerLeadStory.title}</h2>
                <p>{centerLeadStory.dek}</p>
                <span className="inline-story-link">
                  Open story
                </span>
              </div>
            </Link>
          ) : null}

          {centerColumnStories.length > 0 ? (
            <div className="home-center-stack">
              {centerColumnStories.map((story) => (
                <Link
                  className="home-center-story home-story-link-card"
                  href={`/stories/${story.slug}`}
                  key={story.slug}
                >
                  <img
                    src={story.heroImage}
                    alt={story.heroAlt}
                    className="home-center-story-image"
                  />
                  <div className="home-center-story-copy">
                    <span className="headline-link-kicker">
                      {story.topic} · {story.updatedAt}
                    </span>
                    <strong>{story.title}</strong>
                  </div>
                </Link>
              ))}
            </div>
          ) : null}
        </div>

        <aside className="home-news-column home-news-column-right">
          <div className="home-latest-feed">
            <div className="home-latest-header">
              <p className="panel-label">Latest news</p>
              <h2>Developments</h2>
            </div>
            <div className="home-latest-list">
              {latestFeedStories.map((story) => (
                <Link className="home-latest-item" href={`/stories/${story.slug}`} key={story.slug}>
                  <div className="home-latest-meta">
                    <span>{story.updatedAt}</span>
                    <span className="home-latest-topic">{story.topic}</span>
                  </div>
                  <strong>{story.title}</strong>
                </Link>
              ))}
            </div>
          </div>
        </aside>
      </section>

      <section className="front-page-sections">
        {groupedSections.map((section) => (
          <section className="section-block" id={section.anchor} key={section.key}>
            <div className="section-heading">
              <div>
                <p className="panel-label">Desk</p>
                <h2>{section.title}</h2>
              </div>
            </div>
            <div className={`section-story-grid${section.stories.length === 1 ? ' single-column' : ''}`}>
              <Link
                className="cluster-card home-section-feature home-story-link-card"
                href={`/stories/${section.stories[0].slug}`}
                key={section.stories[0].slug}
              >
                <img
                  src={section.stories[0].heroImage}
                  alt={section.stories[0].heroAlt}
                  className="cluster-card-image"
                />
                <div className="cluster-card-body">
                  <div className="cluster-card-meta">
                    <span className="status-chip">{section.stories[0].status}</span>
                    <span>{section.stories[0].updatedAt}</span>
                  </div>
                  <h3>{section.stories[0].title}</h3>
                  <p>{section.stories[0].dek}</p>
                  <div className="cluster-card-footer">
                    <span>{section.stories[0].outletCount} outlets</span>
                    <span>Open story</span>
                  </div>
                </div>
              </Link>

              {section.stories.length > 1 ? (
                <div className="section-headline-stack">
                  {section.stories.slice(1).map((cluster) => (
                    <Link
                      className="section-headline-link"
                      href={`/stories/${cluster.slug}`}
                      key={cluster.slug}
                    >
                      <span className="headline-link-kicker">
                        {cluster.topic} · {cluster.updatedAt}
                      </span>
                      <strong>{cluster.title}</strong>
                      <span className="headline-link-dek">{cluster.dek}</span>
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          </section>
        ))}
      </section>

      <SiteFooter />
    </main>
  )
}
