# Content Specification

This document defines the content style for videos that journal development of
the quant trading platform. Use it as the reference when turning coding sessions
into video transcripts, episode outlines, hooks, captions, or short-form scripts.

The content should make serious engineering feel alive, funny, and accessible
without pretending the system is safer or more profitable than it is.

## Core Positioning

The channel is a public development journal about building a professional quant
trading platform.

The main story is not:

```text
I found a money printer.
```

The main story is:

```text
I am building the machinery required before a trading system deserves trust.
```

The recurring tension:

```text
Markets are chaotic.
Trading systems are fragile.
Reliability is the actual alpha.
```

## Target Audience

Primary audience:

- Gen Z builders.
- Technical beginners who like chaotic but useful explanations.
- Quant-curious developers.
- AI-assisted coding watchers.
- People who enjoy seeing complex systems built in public.

Secondary audience:

- Engineers interested in reliability, testing, and simulation.
- Finance people curious about what serious trading infrastructure looks like.
- Future collaborators who care about craft.

## Voice

The voice should be:

- Unserious but coherent.
- Edgy but not cruel.
- Technical in flashes.
- Self-aware.
- Fast-moving.
- Honest about uncertainty.
- Allergic to finance-guru energy.
- Comfortable saying when something is not production-ready.

Good baseline:

```text
Serious quant engineering wearing an unserious hoodie.
```

## Inspiration

Take inspiration from internet-native economics and commentary formats with
absurd framing, sharp pacing, and real ideas underneath.

The reference vibe can include the energy of channels such as Primate Economics:

- Humor as the wrapper.
- Real concepts underneath.
- Punchy narration.
- Absurd comparisons.
- A willingness to say the quiet part out loud.

Do not copy another creator's identity, phrases, structure, voice, branding, or
visual style. Borrow the general lesson: make serious ideas digestible through a
memorable comedic frame.

## Persona

The narrator is not a trading genius.

The narrator is:

```text
Someone slowly realizing that building a trading bot is less about finding alpha
and more about preventing the system from doing something catastrophically dumb.
```

Recurring persona traits:

- Suspicious of easy wins.
- Mildly horrified by edge cases.
- Proud of boring reliability.
- Willing to roast slop coding.
- Obsessed with deterministic tests.
- Openly learning in public.

## Language Style

Use Gen Z-coded language selectively, not constantly.

Allowed flavor:

- slop coding
- cooked
- the bot is tweaking
- respectfully, no
- this is where the strategy gets humbled
- cursed market data
- infrastructure trauma
- mathematically toxic
- trust issues, but typed
- edge-case jump scare
- finance bro folklore
- production readiness is not a vibe

Do not overdo slang. The transcript should still be understandable to someone
who is not extremely online.

## Tone Boundaries

Allowed:

- Self-roasting.
- Roasting unsafe engineering patterns.
- Roasting overconfident trading claims.
- Absurd metaphors for technical concepts.
- Calling rushed code "slop" when the point is engineering discipline.

Avoid:

- Promising profits.
- Implying the system is production-ready.
- Giving financial advice.
- Mocking real users, losses, or people without power.
- Making the technical content incomprehensible.
- Copying another creator's exact format.

## Technical Honesty Rules

Every video should respect these rules:

- Do not claim the bot prints money.
- Do not imply simulation proves profitability.
- Do not imply tests remove market risk.
- Do not call the system production-ready until the readiness gate is complete.
- Clearly separate strategy ideas from execution safety.
- Mention when a feature is offline, state-only, or simulated.
- Treat reliability, auditability, and failure reproduction as the serious core.

## Content Pillars

### Building In Public

Show the current slice, the reason it matters, and what broke or improved.

Examples:

- Creating the simulation lab.
- Adding deterministic market generation.
- Testing natural exits.
- Preventing queue logic from forcing closes.
- Making weird market data on purpose.

### Quant Concepts Explained Twice

Start with a funny simplification, then give the real version.

Example:

```text
Cointegration is when two assets are mathematically toxic soulmates.
Real version: their price relationship can wander short term, but the spread is
stationary enough to model mean reversion.
```

### Engineering Pain

Make the audience feel the real difficulty:

- State is hard.
- Config is hard.
- Replay is hard.
- Live safety is hard.
- Real market data does not provide every edge case on demand.

### Safety Obsession

Make safety interesting:

- No live exchange mutation.
- No network in tests.
- State-only replay.
- No forced close hidden behind pair recalculation.
- Natural exit must keep working.

### Anti-Slop Coding

Contrast chaotic prototyping with serious infrastructure:

```text
Vibe coding is cute until your exchange adapter starts improvising.
```

## Video Structure

Use this default short-form structure:

1. Hook.
2. Problem.
3. Why it is dangerous or funny.
4. What was built or changed.
5. Tiny technical explanation.
6. Result or test.
7. Cliffhanger or next slice.

Keep each short video focused on one idea.

## Visual Format

The default format should not require the creator to appear on camera.

Use:

- Voiceover.
- AI-generated narrative stills.
- Short VS Code clips.
- Short terminal/test clips.
- Simple diagrams.
- Caption overlays.

Do not use long raw coding recordings as the main video. Screen recordings are
best as proof moments, not the entire story.

Visual style, prompt templates, thumbnail rules, and AI-image consistency live in
`VISUAL_STYLE_GUIDE.md`.

## Hook Patterns

Examples:

- "I thought the hard part was the trading strategy. Incorrect."
- "Today I taught my trading bot to survive cursed market data."
- "Historical market data is not enough, so I am manufacturing disasters."
- "My bot is not allowed to touch the exchange until it survives the lab."
- "This is why slop coding and live trading should never meet."
- "Cointegration sounds smart until the market starts roleplaying chaos."

## Transcript Requirements

When generating a transcript from a coding session, include:

- Episode title.
- One-sentence premise.
- Hook.
- Main beats.
- Voiceover script.
- On-screen code or terminal moments.
- Suggested captions.
- Safety disclaimer when relevant.
- Next episode tease.

The transcript should explain the engineering decision, not merely narrate file
edits.

## Coding Session Summary Template

Use this template after meaningful coding sessions:

```text
Episode title:

Premise:

Hook:

What changed:

Why it matters:

Technical core:

Funny framing:

Best visual moments:

Safety note:

Short-form script:

Caption:

Next episode:
```

## Example Episode Ideas

1. "I am building fake cursed markets because real data is too polite."
2. "Cointegration is just two assets with attachment issues."
3. "The trading bot must pass the lab before it gets the keys."
4. "I simulated a pair getting removed, and the bot was still not allowed to panic."
5. "State-only mode: the bot gets to hallucinate trades without touching the exchange."
6. "The queue can block future entries, but it cannot assassinate existing positions."
7. "OU process: mean reversion with fewer physics side quests."
8. "GLE is the final boss, but today we are not summoning it."
9. "Websocket simulation: what if one price feed simply ghosts us?"
10. "Slop coding would ship this. We are making it auditable instead."

## Caption Style

Captions should be punchy and specific.

Good:

```text
Building a trading bot is 20% strategy and 80% stopping it from doing cursed
things in edge cases.
```

Avoid:

```text
This bot will make passive income.
```

## Visual Style Notes

Possible visual motifs:

- Terminal clips.
- Simple diagrams.
- Scenario YAML snippets.
- Test output.
- Price/spread/z-score plots.
- Failure reports.
- Quick reaction cuts.
- "The bot is not trusted yet" recurring gag.

Keep visuals connected to real work. Avoid fake luxury trading aesthetics.

## Standing Disclaimer

Use a short disclaimer when a video could be interpreted as trading advice:

```text
This is engineering content, not financial advice. The system is being tested in
offline or state-only modes unless explicitly stated otherwise.
```

## Session-To-Video Rule

At the end of a coding session, a video transcript should answer:

- What did we build?
- What risk does it reduce?
- What did the test prove?
- What remains unproven?
- Why is this funny, painful, or surprising?

If those questions cannot be answered, the session probably is not a video yet.
