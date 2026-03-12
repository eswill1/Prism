import type { ClusterArticle, StoryCluster } from './mock-clusters'
import type { StoryBrief } from './story-brief-types'

export type { StoryBrief } from './story-brief-types'

type TopicFamily = 'politics' | 'world' | 'business' | 'technology' | 'weather' | 'general'

type BriefSource = {
  outlet: string
  framing: ClusterArticle['framing']
  snippet: string
  focus: string
  detail: string
}

const PLACEHOLDER_KEY_FACT = /^Prism has |^Prism only has |^The latest linked reporting came from |^The comparison set /i
const GENERIC_FOCUS_TOKENS = new Set([
  'another',
  'around',
  'current',
  'currently',
  'detailed',
  'development',
  'first',
  'general',
  'headline',
  'holding',
  'linked',
  'main',
  'potentially',
  'prism',
  'report',
  'reported',
  'reporting',
  'source',
  'sources',
  'story',
  'strong',
  'take',
  'this',
  'hold',
  'driving',
  'drive',
  'driven',
  'set',
  'likely',
  'emerge',
  'persist',
  'through',
  'today',
  'update',
  'updates',
])

function ensurePeriod(value: string) {
  const trimmed = value.trim()
  if (!trimmed) {
    return trimmed
  }

  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

function normalizeWhitespace(value: string) {
  return value.replace(/\s+/g, ' ').trim()
}

function stripEndingPunctuation(value: string) {
  return value.trim().replace(/[.!?]+$/, '')
}

function focusFallbackForFamily(family: TopicFamily) {
  switch (family) {
    case 'politics':
      return 'policy and political consequences'
    case 'business':
      return 'prices and economic fallout'
    case 'technology':
      return 'technology policy and platform rules'
    case 'weather':
      return 'weather and temperature impacts'
    case 'world':
      return 'international fallout'
    default:
      return 'the main reported development'
  }
}

function cleanFocusPhrase(value: string, family: TopicFamily) {
  const cleaned = stripEndingPunctuation(value)
  if (!cleaned) {
    return focusFallbackForFamily(family)
  }

  const tokens: string[] = []
  for (const token of cleaned.toLowerCase().match(/[a-zà-ÿ]{4,}/g) || []) {
    if (GENERIC_FOCUS_TOKENS.has(token)) {
      continue
    }
    if (!tokens.includes(token)) {
      tokens.push(token)
    }
  }

  if (tokens.length === 0) {
    return focusFallbackForFamily(family)
  }
  if (tokens.length === 1) {
    return tokens[0]
  }
  return `${tokens[0]} and ${tokens[1]}`
}

function sentenceSimilarity(left: string, right: string) {
  const leftTokens = new Set(left.toLowerCase().match(/[a-z0-9]{4,}/g) || [])
  const rightTokens = new Set(right.toLowerCase().match(/[a-z0-9]{4,}/g) || [])

  if (leftTokens.size === 0 || rightTokens.size === 0) {
    return 0
  }

  let overlap = 0
  for (const token of leftTokens) {
    if (rightTokens.has(token)) {
      overlap += 1
    }
  }

  return overlap / Math.max(leftTokens.size, rightTokens.size)
}

function isNearDuplicateSentence(candidate: string, existing: string[]) {
  return existing.some((value) => sentenceSimilarity(candidate, value) >= 0.72)
}

function firstNarrativeSentences(text: string, sentenceCount: number) {
  const matches = text.match(/[^.!?]+[.!?]+/g) || []
  const cleaned = matches.map((sentence) => normalizeWhitespace(sentence)).filter(Boolean)

  if (cleaned.length === 0) {
    return normalizeWhitespace(text)
  }

  return cleaned.slice(0, sentenceCount).join(' ')
}

function laterNarrativeSentences(text: string, skipCount: number, sentenceCount: number) {
  const matches = text.match(/[^.!?]+[.!?]+/g) || []
  const cleaned = matches.map((sentence) => normalizeWhitespace(sentence)).filter(Boolean)

  if (cleaned.length <= skipCount) {
    return ''
  }

  return cleaned.slice(skipCount, skipCount + sentenceCount).join(' ')
}

function topicFamilyForStory(topic: string): TopicFamily {
  const normalized = topic.toLowerCase()

  if (/(policy|politic|government|congress|senate|election|white house|u\.s\.|us )/.test(normalized)) {
    return 'politics'
  }
  if (/(business|economy|economic|market|trade|finance)/.test(normalized)) {
    return 'business'
  }
  if (/(technology|tech|ai|innovation)/.test(normalized)) {
    return 'technology'
  }
  if (/(climate|weather|storm|wildfire|flood|energy|infrastructure|disaster)/.test(normalized)) {
    return 'weather'
  }
  if (/(world|global|international)/.test(normalized)) {
    return 'world'
  }

  return 'general'
}

function substantiveTextForArticle(article: ClusterArticle) {
  if (article.bodyText) {
    const bodyCandidate = firstNarrativeSentences(article.bodyText, 3)
    if (bodyCandidate.length >= 120) {
      return bodyCandidate
    }
  }

  if (article.summary) {
    return normalizeWhitespace(article.summary)
  }

  if (article.feedSummary) {
    return normalizeWhitespace(article.feedSummary)
  }

  return ''
}

function isSubstantiveArticle(article: ClusterArticle) {
  if (article.extractionQuality === 'article_body' && article.bodyText && article.bodyText.length >= 180) {
    return true
  }

  return substantiveTextForArticle(article).length >= 110
}

function articleFocus(article: ClusterArticle) {
  const namedEntities = (article.namedEntities || []).filter((value) => value.length >= 4)
  if (namedEntities.length >= 2) {
    return `${namedEntities[0]} and ${namedEntities[1]}`
  }
  if (namedEntities.length === 1) {
    return namedEntities[0]
  }

  for (const text of [article.title, article.summary, article.feedSummary]) {
    if (!text) {
      continue
    }
    const tokens = text
      .toLowerCase()
      .match(/[a-zà-ÿ]{4,}/g)
      ?.filter(
        (value) =>
          !GENERIC_FOCUS_TOKENS.has(value) &&
          !['which', 'their', 'there', 'about', 'would', 'could', 'these'].includes(value),
      )
      .slice(0, 2)

    if (tokens && tokens.length >= 2) {
      return `${tokens[0]} and ${tokens[1]}`
    }
    if (tokens && tokens.length === 1) {
      return tokens[0]
    }
  }

  return 'the practical stakes'
}

function buildBriefSources(cluster: StoryCluster) {
  const existing: string[] = []
  const titleAnchors = [cluster.title, cluster.dek]
  const sources: BriefSource[] = []

  for (const article of cluster.articles) {
    if (!isSubstantiveArticle(article)) {
      continue
    }

    const snippet = substantiveTextForArticle(article)
    if (!snippet) {
      continue
    }

    const tooCloseToTitle = titleAnchors.some((title) => sentenceSimilarity(snippet, title) >= 0.72)
    if (tooCloseToTitle && cluster.articles.length > 1) {
      continue
    }

    if (isNearDuplicateSentence(snippet, existing)) {
      continue
    }

    existing.push(snippet)
    sources.push({
      outlet: article.outlet,
      framing: article.framing,
      snippet: ensurePeriod(snippet),
      focus: articleFocus(article),
      detail: ensurePeriod(laterNarrativeSentences(article.bodyText || '', 2, 2)),
    })
  }

  return sources
}

function distinctOutletCount(cluster: StoryCluster) {
  return new Set(cluster.articles.map((article) => article.outlet)).size
}

function outletText(cluster: StoryCluster) {
  const outlets = Array.from(new Set(cluster.articles.map((article) => article.outlet))).slice(0, 3)
  if (outlets.length === 0) {
    return `${cluster.outletCount} outlets`
  }

  if (outlets.length === 1) {
    return outlets[0]
  }

  return `${outlets.slice(0, -1).join(', ')} and ${outlets[outlets.length - 1]}`
}

function outletListText(outlets: string[]) {
  const unique = Array.from(new Set(outlets.filter(Boolean)))
  if (unique.length === 0) {
    return 'multiple outlets'
  }
  if (unique.length === 1) {
    return unique[0]
  }
  if (unique.length === 2) {
    return `${unique[0]} and ${unique[1]}`
  }
  return `${unique.slice(0, -1).join(', ')}, and ${unique[unique.length - 1]}`
}

function centralSource(sources: BriefSource[]) {
  if (sources.length === 0) {
    return null
  }

  let best: BriefSource | null = null
  let bestScore = -1

  for (const source of sources) {
    const score = sources.reduce((total, other) => total + sentenceSimilarity(source.snippet, other.snippet), 0)
    if (score > bestScore) {
      best = source
      bestScore = score
    }
  }

  return best
}

function divergentSource(sources: BriefSource[], central: BriefSource | null) {
  if (!central) {
    return sources[1] || null
  }

  return (
    sources
      .filter((source) => source.outlet !== central.outlet)
      .sort((left, right) => {
        const leftFramingBonus = left.framing !== central.framing ? -0.25 : 0
        const rightFramingBonus = right.framing !== central.framing ? -0.25 : 0
        const leftScore = sentenceSimilarity(left.snippet, central.snippet) + leftFramingBonus
        const rightScore = sentenceSimilarity(right.snippet, central.snippet) + rightFramingBonus
        return leftScore - rightScore
      })[0] || null
  )
}

function visibleKeyFacts(cluster: StoryCluster) {
  return cluster.keyFacts
    .map((fact) => ensurePeriod(fact))
    .filter((fact) => !PLACEHOLDER_KEY_FACT.test(fact))
    .filter((fact, index, values) => values.findIndex((value) => sentenceSimilarity(value, fact) >= 0.8) === index)
    .slice(0, 3)
}

function whyItMattersCopy(cluster: StoryCluster, family: TopicFamily, sources: BriefSource[]) {
  const visibleFacts = visibleKeyFacts(cluster)
  if (visibleFacts[1]) {
    return visibleFacts[1]
  }

  if (sources[1]) {
    return `This matters because the reporting is already pointing beyond the immediate headline and toward ${cleanFocusPhrase(
      sources[1].focus,
      family,
    )}.`
  }

  if (sources[0]) {
    switch (family) {
      case 'politics':
        return `This matters because the next move here could affect public policy, negotiations, or the balance of political leverage in a visible way.`
      case 'business':
        return `This matters because the practical effects are likely to show up in prices, markets, or business decisions faster than in many political stories.`
      case 'technology':
        return `This matters because the story is really about who sets the rules for platforms, infrastructure, or emerging technology before those rules harden.`
      case 'weather':
        return `This matters because the real consequences are operational: safety, infrastructure, recovery, and the public systems people rely on every day.`
      case 'world':
        return `This matters because the story is already affecting how other governments, markets, or institutions are responding beyond the immediate event itself.`
      default:
        return `This matters because the story is broad enough that reading one outlet alone is already likely to miss part of the picture.`
    }
  }

  switch (family) {
    case 'politics':
      return `This matters because the next move here could affect public policy, negotiations, or the balance of political leverage in a visible way.`
    case 'business':
      return `This matters because the practical effects are likely to show up in prices, markets, or business decisions faster than in many political stories.`
    case 'technology':
      return `This matters because the story is really about who sets the rules for platforms, infrastructure, or emerging technology before those rules harden.`
    case 'weather':
      return `This matters because the real consequences are operational: safety, infrastructure, recovery, and the public systems people rely on every day.`
    case 'world':
      return `This matters because the story is already affecting how other governments, markets, or institutions are responding beyond the immediate event itself.`
    default:
      return `This matters because the story is broad enough that reading one outlet alone is already likely to miss part of the picture.`
  }
}

function watchNextCopy(cluster: StoryCluster, family: TopicFamily) {
  if (cluster.whatChanged[0] && !/^Story shell refreshed from \d+ publisher signals$/i.test(cluster.whatChanged[0])) {
    return `Watch for the next turn: ${ensurePeriod(cluster.whatChanged[0])}`
  }

  switch (family) {
    case 'politics':
      return `Watch for new votes, official statements, or negotiation details that change the practical stakes instead of just the rhetoric.`
    case 'business':
      return `Watch for any move in prices, official economic action, or company response that makes the downstream effects easier to measure.`
    case 'technology':
      return `Watch for regulatory details, product changes, or company statements that turn the broad argument into concrete action.`
    case 'weather':
      return `Watch for damage figures, recovery updates, and official assessments that show whether this is a short disruption or a longer resilience problem.`
    case 'world':
      return `Watch for international responses, official confirmations, and any change that broadens the story beyond the first wave of headlines.`
    default:
      return `Watch for new reporting or official updates that widen the source mix and sharpen where the coverage starts to split.`
  }
}

export function buildStoryBrief(cluster: StoryCluster): StoryBrief {
  const family = topicFamilyForStory(cluster.topic)
  const sources = buildBriefSources(cluster)
  const central = centralSource(sources)
  const divergent = divergentSource(sources, central)
  const fullBrief = sources.length >= 2 && distinctOutletCount(cluster) >= 2
  const secondarySources = sources
    .filter((source) => source.outlet !== central?.outlet)
    .slice(0, 3)
  const corroboratingOutlets = outletListText(secondarySources.map((source) => source.outlet))

  const paragraphs = fullBrief
    ? [
        ensurePeriod(cluster.dek),
        central
          ? `Across ${outletText(cluster)}, the core sequence is consistent. ${central.snippet}`
          : ensurePeriod(cluster.dek),
        secondarySources.length > 0
          ? `${corroboratingOutlets} add more detail around ${stripEndingPunctuation(
              secondarySources[0]?.focus || 'the practical stakes',
            )}, which helps turn the headline into a clearer working picture of the story.`
          : '',
        divergent
          ? `${divergent.outlet} puts more emphasis on ${stripEndingPunctuation(
              divergent.focus,
            )}, so the difference in coverage is mostly about what deserves the most attention rather than basic disagreement about the event itself.`
          : `The coverage is still relatively aligned on the event itself, with the main differences showing up in emphasis and downstream consequences.`,
      ]
    : [
        ensurePeriod(cluster.dek),
        sources[0]
          ? sources[0].detail &&
            (sources[0].snippet.includes(cluster.dek) || sentenceSimilarity(sources[0].snippet, cluster.dek) >= 0.72)
            ? `The clearest detailed reporting so far comes from ${sources[0].outlet}. ${sources[0].detail}`
            : sentenceSimilarity(sources[0].snippet, cluster.dek) < 0.72
            ? `The clearest detailed reporting so far comes from ${sources[0].outlet}. ${sources[0].snippet}`
            : `The clearest detailed reporting so far comes from ${sources[0].outlet}, and it supports the same overall picture while adding detail beyond the first headline.`
          : '',
        sources[1]
          ? `Prism has also linked another read from ${sources[1].outlet}, but the source mix is still too thin to treat differences in emphasis as a meaningful split in coverage.`
          : `Prism is still working with a thin source set here. This early brief will become more useful once another detailed report arrives and the comparison layer has more than one substantive account to work with.`,
      ]

  const whereSourcesAgree = fullBrief
    ? `Across ${outletText(cluster)}, the shared baseline is clear: ${central?.snippet || ensurePeriod(cluster.dek)}`
    : `Prism only has one substantive linked report so far, so the shared baseline is still forming from early reporting rather than a mature multi-source comparison.`

  const whereCoverageDiffers = fullBrief
    ? divergent
      ? `The split so far is more about emphasis than the event itself. ${central?.outlet || 'One outlet'} stays closest to the core sequence, while ${divergent.outlet} gives more weight to ${divergent.focus}.`
      : `The reporting is still fairly aligned on the core sequence, but outlets are beginning to diverge in what they emphasize most.`
    : `It is too early to call a real split in coverage. Prism needs at least one more detailed independent report before differences in framing become useful to compare.`

  return {
    label: fullBrief ? 'Prism brief' : 'Early brief',
    title: fullBrief ? 'The story so far' : 'What the reporting says so far',
    paragraphs: paragraphs.filter((paragraph, index, values) => {
      if (!paragraph.trim()) {
        return false
      }
      return values.findIndex((value) => sentenceSimilarity(value, paragraph) >= 0.82) === index
    }),
    whyItMatters: whyItMattersCopy(cluster, family, sources),
    whereSourcesAgree,
    whereCoverageDiffers,
    whatToWatch: watchNextCopy(cluster, family),
    supportingPoints: visibleKeyFacts(cluster),
    substantiveSourceCount: sources.length,
    isEarlyBrief: !fullBrief,
  }
}
