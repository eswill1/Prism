export type NewsSectionKey =
  | 'world'
  | 'politics'
  | 'business'
  | 'technology'
  | 'weather'
  | 'more'

export type NewsSection = {
  key: NewsSectionKey
  title: string
  navLabel: string
  anchor: string
  description: string
}

export const NEWS_SECTIONS: NewsSection[] = [
  {
    key: 'world',
    title: 'World',
    navLabel: 'World',
    anchor: 'world',
    description: 'Major international developments and global conflict, diplomacy, and society.',
  },
  {
    key: 'politics',
    title: 'Politics',
    navLabel: 'Politics',
    anchor: 'politics',
    description: 'Government, elections, public policy, and the stories shaping civic life.',
  },
  {
    key: 'business',
    title: 'Business',
    navLabel: 'Business',
    anchor: 'business',
    description: 'Markets, economic pressure, trade, labor, and the money side of public events.',
  },
  {
    key: 'technology',
    title: 'Technology',
    navLabel: 'Tech',
    anchor: 'technology',
    description: 'AI, platforms, infrastructure, and the industries reshaping daily life.',
  },
  {
    key: 'weather',
    title: 'Weather',
    navLabel: 'Weather',
    anchor: 'weather',
    description: 'Weather, disasters, energy, resilience, and environmental consequences with public impact.',
  },
  {
    key: 'more',
    title: 'More',
    navLabel: 'More',
    anchor: 'more',
    description: 'Additional stories that do not fit the launch section taxonomy cleanly yet.',
  },
]

export const PRIMARY_NEWS_SECTIONS = NEWS_SECTIONS.filter((section) => section.key !== 'more')

export function getNewsSectionKey(topic: string): NewsSectionKey {
  const normalized = topic.toLowerCase()

  if (/(technology|tech|innovation|ai)/.test(normalized)) {
    return 'technology'
  }

  if (/(business|economy|economic|market|trade|finance)/.test(normalized)) {
    return 'business'
  }

  if (/(climate|weather|storm|hurricane|wildfire|flood|energy|infrastructure|environment|disaster)/.test(normalized)) {
    return 'weather'
  }

  if (/(politic|policy|government|congress|senate|election|white house|u\.s\.|us )/.test(normalized)) {
    return 'politics'
  }

  if (/(world|global|international)/.test(normalized)) {
    return 'world'
  }

  return 'more'
}

export function getNewsSection(topic: string): NewsSection {
  const key = getNewsSectionKey(topic)
  return NEWS_SECTIONS.find((section) => section.key === key) ?? NEWS_SECTIONS[NEWS_SECTIONS.length - 1]
}
