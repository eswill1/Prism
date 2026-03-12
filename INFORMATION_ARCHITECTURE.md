# Prism Information Architecture
### Version 0.2 — Updated 2026-03-12: homepage as front door, source links direct by default

---

## 1. Problem To Solve

Prism had started drifting into system-centric language:

- `Stories` in primary navigation even though the homepage already was the story list
- `Live` as a top-level surface without a clear distinction from the homepage
- utility pages in primary navigation competing with the actual news product

That structure makes sense to builders. It is weak for normal readers.

The homepage should answer:

- what is happening now
- what matters most
- where do I click next

For a broad reader, the right answer is simple:

- open the homepage
- click a story
- inspect the Prism story page
- open original reporting from inside that story page if needed

---

## 2. What Major News Sites Already Teach

As of March 11, 2026, major outlets still organize around a live homepage plus broad section labels.

### NBC News

Useful pattern:

- homepage as the default current-news front door
- broad familiar section expectations such as world, business, politics, health, and culture-adjacent coverage

Official signals:

- NBC News contact page describes NBCNews.com as the place for top stories in world news, business, politics, health, and pop culture.
- NBC News Digital masthead still separates major editorial functions such as politics, international news, and technology and science.

### CNN

Useful pattern:

- homepage is the main live entry point
- broad section taxonomy helps readers scan by interest and urgency
- live or special coverage sits beside the homepage, not above it

Official signal:

- CNN's fact sheet describes CNN Digital programming across news, business, politics, style, entertainment, climate, weather, science and technology, travel, health, and more.

### BBC

Useful pattern:

- homepage blends biggest stories with editors' picks
- major categories stay broad and recognizable
- `Live` exists as a secondary format, not as a replacement for the homepage

Official signal:

- BBC Help says the homepage mixes the biggest stories with editors' picks, while navigation includes Business, Travel, Culture, Innovation, Earth, Video, and Live.

---

## 3. Prism IA Rules

### Rule 1: Home is the definitive current-news surface

The homepage should feel alive by default.

It is where readers:

- catch up quickly
- scan major stories
- move by section when they want topic-specific browsing

It should not send the user hunting for a second "real" news page.

### Rule 2: The story page is the primary click target

Every homepage card should open a Prism story page for that event.

The story page is where readers get:

- the structured event summary
- comparison coverage
- Perspective
- evidence
- context packs
- change history

Reader movement rule:

- the whole homepage story package should be clickable wherever practical
- original source links should live inside the story page, not on the homepage

### Rule 3: the homepage should absorb the fast-moving view

Prism should not split the reader's attention between two separate front doors.

If story movement matters, it should be visible on the homepage itself through:

- freshness indicators
- a right-rail latest feed
- visible change signals

A separate latest queue may exist as an internal or secondary surface, but it should not be
part of the normal reader path.

### Rule 4: Categories are for wayfinding, not for replacing story-first design

Prism should adopt mainstream-style categories, but use them lightly.

They help readers answer:

- "I want world news"
- "Show me politics"
- "What is happening in business or tech?"

They should not change the core unit of the product.

The core unit remains the story, not the section page.

### Rule 5: Utility pages move out of the primary nav

Methodology, Corrections, and Pricing matter for trust and business.

They do not belong in the main reader task bar ahead of the news itself.

They should live in footer or secondary utility navigation.

### Rule 6: Source links stay direct by default

When Prism presents a source read or alternate read:

- use the original publisher URL if Prism has one
- do not insert a wrapper page unless that wrapper creates clear extra value
- if Prism does not have a real source URL, the UI should not pretend the item is clickable

---

## 4. Prism V1 Navigation Model

### Primary navigation

- logo = Home
- World
- Politics
- Business
- Tech
- Weather

### Secondary / footer navigation

- Saved
- Methodology
- Corrections
- Pricing

---

## 5. Prism V1 Homepage Structure

### 1. Lead story

The biggest or most useful story right now.

### 2. Supporting story columns

A three-column top deck with:

- a lead package on the left
- mixed-size supporting story blocks in the center
- a latest-news feed in the right rail

### 3. Section blocks

Grouped sets of stories under broad newsroom headings.

### 4. Footer trust/utility

Methodology, corrections, pricing.

---

## 6. Launch Section Taxonomy

Prism does not need the full section sprawl of a legacy outlet on day one.

Start with:

- World
- Politics
- Business
- Technology
- Weather

Add later only when the content volume justifies it:

- U.S.
- Health
- Culture
- Sports
- Opinion or analysis products

---

## 7. Implementation Path

### Phase 1

- remove `Stories` from primary nav
- remove `Latest` from the primary reader path
- make the homepage feel like the real live front door
- move methodology, corrections, and pricing into footer utility

### Phase 2

- add section-based homepage grouping
- keep `/live` only as compatibility or internal alias if needed
- continue pushing utility and product explanation out of the main news-reading path

### Phase 3

- add dedicated topic pages when story volume is high enough
- add topic following and briefings by section

---

## 8. External References

- NBC News contact page: https://www.nbcnews.com/information/nbc-news-info/contact-us-n1232521
- NBC News Digital masthead: https://www.nbcnews.com/news/us-news/nbc-news-digital-editors-n893846
- CNN Worldwide Fact Sheet: https://cnnpressroom.blogs.cnn.com/cnn-fact-sheet/
- BBC Help on content types and top navigation: https://help.bbc.com/hc/en-us/articles/39027623773331-What-types-of-news-content-will-be-available
