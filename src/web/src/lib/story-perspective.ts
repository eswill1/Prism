import type { StoryCluster } from './mock-clusters'
import type { StoryPerspective } from './story-perspective-types'

function articleSourceFamily(outlet: string) {
  if (['Associated Press', 'Reuters'].includes(outlet)) {
    return 'Wire services'
  }
  if (['BBC News', 'NPR', 'PBS NewsHour'].includes(outlet)) {
    return 'Public media'
  }
  if (['NBC News', 'ABC News', 'CBS News', 'CNN', 'Fox News', 'MSNBC'].includes(outlet)) {
    return 'Broadcast networks'
  }
  if (['Politico', 'The Hill'].includes(outlet)) {
    return 'Policy publications'
  }
  return 'National publications'
}

function articleScope(cluster: StoryCluster, article: StoryCluster['articles'][number]) {
  const haystack = `${cluster.topic} ${cluster.title} ${article.title} ${article.summary}`.toLowerCase()
  if (
    /\b(local|state|city|county|community|residents|families|utility|outage|operations|jobs|workers|customers)\b/.test(
      haystack,
    )
  ) {
    return 'Local impact'
  }
  if (
    ['BBC News', 'Reuters', 'Financial Times', 'Bloomberg'].includes(article.outlet) ||
    /\b(global|international|foreign|europe|china|iran|ukraine|britain|parliament|strait of hormuz)\b/.test(
      haystack,
    )
  ) {
    return 'International frame'
  }
  return 'National frame'
}

function joinLabels(labels: string[]) {
  if (labels.length === 0) return ''
  if (labels.length === 1) return labels[0]
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`
  return `${labels.slice(0, -1).join(', ')}, and ${labels.at(-1)}`
}

function presenceRows(counts: Record<string, number>, notes: Record<string, string>) {
  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1])
    .map(([label, count]) => ({
      label,
      count,
      note: notes[label] || '',
    }))
}

export function buildFallbackPerspective(cluster: StoryCluster): StoryPerspective {
  const framingCounts = {
    'Left / advocacy-leaning framing': cluster.coverageCounts.left,
    'Center / straight-news framing': cluster.coverageCounts.center,
    'Right / advocacy-leaning framing': cluster.coverageCounts.right,
  }

  const familyCounts = cluster.articles.reduce<Record<string, number>>((accumulator, article) => {
    const family = articleSourceFamily(article.outlet)
    accumulator[family] = (accumulator[family] || 0) + 1
    return accumulator
  }, {})

  const scopeCounts = cluster.articles.reduce<Record<string, number>>((accumulator, article) => {
    const scope = articleScope(cluster, article)
    accumulator[scope] = (accumulator[scope] || 0) + 1
    return accumulator
  }, {})

  const familyLabels = Object.entries(familyCounts)
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1])
    .map(([label]) => label)
    .slice(0, 2)

  const dominantFraming =
    cluster.coverageCounts.center >= Math.max(cluster.coverageCounts.left, cluster.coverageCounts.right)
      ? 'center / straight-news framing'
      : cluster.coverageCounts.left > cluster.coverageCounts.right
        ? 'left / advocacy-leaning framing'
        : 'right / advocacy-leaning framing'

  return {
    status: cluster.outletCount >= 2 ? 'ready' : 'early',
    summary:
      cluster.outletCount >= 2
        ? `Prism is seeing a broader comparison set here. Coverage is led by ${dominantFraming}, with the strongest family presence coming from ${joinLabels(familyLabels).toLowerCase() || 'a mixed outlet set'}.`
        : `Perspective is still early here. Prism has a narrow reporting set so far, and the clearest visible frame is ${dominantFraming}.`,
    takeaways:
      cluster.outletCount >= 2
        ? [
            'Shared baseline: multiple outlets are now covering the same core development.',
            'Main split: the current reporting mix spans straight-news coverage and more explicitly framed takes.',
            'Scope check: Perspective is showing which kinds of coverage are present, not deciding who is right.',
          ]
        : [
            'This is still an early comparison view because only one outlet family is strongly represented.',
            'Perspective will sharpen once Prism has more detailed reporting from another source.',
          ],
    framingPresence: presenceRows(framingCounts, {
      'Left / advocacy-leaning framing': 'Present in the linked reporting, not treated as a verdict.',
      'Center / straight-news framing': 'Baseline straight-news framing present in the current mix.',
      'Right / advocacy-leaning framing': 'Present in the linked reporting, not treated as a verdict.',
    }),
    sourceFamilyPresence: presenceRows(familyCounts, {
      'Wire services': 'Useful for baseline facts and fast-moving updates.',
      'Public media': 'Often adds explanatory framing and civic context.',
      'Broadcast networks': 'Adds broad public-facing framing and urgency signals.',
      'Policy publications': 'Often emphasizes institutional or strategic implications.',
      'National publications': 'Adds deeper narrative framing and enterprise context.',
    }),
    scopePresence: presenceRows(scopeCounts, {
      'Local impact': 'Highlights practical effects on residents, services, or operations.',
      'National frame': 'Centers national politics, institutions, or broad domestic effects.',
      'International frame': 'Shows how the story is framed outside the immediate domestic lens.',
    }),
    methodologyNote:
      'Perspective shows what kinds of coverage are present in the linked reporting. It does not decide who is right.',
  }
}
