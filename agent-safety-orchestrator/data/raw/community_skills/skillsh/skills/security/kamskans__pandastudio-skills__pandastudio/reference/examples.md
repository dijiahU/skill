# Recipes

End-to-end flows you can lift verbatim. Each is one shell session.

## 1. Render a 16:9 title card with a chosen style pack

```bash
# Pre-flight
pandastudio system.status --json | jq '.data.license'

# Pick a template + theme
pandastudio motion.list --json | jq '.data.templates[] | {id, name, slots: [.slots[].key]} | select(.id=="title-card-vox")'
pandastudio motion.themes --json | jq '.data.themes'

# Resolve the theme client-side: deep-merge theme.colors into slots
THEME_COLORS=$(pandastudio motion.themes --json | jq -c '.data.themes[] | select(.id=="mr-beast") | .colors')
SLOTS=$(jq -nc --argjson colors "$THEME_COLORS" \
  '$colors + {title:"How I Spent $10,000",subtitle:"in 24 hours"}')

# Render
JOB=$(pandastudio motion.generate \
  --templateId=title-card-vox \
  --aspectRatio=16:9 \
  --outputName=intro-card \
  --slots="$SLOTS" \
  --json | jq -r '.data.jobId')

# Wait + report
pandastudio job.wait --id="$JOB" --json | jq '.data.job | {status, result}'
```

## 2. Render a 9:16 (Shorts) lower-third

```bash
# Filter templates to ones that support 9:16
pandastudio motion.list --json | \
  jq '.data.templates[] | select(.aspectRatios | index("9:16")) | {id, name}'

# Pick one — say chapter-divider for a 9:16 chapter break — and
# inspect its slots
pandastudio motion.list --json | \
  jq '.data.templates[] | select(.id=="chapter-divider") | .slots'

# Render
JOB=$(pandastudio motion.generate \
  --templateId=chapter-divider \
  --aspectRatio=9:16 \
  --slots='{"chapterLabel":"Chapter","chapterNumber":"02","chapterTitle":"The Setup"}' \
  --json | jq -r '.data.jobId')

pandastudio job.wait --id="$JOB" --json | jq '.data.job.result.outputPath'
```

## 3. List recent exports and have the local LLM rewrite weak titles

```bash
# Pull exports needing better titles
pandastudio export.list --json | \
  jq -r '.data.exports[] | select(.generatedTitle | length < 20) | .id' | \
while read -r ID; do
  ENTRY=$(pandastudio export.get --id="$ID" --json)
  TRANSCRIPT=$(echo "$ENTRY" | jq -r '.data.entry.transcript.words[].text' | head -c 4000)

  NEW_TITLE=$(pandastudio llm.infer \
    --prompt="Rewrite this transcript's first 4000 chars as a punchy YouTube title (under 60 chars). Reply ONLY with the title, no quotes:\n\n$TRANSCRIPT" \
    --maxTokens=80 \
    --json | jq -r '.data.text' | head -1)

  pandastudio export.update --id="$ID" --patch="$(jq -nc --arg t "$NEW_TITLE" '{generatedTitle:$t}')"
done
```

## 4. Open a project for the user to edit visually

When the user asks "open my latest project," don't try to load it programmatically — there's no headless project-load verb. Just open the editor and tell them where to find it:

```bash
LATEST=$(pandastudio project.list --json | jq -r '.data.projects[0]')
echo "Opening editor — your latest project is: $(echo "$LATEST" | jq -r '.name') at $(echo "$LATEST" | jq -r '.path')"
pandastudio window.editor
```

## 5. Bulk-generate intros for a content series

```bash
# Read a CSV of episode titles, render a title card per row
while IFS=, read -r EP TITLE SUB; do
  SLOTS=$(jq -nc --arg t "$TITLE" --arg s "$SUB" '{title:$t, subtitle:$s}')
  JOB=$(pandastudio motion.generate \
    --templateId=title-card-vox \
    --aspectRatio=16:9 \
    --outputName="intro-ep$EP" \
    --slots="$SLOTS" \
    --json | jq -r '.data.jobId')

  RESULT=$(pandastudio job.wait --id="$JOB" --timeoutMs=120000 --json)
  echo "ep$EP → $(echo "$RESULT" | jq -r '.data.job.result.outputPath')"
done < episodes.csv
```

## 6. Probe the bundled FX library and pick one matching a vibe

```bash
pandastudio asset.list-fx --json | jq '.data.fx[] | {id, title, blendMode, durationSeconds}'

# Resolve a chosen id to its on-disk path (so you can hand it to ffmpeg
# or include it in a project.save payload).
pandastudio asset.resolve --id=light-leak-warm --json | jq '.data.path'
```

## 7. Compose a full edit from scratch (the v1.9.1 flow)

The end-to-end "I gave you 2 videos, give me an edited project" workflow.

```bash
# Step 1: create a project pre-loaded with the source clips. FFmpeg
# probes durations for you.
P=$(pandastudio project.new \
  --name="My Edit" \
  --withMedia='["/Users/me/Downloads/clip-a.mp4","/Users/me/Downloads/clip-b.mp4"]' \
  --json)
ID=$(echo "$P" | jq -r '.data.id')

# Step 2: render an intro title card via motion.generate
INTRO_JOB=$(pandastudio motion.generate \
  --templateId=title-card-vox \
  --slots='{"title":"My Edit","subtitle":"a recap"}' \
  --aspectRatio=16:9 \
  --outputName=intro \
  --json | jq -r '.data.jobId')

INTRO=$(pandastudio job.wait --id="$INTRO_JOB" --timeoutMs=120000 --json)
INTRO_PATH=$(echo "$INTRO" | jq -r '.data.job.result.outputPath')
INTRO_DUR=$(echo "$INTRO" | jq -r '.data.job.result.durationMs')

# Step 3: drop the intro at t=0
pandastudio project.add-motion-graphic \
  --id="$ID" --file="$INTRO_PATH" --durationMs="$INTRO_DUR" --atMs=0

# Step 4: add a lower-third intro 5 seconds in
pandastudio project.add-lower-third \
  --id="$ID" --content="Kamal" --subtitle="Founder" --atMs=5000

# Step 5: drop a film-burn FX between the two source clips
# (assume clip-a is 30s; transition is at the cut)
pandastudio project.add-fx \
  --id="$ID" --fxId=film-burn --atMs=30000

# Step 6: open the editor for the user to take over
pandastudio window.preview --id="$ID"

echo "Project ready: id=$ID"
echo "User can find it at: $(pandastudio project.show --id=$ID --json | jq -r .data.path)"
```

The user can now see + tweak everything in the editor. The agent and the user are working on the same project file — `expectedRevision` keeps them from clobbering each other.

## 8. Round-trip: agent edits, user takes over, agent continues

```bash
# Agent's first pass
P=$(pandastudio project.read --id="$ID" --json)
REV=$(echo "$P" | jq -r '.data.project.revision')

# User opens project in editor and makes changes (manual). Editor's
# autosave bumps the revision. The agent's $REV is now stale.

# Agent comes back later, tries to add another lower-third
RESULT=$(pandastudio project.add-lower-third \
  --id="$ID" --content="More" --atMs=10000 \
  --expectedRevision="$REV" --json)

# If conflict: re-read and retry
if [ "$(echo "$RESULT" | jq -r '.details.code')" = "revision_conflict" ]; then
  # Re-read with the actual on-disk revision
  P=$(pandastudio project.read --id="$ID" --json)
  REV=$(echo "$P" | jq -r '.data.project.revision')
  pandastudio project.add-lower-third \
    --id="$ID" --content="More" --atMs=10000 \
    --expectedRevision="$REV" --json
fi
```

Always check for `revision_conflict` after any save / add-* / remove-* / split-* call. The `details.expected` and `details.actual` tell you how far ahead the on-disk version is.

## 9. THE big one — full agentic edit + export

This is the v1.9.1 flagship workflow: agent gets a folder of source clips, returns a polished, exported MP4 ready to upload. End-to-end, headless, no human in the editor.

```bash
# Step 1: Create a project pre-loaded with the source clips. FFmpeg
# probes durations automatically.
P=$(pandastudio project.new \
  --name="Q4 Recap" \
  --withMedia='["/Users/me/Downloads/clip-a.mp4","/Users/me/Downloads/clip-b.mp4"]' \
  --json)
ID=$(echo "$P" | jq -r '.data.id')
echo "Project: $ID"

# Step 2: Transcribe every clip (Parakeet TDT, ~real-time)
JOB=$(pandastudio transcript.transcribe --id=$ID --json | jq -r '.data.jobId')
pandastudio job.wait --id=$JOB --timeoutMs=600000 --json | jq '.data.job.status'

# Step 3: Clean up the audio (DeepFilter denoising)
JOB=$(pandastudio audio.clean --id=$ID --json | jq -r '.data.jobId')
pandastudio job.wait --id=$JOB --timeoutMs=600000 --json | jq '.data.job.status'

# Step 4: Auto-trim filler words and back-to-back repeats
pandastudio transcript.remove-fillers --id=$ID --json | jq '.data'
# → { fillersDeleted: 14, repeatsDeleted: 3, trimsAdded: 11 }

# Step 5: Surgical phrase deletion — find and drop a flubbed take
WORDS=$(pandastudio transcript.search --id=$ID --query="actually wait let me restart" --json \
  | jq -c '[.data.matches[].wordIds | .[]]')
[ "$WORDS" != "[]" ] && pandastudio transcript.delete-words --id=$ID --wordIds="$WORDS" --json

# Step 6: Find a "click here" moment and drop a zoom on it
ZOOM_AT=$(pandastudio transcript.search --id=$ID --query="click on the menu" --json \
  | jq -r '.data.matches[0].startMs // empty')
[ -n "$ZOOM_AT" ] && pandastudio project.add-zoom --id=$ID \
  --atMs=$ZOOM_AT --durationMs=2000 --depth=4

# Step 7: Render an intro title card and drop it at t=0
INTRO_JOB=$(pandastudio motion.generate \
  --templateId=title-card-vox \
  --slots='{"title":"Q4 in 90 seconds","subtitle":"the highlights"}' \
  --aspectRatio=16:9 --outputName=intro --json | jq -r '.data.jobId')
INTRO=$(pandastudio job.wait --id=$INTRO_JOB --timeoutMs=120000 --json)
pandastudio project.add-motion-graphic --id=$ID \
  --file="$(echo $INTRO | jq -r '.data.job.result.outputPath')" \
  --durationMs="$(echo $INTRO | jq -r '.data.job.result.durationMs')" \
  --atMs=0

# Step 8: Add a film-burn FX between the two source clips
CLIP_A_DUR=$(pandastudio project.read --id=$ID --json | jq '.data.project.mainTrack.clips[0].sourceDurationMs')
pandastudio project.add-fx --id=$ID --fxId=film-burn --atMs=$CLIP_A_DUR

# Step 9: Add captions in the bold-yellow MrBeast style
pandastudio caption.toggle --id=$ID --enabled=true
pandastudio caption.set-template --id=$ID --templateId=bold
pandastudio caption.set-style --id=$ID --highlightColor="#FFD60A" --positionY=85

# Step 10: Apply a cinematic preset
pandastudio project.set-style --id=$ID --padding=40 --shadowIntensity=30 \
  --borderRadius=20 --motionBlurAmount=15
pandastudio project.set-wallpaper --id=$ID --wallpaper=gradient-night

# Step 11: Show the user what's about to render (live preview window)
pandastudio window.preview --id=$ID
echo "Preview opened — give the user a moment to scrub."

# Step 12: EXPORT. Routes through the same Tier-3 renderer the UI uses
# (reusing an open editor on the project, or spawning a hidden one).
EXPORT_JOB=$(pandastudio export.start --id=$ID --quality=high --json \
  | jq -r '.data.jobId')
RESULT=$(pandastudio job.wait --id=$EXPORT_JOB --timeoutMs=900000 --json)
MP4=$(echo "$RESULT" | jq -r '.data.job.result.outputPath')
echo "✓ Exported: $MP4"

# Step 13: Generate YouTube metadata (local LLM, project-aware)
TITLE=$(pandastudio llm.generate-title --id=$ID --json | jq -r '.data.title')
DESC=$(pandastudio llm.generate-description --id=$ID --json | jq -r '.data.description')
TIMESTAMPS=$(pandastudio llm.generate-timestamps --id=$ID --json | jq '.data.timestamps')

cat <<EOF

🎬 Ready to upload to YouTube
Video:        $MP4
Title:        $TITLE
Description:  $DESC

Chapters:
$(echo "$TIMESTAMPS" | jq -r '.[] | "  \((.timeMs/1000) | floor | (./ 60 | floor) | tostring + ":" + (. % 60 | tostring | if length == 1 then "0" + . else . end))  \(.label)"' 2>/dev/null || echo "$TIMESTAMPS")
EOF
```

13 commands, fully unattended, produces a polished MP4 + ready-to-paste YouTube metadata. The agent and the user can also work the same project in parallel (revision-conflict-detected) — at any point, the user can open it in the editor and tweak.

## Pattern: degrade gracefully when license-gated

```bash
STATUS=$(pandastudio system.status --json)
GATED=$(echo "$STATUS" | jq -r '.data.license.automationGated')
if [ "$GATED" = "true" ]; then
  echo "PandaStudio's CLI is license-gated. Open the app, go to Settings → License, and activate. I can re-try once you're done."
  exit 1
fi
# … real work …
```
