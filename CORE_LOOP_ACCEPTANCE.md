# Prism Core Loop Acceptance
### Local Prototype Checklist

This checklist is for the local, pre-Supabase Prism prototype.

The loop being tested is:

1. open a story
2. get oriented quickly
3. inspect another angle, evidence item, or correction note
4. save or follow the story
5. return to a working set and see whether Prism feels useful enough to come back to

---

## Preconditions

- local web app is running
- homepage and story routes render
- browser local storage is available

---

## Checklist

- [ ] Open the homepage and identify a story worth opening within 10 seconds.
- [ ] Open a story page and explain the main event in one or two sentences.
- [ ] Read the Prism Brief and confirm the story itself is understandable before inspecting source comparison.
- [ ] Use the Perspective panel and source stack without confusion.
- [ ] Open at least one source read and one alternate read from the story page and confirm the linking behavior is clear.
- [ ] Open Methodology from the story surface and confirm the explanation feels product-grade.
- [ ] Open Corrections log from the story surface and confirm the correction model feels visible.
- [ ] Save the story and verify the UI confirms browser-local tracking state.
- [ ] Follow updates and verify the UI confirms browser-local follow state.
- [ ] Open the Saved page and confirm the tracked story appears with update context.
- [ ] Refresh the browser and confirm saved/followed state persists locally.
- [ ] Open Pricing and confirm the subscription model feels aligned with the product thesis.

---

## Pass Criteria

The local prototype passes if:

- a first-time reader can explain what Prism is after one story session
- the story page feels like the hero surface
- the story page feels story-first rather than comparison-first
- save/follow behavior is understandable without account infrastructure
- methodology and corrections feel central, not buried
- the product leaves the tester feeling more oriented, not more stimulated

---

## Known Limits

- saved/follow stays browser-local until a reader opts into sync
- synced save/follow requires optional account sign-in
- no real notifications yet
- story data may still come from mocks or temporary live snapshots
