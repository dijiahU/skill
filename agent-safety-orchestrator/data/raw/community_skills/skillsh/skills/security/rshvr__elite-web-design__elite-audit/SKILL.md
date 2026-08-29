---
name: elite-audit
description: |
  UI/UX quality audit for web implementations. Run after building to verify accessibility, performance, animation quality, touch interaction, forms, navigation, typography, and brand consistency. Checks ~190 rules organized by priority (CRITICAL, HIGH, MEDIUM). When a rule fails, triggers the relevant teaching skill for remediation. Use when asked about: audit, review, check, QA, pre-launch, quality check, accessibility audit, performance audit, verify, validate, or "is this ready to ship". This skill orchestrates fixes by invoking elite-accessibility, elite-performance, elite-gsap, elite-css-animations, elite-layouts, elite-design-core, elite-ux-strategy, or elite-brand-design as needed.
---

# Elite Audit

UI/UX quality audit orchestrator. ~190 rules across 8 categories, prioritized CRITICAL → HIGH → MEDIUM. Failures trigger the relevant teaching skill for guided remediation.

## Quick Reference

| File | Priority | Purpose |
|------|----------|---------|
| [critical-rules.md](references/critical-rules.md) | CRITICAL | Must-pass before any deployment |
| [high-rules.md](references/high-rules.md) | HIGH | Should-pass for production quality |
| [medium-rules.md](references/medium-rules.md) | MEDIUM | Polish and best practices |
| [pre-launch-checklist.md](references/pre-launch-checklist.md) | Condensed | Binary go/no-go checklist |

---

## Audit Modes

### Full Audit

All rules, CRITICAL → HIGH → MEDIUM. Use before launch.

Run every rule across all 8 categories. Start with CRITICAL blockers, then HIGH quality gates, then MEDIUM polish. A full audit covers ~190 checks and ensures the implementation meets elite standards end-to-end.

### Quick Audit

CRITICAL rules only (~43 checks). Use for fast sanity check.

Covers the minimum bar: contrast, focus, touch targets, reduced motion, Core Web Vitals, GPU-only animations, viewport meta, visible labels, and design tokens. Takes minutes, not hours. Good for mid-sprint gut checks.

### Focused Audit

Single category. Use for targeted review (e.g., "audit accessibility only").

Load only the relevant checklist section below and the matching reference file. Useful after making changes in one area — verify that category passes without re-running everything.

---

## The Audit Loop

The audit follows a strict feedback cycle:

```
1. Check rules by priority (CRITICAL first)
2. For each failure → state the rule, cite the source, name the fix skill
3. Invoke the teaching skill for implementation guidance
4. Fix the issue
5. Re-check the failed rule
6. Continue until all CRITICAL and HIGH rules pass
7. MEDIUM rules are recommendations, not blockers
```

**Important**: Never skip straight to fixing. Always state the rule ID, the evidence of failure, and which skill provides the remediation pattern. This creates an auditable trail.

---

## Quick Checklists

Condensed inline checklists for rapid scanning. Each item is binary pass/fail. For full rule details and implementation guidance, load the corresponding reference file.

### Accessibility

- [ ] Text contrast >= 4.5:1 (large text >= 3:1)
- [ ] Focus indicator visible on all interactive elements (2px + 2px offset)
- [ ] Touch targets >= 44x44px with >= 8px spacing
- [ ] `prefers-reduced-motion` handled on every animation
- [ ] Meaningful images have descriptive alt text; decorative have `alt=""`
- [ ] Heading hierarchy sequential (h1 -> h2 -> h3, no skips)
- [ ] Color not the only means of conveying information
- [ ] Skip-to-content link is first focusable element

### Performance

- [ ] LCP <= 2.5s, INP <= 200ms, CLS <= 0.1
- [ ] Only `transform`, `opacity`, `filter` animated (GPU-only)
- [ ] Initial JS < 100KB, CSS < 50KB (gzipped)
- [ ] Images use AVIF/WebP with explicit dimensions
- [ ] Below-fold content lazy loaded
- [ ] `font-display: swap` on all custom fonts
- [ ] `gsap.context()` used with `revert()` on cleanup

### Animation

- [ ] Duration: 100-300ms micro, 300-500ms reveals, never >800ms
- [ ] Easing: ease-out for entering, ease-in for exiting, never linear for UI
- [ ] Exit animations 60-70% of enter duration
- [ ] Animations interruptible (no blocking user input)
- [ ] Scale feedback 0.95-1.05 on press (not larger)
- [ ] No opacity lingering below 0.2
- [ ] Modal animates from trigger source

### Layout

- [ ] `<meta name="viewport" content="width=device-width, initial-scale=1">` (no user-scalable=no)
- [ ] Mobile-first breakpoints (min-width, not max-width)
- [ ] `100dvh` used instead of `100vh` for full-screen sections
- [ ] Fixed elements reserve safe padding for content
- [ ] Body text max-width 65ch
- [ ] Safe areas respected (`env(safe-area-inset-*)`)

### Forms & Feedback

- [ ] Every input has a visible label (not placeholder-only)
- [ ] Errors appear below the field with cause + fix
- [ ] Focus moves to first error on submit failure
- [ ] Toast uses `aria-live="polite"`, auto-dismisses 3-5s
- [ ] Destructive actions require confirmation dialog
- [ ] Disabled state: opacity 0.4 + `cursor: not-allowed` + semantic attribute
- [ ] Multi-step forms show progress indicator

### Navigation

- [ ] Bottom nav <= 5 items with icon + text label
- [ ] Active state visually indicated (color, weight, or indicator)
- [ ] Back navigation predictable (preserves scroll/state)
- [ ] Modals not used for primary navigation flows
- [ ] Breadcrumbs for 3+ level hierarchies
- [ ] Focus moves to main content on route change

### Typography & Color

- [ ] Type scale with consistent ratio (1.25 recommended)
- [ ] Fluid sizes via `clamp()` for headings
- [ ] Line-height 1.5+ for body text
- [ ] Semantic color tokens (not raw hex in components)
- [ ] `font-variant-numeric: tabular-nums` for data/prices

### Brand Consistency

- [ ] Design tokens defined (not magic values)
- [ ] Spacing follows 4/8px scale
- [ ] One primary CTA per screen
- [ ] SVG icons (never emoji)
- [ ] Consistent icon stroke width and style
- [ ] hover/pressed/disabled states visually distinct

---

## Remediation Map

When a rule fails, invoke the corresponding teaching skill. The skill provides implementation patterns, code examples, and verification steps.

| Failed Category | Invoke Skill | Key Reference |
|-----------------|-------------|---------------|
| Contrast / Color a11y | `elite-accessibility` | wcag-contrast.md |
| Focus / Keyboard | `elite-accessibility` | focus-keyboard.md |
| Touch targets / Gestures | `elite-accessibility` | touch-interaction.md |
| Reduced motion | `elite-accessibility` | reduced-motion.md |
| Core Web Vitals | `elite-performance` | SKILL.md (budget table) |
| GPU properties / Animation perf | `elite-performance` | animation-performance.md |
| Bundle size / Loading | `elite-performance` | asset-optimization.md |
| GSAP cleanup / Context | `elite-gsap` | utility-library.md |
| Duration / Easing / UX timing | `elite-gsap` | utility-library.md (Animation UX Rules) |
| CSS effects / Micro-interactions | `elite-css-animations` | visual-effects.md |
| Scroll-driven animations | `elite-css-animations` | scroll-driven-api.md |
| Navigation patterns | `elite-ux-strategy` | navigation-patterns.md |
| Forms / Feedback / Toasts | `elite-ux-strategy` | forms-feedback.md |
| Mobile conversion | `elite-ux-strategy` | mobile-conversion.md |
| Social proof / Trust | `elite-ux-strategy` | social-proof-trust.md |
| Layout / Responsive / Grid | `elite-layouts` | editorial-patterns.md |
| Typography / Type scale | `elite-design-core` | typography.md |
| Color tokens / Design system | `elite-design-core` | design-tokens.md |
| Charts / Data viz | `elite-design-core` | data-visualization.md |
| Brand identity / Consistency | `elite-brand-design` | SKILL.md |

### How to Use the Remediation Map

1. Identify the failed rule's category from the quick checklists above
2. Find the matching row in the remediation map
3. Load the teaching skill (e.g., `/skill:elite-accessibility`)
4. Navigate to the key reference file within that skill
5. Follow the implementation pattern to fix the issue
6. Re-run the specific check to verify the fix

---

## Testing Tools

Quick reference of tools to verify audit rules. Use these to gather evidence for pass/fail decisions.

### Contrast

- **WebAIM Contrast Checker** — paste foreground/background colors, get WCAG ratio
- **DevTools CSS Overview** — Chrome > More Tools > CSS Overview > Colors tab shows all contrast issues
- **axe DevTools** — automated contrast scanning across the entire page

### Performance

- **Lighthouse** — DevTools > Lighthouse tab, or `npx lighthouse <url> --view`
- **DevTools Performance panel** — record interactions, check for long tasks and layout shifts
- **WebPageTest** — multi-device, multi-location real-world performance testing
- **`npx unlighthouse`** — audit every page on the site in one run

### Animation

- **DevTools Rendering** — enable Paint Flashing to see repaints (red = bad)
- **DevTools FPS meter** — Rendering > Frame Rendering Stats for live FPS overlay
- **DevTools Animations panel** — inspect timeline, duration, easing of running animations
- **DevTools Layers panel** — verify animated elements are on their own compositor layer

### Accessibility

- **axe DevTools** — browser extension, catches ~57% of WCAG issues automatically
- **WAVE** — visual overlay showing errors, alerts, and structural elements
- **VoiceOver** (macOS) — manual screen reader testing, Cmd+F5 to toggle
- **NVDA** (Windows) — free screen reader for Windows testing
- **Accessibility Insights** — Microsoft tool with tab-stop visualization

### Layout

- **DevTools Device Toolbar** — responsive mode with device presets
- **DevTools device emulation** — test notch/safe-area behavior on iOS/Android frames
- **BrowserStack / LambdaTest** — real device testing across OS and browser combinations

### Bundle

- **`npx vite-bundle-visualizer`** — treemap of Vite output bundles
- **source-map-explorer** — `npx source-map-explorer dist/assets/*.js`
- **bundlephobia.com** — check npm package sizes before adding dependencies
- **Import Cost** (VS Code extension) — inline size display for imports

---

## Audit Report Format

When reporting audit results, use this structure:

```
## Audit Report — [Project Name]
**Mode**: Full / Quick / Focused ([category])
**Date**: YYYY-MM-DD

### CRITICAL ([X] passed / [Y] total)
- PASS: [rule description]
- FAIL: [rule description] → Fix: [skill name] > [reference file]

### HIGH ([X] passed / [Y] total)
- PASS: [rule description]
- FAIL: [rule description] → Fix: [skill name] > [reference file]

### MEDIUM ([X] passed / [Y] total)
- PASS: [rule description]
- REC: [rule description] → Suggested: [skill name] > [reference file]

### Verdict
- CRITICAL: [all pass / N failures — BLOCKED]
- HIGH: [all pass / N failures — needs work]
- MEDIUM: [X recommendations]
- Ship: YES / NO
```

CRITICAL failures block deployment. HIGH failures should be resolved but are not hard blockers for staging. MEDIUM items are recommendations for polish.

---

## Common Audit Patterns

### Pattern: Post-Build Audit

After completing a feature or page build:

1. Run **Quick Audit** (CRITICAL only) to catch blockers immediately
2. Fix any CRITICAL failures using the remediation map
3. Run **Full Audit** before requesting review
4. Document findings in the audit report format above

### Pattern: PR Review Audit

When reviewing a pull request:

1. Run **Focused Audit** on the categories touched by the PR
2. Check that no existing passing rules have regressed
3. Flag new CRITICAL/HIGH failures as blocking review comments
4. Flag MEDIUM items as non-blocking suggestions

### Pattern: Pre-Launch Audit

Before deploying to production:

1. Run **Full Audit** across all categories
2. Verify all CRITICAL rules pass (use [pre-launch-checklist.md](references/pre-launch-checklist.md))
3. Verify all HIGH rules pass
4. Document any accepted MEDIUM exceptions with rationale
5. Final verdict: Ship YES requires zero CRITICAL and zero HIGH failures
