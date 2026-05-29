# Visual Style Guide

This guide defines the image style for TikTok, Instagram Reels, carousel frames,
and thumbnails.

## Core Direction

Use a simple, funny, childlike drawing style inspired by the general visual
energy of Primate Economics:

- White or near-white background.
- Childlike hand-drawn characters.
- Simple marker, crayon, or MS Paint energy.
- Flat colors.
- Intentionally rough shapes.
- Sharp, jagged, uneven edges.
- Low-effort drawing energy.
- No smoothing, no polish, no soft gradients.
- Big readable expressions.
- Minimal detail.
- Meme-like composition.
- Clear visual joke.
- One idea per image.

The goal is not polished illustration. The goal is a recognizable, low-fi,
funny visual language that makes serious quant engineering feel unserious and
approachable.

Do not copy another creator's exact characters, branding, recurring assets, or
specific compositions. Use the broad style direction only.

## Default Image Style

Use this as the baseline prompt style:

```text
White background, childlike hand-drawn cartoon, rough marker drawing, simple
flat colors, intentionally imperfect shapes, sharp jagged uneven edges,
low-effort MS Paint energy, no smoothing, no soft gradients, funny educational
internet style, big readable facial expressions, minimal detail, one clear
visual joke, phone-readable composition.
```

## Composition Rules

- Keep the background mostly white.
- Use very few objects.
- Make the main idea obvious in one second.
- Use large simple characters.
- Keep text short when text is needed.
- Leave empty space for captions.
- Avoid clutter.
- Avoid realistic rendering.
- Avoid cinematic lighting.
- Avoid polished corporate design.
- Avoid smooth vector art.
- Avoid rounded friendly app-icon edges.
- Avoid airbrushed or painterly finishes.

## Recurring Visual Elements

Use simple recurring symbols:

- Stick-figure creator with smiley face.
- Greedy exchange as an angry suited cartoon character.
- Tiny trading bot.
- Pile of cash.
- Broken chart line.
- Laptop with code.
- Terminal box with green checkmarks.
- Warning sign.
- Big red X.
- Big green check.
- Simple market candles.
- Lab flask labeled "simulation".

## Character Style

Characters should look intentionally simple:

- Stick figures are allowed.
- Round smiley faces are allowed.
- Big angry eyebrows are allowed.
- Suits, hoodies, laptops, charts, and money can signal roles.
- Faces should be expressive, not realistic.

Do not generate realistic people or characters that look like public figures.

## Color Rules

Use mostly:

- White background.
- Black outlines.
- Red for danger, anger, failure, or market chaos.
- Green for tests, safety, or passing checks.
- Yellow for warnings.
- Blue for code, data, or simulation.

Keep the palette simple.

## Text Rules

Use text sparingly.

Good:

- "NO LIVE MONEY"
- "QUEUE SAID NO"
- "BOT FAILED SAFELY"
- "SLOP CODING"
- "FAKE MARKET LAB"

Avoid:

- Long explanations inside the image.
- Tiny unreadable code.
- Dense captions baked into the image.

## Prompt Template

Use this template for normal image frames:

```text
Create a vertical [9:16 or 4:5] image.

Style: white background, childlike hand-drawn cartoon, rough marker drawing,
simple flat colors, intentionally imperfect shapes, funny educational internet
style, sharp jagged uneven edges, low-effort MS Paint energy, no smoothing, no
soft gradients, big readable facial expressions, minimal detail, one clear
visual joke, phone-readable composition.

Scene: [describe the scene].

Composition: [describe where each subject goes].

Avoid: realistic rendering, cinematic lighting, luxury finance aesthetic,
photorealistic people, real exchange logos, public figures, clutter, tiny text,
smooth vector art, rounded app-icon style, airbrushed finishes, copying another
creator's exact characters or branding.
```

## Example Prompt

```text
Create a vertical 4:5 Instagram carousel frame.

Style: white background, childlike hand-drawn cartoon, rough marker drawing,
simple flat colors, intentionally imperfect shapes, funny educational internet
style, sharp jagged uneven edges, low-effort MS Paint energy, no smoothing, no
soft gradients, big readable facial expressions, minimal detail, one clear
visual joke, phone-readable composition.

Scene: a stick-figure creator with a smiley face sits in the lower-left corner.
A pile of cash is in the top-right corner. In the center stands "the exchange",
represented as a greedy angry suited cartoon gentleman, blocking the creator
from reaching the cash.

Composition: creator lower-left, exchange character center, cash top-right,
empty space at the top for a short caption.

Avoid: realistic rendering, cinematic lighting, luxury finance aesthetic,
photorealistic people, real exchange logos, public figures, clutter, tiny text,
smooth vector art, rounded app-icon style, airbrushed finishes, copying another
creator's exact characters or branding.
```

## Thumbnail Rule

Thumbnails should be even simpler:

- One character.
- One object.
- One emotion.
- Four words or fewer.
- White background.
- Big expression.

Example:

```text
BOT FAILED SAFELY
```

with a tiny trading bot smiling inside a safety cage while a red market chart
explodes outside.
