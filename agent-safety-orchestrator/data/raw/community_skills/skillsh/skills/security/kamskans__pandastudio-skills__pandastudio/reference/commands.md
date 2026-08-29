# Command reference

The canonical list lives at `pandastudio commands --json` (run it — the registry grows). This file is a snapshot for offline reading.

Every command takes args as `--key=value` flags. Object/array values must be JSON: `--slots='{"a":1}'`.

## system.*

| Command | Args | Purpose |
|---|---|---|
| `system.status` | — | App version + license block. Always run this first. |
| `system.list` | — | List every available `verb.noun` with summaries. Same as `pandastudio commands`. |
| `system.ping` | — | `{ pong: true }`. Heartbeat. |
| `system.echo` | `payload` (any) | Echo for transport debugging. |

## project.*

Project files are JSON on disk under the user's recordings dir. All paths are validated to live inside that dir — out-of-tree absolute paths are rejected. Most commands accept either `--id=<uuid>` (preferred — stable across renames) or `--path=...`.

### Lookup + lifecycle

| Command | Args | Purpose |
|---|---|---|
| `project.list` | `allWorkspaces` (bool, default false) | Projects in the active workspace (or all, with `allWorkspaces=true`), newest-first: `{ id, revision, path, name, clipCount, modifiedAt, createdAt, sizeBytes, workspaceId }`. Top-level response also returns `currentWorkspaceId`. |
| `project.locate` | `id` (req) | Look up a project's owning workspace WITHOUT reading the body. Returns `{ id, filePath, workspaceId, workspaceName, isInActiveWorkspace }`. Pre-flight check before any edit/export/publish on a bare project id — prevents publishing to the wrong client's YouTube channel. See SKILL.md "Workspaces" §"When given a project id with no other context". |
| `project.read` | `id` \| `path` | Full JSON. **Pass back `project.revision` as `expectedRevision` on save.** |
| `project.show` | `id` \| `path` (or no args) | Resolve to path + summary. With no args, returns recordingsDir + userDataDir. |
| `project.new` | `name` (req), `withMedia` (string\[\] or comma-list of paths) | Create v3 project; if `withMedia` set, FFmpeg-probes each video and adds it as a clip. |
| `project.save` | `id` \| `path`, `project` (req), `expectedRevision` (optional) | Overwrite. Returns `{ ok:false, details:{ code:"revision_conflict" } }` if expectedRevision is stale. |
| `project.delete` | `id` \| `path` | Permanent delete (no trash). |
| `project.open` | `id` \| `path` (optional) | Open editor focused on this project. |

### Edit primitives (no schema knowledge required)

All accept `id` or `path`, plus optional `expectedRevision` for conflict-safe writes. Returns the updated `project` (with bumped `revision`).

| Command | Args | Purpose |
|---|---|---|
| `project.add-clip` | `media` (path), `atIndex` (optional, 0 = prepend) | Insert a video clip on the main track. Probes duration. Default: append at end. |
| `project.remove-clip` | `clipId` | Drop a clip by id. |
| `project.move-clip` | `clipId`, `toIndex` | Reorder a clip on the main track. Project-level regions automatically migrate to follow their original clips, so zooms/trims/etc. stay attached to the same content after the reorder. |
| `project.split-clip` | `clipId`, `atSourceMs` | Split a clip in two at a position in its source time. |
| `project.add-motion-graphic` | `file`, `durationMs`, `atMs` (optional, defaults to end-of-timeline) | Drop an MP4 (typically from `motion.generate`) as a media-overlay region. |
| `project.add-fx` | `fxId` (bundled) OR `src` (custom URL/path), `atMs`, `durationMs` (optional) | Drop an FX overlay. Bundled FX inherits blend mode + opacity from the manifest. |
| `project.add-lower-third` | `content` (req), `subtitle`, `atMs` (req), `durationMs`, `designType`, `accentColor` | Drop a lower-third name plate. |
| `project.add-zoom` | `atMs`, `durationMs`, `depth` (1-6, default **2** = 1.5× soft modern), `focusX/Y` (0-1), `soundUrl` (default `bundled:sound/swoosh-fast`) | Highlight a UI moment with a zoom region. Ships with a default swoosh SFX; pass `soundUrl=none` to silence. |
| `project.add-clip-transform-region` | `startMs`, `endMs`, `preset` (`cam-bottom-half` / `cam-top-half` / `cam-right-portrait` / `cam-left-portrait` / `cam-bottom-right-quarter` / `cam-bottom-left-quarter`), `transitionMs` (default 320) | Time-bounded layout transform on the main video clip — shrink camera to make room for a motion graphic during an explainer beat. **Camera-only / user-uploaded recordings only — never on screen recordings.** See video-authoring §5b. |
| `project.add-trim` | `startMs`, `endMs` | Cut a section the exporter skips. |
| `project.add-speed` | `startMs`, `endMs`, `speed` (0.25/0.5/0.75/1.25/1.5/1.75/2) | Speed up or slow down a span. |
| `project.add-annotation` | `startMs`, `endMs`, `type` (text/figure), `text`, `x/y/width/height` (%) | Drop text or figure annotation on canvas. |
| `project.set-aspect-ratio` | `ratio` (16:9/9:16/1:1/4:3/3:4) | Switch project aspect ratio. |
| `project.set-wallpaper` | `wallpaper` | Set project background wallpaper id or 'none'. |
| `project.set-style` | `padding/shadowIntensity/borderRadius/motionBlurAmount/showBlur` | Bulk-set cinematic style preset fields. |

## asset.*

Bundled sound effects + FX overlays that ship inside the app installer.

| Command | Args | Purpose |
|---|---|---|
| `asset.list-sounds` | — | Every bundled sound: `{ id, name, category, absolutePath }`. |
| `asset.list-fx` | — | Every FX overlay: `{ id, title, blendMode, defaultOpacity, durationSeconds, defaultSoundId, absolutePath }`. |
| `asset.resolve` | `id` (string, required) | Resolve a bundled-asset id to its on-disk path. Returns `{ kind: "sound" \| "fx", path }`. |

## motion.*

Motion-graphic templates (title cards, lower thirds, end screens, etc.) with optional style packs.

| Command | Args | Purpose |
|---|---|---|
| `motion.list` | — | Every template: `{ id, name, slots, defaults, aspectRatios, durationMs, fileUrl }`. |
| `motion.themes` | — | Every style pack: `{ id, name, swatch, colors }`. |
| `motion.generate` | `templateId` (string, required), `slots` (object, required), `aspectRatio` (`16:9` \| `9:16` \| `1:1`), `outputName` (string) | **Async.** Returns `{ jobId, outputPath }`. Poll `job.get` or block on `job.wait`. |
| `motion.render-html` | `html` OR `htmlPath` (one required), `aspectRatio` (`16:9`/`9:16`/`1:1`) or explicit `width`+`height`, `durationMs` (default 2500), `frameRate` (default 30), `outputName` | **Async.** Render arbitrary HTML/CSS/JS to MP4 — escape hatch when the 19 bundled templates don't fit. Returns `{ jobId, outputPath }`. |

Theme application: pull `motion.themes`, find the theme the user wants, merge `theme.colors` into `slots` before sending. The backend doesn't know about themes — they're a pre-render layer.

## media.*

Project-agnostic media generation. Currently a single verb wrapping Replicate gpt-image-2 for B-roll, concept stills, reference frames.

| Command | Args | Purpose |
|---|---|---|
| `media.generate-image` | `prompt` (required), `aspectRatio` (`1:1` \| `3:2` (default) \| `2:3`), `quality` (`low` \| `medium` (default) \| `high`), `referenceImagePath` (path/URL, optional), `outputName` (slug, optional) | Generate one image. Returns `{ imagePath, prompt, aspectRatio, predictionId }`. Requires the user's Replicate API key (Settings → Integrations). The canonical B-roll workflow is `media.generate-image` → `motion.render-html` (Ken-Burns + vignette wrap) → `project.add-motion-graphic` — see SKILL.md "B-roll generation". For 16:9 video, generate `3:2` and crop in the wrap; for 9:16, generate `2:3`. |

## export.*

The export library (MyExports view). Read + patch only — there's no `export.start` yet; new exports require the editor.

| Command | Args | Purpose |
|---|---|---|
| `export.list` | — | Every export entry, newest-first. |
| `export.get` | `id` (string, required) | Single entry by id. |
| `export.update` | `id` (string, required), `patch` (object, required) | Patch entry fields (e.g. `generatedTitle`, `generatedDescription`). |
| `export.delete` | `id` (string, required) | Delete the library row (does NOT delete the underlying MP4 on disk). |

## transcript.* (v1.9.1)

The editorial primitive that makes PandaStudio PandaStudio. Every operation that "deletes words" actually adds trim regions the export pipeline skips.

| Command | Args | Purpose |
|---|---|---|
| `transcript.transcribe` | `id` \| `path`, `clipId` (optional) | **Async.** Run Parakeet TDT 0.6B on each clip's audio. Returns `{ jobId }`. |
| `transcript.get` | `id` \| `path` | Merged edited-time transcript: every word with `id`, `text`, `startMs`, `endMs`. Use `id`s as input to `delete-words`. |
| `transcript.delete-words` | `id` \| `path`, `wordIds` (string[]) | Translate word IDs into trim regions. Coalesces adjacent deletions. |
| `transcript.remove-fillers` | `id` \| `path`, `includeRepeats` (bool, default true) | Auto-detect filler words ('um','uh','you know',…) plus back-to-back repeats. Bulk-trims them. |
| `transcript.search` | `id` \| `path`, `query` | Find a phrase across the merged transcript. Returns matches with their word IDs. |

## audio.* (v1.9.1)

| Command | Args | Purpose |
|---|---|---|
| `audio.clean` | `id` \| `path`, `clipId` (optional) | **Async.** Run DeepFilter denoising on each clip; writes a sibling `.cleaned.wav` and points `clip.cleanedAudioPath` at it. |

## caption.* (v1.9.1)

| Command | Args | Purpose |
|---|---|---|
| `caption.toggle` | `id` \| `path`, `enabled` (bool) | Show/hide captions for the whole project. |
| `caption.set-template` | `id` \| `path`, `templateId` | One of: `classic, modern, minimal, bold, spotlight, boxed, neon, colored`. |
| `caption.set-style` | `id` \| `path`, color/font/stroke/positionY/wordsPerLine overrides | Per-template style overrides. |

## export.* (v1.9.1 — the centerpiece)

| Command | Args | Purpose |
|---|---|---|
| `export.start` | `id` \| `path`, `outputPath` (optional), `quality` (`draft \| standard \| high \| ultra`) | **Async.** Render the project to MP4 via the same Tier-3 PixiJS pipeline the editor's Export Video button uses (v1.24+). Reuses an open editor if it's already on the target project, otherwise spawns a hidden editor window for the duration of the render. Returns `{ jobId, outputPath }`. Honours every region/style/caption/FX/lower-third/motion-graphic in the project. |
| `export.list` | — | Every entry in the export library, newest-first. |
| `export.get` | `id` | Read a single library entry. |
| `export.update` | `id`, `patch` | Patch fields like generatedTitle. |
| `export.delete` | `id` | Delete library row (NOT the underlying MP4). |

## llm.*

PandaStudio bundles Gemma 4 E2B (~2B params). Good for summarisation / classification / short structured output. Bad for long prose or visuals.

| Command | Args | Purpose |
|---|---|---|
| `llm.status` | — | `{ downloaded, downloading, path, size }`. |
| `llm.infer` | `prompt` (string, required), `maxTokens` (number, default 256) | One-shot inference. Returns `{ text }`. |
| `llm.generate-title` | `id` \| `path`, `maxChars` (default 70) | **Project-aware.** Reads the merged transcript, returns a YouTube-ready title. |
| `llm.generate-description` | `id` \| `path`, `maxChars` (default 400) | **Project-aware.** Returns a 3-5 sentence description. |
| `llm.generate-timestamps` | `id` \| `path`, `maxChapters` (default 8) | **Project-aware.** Returns `[{ timeMs, label }, …]` chapter markers. |

## job.*

| Command | Args | Purpose |
|---|---|---|
| `job.get` | `id` (string, required) | Snapshot of one job's status + progress + result. |
| `job.list` | — | Every job in memory (last hour after completion). |
| `job.wait` | `id` (string, required), `timeoutMs` (number, default 60_000, max 300_000) | Block server-side until terminal state. Returns `{ job, timedOut? }`. **Prefer this over client-side polling.** |

## preview.* (v1.9.2)

Floating, always-on-top overlay window that mounts the editor's WYSIWYG canvas. ~1-2s boot, same render code path as the in-app preview pane. Singleton — second `preview.show` reuses the existing window.

| Command | Args | Purpose |
|---|---|---|
| `preview.show` | `id` \| `path`, `atMs` (optional), `autoplay` (bool, default true), `width` (default 800), `height` (default 450) | Open or refocus the preview overlay on a project. |
| `preview.seek` | `atMs` | Move the playhead in the open overlay. |
| `preview.hide` | — | Close the overlay. |
| `preview.list` | — | `{ open, size?, position?, url? }` — what's visible right now. |

## window.*

| Command | Args | Purpose |
|---|---|---|
| `window.editor` | — | Open (or focus) the editor window. |
| `window.home` | — | Open (or focus) the home/dashboard window. |
| `window.exports` | — | Open (or focus) the MyExports library window. |
| `window.preview` | `id` \| `path` (optional) | **v1.9.1** — open the editor focused on a project so the user can SEE what an agent is doing visually. No rendering cost beyond the existing live preview pane. Chromeless overlay variant ships in v1.9.2. |
| `window.focus` | — | Bring the front-most app window to the foreground. (Available even when license-gated.) |
| `window.list` | — | Every open window: `{ id, title, url, visible, focused }`. |
