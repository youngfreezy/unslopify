# unslopify rule catalog

<!-- unslopify:disable=repeated-ngram : a catalog repeats its own severity labels; that is structure, not prose stamps -->

Generated from `src/unslopify/rubric.py` by `scripts/rules_md.py`; edit the rubric, not this file. Every definition and example is original to this project. Hard rules fail an audit on one hit. Soft rules fail past a threshold that scales with document length. Rules marked judgment have no regex and belong to the agent pass.

## Formula and manufactured rhythm

### `inflated-contrast` (hard)

A plain statement dressed up as a reveal by denying a smaller version of itself first.

Before: "This is not just a to-do list. It is a commitment engine."

After: "The app tracks tasks and nags you until each one is done."

### `negative-parallelism` (hard)

The not-X-but-Y frame used as a rhythm device rather than a real correction.

Before: "The launch was not a finish line, but a starting gun."

After: "The launch shipped the core flow. Billing and admin tools are still open."

### `slogan-fragment` (soft, threshold 2 per 1,000 words)

A clipped tagline standing in for analysis, often a verbless fragment or drumbeat sentence pair.

Before: "One codebase. Zero excuses. Ship it."

After: "Merging the two apps into one codebase removes the duplicate release work."

### `stock-triad` (soft, threshold 2 per 1,000 words)

Three parallel adjectives or clauses deployed for cadence when one precise word would do.

Before: "The new editor is faster, cleaner, and more delightful."

After: "The new editor opens files in under 200 ms."

### `staged-punctuation` (judgment)

Colons, semicolons, or dashes stacked to fake momentum instead of marking a real relationship.

Before: "The verdict is in: budgets are tight; deadlines are tighter; something has to give."

After: "The budget covers two of the three features, so one has to wait for next quarter."

### `canned-empathy` (hard)

A sympathy phrase that could be pasted under any complaint without reading it.

Before: "I completely understand how challenging this must be for you."

After: "A double charge is a real problem. The refund went out this morning."

### `synthetic-balance` (hard)

A both-sides sentence with no actual tradeoff behind it.

Before: "While automation brings efficiency, it also introduces unique challenges."

After: "Automation cut ticket volume 40 percent but broke the two workflows that need a human sign-off."

### `fake-authority` (hard)

An appeal to unnamed experts or unspecified research standing in for a source.

Before: "Experts agree that this approach yields better outcomes."

After: "The 2025 DORA report links trunk-based development to shorter recovery times."

### `canned-conclusion` (hard)

A wrap-up about challenges, legacy, or the future that no part of the text earned.

Before: "Ultimately, only time will tell what the future holds for the project."

After: "The migration finishes in March. The old API shuts off in June."

### `ai-vocab` (soft, threshold 2 per 1,000 words)

Words that plain writing rarely needs but generated text reaches for constantly.

Before: "The team will delve into the intricate landscape of vendor contracts."

After: "The team will read the vendor contracts and list the renewal dates."

### `significance-inflation` (hard)

An ordinary fact promoted into a milestone, turning point, or statement about broader trends.

Before: "The office move marks a defining chapter in the company's story."

After: "The company moved to a smaller office in Frisco to cut rent by half."

### `promo-tone` (soft, threshold 2 per 1,000 words)

Brochure adjectives and travel-guide praise nobody asked for.

Before: "Guests can savor world-class cuisine in the heart of a bustling downtown."

After: "The hotel restaurant serves Gulf seafood and stays open until midnight."

## Vague or unsupported substance

### `empty-abstraction` (hard)

A claim built from value-words with no observable change underneath.

Before: "The initiative drives alignment and unlocks meaningful impact across teams."

After: "Support and sales now share one ticket queue, so handoffs stopped losing customer context."

### `tacked-on-benefit` (hard)

An -ing clause bolted to a sentence to assert a benefit the text never demonstrates.

Before: "The dashboard consolidates metrics, ensuring better decision-making at every level."

After: "The dashboard shows all four regions on one page, so the Monday review no longer needs five tabs."

### `process-not-reason` (hard)

The meetings that happened offered in place of the reason a decision was made.

Before: "After extensive stakeholder consultation, we have decided to sunset the feature."

After: "Fewer than 2 percent of accounts used the feature, so we are removing it to simplify billing."

### `unsupported-claim` (soft, threshold 2 per 1,000 words)

A significance or improvement claim with no number, source, or observable result attached.

Before: "This change dramatically improves performance across the board."

After: "Page load dropped from 3.1 s to 0.9 s on the checkout flow."

### `meaning-loss` (judgment)

A sentence compressed or abstracted until the specific point can no longer be recovered.

Before: "The proposal addresses where to draw the line."

After: "The proposal caps overnight shipping subsidies at 4 percent of order value."

## Wordy, indirect, or jargon-heavy wording

### `bureaucratic-phrasing` (soft, threshold 2 per 1,000 words)

Office-memo constructions where a person doing a thing hides behind nouns.

Before: "Stakeholders should be apprised of the operational implications of this transition."

After: "Tell the support team the phone tree changes on Monday."

### `hedge-stack` (soft, threshold 2 per 1,000 words)

Multiple uncertainty markers piled on one claim until it says nothing.

Before: "It may potentially be worth considering whether a delay could possibly help."

After: "Delaying two weeks lets QA finish the payment tests. I recommend it."

### `unexplained-jargon` (soft, threshold 2 per 1,000 words)

Insider or invented terminology dropped on a reader who was never given the decoder.

Before: "The rollout activates our engagement flywheel across acquisition surfaces."

After: "The rollout adds signup prompts to the blog and the mobile app."

### `copula-avoidance` (soft, threshold 2 per 1,000 words)

Ornate verbs substituted for is, has, and are, usually to sound weightier.

Before: "The library serves as the backbone of the rendering pipeline."

After: "The library is the rendering pipeline's core dependency."

### `verbosity` (judgment)

A sentence that runs far past the length its content needs.

Before: "(any sentence longer than the configured word cap)"

After: "Split it, or cut the clauses that repeat the point."

## Unnecessary framing and structure

### `scene-setting` (hard)

A weather-report opener about today's fast-moving world before the actual topic.

Before: "In an era of rapid technological change, documentation matters more than ever."

After: "The API docs are eight months stale. Here is the update plan."

### `request-restatement` (hard)

The question handed back to the reader as filler before the answer starts.

Before: "When it comes to choosing a database, there are several factors to consider."

After: "Use Postgres. The workload is relational and the team already knows it."

### `meta-announcement` (hard)

The text narrating itself instead of saying the thing.

Before: "Below is a comprehensive overview tailored to your requirements."

After: "(delete the line; start with the first point)"

### `redundant-conclusion` (soft, threshold 2 per 1,000 words)

A closing paragraph that re-says the piece in softer words.

Before: "To sum up, the measures above will help the team reach its goals."

After: "(delete it; the last real point is the ending)"

### `over-structure` (soft, threshold 4 per 1,000 words)

Headings, bullets, and bold labels multiplying past what the content can fill.

Before: "(a two-paragraph answer split across six headings, or runs of **Label:** bullets)"

After: "Merge into prose; keep structure only where a reader will scan or look things up."
