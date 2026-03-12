# Prism UI/UX Direction
### Version 0.2 — Updated 2026-03-12: newsroom-style homepage and article-first story surface

---

## Design Position

Prism should not clone a newspaper homepage blindly, and it should not look like a generic SaaS dashboard.

It needs a hybrid identity:

- the authority of an editorial product
- the inspectability of a research tool
- the finish and ease of a premium consumer app

The right direction for Prism is:

> **Editorial Instrument Panel**

The product should feel like a calm briefing desk built for serious readers, not a feed built for stimulation.

It should also respect the mainstream reader mental model:

- the homepage is where the news lives
- broad section labels help readers scan
- the story page is where depth happens
- any faster-moving queue is secondary or internal, not the primary front door

The design should actively support Prism's core loop:

- orient quickly
- inspect structure
- save or follow what matters
- return to "what changed"

---

## What The Market Already Gets Right

### Financial Times

Useful lessons:

- strong information hierarchy
- dense but readable sectioning
- premium tone without decorative excess

What to borrow:

- disciplined layout hierarchy
- confidence in density
- obvious "this is worth paying for" seriousness

What not to copy:

- old-newspaper sprawl
- too much equal-weight homepage clutter

### Semafor

Useful lessons:

- transparent content structure
- modular story packaging
- explicit signals about how content is framed

What to borrow:

- visible structure as part of the product
- distinct modules that help the reader compare

What not to copy:

- newsletter-like fragmentation as the dominant interface

### Apple News

Useful lessons:

- premium motion restraint
- high polish on spacing and typography
- consumer-grade ease around subscriptions and reading

What to borrow:

- tactile, calm transitions
- polished card surfaces and reading comfort

What not to copy:

- overly soft, generic card stacks that hide information scent

### The Information

Useful lessons:

- high-trust professional minimalism
- premium membership feel
- strong signal that the product is for serious readers

What to borrow:

- sharp restraint
- uncluttered premium surfaces
- membership-first confidence

What not to copy:

- overly austere presentation that underplays Prism's differentiating structure

---

## The Prism Direction

### 1. Make the product feel like a briefing desk

The first impression should be:

- structured
- composed
- expensive in the right way
- easier to think in than the rest of the news internet

This means:

- broad editorial margins
- strong typographic contrast
- clear ruled divisions
- visible data panels
- restrained but confident accent color

### 2. Make the story page feel like a story-first workstation

Prism's signature surface should be an article-first layout on desktop:

- **Main story column**: event header, Prism Brief, source reads, alternate reads
- **Inspector rail**: Perspective, evidence ledger, methodology, corrections

This is the core differentiator. The user should feel they are inspecting a live story structure, not reading a prettier feed.

It should also be obvious where the user goes next:

- inspect another angle
- check evidence
- save the story
- follow updates

### 3. Use modern polish, not trend-chasing gloss

Prism should feel current because it is precise, not because it chases dribbble fashion.

Use:

- soft layered depth
- quiet translucency on utility panels
- crisp rule lines
- elegant hover states
- subtle section-reveal motion

Avoid:

- neon gradients
- excessive blur
- loud floating dashboards
- whimsical illustration systems

### 4. Treat transparency as a first-class visual object

Perspective, evidence, and correction surfaces should be visually prominent enough to feel central, but never loud enough to feel ideological.

The opening Perspective summary should read like a note or annotation, not like another giant story headline.

Prism's visual signature should come from:

- dot-group coverage displays
- evidence ledger rows
- change logs
- version tags
- labeled Context Packs

These are product assets, not footnotes.

---

## Proposed Surface Architecture

### Home

The homepage should behave more like BBC, CNN, and NBC News than an internal tool screen:

- it is the main live/current surface
- it has broad section wayfinding
- it uses a three-column editorial top deck
- it does not require the reader to discover another page to see the real news product

The global frame should also feel like a real national news product:

- a tight utility strap
- a centered masthead with a distinct Prism mark
- a section nav bar that reads like a newsroom, not an app tab strip

The home page should read like a finite daily briefing.

Recommended zones:

1. Lead story package in the left column
2. Mixed-size supporting story blocks in the center column
3. A right-rail latest-news feed with timestamps
4. Section-led story blocks below the fold
5. Methodology and corrections access in the global frame, not the body of the front page

The home page should not try to do everything. Its job is to get the reader into the right story fast enough for the core loop to begin. Story packages should feel clickable and immediate, not like static promo units.

### Story Detail

This is the hero surface and should receive the most design energy.

Desktop:

- wide article column on the left
- sticky Perspective / inspection rail on the right

Mobile:

- top summary block
- Perspective and evidence in collapsible or stacked inspector modules

### Saved View

Saved should feel like a working notebook, not a bookmark dump.

- story cards grouped by topic or urgency
- visible "updated since saved" markers
- direct access to correction notes

---

## Visual System Recommendation

### Palette

Keep the existing Prism palette direction, but use it with more force:

- bone-paper base
- near-black ink
- oxidized teal for inspectable actions
- brass for premium emphasis
- rusted wire for corrections and caution

The product should feel warmer and more grounded than blue-white tech news sites.

### Typography

Use editorial contrast aggressively:

- serif for large headlines and story titles
- sans for everything interactive
- mono for methodology, versions, and ledger metadata

### Shapes

- large-radius panels for major surfaces
- squared internal tables and ledger rows
- pill labels only where they carry real meaning

This mix helps the product feel both refined and operational.

---

## Interaction Rules

### Motion

- panel reveals should slide and fade, not pop
- coverage dots may animate in on load, but only once
- sticky rails should feel stable, not jumpy

### Hover and focus

- every inspectable element needs a clear hover state
- links should feel exact, not glossy
- focus rings should be visible and elegant

### Mobile priorities

- story summary always reachable within one thumb move
- Perspective panel opens quickly and closes cleanly
- evidence items should be easy to skim without losing place

---

## Anti-Patterns

- cloning the FT homepage directly
- leaning into generic glassmorphism
- turning framing into colorful ideology charts
- making every surface look like a card feed
- hiding the methodology under tertiary navigation

---

## Recommendation

Prism should be built as a **premium editorial workstation**.

If Harbor is a harbor, Prism should be a desk lamp, ledger, and wire service terminal combined: warm, serious, modern, and precise.

That is the right visual territory for a product asking users to trust the interface without surrendering their judgment to it.
