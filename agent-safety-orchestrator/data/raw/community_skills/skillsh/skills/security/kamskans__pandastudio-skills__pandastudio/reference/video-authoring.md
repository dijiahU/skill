# Video Authoring Playbook — 9:16 shorts + 16:9 YouTube

**Load this file when the user's task is a short-form video (9:16
TikTok/Shorts/Reels) or a YouTube edit (16:9).** This is the layer on
top of `motion-philosophy.md` — philosophy governs the *look*, this doc
governs *where things go* and *how audio, face, screen, captions, and
motion graphics compose* in each aspect ratio.

**Prerequisites:** load `reference/motion-philosophy.md` first. This
playbook assumes the 11 Laws, visual vocabulary, and easing dictionary
are in context.

---

## 0 · The three modes PandaStudio authors

PandaStudio is both recorder and editor, so we can detect which layout a
project is in and apply the matching playbook. Three modes:

| Mode | Aspect | Primary content | Secondary content | When |
|---|---|---|---|---|
| **A. 9:16 camera-only** | 9:16 | Face (webcam, full or top-half) | Motion graphics in bottom half | TikTok/Shorts/Reels talking-head |
| **B. 9:16 screen-rec + PiP face** | 9:16 | Screen recording (top 50–60%) | PiP face (bottom 40%), captions | Product demos, tutorials, app walkthroughs posted as shorts |
| **C. 16:9 YouTube side-overlay** | 16:9 | Full-frame video (face, screen, or both) | Side-panel / corner motion graphics that DO NOT cover the video | Regular YouTube long-form where the speaker keeps the camera live and graphics slide in beside them |

**How to detect which mode:**

1. Read `project.current` → inspect `aspect_ratio` field:
   - `9:16` → Mode A or B
   - `16:9` → Mode C
2. For 9:16, inspect `webcam_layout_preset`:
   - `fullscreen` or no screen source → Mode A
   - `picture-in-picture` + screen source present → Mode B
3. For 16:9, default to Mode C unless the user asks for full-frame
   takeover scenes (logo reveal, brand outro).

If unsure, ask the user once. Don't silently pick.

---

## 1 · Mode A — 9:16 camera-only (TikTok/Shorts/Reels talking-head)

The TikTok/Shorts default. Face fills top half or whole frame; motion
graphics live in the bottom portion; captions across the middle or
bottom third.

> **Default pairing:** for any motion graphic that plays mid-video
> (not a full-screen intro/outro card), add a
> `project.add-clip-transform-region preset=cam-bottom-half` (or
> `cam-top-half`) over the same time window. Camera shrinks to one
> half, the graphic gets the other half, then the camera returns to
> full-frame. See §5b. Without this, the graphic either covers the
> face or you have to permanently downsize the camera — both are
> worse than the time-bounded shrink.

### 1.1 Face choreography — the most jarring mistake

A face that **snaps between sizes instantly is the single worst frame
in a vertical video.** Always interpolate.

**Two canonical face modes:**

- **BOTTOM** — face occupies bottom ~40% (y ≈ 1150–1920 of a 1080×1920),
  top ~60% free for motion graphics. Default for informational beats
  where the graphic IS the content.
- **FULLSCREEN** — face fills the whole 1080×1920 frame. Default for
  emphasis beats where the face IS the content (reaction, punchline,
  intro hook, outro CTA).

**Transitions between modes:**
- **Duration:** 0.32s
- **Start:** 0.15s BEFORE the scene lands (so the face has already
  settled when the new graphic appears)
- **Ease:** `expo.inOut` on both `transform: scale()` and `top` (or
  `transform: translateY`)
- **Never instant.** 0.32s is the floor. 0.5s is fine. 0s reads as a
  glitch.

```js
// Transition from FULLSCREEN → BOTTOM at scene t=5.0s
tl.to('.face-container', {
  scale: 0.58,
  top: '55%',      // face top edge at 1060 (out of 1920)
  duration: 0.32,
  ease: 'expo.inOut'
}, 4.85);  // 0.15s before the scene lands
```

### 1.2 Face grading (mandatory for Mode A)

Raw webcam footage looks flat next to stylised motion graphics. Grade
the face so it sits visually in the same world:

```css
.face-container video {
  filter: contrast(1.08) saturate(1.08) brightness(0.97);
}
```

Plus:
- **Subtle Ken Burns:** `scale: 1.0 → 1.05` over the full beat, `ease:
  'none'`. Adds imperceptible life that the eye registers as "camera
  alive." Without this, the face reads as frozen between expression
  changes.
- **Side vignette:** a radial gradient overlay darkening the L/R edges
  of the face frame to focus attention centre. `background:
  radial-gradient(ellipse 80% 120% at 50% 50%, transparent 50%,
  rgba(0,0,0,0.5) 100%)`.

### 1.3 Caption placement (Mode A)

- **Safe zone:** bottom 40% (y 1150–1900 in 1080×1920). Avoid the top 15%
  (y 0–288) which collides with the face in FULLSCREEN mode.
- **When face is in BOTTOM mode:** captions shift UP — place in
  y 960–1140 (the band above the face block).
- **Style:**
  ```css
  .caption {
    position: absolute;
    left: 50%; transform: translateX(-50%);
    bottom: 320px;   /* measured from bottom; adjust per face mode */
    font-family: 'Montserrat', sans-serif;
    font-weight: 900;
    font-size: 52px;   /* range 46–58 */
    color: #fff;
    text-shadow: 0 0 8px rgba(0,0,0,0.8), 0 4px 6px rgba(0,0,0,0.6);
    padding: 12px 22px;
    max-width: 900px;
    text-align: center;
  }
  .caption .active-word {
    color: var(--accent);        /* brand accent, e.g. teal */
    transform: scale(1.08);
    display: inline-block;
  }
  ```
- **Active word POPS** — scale 1.08 + accent color + subtle lift. NEVER
  `-webkit-text-stroke` (renders inconsistently across platforms; use
  `text-shadow` for outline).
- **Captions feel like graffiti on the frame, not a subtitle track.**
  Bold, sized up, confident. Polite captions = amateur.

### 1.4 Scene pacing floor for Mode A

- **One "jaw-dropper" every 5 seconds** or the viewer scrolls. Jaw-dropper
  = typography slam, glitch/chromatic reveal, whip-pan transition,
  audio-sync slam, object materialise.
- **Hook beat 0–3s:** FULLSCREEN face + a dropped-in headline
  (chrome-gradient, glow, scales in 0.33s). Don't waste the first 3s on
  setup — the hook has to HIT.
- **Body beats 3–20s:** BOTTOM face + motion-graphics content beats,
  scene length 1.5–2.5s, transition every scene.
- **CTA 20s onward:** FULLSCREEN face + brand card / handle / "follow"
  graphic. Hold 3–4s before the video ends.

### 1.5 Mode A pre-flight (before `export.start`)

- [ ] Face mode transitions are interpolated (0.32s+ ease) everywhere,
      not snapped
- [ ] **Every mid-video motion graphic has a paired
      `clip-transform-region` covering the same window** (see §5b) —
      so the camera shrinks to make room for the graphic instead of
      being covered by it
- [ ] Face is graded (contrast 1.08 / saturate 1.08 / brightness 0.97)
- [ ] Ken Burns on face (1.0 → 1.05 over beat, `ease: 'none'`)
- [ ] Side vignette on face frame
- [ ] Captions live in the correct safe zone for the active face mode
- [ ] Active word POP applied (scale + accent color)
- [ ] Caption font is bold (Montserrat 900 or similar), not subtitle-lite
- [ ] Seam between face and MG panel hidden with gradient/scan-line
- [ ] At least one jaw-dropper per 5s of runtime
- [ ] Hook beat doesn't waste the first 3s
- [ ] CTA holds 3–4s at the end

---

## 2 · Mode B — 9:16 screen-rec + PiP face (PandaStudio's unique mode)

**The mode HyperFrames can't author, because HyperFrames doesn't own the
recorder.** PandaStudio owns the screen + cam recording pipeline, so we
can use that surface-level knowledge to build a shorts playbook the
competition can't.

### 2.1 The inversion — this is the important part

In Mode A, the face occupies the top / full frame, so captions and MG
live in the bottom half and the **top 15% is the unsafe zone**.

In Mode B, **the screen recording IS the content** — it's the user
working in an app, scrolling a design, coding, clicking through a
dashboard. The cropped regions of interest are the top 50–60%. You
cannot cover the screen with motion graphics or captions mid-beat — the
user scrolled there to watch the screen, not the graphics.

**Inverted safe zones for Mode B:**

| Region | y range (of 1080×1920) | Use |
|---|---|---|
| **Top edge strip** (0–180) | very top | Chapter label, brand wordmark, timestamp badge. Avoid the very top 60px (OS menubar in many recordings). |
| **Left/right rails** (0–120 and 960–1080 px width) | full height | Vertical callouts, numbered steps (1/2/3), tag labels. |
| **Screen zone** (180–1200) | middle 63% | **DO NOT COVER.** Zoom regions, cursor callouts, highlight rings are OK here because they're contextual to the screen (they emphasise, don't occlude). |
| **MG band** (1200–1520) | bottom ~30% | Motion graphics narration panel. Slide in from below. This is the "bottom third" equivalent. |
| **PiP face zone** (1520–1900) | bottom ~20% | PiP webcam. Off-limits to anything else except the caption if needed. |

### 2.2 When the screen IS the jaw-dropper

Mode A needs authored jaw-droppers every 5s because the content is a
talking head with no inherent visual story. Mode B **has built-in
visual interest** — the screen is doing something. The agent's job is
**emphasis, not replacement.** Use:

1. **Zoom regions** (already a first-class PandaStudio feature) — zoom
   into the relevant part of the screen at the moment of emphasis. This
   IS the jaw-dropper for 80% of Mode B beats. Aim for a zoom every
   3–4s if the screen is dense; every 6–8s if the action is already
   large.
2. **Cursor callouts** — the faux-cursor click sequence from
   motion-philosophy §3.2 overlayed on the user's actual cursor. When
   the user clicks a button on screen, fire the 7-tween ripple. This is
   pure authoring — the real click is already on screen.
3. **Highlight rings** — at the moment the user's cursor moves to a
   target, fade in a glowing ring around the target for 0.4s. Use
   `box-shadow: 0 0 0 3px var(--accent), 0 0 20px var(--accent)`.
4. **Numbered step labels** — bottom-left corner, large numeric ("1",
   "2", "3") + 1-line description, slides in from left at the start of
   each step. Uses the L/R rail safe zone.

### 2.3 Caption placement (Mode B)

- **Primary position:** top edge strip, y 100–180. Styled:
  ```css
  .caption-top {
    position: absolute;
    top: 120px;
    left: 50%; transform: translateX(-50%);
    font-family: 'Montserrat', sans-serif;
    font-weight: 900;
    font-size: 44px;
    color: #fff;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(10px);
    padding: 10px 20px;
    border-radius: 12px;
    max-width: 900px;
    text-align: center;
  }
  ```
- **Alternate:** between screen zone and PiP band, y 1220–1280. Only if
  the screen has empty space there AND it won't collide with MG panels.
- **Never over the screen mid-click.** If the user is clicking a button
  and a caption would cover the button, move the caption to the top
  strip or bottom strip.
- **Active word POP** still applies — scale 1.08 + accent.

### 2.4 PiP face handling (Mode B)

- PiP face zone is **off-limits** to motion graphics. Don't slide
  anything across it.
- PiP face doesn't need Ken Burns (it's small; the eye reads it as a
  reference, not the subject).
- Face grading (contrast/saturate/brightness) still applies — the raw
  webcam looks flat next to the screen's UI colors.
- Position the PiP consistently: bottom-right corner by default (right
  rail reserved for callouts means bottom-left is occupied, so
  bottom-right is the default for PiP). Respect `webcam_position` from
  the project if the user set it.

### 2.5 Mode B pre-flight

- [ ] Screen zone (y 180–1200) is never occluded by MG panels or captions
- [ ] Zoom regions fire at moments of emphasis (≥ 1 per 6s)
- [ ] Cursor callouts on every user click (ripple + target overshoot)
- [ ] Highlight rings on target elements before user clicks them
- [ ] Numbered step labels slide in on scene change
- [ ] Captions live in top strip (y 100–180) unless the screen has clear
      space elsewhere
- [ ] PiP face is in corner, not centred (don't compete with screen)
- [ ] PiP face is graded (contrast/saturate/brightness)
- [ ] Seam between screen and PiP hidden (subtle gradient divider)

---

## 3 · Mode C — 16:9 YouTube with side-overlay motion graphics

**This is the mode the user explicitly called out.** 16:9 YouTube edits
where the host keeps talking on camera and graphics appear BESIDE them,
not over them. The video stays visible throughout; motion graphics
occupy the margins.

### 3.1 The mental model

Default YouTube edits cut between A-roll (host talking) and B-roll (cut
to graphic, host's voice over). Cutting to full-frame graphics is
jarring and loses audience — the viewer is watching for the *person*,
not the graphic.

The premium pattern: **host stays live, graphic slides in beside them,
they keep talking.** Graphic earns its space, plays its beat, slides
out. Host was never interrupted.

> **For camera-only Mode C (single-host explainers, no screen rec):
> reach for `project.add-clip-transform-region preset=cam-right-portrait`
> on every mid-video graphic.** The host shrinks to a portrait card on
> the right while the graphic plays in the left half, then the host
> returns to full-frame. This is the Ali-Abdaal / MKBHD pattern and
> it is the default — see §5b. Skipping the clip-transform means
> either the graphic covers the host's face (worst) or you're stuck
> permanently letterboxing the host (a worse design choice than
> time-bounded shrinking).

Zones for 16:9 1920×1080:

```
┌─────────────────────────────────────────┐
│                                         │
│  MARGIN          HOST VIDEO    MARGIN   │
│  (MG zone 1)   (never cover)  (MG zone 2)│
│                                         │
│  ░░░░░░░░░░░░  ▓▓▓▓▓▓▓▓▓▓▓▓  ░░░░░░░░  │  (1080 high)
│  ░░░░░░░░░░░░  ▓▓▓ face ▓▓▓  ░░░░░░░░  │
│  ░░░░░░░░░░░░  ▓▓▓▓▓▓▓▓▓▓▓▓  ░░░░░░░░  │
│                                         │
│  LOWER THIRD (bottom 200px, y 880–1080) │
└─────────────────────────────────────────┘
```

### 3.2 Zone geometry (1920×1080)

| Zone | Coordinates | Use |
|---|---|---|
| **Host video** | usually 960×1080 centred (x 480–1440) with slight letterbox, OR reframed to fill 1920×1080 with graphics composited on top | Never covered. |
| **Left MG margin** | x 0–480, full height | Picture-adjacent graphics, quote cards, stat reveals, chapter labels |
| **Right MG margin** | x 1440–1920, full height | Picture-adjacent graphics (mirrored), source attribution, subscribe nudge |
| **Lower third** | y 880–1080, x 80–1400 | Host name / title card, timestamp chapters, link-in-description pointer |
| **Top banner** | y 0–100, full width | Chapter badge (minimal — don't crowd) |
| **Corner (top-right)** | x 1620–1880, y 40–200 | Running stats, counter, channel handle |
| **Corner (bottom-right)** | x 1620–1880, y 880–1040 | Subscribe reminder, end-card pointer |

### 3.3 The three compositional strategies

**Strategy 1 — Letterboxed host + full-height MG rails (premium):** Host
video reframed to 960×1080 (or 1280×1080) centre-cropped from the
original 16:9. Left and right 480px become MG rails where content
slides in. Used by Linear, Figma, Vercel-style marketing edits. The
"picture-adjacent" look.

```html
<div class="stage">
  <video class="host" src="host.mp4" style="
    position: absolute;
    left: 50%; transform: translateX(-50%);
    width: 960px; height: 1080px;
    object-fit: cover;
  "></video>
  <div class="mg-rail mg-left"  style="position:absolute; left:0; top:0; width:480px; height:1080px;"></div>
  <div class="mg-rail mg-right" style="position:absolute; right:0; top:0; width:480px; height:1080px;"></div>
</div>
```

MG content slides in from the edge (`x: -100% → 0`) at scene start,
holds for the beat, slides out (`x: 0 → -100%`) before the next scene.
Ease: `expo.out` in, `power2.in` out. Duration: 0.5s each.

**Strategy 2 — Full-frame host + corner / lower-third MG (default
YouTube):** Host video fills 1920×1080. MG appears in bottom-third,
top-banner, or corners — never over the host's face area (roughly x
640–1280, y 200–800). Used by most YouTubers who don't want to reframe
their host footage.

```html
<video class="host-full" src="host.mp4" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover;"></video>
<div class="lower-third"
     style="position:absolute; left:80px; right:80px; bottom:80px; height:120px;"></div>
<div class="stat-card"
     style="position:absolute; right:80px; top:80px; width:320px; height:180px;"></div>
```

**Strategy 3 — Quarter-screen picture-adjacent (emphasis beats only):**
Host video temporarily shrinks and reframes to the left half (or
bottom-left corner 640×360), MG occupies the other half. Used for
"look at this stat / chart / screen" beats. Transition back to full
frame when the emphasis beat ends.

```js
// Shrink host to left half at t=12s
tl.to(host, { width: 960, left: 0, duration: 0.5, ease: 'power2.inOut' }, 12);
tl.from('.insert-panel', { x: '100%', duration: 0.5, ease: 'power2.out' }, 12);
// Hold 4s then return
tl.to(host, { width: 1920, left: 0, duration: 0.5, ease: 'power2.inOut' }, 16.5);
tl.to('.insert-panel', { x: '100%', duration: 0.5, ease: 'power2.in' }, 16.5);
```

### 3.4 Picking the right strategy

| Use case | Strategy |
|---|---|
| Podcast-style long-form, host is the star | 2 (full-frame host + lower-third) |
| Product demo / explainer / marketing edit | 1 (letterboxed + rails) |
| "I was looking at this data…" / screenshare beat | 3 (quarter-screen picture-adjacent) |
| Logo reveal / brand outro / sponsor read | Full-frame MG takeover is OK here (host cuts out deliberately) |

Default to strategy 2 unless the project design says otherwise. If the
user says "make it feel like [brand] video", and [brand] is Linear /
Figma / Vercel / Infinite / any clean-aesthetic brand → use 1.

### 3.4.5 Overlay pacing — **read `motion-philosophy.md` §1.6**

Every overlay below is a motion graphic on top of a live host. Viewers
are split-attention. Use the slower timing table in
[`motion-philosophy.md`](motion-philosophy.md) §1.6, not §1.5 (which is
for standalone hero pieces). Summary:

| Overlay | Total timeline duration | Animation completes at | Hold |
|---|---|---|---|
| Concept callout | **5–7s** | 1.2s | 4–5.5s hold |
| Lower third | **5–8s** | 1.0s | 4.5–7s hold |
| Stat reveal | **4–5s** | 1.5s (counter tween) | 2.5–3.5s hold |
| Intro title card | **3–5s** | 1.8s | 1–3s hold |
| Chapter marker | **2–3s** | 0.4s | 1.5–2.5s hold |
| Outro CTA | **5–7s** | 1.5s | 3.5–5.5s hold (+ shimmer) |

**Critical:** match `project.add-motion-graphic --durationMs` to the
total scene duration you authored. If you rendered a 6000ms scene and
placed it with `--durationMs=3000`, half the hold is truncated —
viewer sees the reveal and then it disappears mid-read.

### 3.5 Side-rail content vocabulary (strategy 1)

These are the reusable MG primitives that work in the left/right rails
of a 480-px-wide × 1080-px-tall zone.

| Element | Recipe |
|---|---|
| **Quote card** | Large serif pull-quote, chrome-gradient, max 12 words. Enters with chrome-sweep. `font-size: 72px; line-height: 1.15;` |
| **Stat reveal** | Huge number (150–200px, chrome gradient) over a 1-line label. Counter tween counts up from 0 to final value over 0.8s, `ease: 'power2.out'`. |
| **Chapter label** | Small numeric in top-left of rail ("01"), large title below. |
| **Bulleted checklist** | 3–4 line items, each staggered reveal 0.2s, check-mark icon morphs in with `back.out(1.5)` |
| **Icon-label card** | Glyph (Lucide / custom SVG) + short label below, 180px wide. Good for "feature 1 / 2 / 3" runs. |
| **Product shot** | Device mockup (phone / laptop / tablet) with a screen-fill, enters from bottom with slight rotation `from(x: 100%, rotation: 8, opacity: 0)`. |
| **Source attribution** | Bottom of right rail, small text "Source: The Economist, 2024" in muted gray. Appears with the stat, persists through the beat. |

### 3.6 Lower-third (strategy 2)

- **Position:** y 880–1040 (120px tall + 40px bottom margin), x 80–1400.
- **Composition:**
  - Left block: host name (48px chrome) + subtitle (24px muted, e.g. title)
  - Right block (optional): handle / URL
  - Background: dark bar with blur, or a gradient fill
- **Enter:** slide from left `x: -100% → 0`, 0.5s `expo.out`
- **Hold:** 3–5s
- **Exit:** slide out `x: 0 → -100%`, 0.4s `power2.in`

### 3.7 Corner cards (strategy 2)

- **Top-right "stats":** 320×180 card, slides down from top `y: -100% → 0`, holds the beat, fades out. Contains 1 big number + 1 small label.
- **Bottom-right "subscribe":** small 280×80 card, appears 5s before video end, persistent through outro.
- **Top-left "chapter":** small chapter badge, appears on chapter change, persists 3s then fades.

### 3.8 Mode C pre-flight

- [ ] Host video is NEVER covered by a MG panel during a speaking beat
- [ ] Chosen compositional strategy (1/2/3) is consistent throughout the
      piece — don't mix strategies without a reason
- [ ] Side-rail (strategy 1) MG content never exceeds 460px wide (leaves
      breathing room against the host frame)
- [ ] Every MG enters from an edge (slide, not fade-from-nothing)
- [ ] Every MG exits before the next MG enters (no visual stacking)
- [ ] Lower thirds hold 3–5s (not 1.5s like a short)
- [ ] Chapter labels + stats obey the margin / corner geometry
- [ ] Any full-frame MG takeover is only for logo reveal / brand outro /
      sponsor read — not mid-body
- [ ] Host face area (x 640–1280, y 200–800 in strategy 2) has nothing
      on top of it at any frame
- [ ] **Camera-only Mode C: every mid-video motion graphic has a paired
      `clip-transform-region preset=cam-right-portrait` (or
      `cam-left-portrait`) over the same window** (see §5b). The host
      shrinks to a portrait card during the graphic's beat and returns
      to full-frame after — Ali-Abdaal pattern. Skip only when the
      project has a screen recording (those use cursor-telemetry zooms,
      not clip-transform).

---

## 4 · Audio-sync protocol (all modes)

When the user trims or retimes audio after motion graphics are placed,
every MG anchored by a timestamp drifts out of sync. Standard problem.

### 4.1 The source-edited time model

PandaStudio already tracks this:
- **Source time** — the raw recording clock, 0 at the start of the
  original recording.
- **Edited time** — the playback clock after trims are applied, 0 at
  the start of the edited timeline.

Every caption, motion graphic, and zoom region has an `anchor.sourceMs`
(when in the original recording this should fire) and a derived
`startMs` (when in edited time it currently fires). `rebaseZoomRegions`
already recalculates `startMs` from `sourceMs` + trim/speed regions on
every edit.

### 4.2 When authoring MG timestamps, ALWAYS set `anchor`

Motion graphics you add should carry `anchor.sourceMs` so they follow
the content even if the user trims before the MG's beat:

```json
{
  "id": "mg-stat-card-1",
  "startMs": 12000,
  "endMs": 15000,
  "anchor": {
    "type": "transcriptWord",
    "sourceMs": 12000
  }
}
```

If the anchor isn't set, a future trim of the 0–5s intro will push the
MG to the wrong word.

### 4.3 `shift()` function for retimes

When the user asks "move everything after 10s back by 2s":

```js
function shift(regions, afterMs, deltaMs) {
  return regions.map(r =>
    r.startMs >= afterMs
      ? { ...r, startMs: r.startMs + deltaMs, endMs: r.endMs + deltaMs }
      : r
  );
}
```

Apply to captions, zoom regions, motion graphics. Re-anchor if anchors
no longer point at the right word (agent may need to re-map via
transcript word offsets).

---

## 5 · Frame verification — MANDATORY before export

Lint passing ≠ design working. Before calling `export.start` on any
piece that used motion graphics, the agent MUST extract frames at hero
timestamps and look at them.

```bash
# Extract 8–15 frames at hero moments
pandastudio motion.verify-frames \
  --entryId=$EID \
  --timestamps='0.5,1.5,3.0,5.0,7.5,10.0,12.5,15.0,18.0,20.5,23.0,25.5,28.0'
```

The verb writes PNGs and returns a manifest with file paths the agent
reads (multimodal). Check each frame for:

- [ ] No cropped faces / text overflow / blank frames
- [ ] Caption lands on the right word at each captured moment
- [ ] Face mode transitions (Mode A) look smooth, not snapped
- [ ] No MG covers the host face area (Mode C)
- [ ] No MG covers the screen zone during a click (Mode B)
- [ ] Color palette looks right (no accidental flat-white text)
- [ ] Backgrounds have the grid + vignette + grain texture

If any frame fails, re-render and re-verify. No shipping un-looked-at
work.

---

## 5b · Clip-transform regions — the default move for explainer beats

> **Read this as a default rule, not a niche feature.** Whenever you
> add a motion graphic to a **camera-only** project (Mode A 9:16
> talking-head, or Mode C 16:9 single-host), you should also add a
> clip-transform-region over the same time window. The camera shrinks
> to make room for the graphic, plays the beat, then returns to
> full-frame. **Skipping it = the graphic covers the host's face**,
> which is the worst version of this edit.

This is the "camera moves to corner / portrait card while a graphic
plays" pattern Ali Abdaal, MKBHD, and most modern YouTube explainers
use for every mid-video graphic. It's not advanced — it's the
baseline. Reach for it whenever:

- A motion graphic plays mid-video (not as a full-screen intro/outro)
- The host is the main subject (camera-only / talking-head)
- The graphic and the host both need to be visible at the same time

> **Constraint — camera-only or user-uploaded recordings only.** Do
> not add `clipTransformRegions` to projects whose primary clip is a
> screen recording. Screen recordings have their own time-aware
> visual story via cursor-telemetry zooms (`zoomRegions`); stacking
> a layout transform on top of that fights the zoom math and produces
> two competing motions.

### 5b.1 Verb

```bash
pandastudio project.add-clip-transform-region \
  --startMs=2000 \
  --endMs=8000 \
  --preset=cam-bottom-half \
  --transitionMs=320          # optional, default 320
```

The default 320 ms transition is a cubic ease-in/out at both region
boundaries. The verb supports `anchor.sourceMs` (passes through
`rebaseAnchored` like every other anchored region type).

### 5b.2 Presets

| Preset | Use it when… |
|---|---|
| `cam-bottom-half` | 9:16 Mode A — motion graphic plays in top half, camera shrinks to bottom half. The default 9:16 explainer beat. |
| `cam-top-half` | 9:16 Mode A inverse — graphic on bottom (lower-third style), camera occupies top. |
| `cam-right-portrait` | 16:9 Mode C — Ali-Abdaal-style. Camera shrinks to a ~35% right-side portrait card while the left half hosts the motion graphic. The canonical 16:9 explainer beat. |
| `cam-left-portrait` | 16:9 Mode C mirror — camera on left, graphic on right. Less common; only when the user specifies. |
| `cam-bottom-right-quarter` | 16:9 brand corner — camera in a small bottom-right quarter while the rest is graphic-driven (logo reveals, big stat reveals). |
| `cam-bottom-left-quarter` | Mirror of the above. |

### 5b.3 The pattern

A clip-transform region by itself is not the deliverable — it's
infrastructure for an explainer beat. Always pair it with a motion
graphic that plays during the same window:

```bash
# 1. Author and add the motion graphic (use motion.render-html)
pandastudio motion.render-html --html=$HTML --outId=$MGID --aspect=16:9
pandastudio project.add-motion-graphic \
  --src=$MGOUT --startMs=2000 --endMs=8000 \
  --x=0 --y=0 --width=960 --height=1080   # left half of a 1920x1080 stage

# 2. Add the matching clip-transform so the camera makes room
pandastudio project.add-clip-transform-region \
  --startMs=2000 --endMs=8000 --preset=cam-right-portrait
```

Match the region timestamps to the motion graphic's. The 320 ms
ease-in/out at boundaries means the camera glides into the portrait
card just before the graphic starts and glides back to full-frame just
after it ends — feels intentional, not snapped.

### 5b.4 What clip-transform is NOT for

- **Screen recordings.** Use `zoomRegions` (`project.add-zoom`) for
  time-aware emphasis on screen content.
- **Picture-in-picture webcam over a screen recording.** That's
  configured project-wide via `project.set-webcam-layout`, not via
  per-region transforms.
- **Permanent layout changes.** If the entire video should be
  side-by-side, set `webcamLayout` once. Clip-transform is exclusively
  for time-bounded explainer beats.

---

## 6 · Mode-to-template cheat sheet

Until the template library is audited and upgraded to match these
playbooks, here's the quick map:

| User said… | Mode | First tool | Fallback |
|---|---|---|---|
| "Make a TikTok from my recording" (webcam only) | A | `motion.generate templateId=short-intro-a` | `motion.render-html` with Mode A shell |
| "Turn this tutorial into a short" (screen + cam) | B | `motion.generate templateId=short-screen-pip` | `motion.render-html` with Mode B shell |
| "YouTube intro / outro card" | C | `motion.generate templateId=youtube-lower-third` or `templateId=youtube-outro` | `motion.render-html` |
| "Hero logo reveal for my brand" | A/B/C | `motion.render-html` (templates won't have the polish) | — |
| "Explain this stat with a graphic" (mid-YouTube, talking-head) | C | `motion.render-html` left-half graphic **+ `project.add-clip-transform-region preset=cam-right-portrait`** | — |
| "Make this explainer Ali-Abdaal-style" (16:9 talking-head + tools) | C | For each tool intro: `motion.render-html` + `project.add-clip-transform-region preset=cam-right-portrait` | — |
| "When I say X, show a graphic in the top half" (9:16 talking-head) | A | `motion.render-html` + `project.add-clip-transform-region preset=cam-bottom-half` | — |
| "Add chapter markers" (YouTube) | C | `motion.generate templateId=chapter-marker` + clip-transform if mid-video over face | `motion.render-html` |
| "Drop a logo / brand corner during my intro line" (camera-only) | A/C | `motion.render-html` + `project.add-clip-transform-region preset=cam-bottom-right-quarter` | — |

**When in doubt: `motion.render-html` with the canonical shell from
`motion-philosophy.md` §7.** Templates are faster but can only go as
far as the template was designed for. Hand-authored HTML gets you to
HyperFrames-level.

---

## 7 · Final sanity check — all modes

Before you say "done", re-read the 11 Laws (motion-philosophy §0). If
your piece doesn't honour at least 9 of them, it's not done. The two
you can skip (maybe) are #10 (unifying texture — if the piece is a
one-scene short) and #6 (callback — if it's under 15s). Every other
law is mandatory on every piece, every time.
