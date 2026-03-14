import type { User } from '@supabase/supabase-js'

import type { ReaderTrackingMutation, ReaderTrackingState, RemoteTrackedStory } from './reader-tracking-types'
import type { PerspectiveRevisionSnapshot } from './perspective-versioning'
import type { StoryBriefRevisionSnapshot } from './story-brief-versioning'
import {
  getSupabaseServiceRoleClient,
  hasSupabaseServiceRoleConfig,
  type JsonObject,
  type SupabaseServerClient,
} from './supabase/server'
import { buildTrackedStoryHistory } from './tracked-story-history'

type ReaderProfileRow = {
  id: string
  handle: string
  display_name: string
}

type SavedClusterRow = {
  cluster_id: string
  created_at: string
}

type ClusterFollowRow = {
  cluster_id: string
  created_at: string
}

type ClusterReaderStateRow = {
  cluster_id: string
  last_viewed_at: string | null
  last_seen_brief_revision_tag: string | null
  last_seen_perspective_revision_tag: string | null
}

type ClusterSlugRow = {
  id: string
  slug: string
  topic_label?: string | null
  canonical_headline?: string | null
}

type TrackedStoryRow = {
  id: string
  slug: string
  topic_label: string
  canonical_headline: string
  summary: string
  latest_event_at: string
  hero_media_url: string | null
  hero_media_alt: string | null
}

type CorrectionEventRow = {
  cluster_id: string
  display_summary: string
}

type StoryBriefRevisionRow = {
  cluster_id: string
  revision_tag: string
  status: string
  is_current: boolean
  created_at: string
  title: string
  paragraphs: string[] | null
  why_it_matters: string
  where_sources_agree: string
  where_coverage_differs: string
  what_to_watch: string
  supporting_points: string[] | null
  metadata: JsonObject | null
}

type StoryPerspectiveRevisionRow = {
  cluster_id: string
  revision_tag: string
  status: string
  is_current: boolean
  created_at: string
  generation_method: string
  summary: string
  takeaways: string[] | null
  metadata: JsonObject | null
}

export type AuthenticatedReader = {
  authUserId: string
  email: string | null
  profileId: string
  handle: string
  displayName: string
}

export class ReaderAuthError extends Error {
  status: number

  constructor(message: string, status = 400) {
    super(message)
    this.status = status
  }
}

export function sanitizeHandleSeed(value: string | null | undefined) {
  const normalized = (value || '')
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24)

  return normalized.length >= 3 ? normalized : 'reader'
}

export function buildDisplayNameFromEmail(value: string | null | undefined) {
  const localPart = (value || '').split('@')[0] || 'Reader'
  const cleaned = localPart
    .replace(/[._-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 40)

  if (!cleaned) {
    return 'Reader'
  }

  return cleaned
    .split(' ')
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ')
}

export function chooseAvailableHandle(base: string, takenHandles: string[]) {
  const taken = new Set(takenHandles.map((value) => value.toLowerCase()))
  if (!taken.has(base.toLowerCase())) {
    return base
  }

  for (let suffix = 2; suffix < 1000; suffix += 1) {
    const candidate = `${base}-${suffix}`.slice(0, 32)
    if (!taken.has(candidate.toLowerCase())) {
      return candidate
    }
  }

  return `${base}-${Date.now().toString().slice(-6)}`.slice(0, 32)
}

function fallbackClusterImage(slug: string) {
  return `https://picsum.photos/seed/${slug}/1600/900`
}

function formatUpdatedAt(value: string | null | undefined) {
  if (!value) {
    return 'Updated recently'
  }

  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return 'Updated recently'
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000))
  if (diffMinutes < 60) {
    return `Updated ${diffMinutes}m ago`
  }

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `Updated ${diffHours}h ago`
  }

  const diffDays = Math.round(diffHours / 24)
  return `Updated ${diffDays}d ago`
}

function readStringArray(values: string[] | null | undefined) {
  return Array.isArray(values)
    ? values.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    : []
}

function toBriefRevisionSnapshot(
  row: StoryBriefRevisionRow | undefined,
): StoryBriefRevisionSnapshot | undefined {
  if (!row) {
    return undefined
  }

  return {
    revisionTag: row.revision_tag,
    createdAt: row.created_at,
    status: row.status === 'full' ? 'full' : 'early',
    title: row.title,
    paragraphs: readStringArray(row.paragraphs),
    whyItMatters: row.why_it_matters,
    whereSourcesAgree: row.where_sources_agree,
    whereCoverageDiffers: row.where_coverage_differs,
    whatToWatch: row.what_to_watch,
    supportingPoints: readStringArray(row.supporting_points),
    metadata: row.metadata || {},
  }
}

function toPerspectiveRevisionSnapshot(
  row: StoryPerspectiveRevisionRow | undefined,
): PerspectiveRevisionSnapshot | undefined {
  if (!row) {
    return undefined
  }

  return {
    revisionTag: row.revision_tag,
    createdAt: row.created_at,
    generationMethod: row.generation_method,
    status: row.status === 'ready' ? 'ready' : 'early',
    summary: row.summary,
    takeaways: readStringArray(row.takeaways),
    metadata: row.metadata || {},
  }
}

function groupRowsByCluster<T extends { cluster_id: string }>(rows: T[]) {
  const grouped = new Map<string, T[]>()

  for (const row of rows) {
    grouped.set(row.cluster_id, [...(grouped.get(row.cluster_id) ?? []), row])
  }

  return grouped
}

function currentRevisionRow<T extends { is_current: boolean }>(rows: T[]) {
  return rows.find((row) => row.is_current) ?? rows[0]
}

function previousRevisionRow<T extends { revision_tag: string; is_current: boolean }>(rows: T[]) {
  const current = currentRevisionRow(rows)
  if (!current) {
    return undefined
  }

  return rows.find((row) => row.revision_tag !== current.revision_tag)
}

function revisionRowByTag<T extends { revision_tag: string }>(rows: T[], revisionTag?: string) {
  if (!revisionTag) {
    return undefined
  }

  return rows.find((row) => row.revision_tag === revisionTag)
}

function ensureServiceClient() {
  const client = getSupabaseServiceRoleClient()
  if (!client || !hasSupabaseServiceRoleConfig()) {
    throw new ReaderAuthError('Reader sync is not configured on this environment yet.', 503)
  }

  return client
}

export function requireReaderServiceClient() {
  return ensureServiceClient()
}

function parseBearerToken(request: Request) {
  const authorization = request.headers.get('authorization') || request.headers.get('Authorization')
  if (!authorization) {
    throw new ReaderAuthError('Sign in to sync saved stories across devices.', 401)
  }

  const match = authorization.match(/^Bearer\s+(.+)$/i)
  if (!match) {
    throw new ReaderAuthError('Invalid reader session token.', 401)
  }

  return match[1]
}

async function loadExistingProfile(client: SupabaseServerClient, authUserId: string) {
  const { data, error } = await client
    .from('user_profiles')
    .select('id, handle, display_name')
    .eq('auth_user_id', authUserId)
    .maybeSingle<ReaderProfileRow>()

  if (error) {
    throw new ReaderAuthError(`Unable to load reader profile: ${error.message}`, 500)
  }

  return data
}

async function createReaderProfile(client: SupabaseServerClient, user: User) {
  const email = user.email || null
  const baseHandle = sanitizeHandleSeed(email ? email.split('@')[0] : user.id)
  const displayName = buildDisplayNameFromEmail(email)

  const { data: takenHandles, error: takenError } = await client
    .from('user_profiles')
    .select('handle')
    .ilike('handle', `${baseHandle}%`)

  if (takenError) {
    throw new ReaderAuthError(`Unable to reserve a reader handle: ${takenError.message}`, 500)
  }

  const handle = chooseAvailableHandle(
    baseHandle,
    ((takenHandles as Array<{ handle: string }> | null) ?? []).map((row) => row.handle),
  )

  const { data, error } = await client
    .from('user_profiles')
    .insert({
      auth_user_id: user.id,
      handle,
      display_name: displayName,
    })
    .select('id, handle, display_name')
    .single<ReaderProfileRow>()

  if (!error) {
    return data
  }

  const existing = await loadExistingProfile(client, user.id)
  if (existing) {
    return existing
  }

  throw new ReaderAuthError(`Unable to create reader profile: ${error.message}`, 500)
}

async function ensureReaderProfile(client: SupabaseServerClient, user: User) {
  const existing = await loadExistingProfile(client, user.id)
  if (existing) {
    return existing
  }

  return createReaderProfile(client, user)
}

async function resolveClusterId(
  client: SupabaseServerClient,
  clusterId: string | undefined,
  slug: string,
) {
  if (clusterId) {
    return clusterId
  }

  const { data, error } = await client
    .from('story_clusters')
    .select('id')
    .eq('slug', slug)
    .maybeSingle<{ id: string }>()

  if (error) {
    throw new ReaderAuthError(`Unable to resolve story cluster: ${error.message}`, 500)
  }

  if (!data?.id) {
    throw new ReaderAuthError('That story is not available for synced tracking yet.', 404)
  }

  return data.id
}

async function loadClusterContext(
  client: SupabaseServerClient,
  clusterIds: string[],
): Promise<Record<string, ClusterSlugRow>> {
  if (clusterIds.length === 0) {
    return {}
  }

  const { data, error } = await client
    .from('story_clusters')
    .select('id, slug, topic_label, canonical_headline')
    .in('id', clusterIds)

  if (error) {
    throw new ReaderAuthError(`Unable to load tracked stories: ${error.message}`, 500)
  }

  return Object.fromEntries(
    ((data as ClusterSlugRow[] | null) ?? []).map((row) => [row.id, row]),
  )
}

async function loadClusterContextBySlug(
  client: SupabaseServerClient,
  slugs: string[],
): Promise<Record<string, ClusterSlugRow>> {
  if (slugs.length === 0) {
    return {}
  }

  const { data, error } = await client
    .from('story_clusters')
    .select('id, slug, topic_label, canonical_headline')
    .in('slug', slugs)

  if (error) {
    throw new ReaderAuthError(`Unable to load tracked stories: ${error.message}`, 500)
  }

  return Object.fromEntries(
    ((data as ClusterSlugRow[] | null) ?? []).map((row) => [row.slug, row]),
  )
}

async function loadTrackingRows(
  client: SupabaseServerClient,
  profileId: string,
  clusterIds: string[],
) {
  const uniqueIds = Array.from(new Set(clusterIds.filter(Boolean)))
  if (uniqueIds.length === 0) {
    return {
      clusterContext: {} as Record<string, ClusterSlugRow>,
      savedRows: [] as SavedClusterRow[],
      followRows: [] as ClusterFollowRow[],
      readerStateRows: [] as ClusterReaderStateRow[],
    }
  }

  const [{ data: savedRows, error: savedError }, { data: followRows, error: followError }, { data: readerStateRows, error: readerStateError }, clusterContext] =
    await Promise.all([
      client
        .from('saved_clusters')
        .select('cluster_id, created_at')
        .eq('user_id', profileId)
        .in('cluster_id', uniqueIds),
      client
        .from('cluster_follows')
        .select('cluster_id, created_at')
        .eq('user_id', profileId)
        .in('cluster_id', uniqueIds),
      client
        .from('cluster_reader_state')
        .select('cluster_id, last_viewed_at, last_seen_brief_revision_tag, last_seen_perspective_revision_tag')
        .eq('user_id', profileId)
        .in('cluster_id', uniqueIds),
      loadClusterContext(client, uniqueIds),
    ])

  if (savedError) {
    throw new ReaderAuthError(`Unable to load saved stories: ${savedError.message}`, 500)
  }
  if (followError) {
    throw new ReaderAuthError(`Unable to load followed stories: ${followError.message}`, 500)
  }
  if (readerStateError) {
    throw new ReaderAuthError(`Unable to load reader history state: ${readerStateError.message}`, 500)
  }

  return {
    clusterContext,
    savedRows: (savedRows as SavedClusterRow[] | null) ?? [],
    followRows: (followRows as ClusterFollowRow[] | null) ?? [],
    readerStateRows: (readerStateRows as ClusterReaderStateRow[] | null) ?? [],
  }
}

function buildTrackingStateMap(
  clusterContext: Record<string, ClusterSlugRow>,
  savedRows: SavedClusterRow[],
  followRows: ClusterFollowRow[],
  readerStateRows: ClusterReaderStateRow[],
): Record<string, ReaderTrackingState> {
  const stateMap: Record<string, ReaderTrackingState> = {}

  for (const [clusterId, row] of Object.entries(clusterContext)) {
    stateMap[clusterId] = {
      clusterId,
      slug: row.slug,
      title: row.canonical_headline || undefined,
      topic: row.topic_label || undefined,
      saved: false,
      followed: false,
    }
  }

  for (const row of savedRows) {
    const existing = stateMap[row.cluster_id]
    if (!existing) {
      continue
    }
    existing.saved = true
    existing.savedAt = row.created_at
  }

  for (const row of followRows) {
    const existing = stateMap[row.cluster_id]
    if (!existing) {
      continue
    }
    existing.followed = true
    existing.followedAt = row.created_at
  }

  for (const row of readerStateRows) {
    const existing = stateMap[row.cluster_id]
    if (!existing) {
      continue
    }
    existing.lastViewedAt = row.last_viewed_at || undefined
    existing.lastSeenBriefRevisionTag = row.last_seen_brief_revision_tag || undefined
    existing.lastSeenPerspectiveRevisionTag = row.last_seen_perspective_revision_tag || undefined
  }

  return stateMap
}

async function upsertReaderState(
  client: SupabaseServerClient,
  profileId: string,
  clusterId: string,
  mutation: ReaderTrackingMutation,
) {
  const shouldWrite =
    mutation.markViewed ||
    mutation.lastSeenBriefRevisionTag !== undefined ||
    mutation.lastSeenPerspectiveRevisionTag !== undefined

  if (!shouldWrite) {
    return
  }

  const { data: existing, error: existingError } = await client
    .from('cluster_reader_state')
    .select('last_viewed_at, last_seen_brief_revision_tag, last_seen_perspective_revision_tag')
    .eq('user_id', profileId)
    .eq('cluster_id', clusterId)
    .maybeSingle<ClusterReaderStateRow>()

  if (existingError) {
    throw new ReaderAuthError(`Unable to load reader state: ${existingError.message}`, 500)
  }

  const { error } = await client.from('cluster_reader_state').upsert(
    {
      user_id: profileId,
      cluster_id: clusterId,
      last_viewed_at: mutation.markViewed
        ? new Date().toISOString()
        : existing?.last_viewed_at ?? null,
      last_seen_brief_revision_tag:
        mutation.lastSeenBriefRevisionTag ?? existing?.last_seen_brief_revision_tag ?? null,
      last_seen_perspective_revision_tag:
        mutation.lastSeenPerspectiveRevisionTag ??
        existing?.last_seen_perspective_revision_tag ??
        null,
    },
    {
      onConflict: 'user_id,cluster_id',
    },
  )

  if (error) {
    throw new ReaderAuthError(`Unable to update reader history state: ${error.message}`, 500)
  }
}

async function setSavedState(
  client: SupabaseServerClient,
  profileId: string,
  clusterId: string,
  saved: boolean,
) {
  if (saved) {
    const { error } = await client
      .from('saved_clusters')
      .upsert({ user_id: profileId, cluster_id: clusterId }, { onConflict: 'user_id,cluster_id' })
    if (error) {
      throw new ReaderAuthError(`Unable to save story: ${error.message}`, 500)
    }
    return
  }

  const { error } = await client
    .from('saved_clusters')
    .delete()
    .eq('user_id', profileId)
    .eq('cluster_id', clusterId)

  if (error) {
    throw new ReaderAuthError(`Unable to unsave story: ${error.message}`, 500)
  }
}

async function setFollowedState(
  client: SupabaseServerClient,
  profileId: string,
  clusterId: string,
  followed: boolean,
) {
  if (followed) {
    const { error } = await client
      .from('cluster_follows')
      .upsert({ user_id: profileId, cluster_id: clusterId }, { onConflict: 'user_id,cluster_id' })
    if (error) {
      throw new ReaderAuthError(`Unable to follow story: ${error.message}`, 500)
    }
    return
  }

  const { error } = await client
    .from('cluster_follows')
    .delete()
    .eq('user_id', profileId)
    .eq('cluster_id', clusterId)

  if (error) {
    throw new ReaderAuthError(`Unable to unfollow story: ${error.message}`, 500)
  }
}

async function importSavedState(
  client: SupabaseServerClient,
  profileId: string,
  clusterId: string,
  savedAt?: string,
) {
  const { error } = await client.from('saved_clusters').upsert(
    {
      user_id: profileId,
      cluster_id: clusterId,
      created_at: savedAt || new Date().toISOString(),
    },
    {
      onConflict: 'user_id,cluster_id',
      ignoreDuplicates: true,
    },
  )

  if (error) {
    throw new ReaderAuthError(`Unable to import saved story: ${error.message}`, 500)
  }
}

async function importFollowedState(
  client: SupabaseServerClient,
  profileId: string,
  clusterId: string,
  followedAt?: string,
) {
  const { error } = await client.from('cluster_follows').upsert(
    {
      user_id: profileId,
      cluster_id: clusterId,
      created_at: followedAt || new Date().toISOString(),
    },
    {
      onConflict: 'user_id,cluster_id',
      ignoreDuplicates: true,
    },
  )

  if (error) {
    throw new ReaderAuthError(`Unable to import followed story: ${error.message}`, 500)
  }
}

export async function requireAuthenticatedReader(request: Request) {
  const client = ensureServiceClient()
  const accessToken = parseBearerToken(request)
  const { data, error } = await client.auth.getUser(accessToken)

  if (error || !data.user) {
    throw new ReaderAuthError('Your reader session expired. Sign in again to sync.', 401)
  }

  const profile = await ensureReaderProfile(client, data.user)

  return {
    client,
    reader: {
      authUserId: data.user.id,
      email: data.user.email || null,
      profileId: profile.id,
      handle: profile.handle,
      displayName: profile.display_name,
    } satisfies AuthenticatedReader,
  }
}

export async function loadReaderTrackingState(
  client: SupabaseServerClient,
  profileId: string,
  clusterIds: string[],
) {
  const rows = await loadTrackingRows(client, profileId, clusterIds)
  return buildTrackingStateMap(
    rows.clusterContext,
    rows.savedRows,
    rows.followRows,
    rows.readerStateRows,
  )
}

export async function applyReaderTrackingMutation(
  client: SupabaseServerClient,
  profileId: string,
  mutation: ReaderTrackingMutation,
) {
  const clusterId = await resolveClusterId(client, mutation.clusterId, mutation.slug)

  if (mutation.saved !== undefined) {
    await setSavedState(client, profileId, clusterId, mutation.saved)
  }
  if (mutation.followed !== undefined) {
    await setFollowedState(client, profileId, clusterId, mutation.followed)
  }

  await upsertReaderState(client, profileId, clusterId, mutation)

  const stateMap = await loadReaderTrackingState(client, profileId, [clusterId])
  const state = stateMap[clusterId]

  if (!state) {
    throw new ReaderAuthError('Unable to load synced reader state after saving.', 500)
  }

  return state
}

export async function importReaderTrackingRecords(
  client: SupabaseServerClient,
  profileId: string,
  records: ReaderTrackingState[],
) {
  for (const record of records) {
    if (!record.slug || (!record.saved && !record.followed && !record.lastViewedAt)) {
      continue
    }

    const clusterId = await resolveClusterId(client, record.clusterId, record.slug)

    if (record.saved) {
      await importSavedState(client, profileId, clusterId, record.savedAt)
    }
    if (record.followed) {
      await importFollowedState(client, profileId, clusterId, record.followedAt)
    }

    const { data: existing, error: existingError } = await client
      .from('cluster_reader_state')
      .select('last_viewed_at, last_seen_brief_revision_tag, last_seen_perspective_revision_tag')
      .eq('user_id', profileId)
      .eq('cluster_id', clusterId)
      .maybeSingle<ClusterReaderStateRow>()

    if (existingError) {
      throw new ReaderAuthError(`Unable to import reader history state: ${existingError.message}`, 500)
    }

    const nextViewedAt =
      existing?.last_viewed_at && record.lastViewedAt
        ? existing.last_viewed_at > record.lastViewedAt
          ? existing.last_viewed_at
          : record.lastViewedAt
        : existing?.last_viewed_at || record.lastViewedAt || null

    if (!nextViewedAt && !record.lastSeenBriefRevisionTag && !record.lastSeenPerspectiveRevisionTag) {
      continue
    }

    const { error } = await client.from('cluster_reader_state').upsert(
      {
        user_id: profileId,
        cluster_id: clusterId,
        last_viewed_at: nextViewedAt,
        last_seen_brief_revision_tag:
          existing?.last_seen_brief_revision_tag || record.lastSeenBriefRevisionTag || null,
        last_seen_perspective_revision_tag:
          existing?.last_seen_perspective_revision_tag ||
          record.lastSeenPerspectiveRevisionTag ||
          null,
      },
      {
        onConflict: 'user_id,cluster_id',
      },
    )

    if (error) {
      throw new ReaderAuthError(`Unable to import reader state: ${error.message}`, 500)
    }
  }
}

async function resolvePreviewTrackingState(
  client: SupabaseServerClient,
  records: ReaderTrackingState[],
) {
  const filteredRecords = records.filter(
    (record) => record.slug && (record.saved || record.followed || record.lastViewedAt),
  )
  if (filteredRecords.length === 0) {
    return {} as Record<string, ReaderTrackingState>
  }

  const [clusterContextById, clusterContextBySlug] = await Promise.all([
    loadClusterContext(
      client,
      Array.from(
        new Set(filteredRecords.map((record) => record.clusterId).filter((value): value is string => Boolean(value))),
      ),
    ),
    loadClusterContextBySlug(
      client,
      Array.from(
        new Set(
          filteredRecords
            .filter((record) => !record.clusterId)
            .map((record) => record.slug)
            .filter(Boolean),
        ),
      ),
    ),
  ])

  const trackingState: Record<string, ReaderTrackingState> = {}

  for (const record of filteredRecords) {
    const cluster =
      (record.clusterId ? clusterContextById[record.clusterId] : undefined) ||
      clusterContextBySlug[record.slug]
    if (!cluster) {
      continue
    }

    trackingState[cluster.id] = {
      clusterId: cluster.id,
      slug: cluster.slug,
      title: record.title || cluster.canonical_headline || undefined,
      topic: record.topic || cluster.topic_label || undefined,
      saved: record.saved,
      followed: record.followed,
      savedAt: record.savedAt,
      followedAt: record.followedAt,
      lastViewedAt: record.lastViewedAt,
      lastSeenBriefRevisionTag: record.lastSeenBriefRevisionTag,
      lastSeenPerspectiveRevisionTag: record.lastSeenPerspectiveRevisionTag,
    }
  }

  return trackingState
}

async function buildTrackedStoriesFromState(
  client: SupabaseServerClient,
  trackingState: Record<string, ReaderTrackingState>,
) {
  const clusterIds = Array.from(
    new Set(
      Object.entries(trackingState)
        .filter(([, state]) => state.saved || state.followed)
        .map(([clusterId]) => clusterId)
        .filter(Boolean),
    ),
  )

  if (clusterIds.length === 0) {
    return [] as RemoteTrackedStory[]
  }

  const [
    { data: stories, error: storiesError },
    { data: corrections, error: correctionsError },
    { data: briefRevisions, error: briefRevisionsError },
    { data: perspectiveRevisions, error: perspectiveRevisionsError },
  ] = await Promise.all([
    client
      .from('story_clusters')
      .select(
        'id, slug, topic_label, canonical_headline, summary, latest_event_at, hero_media_url, hero_media_alt',
      )
      .in('id', clusterIds),
    client
      .from('correction_events')
      .select('cluster_id, display_summary')
      .in('cluster_id', clusterIds)
      .order('created_at', { ascending: false }),
    client
      .from('story_brief_revisions')
      .select(
        'cluster_id, revision_tag, status, is_current, created_at, title, paragraphs, why_it_matters, where_sources_agree, where_coverage_differs, what_to_watch, supporting_points, metadata',
      )
      .in('cluster_id', clusterIds)
      .order('created_at', { ascending: false }),
    client
      .from('story_perspective_revisions')
      .select(
        'cluster_id, revision_tag, status, is_current, created_at, generation_method, summary, takeaways, metadata',
      )
      .in('cluster_id', clusterIds)
      .order('created_at', { ascending: false }),
  ])

  if (storiesError) {
    throw new ReaderAuthError(`Unable to load tracked story details: ${storiesError.message}`, 500)
  }
  if (correctionsError) {
    throw new ReaderAuthError(`Unable to load tracked story change history: ${correctionsError.message}`, 500)
  }
  if (briefRevisionsError) {
    throw new ReaderAuthError(`Unable to load tracked story briefs: ${briefRevisionsError.message}`, 500)
  }
  if (perspectiveRevisionsError) {
    throw new ReaderAuthError(`Unable to load tracked story Perspective history: ${perspectiveRevisionsError.message}`, 500)
  }

  const correctionMap = groupRowsByCluster((corrections as CorrectionEventRow[] | null) ?? [])
  const briefRevisionMap = groupRowsByCluster(
    (briefRevisions as StoryBriefRevisionRow[] | null) ?? [],
  )
  const perspectiveRevisionMap = groupRowsByCluster(
    (perspectiveRevisions as StoryPerspectiveRevisionRow[] | null) ?? [],
  )

  return ((stories as TrackedStoryRow[] | null) ?? [])
    .flatMap((story) => {
      const storyTracking = trackingState[story.id]
      if (!storyTracking || (!storyTracking.saved && !storyTracking.followed)) {
        return []
      }

      const storyCorrections = correctionMap.get(story.id) ?? []
      const storyBriefRows = briefRevisionMap.get(story.id) ?? []
      const storyPerspectiveRows = perspectiveRevisionMap.get(story.id) ?? []
      const currentBriefRow = currentRevisionRow(storyBriefRows)
      const currentPerspectiveRow = currentRevisionRow(storyPerspectiveRows)
      const history = buildTrackedStoryHistory({
        currentBrief: toBriefRevisionSnapshot(currentBriefRow),
        seenBrief: toBriefRevisionSnapshot(
          revisionRowByTag(storyBriefRows, storyTracking.lastSeenBriefRevisionTag),
        ),
        previousBrief: toBriefRevisionSnapshot(previousRevisionRow(storyBriefRows)),
        lastSeenBriefRevisionTag: storyTracking.lastSeenBriefRevisionTag,
        currentPerspective: toPerspectiveRevisionSnapshot(currentPerspectiveRow),
        seenPerspective: toPerspectiveRevisionSnapshot(
          revisionRowByTag(
            storyPerspectiveRows,
            storyTracking.lastSeenPerspectiveRevisionTag,
          ),
        ),
        previousPerspective: toPerspectiveRevisionSnapshot(
          previousRevisionRow(storyPerspectiveRows),
        ),
        lastSeenPerspectiveRevisionTag: storyTracking.lastSeenPerspectiveRevisionTag,
      })

      return [
        {
          clusterId: story.id,
          slug: story.slug,
          topic: story.topic_label,
          title: story.canonical_headline,
          dek: story.summary || 'No summary available yet.',
          updatedAt: formatUpdatedAt(story.latest_event_at),
          heroImage: story.hero_media_url || fallbackClusterImage(story.slug),
          heroAlt:
            story.hero_media_alt || `Editorial image for the ${story.canonical_headline} story.`,
          latestChange: storyCorrections[0]?.display_summary,
          changeCount: storyCorrections.length,
          tracking: storyTracking,
          history,
        } satisfies RemoteTrackedStory,
      ]
    })
    .sort((left, right) => {
      const leftTimestamp =
        left.tracking.followedAt || left.tracking.savedAt || left.tracking.lastViewedAt || ''
      const rightTimestamp =
        right.tracking.followedAt || right.tracking.savedAt || right.tracking.lastViewedAt || ''

      return rightTimestamp.localeCompare(leftTimestamp)
    })
}

export async function listTrackedStories(client: SupabaseServerClient, profileId: string) {
  const { data: savedRows, error: savedError } = await client
    .from('saved_clusters')
    .select('cluster_id, created_at')
    .eq('user_id', profileId)

  if (savedError) {
    throw new ReaderAuthError(`Unable to load saved stories: ${savedError.message}`, 500)
  }

  const { data: followRows, error: followError } = await client
    .from('cluster_follows')
    .select('cluster_id, created_at')
    .eq('user_id', profileId)

  if (followError) {
    throw new ReaderAuthError(`Unable to load followed stories: ${followError.message}`, 500)
  }

  const clusterIds = Array.from(
    new Set(
      [
        ...(((savedRows as SavedClusterRow[] | null) ?? []).map((row) => row.cluster_id)),
        ...(((followRows as ClusterFollowRow[] | null) ?? []).map((row) => row.cluster_id)),
      ].filter(Boolean),
    ),
  )

  if (clusterIds.length === 0) {
    return [] as RemoteTrackedStory[]
  }

  const trackingState = await loadReaderTrackingState(client, profileId, clusterIds)
  return buildTrackedStoriesFromState(client, trackingState)
}

export async function listTrackedStoriesPreview(
  client: SupabaseServerClient,
  records: ReaderTrackingState[],
) {
  const trackingState = await resolvePreviewTrackingState(client, records)
  return buildTrackedStoriesFromState(client, trackingState)
}
