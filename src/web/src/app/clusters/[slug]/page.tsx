import { StoryPage } from '../../../components/story-page'

export default async function ClusterPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  return <StoryPage slug={slug} />
}
