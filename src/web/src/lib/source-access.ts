export type SourceAccessTier = 'open' | 'likely_paywalled' | 'unknown'

const OPEN_SOURCE_LABELS = new Set([
  'ABC News',
  'Associated Press',
  'BBC',
  'BBC News',
  'CBS News',
  'CNN',
  'Fox News',
  'MSNBC',
  'NBC News',
  'NPR',
  'PBS NewsHour',
  'Politico',
  'Reuters',
  'The Hill',
])

const PAYWALLED_SOURCE_LABELS = new Set([
  'Bloomberg',
  'Financial Times',
  'New York Times',
  'Wall Street Journal',
  'WSJ World',
])

const OPEN_SOURCE_DOMAINS = [
  'abcnews.com',
  'apnews.com',
  'bbc.com',
  'cbsnews.com',
  'cnn.com',
  'foxnews.com',
  'msnbc.com',
  'nbcnews.com',
  'npr.org',
  'pbs.org',
  'politico.com',
  'reuters.com',
  'thehill.com',
]

const PAYWALLED_SOURCE_DOMAINS = ['bloomberg.com', 'ft.com', 'nytimes.com', 'wsj.com']

function normalizeDomain(value: string | null | undefined) {
  if (!value) {
    return ''
  }

  try {
    const url = new URL(value)
    return url.hostname.replace(/^www\./, '').toLowerCase()
  } catch {
    return value.replace(/^www\./, '').toLowerCase()
  }
}

export function inferSourceAccessTier(params: {
  outlet?: string | null
  url?: string | null
  domain?: string | null
}): SourceAccessTier {
  const outlet = params.outlet?.trim() ?? ''
  const domain = normalizeDomain(params.domain || params.url)

  if (OPEN_SOURCE_LABELS.has(outlet)) {
    return 'open'
  }
  if (PAYWALLED_SOURCE_LABELS.has(outlet)) {
    return 'likely_paywalled'
  }

  if (OPEN_SOURCE_DOMAINS.some((candidate) => domain === candidate || domain.endsWith(`.${candidate}`))) {
    return 'open'
  }
  if (
    PAYWALLED_SOURCE_DOMAINS.some((candidate) => domain === candidate || domain.endsWith(`.${candidate}`))
  ) {
    return 'likely_paywalled'
  }

  return 'unknown'
}
