# Motion-graphic templates

PandaStudio ships with 19 bundled templates. The canonical, version-accurate list (with the slot schema for each) is:

```bash
pandastudio motion.list --json
```

Always discover; never hard-code. This file is a snapshot for offline reading.

## All 19 templates

| id | name | aspects | slots |
|---|---|---|---|
| `title-card-vox` | Title Card | 16:9, 9:16 | `title`, `subtitle`, `accentColor`, `textColor` |
| `listicle-vox` | Listicle | 16:9, 9:16 | `title`, `items`, `accentColor`, `bgColor`, `textColor`, `footer`, `footerCta` |
| `flow-diagram-explainer` | Flow Diagram | 16:9 | `title`, `titleAccent`, `nodes`, `summary`, `accentColor`, `bgColor`, `nodeBgColor` |
| `subscribe-cta` | Subscribe CTA | 16:9, 9:16 | `channelName`, `ctaText`, `hookLine`, `bellText`, `accentColor`, `bgColor` |
| `end-screen` | End Screen | 16:9 | `channelName`, `channelHandle`, `ctaText`, `thanksText`, `accentColor`, `bgColor` |
| `sponsor-intro` | Sponsor Intro | 16:9, 9:16 | `introText`, `sponsorName`, `tagline`, `ctaText`, `accentColor`, `bgColor`, `textColor` |
| `chapter-divider` | Chapter Divider | 16:9, 9:16 | `chapterLabel`, `chapterNumber`, `chapterTitle`, `accentColor`, `bgColor`, `textColor` |
| `channel-intro` | Channel Intro | 16:9, 9:16 | `channelName`, `tagline`, `accentColor`, `bgColor`, `textColor` |
| `stat-reveal` | Stat Reveal | 16:9, 9:16 | `statLabel`, `prefix`, `statValue`, `suffix`, `unit`, `context`, `accentColor`, `bgColor`, `textColor` |
| `pull-quote` | Pull Quote | 16:9, 9:16 | `quote`, `attribution`, `role`, `accentColor`, `bgColor`, `textColor` |
| `before-after` | Before / After | 16:9, 9:16 | `title`, `beforeLabel`, `beforeValue`, `beforeCaption`, `afterLabel`, `afterValue`, `afterCaption`, `beforeColor`, `afterColor`, `bgColor`, `textColor` |
| `comparison-table` | Comparison Table | 16:9 | `title`, `columnA`, `columnAColor`, `columnB`, `columnBColor`, `rows`, `bgColor`, `textColor` |
| `bar-chart` | Bar Chart | 16:9, 9:16 | `title`, `bars`, `caption`, `accentColor`, `bgColor`, `textColor` |
| `word-pop` | Word Pop | 16:9, 9:16 | `text`, `accentColor`, `bgColor` |
| `reaction-burst` | Reaction Burst | 16:9, 9:16 | `text`, `burstColor`, `textColor`, `strokeColor`, `bgColor` |
| `source-attribution` | Source Attribution | 16:9, 9:16 | `sourceLabel`, `sourceName`, `url`, `accentColor`, `bgColor`, `textColor` |
| `date-location` | Date / Location Stamp | 16:9, 9:16 | `dayLabel`, `location`, `subLine`, `accentColor`, `bgColor`, `textColor` |
| `countdown` | Countdown | 16:9, 9:16 | `caption`, `startFrom`, `finalWord`, `accentColor`, `numberColor`, `bgColor`, `textColor` |
| `spotlight-ring` | Spotlight Ring | 16:9, 9:16 | `x`, `y`, `radius`, `label`, `labelPosition`, `accentColor`, `bgColor`, `dimAlpha` |

## Style packs

Themes overlay color slots without changing the template. Five ship out of the box:

| theme id | vibe |
|---|---|
| `default` | PandaStudio house style — neutral grey/green |
| `mr-beast` | High-energy YouTube — yellow + black |
| `mkbhd` | Premium tech — teal + black |
| `kurzgesagt` | Educational — teal + warm cream + orange |
| `veritasium` | Science — deep blue + cream + warm yellow |

Always merge `theme.colors` into your `slots` object before `motion.generate`. The render path doesn't know about themes — they're a pre-render layer.

## Picking a template by intent

The catalogue isn't named by intent — pick by tags + name. If the user says "outro," look at `end-screen` and `subscribe-cta`. If they say "intro," look at `title-card-vox`, `channel-intro`, or `sponsor-intro` depending on the brief. If they want a stat or number reveal, `stat-reveal` and `bar-chart`. For comparisons, `before-after` or `comparison-table`. For emphasis moments mid-video, `word-pop`, `reaction-burst`, or `spotlight-ring`.

When uncertain, run `pandastudio motion.list --json | jq '.data.templates[] | {id, name, tags}'` and pattern-match.

## Verifying before render

```bash
# Inspect a chosen template's full slot schema + defaults BEFORE generating
pandastudio motion.list --json | \
  jq '.data.templates[] | select(.id=="title-card-vox") | {slots, defaults, durationMs}'
```

Always check `defaults` — if a slot has a sensible default, you don't need to pass it. Pass only the slots you want to override.

## Aspect ratios

Most templates support 16:9 + 9:16. A few are 16:9-only (flow diagrams, end screens, comparison tables — they need the horizontal real estate). Filter:

```bash
pandastudio motion.list --json | \
  jq '.data.templates[] | select(.aspectRatios | index("9:16")) | .id'
```

## When none of the 19 fit

Use `motion.render-html` to render arbitrary HTML/CSS/JS — same Chromium-based pipeline, no slot machinery. Pass `--html` (inline) or `--htmlPath` plus dimensions / `aspectRatio` / `durationMs` / `frameRate`, get back an MP4 you can `project.add-motion-graphic` straight onto the timeline.
