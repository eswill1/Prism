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
  assert.match(
    brief.paragraphs[brief.paragraphs.length - 1] || '',
    /one-source early brief|fuller working summary/i,
  )
})
