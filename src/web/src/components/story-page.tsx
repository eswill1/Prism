import Link from 'next/link'
import { notFound } from 'next/navigation'

import { SiteFooter } from './site-footer'
import { SiteNav } from './site-nav'
import { getClusterDetail } from '../lib/cluster-api'
import type { ContextItem, StoryCluster } from '../lib/mock-clusters'
import type { SourceAccessTier } from '../lib/source-access'
import { buildStoryBrief } from '../lib/story-briefs'

type StoryPageProps = {
  slug: string
}

function buildCoverageSummary(cluster: StoryCluster) {
  if (cluster.outletCount <= 1) {
    return `Prism only has one linked report in this story so far, so treat this as an early read rather than a full comparison view.`
  }

  const counts = cluster.coverageCounts
  const parts = []

  if (counts.left > 0) parts.push(`${counts.left} left-leaning`)
  if (counts.center > 0) parts.push(`${counts.center} center-leaning`)
  if (counts.right > 0) parts.push(`${counts.right} right-leaning`)

  if (parts.length === 0) {
    return `Prism is still gathering enough coverage to show a useful comparison set for this story.`
  }

  return `Prism has ${cluster.outletCount} outlets in this comparison set, with ${parts.join(', ')} sources represented so far.`
}

function buildPerspectiveTakeaways(cluster: StoryCluster) {
  const agreement = cluster.keyFacts[0] || cluster.dek
  const disagreement =
    cluster.keyFacts[2] ||
    `Outlets are putting different weight on politics, practical fallout, and who to blame.`
  const watchNext =
    cluster.whatChanged[0] ||
    `Expect the story to keep moving as more outlets add fresh reporting and official updates.`

  return [
    `Shared baseline: ${agreement}`,
    `Main split in coverage: ${disagreement}`,
    `What to watch next: ${watchNext}`,
  ]
}

function buildAlternateReads(cluster: StoryCluster): ContextItem[] {
  const seen = new Set<string>()
  const items: ContextItem[] = []

  for (const pack of Object.values(cluster.contextPacks)) {
    for (const item of pack) {
      const key = `${item.outlet}:${item.title}`
      if (seen.has(key)) continue
      seen.add(key)
      items.push(item)
      if (items.length === 3) {
        return items
      }
    }
  }

  return items
}

function titleTokenOverlap(left: string, right: string) {
  const leftTokens = new Set(left.toLowerCase().match(/[a-z]{4,}/g) || [])
  const rightTokens = new Set(right.toLowerCase().match(/[a-z]{4,}/g) || [])

  if (leftTokens.size === 0 || rightTokens.size === 0) {
    return 0
  }

  let overlap = 0
  for (const token of leftTokens) {
    if (rightTokens.has(token)) {
      overlap += 1
    }
  }

  return overlap
}

function articleBaseScore(article: StoryCluster['articles'][number], index: number) {
  let score = 28 - index * 4
  score += article.framing === 'center' ? 10 : 6
  score += article.url ? 6 : 0
  score += Math.min(article.summary.length, 180) / 18
  score += article.extractionQuality === 'article_body' ? 8 : article.extractionQuality === 'metadata_description' ? 4 : 0
  score += article.bodyText && article.bodyText.length >= 180 ? 5 : 0
  score += article.accessTier === 'open' ? 10 : article.accessTier === 'likely_paywalled' ? -10 : 0

  if (/direct|baseline|process|best|strong|clear/i.test(article.reason)) {
    score += 6
  }

  return score
}

function alternateReadScore(item: ContextItem) {
  let score = 12
  score += item.accessTier === 'open' ? 8 : item.accessTier === 'likely_paywalled' ? -8 : 0
  if (/baseline|clear|direct|evidence|detail/i.test(item.why)) {
    score += 4
  }
  return score
}

function hasOpenRead(articles: StoryCluster['articles']) {
  return articles.some((article) => article.accessTier === 'open')
}

function selectPrimaryReads(articles: StoryCluster['articles']) {
  if (articles.length <= 2) {
    return [...articles].sort((left, right) => articleBaseScore(right, articles.indexOf(right)) - articleBaseScore(left, articles.indexOf(left)))
  }

  const ranked = articles
    .map((article, index) => ({ article, index, score: articleBaseScore(article, index) }))
    .sort((left, right) => right.score - left.score)

  const first = ranked[0]?.article
  if (!first) {
    return []
  }

  const second = ranked
    .slice(1)
    .map(({ article, index, score }) => {
      let comparisonScore = score
      if (article.outlet !== first.outlet) comparisonScore += 8
      if (article.framing !== first.framing) comparisonScore += 6
      comparisonScore -= titleTokenOverlap(article.title, first.title) * 2
      return { article, comparisonScore, index }
    })
    .sort((left, right) => right.comparisonScore - left.comparisonScore)[0]?.article

  return second ? [first, second] : [first]
}

function selectMoreReads(articles: StoryCluster['articles'], selected: StoryCluster['articles']) {
  const selectedKeys = new Set(selected.map((article) => `${article.outlet}:${article.title}`))
  return articles
    .filter((article) => !selectedKeys.has(`${article.outlet}:${article.title}`))
    .sort((left, right) => {
      const leftScore = articleBaseScore(left, articles.indexOf(left))
      const rightScore = articleBaseScore(right, articles.indexOf(right))
      return rightScore - leftScore
    })
}

export async function StoryPage({ slug }: StoryPageProps) {
  const cluster = await getClusterDetail(slug)

  if (!cluster) {
    notFound()
  }

  const entryHref = '/'
  const entryLabel = 'Back to homepage'
  const storyBrief = buildStoryBrief(cluster)
  const coverageSummary = buildCoverageSummary(cluster)
  const perspectiveTakeaways = buildPerspectiveTakeaways(cluster)
  const linkedArticles = cluster.articles.filter((article) => Boolean(article.url))
  const primaryReads = selectPrimaryReads(linkedArticles)
  const moreReads = selectMoreReads(linkedArticles, primaryReads)
  const alternateReads = buildAlternateReads(cluster)
    .filter(
    (item) =>
      Boolean(item.url) &&
      !primaryReads.some((article) => article.outlet === item.outlet && article.title === item.title),
    )
    .sort((left, right) => alternateReadScore(right) - alternateReadScore(left))

  const leadRead = primaryReads[0]
  const leadNeedsOpenAlternate =
    leadRead?.accessTier === 'likely_paywalled' && hasOpenRead(primaryReads.concat(moreReads))
  const openAlternate =
    primaryReads.concat(moreReads).find((article) => article.accessTier === 'open' && article.url) || null

  const reportingHeading = leadNeedsOpenAlternate
    ? 'Start with Prism’s strongest available reads, including an open alternate when the lead source may be gated.'
    : 'Start with these source reads if you want the original reporting behind the brief.'

  return (
    <main className="page-shell cluster-page">
      <SiteNav />
      <header className="cluster-topbar">
        <Link href={entryHref} className="secondary-link">
          {entryLabel}
        </Link>
      </header>

      <section className="cluster-shell">
        <section className="cluster-main">
          <section className="cluster-hero panel">
            <div className="cluster-hero-copy">
              <div className="hero-meta-line">
                <span className="status-chip">{cluster.status}</span>
                <span>{cluster.updatedAt}</span>
                <span>{cluster.outletCount} outlets</span>
              </div>
              <p className="panel-label">{cluster.topic}</p>
              <h1>{cluster.title}</h1>
              <p className="hero-dek">{cluster.dek}</p>
            </div>
            <div className="cluster-hero-media">
              <img src={cluster.heroImage} alt={cluster.heroAlt} className="hero-image" />
              <span className="media-credit">{cluster.heroCredit}</span>
            </div>
          </section>

          <article className="panel content-panel story-summary-panel">
            <div className="section-heading">
                <div>
                  <p className="panel-label">{storyBrief.label}</p>
                  <h2>{storyBrief.title}</h2>
                </div>
              </div>

            <div className="story-summary-body">
              {storyBrief.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>

            <div className="brief-sections">
              <article className="brief-section">
                <p className="panel-label">Why it matters</p>
                <p>{storyBrief.whyItMatters}</p>
              </article>
              <article className="brief-section">
                <p className="panel-label">Where sources agree</p>
                <p>{storyBrief.whereSourcesAgree}</p>
              </article>
              <article className="brief-section">
                <p className="panel-label">Where coverage differs</p>
                <p>{storyBrief.whereCoverageDiffers}</p>
              </article>
              <article className="brief-section">
                <p className="panel-label">What to watch</p>
                <p>{storyBrief.whatToWatch}</p>
              </article>
            </div>

            {storyBrief.supportingPoints.length > 0 ? (
              <div className="story-summary-points">
                <p className="panel-label">What to know</p>
                <ul className="simple-list">
                  {storyBrief.supportingPoints.map((fact) => (
                    <li key={fact}>{fact}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>

          {primaryReads.length > 0 ? (
          <article className="panel content-panel">
              <div className="section-heading">
                <div>
                  <p className="panel-label">Reporting to read next</p>
                  <h2>{reportingHeading}</h2>
                </div>
              </div>

            {leadNeedsOpenAlternate && openAlternate ? (
              <p className="article-stack-note">
                The strongest lead source here may be harder to access directly. Prism is also surfacing an open alternate from <strong>{openAlternate.outlet}</strong> so the story does not dead-end on a paywall.
              </p>
            ) : null}

            <div className="article-stack">
              {primaryReads.map((article, index) => (
                article.url ? (
                  <a
                    className={`article-card article-card-link${index === 0 ? ' article-card-featured' : ''}`}
                    href={article.url}
                    key={`${article.outlet}-${article.title}`}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <img
                      src={article.image}
                      alt={`${article.outlet} article visual`}
                      className="article-card-image"
                    />
                    <div className="article-card-copy">
                      <div className="article-card-meta">
                        <span>{article.outlet}</span>
                        <span>{article.published}</span>
                        <span className={`framing-pill framing-${article.framing}`}>
                          {article.framing}
                        </span>
                      </div>
                      <div className="article-card-heading">
                        <span className="article-rank-label">
                          {index === 0 ? 'Baseline read' : 'Different angle'}
                        </span>
                        <h3>{article.title}</h3>
                      </div>
                      <p>{article.summary}</p>
                      <div className="article-card-footer-row">
                        <span className="secondary-link article-card-cta">Read original</span>
                      </div>
                    </div>
                  </a>
                ) : (
                  <article
                    className={`article-card${index === 0 ? ' article-card-featured' : ''}`}
                    key={`${article.outlet}-${article.title}`}
                  >
                    <img
                      src={article.image}
                      alt={`${article.outlet} article visual`}
                      className="article-card-image"
                    />
                    <div className="article-card-copy">
                      <div className="article-card-meta">
                        <span>{article.outlet}</span>
                        <span>{article.published}</span>
                        <span className={`framing-pill framing-${article.framing}`}>
                          {article.framing}
                        </span>
                      </div>
                      <div className="article-card-heading">
                        <span className="article-rank-label">
                          {index === 0 ? 'Baseline read' : 'Different angle'}
                        </span>
                        <h3>{article.title}</h3>
                      </div>
                      <p>{article.summary}</p>
                    </div>
                  </article>
                )
              ))}
            </div>
            {moreReads.length > 0 ? (
              <div className="more-reporting-list">
                <p className="panel-label">Also in the mix</p>
                <ul className="compact-link-list">
                  {moreReads.slice(0, 3).map((article) => (
                    <li key={`${article.outlet}-${article.title}-more`}>
                      {article.url ? (
                        <a href={article.url} rel="noreferrer" target="_blank">
                          <strong>{article.outlet}</strong>: {article.title}
                        </a>
                      ) : (
                        <span>
                          <strong>{article.outlet}</strong>: {article.title}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>
          ) : null}

          {alternateReads.length > 0 ? (
            <article className="panel content-panel">
              <div className="section-heading">
                <div>
                  <p className="panel-label">Another angle</p>
                  <h2>Three useful alternate reads.</h2>
                </div>
              </div>
              <div className="alternate-read-list">
                {alternateReads.map((item) => (
                  item.url ? (
                    <a
                      className="alternate-read-item alternate-read-link"
                      href={item.url}
                      key={`${item.outlet}-${item.title}`}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <div className="alternate-read-top">
                        <strong>{item.outlet}</strong>
                      </div>
                      <h3>{item.title}</h3>
                      <p>{item.why}</p>
                    </a>
                  ) : (
                    <article className="alternate-read-item" key={`${item.outlet}-${item.title}`}>
                      <div className="alternate-read-top">
                        <strong>{item.outlet}</strong>
                      </div>
                      <h3>{item.title}</h3>
                      <p>{item.why}</p>
                    </article>
                  )
                ))}
              </div>
            </article>
          ) : null}

          <details className="panel content-panel disclosure-panel">
            <summary>Source notes and corrections</summary>
            <div className="disclosure-body">
              <div className="disclosure-section">
                <p className="panel-label">What this is based on</p>
                <ul className="evidence-list">
                  {cluster.evidence.map((item) => (
                    <li className="evidence-row" key={item.label}>
                      <div className="evidence-row-top">
                        <strong>{item.label}</strong>
                        <span className="evidence-type">{item.type}</span>
                      </div>
                      <span className="evidence-source">{item.source}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="disclosure-section">
                <p className="panel-label">Corrections</p>
                <ul className="corrections-list">
                  {cluster.corrections.map((item) => (
                    <li className="corrections-row" key={`${item.timestamp}-${item.note}`}>
                      <strong>{item.timestamp}</strong>
                      <span>{item.note}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="inspector-link-row">
                <Link className="secondary-link" href="/corrections">
                  Full corrections log
                </Link>
                <Link className="secondary-link" href="/methodology">
                  Read methodology
                </Link>
              </div>
            </div>
          </details>
        </section>

        <aside className="inspector-rail">
          <article className="panel inspector-panel perspective-panel">
            <div className="section-heading">
              <div>
                <p className="panel-label">Prism perspective</p>
                <h2>How outlets are covering it</h2>
              </div>
            </div>
            <div className="perspective-summary-block">
              <p className="coverage-summary">{coverageSummary}</p>
              <ul className="simple-list perspective-list">
                {perspectiveTakeaways.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="perspective-meter-block">
              <p className="panel-label">Coverage mix</p>
              <div className="coverage-rows">
                <div className="coverage-row">
                  <span>Left</span>
                  <div className="dot-row" aria-hidden="true">
                    {Array.from({ length: cluster.coverageCounts.left }).map((_, index) => (
                      <span className="dot-left" key={`left-${index}`} />
                    ))}
                  </div>
                </div>
                <div className="coverage-row">
                  <span>Center</span>
                  <div className="dot-row" aria-hidden="true">
                    {Array.from({ length: cluster.coverageCounts.center }).map((_, index) => (
                      <span className="dot-center" key={`center-${index}`} />
                    ))}
                  </div>
                </div>
                <div className="coverage-row">
                  <span>Right</span>
                  <div className="dot-row" aria-hidden="true">
                    {Array.from({ length: cluster.coverageCounts.right }).map((_, index) => (
                      <span className="dot-right" key={`right-${index}`} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <p className="inspector-note perspective-note">
              Perspective shows the mix Prism is seeing in coverage. It does not decide who is
              right.
            </p>
          </article>
        </aside>
      </section>
      <SiteFooter />
    </main>
  )
}
