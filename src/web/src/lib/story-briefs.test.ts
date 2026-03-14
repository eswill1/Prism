import assert from 'node:assert/strict'
import test from 'node:test'

import { buildStoryBrief } from './story-briefs'
import type { StoryCluster } from './mock-clusters'

const singleSourceCluster: StoryCluster = {
  clusterId: 'cluster-1',
  slug: 'single-source-story',
  topic: 'World',
  title: 'Single-source story',
  dek: 'Cuba confirmed talks with the Trump administration after fuel shortages deepened the country’s economic crisis.',
  updatedAt: 'Updated 10m ago',
  status: 'Live intake',
  heroImage: 'https://example.com/image.jpg',
  heroAlt: 'Example image',
  heroCredit: 'Example credit',
  outletCount: 1,
  reliabilityRange: 'Early source set',
  coverageCounts: { left: 0, center: 1, right: 0 },
  keyFacts: [
    'Officials said the talks are aimed at resolving immediate fuel and transport shortages.',
    'The shortages have already disrupted domestic power generation and freight movement.',
    'State media framed the talks as crisis management rather than a diplomatic reset.',
  ],
  whatChanged: [],
  changeTimeline: [],
  articles: [
    {
      outlet: 'Reuters',
      title: 'Cuba says talks with Trump administration are focused on fuel emergency',
      summary:
        'Cuba said the talks were focused on fuel shortages, transport disruption and a broader economic crunch after Venezuelan oil shipments were cut.',
      bodyText:
        'Cuba said the talks were focused on fuel shortages, transport disruption and a broader economic crunch after Venezuelan oil shipments were cut. Officials said the immediate goal was to stabilize domestic supply and keep freight lines moving. The government described the contacts as practical rather than a diplomatic reset. Power generation has already been reduced in several provinces because fuel stocks are low. Freight delays have started to disrupt deliveries and factory schedules across the island. State media said any agreement would be judged by whether it eases shortages quickly for households and businesses.',
      extractionQuality: 'article_body',
      accessTier: 'open',
      published: '20m ago',
      framing: 'center',
      image: 'https://example.com/article.jpg',
      reason: 'baseline read',
      url: 'https://example.com/story',
    },
  ],
  evidence: [],
  corrections: [],
  contextPacks: {},
}

test('early briefs still produce a fuller one-source narrative summary', () => {
  const brief = buildStoryBrief(singleSourceCluster)

  assert.equal(brief.isEarlyBrief, true)
  assert.ok(brief.paragraphs.length >= 3)
  assert.equal(brief.isVisible, true)
  assert.ok(brief.paragraphs.every((paragraph) => !/^Prism\b/.test(paragraph)))
})

test('one-source briefs without a distinct grounded followup are hidden', () => {
  const brief = buildStoryBrief({
    ...singleSourceCluster,
    slug: 'thin-single-source-story',
    title: 'Thin single-source story',
    dek: 'Lawmakers delayed the vote until next week.',
    keyFacts: [],
    articles: [
      {
        outlet: 'Reuters',
        title: 'Lawmakers delay vote until next week',
        summary: 'Lawmakers delayed the vote until next week.',
        bodyText: 'Lawmakers delayed the vote until next week.',
        extractionQuality: 'article_body',
        accessTier: 'open',
        published: '20m ago',
        framing: 'center',
        image: 'https://example.com/article.jpg',
        reason: 'baseline read',
        url: 'https://example.com/thin-story',
      },
    ],
  })

  assert.equal(brief.isVisible, false)
  assert.equal(brief.hideReason, 'no_distinct_grounded_followup')
})

test('blocked fetches stay hidden instead of surfacing access boilerplate as a brief', () => {
  const brief = buildStoryBrief({
    ...singleSourceCluster,
    slug: 'blocked-story',
    title: 'Blocked story',
    dek: 'President Trump said Friday that he has his own idea of how long the conflict in Iran could last.',
    keyFacts: ['The strongest available source read is already open.'],
    articles: [
      {
        outlet: 'The Hill',
        title: 'Trump says he has own idea on how long Iran war will last',
        summary: 'President Trump said Friday that he has his own idea of how long the conflict in Iran could last.',
        feedSummary: 'President Trump said Friday that he has his own idea of how long the conflict in Iran could last.',
        extractionQuality: 'rss_only',
        accessTier: 'open',
        fetchBlocked: true,
        fetchBlockReason: 'anti_bot_challenge',
        published: '20m ago',
        framing: 'center',
        image: 'https://example.com/article.jpg',
        reason: 'baseline read',
        url: 'https://thehill.com/example-story',
      },
    ],
  })

  assert.equal(brief.isVisible, false)
  assert.equal(brief.hideReason, 'no_distinct_grounded_followup')
})

test('quoted body sentences stay intact in one-source early briefs', () => {
  const brief = buildStoryBrief({
    ...singleSourceCluster,
    slug: 'quoted-story',
    title: 'Trump says he has own idea on how long Iran war will last',
    dek: 'President Trump said Friday that he has his “own idea” of how long the conflict in Iran could last.',
    articles: [
      {
        outlet: 'The Hill',
        title: 'Trump says he has own idea on how long Iran war will last',
        summary:
          'President Trump said Friday that he has his “own idea” of how long the conflict in Iran could last.',
        bodyText:
          'President Trump said Friday that he has his “own idea” of how long the conflict in Iran could last, adding to a series of shifting messages about the timeline for the joint U.S.-Israeli operation. “I mean, I have my own idea. But what good does it do?” Trump told reporters at Joint Base Andrews when asked about the duration of the war. “It’ll be as long as it’s necessary.” Trump and the Pentagon have offered conflicting signals about when the conflict could come to an end, despite asserting that the U.S. is close to achieving its objectives.',
        extractionQuality: 'article_body',
        accessTier: 'open',
        published: '20m ago',
        framing: 'center',
        image: 'https://example.com/article.jpg',
        reason: 'baseline read',
        url: 'https://thehill.com/example-story',
      },
    ],
  })

  const combined = brief.paragraphs.join(' ')
  assert.match(combined, /But what good does it do\?” Trump told reporters/i)
  assert.ok(!combined.includes('But what good does it do? ”'))
  assert.equal((combined.match(/President Trump said Friday/g) || []).length, 1)
  assert.equal(brief.isVisible, true)
})
