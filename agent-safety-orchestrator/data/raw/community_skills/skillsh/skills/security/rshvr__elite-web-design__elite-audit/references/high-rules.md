# High Rules

Rules that should pass for production-quality sites. Failures indicate significant quality gaps.

## Table of Contents

1. [Accessibility Semantics](#accessibility-semantics)
2. [Touch & Interaction](#touch--interaction)
3. [Performance Loading](#performance-loading)
4. [Image Optimization](#image-optimization)
5. [Font Loading](#font-loading)
6. [Layout & Responsive](#layout--responsive)
7. [Forms & Validation](#forms--validation)
8. [Navigation](#navigation)
9. [Design System](#design-system)
10. [Conversion & Trust](#conversion--trust)

---

## Accessibility Semantics

### H-01: Alt text on meaningful images
**Check:** Images conveying information have descriptive alt text; decorative images have `alt=""`
**Fix:** → `elite-accessibility` / wcag-contrast.md
**Test:** Inspect images; verify alt attributes present and descriptive

### H-02: Decorative elements have aria-hidden="true"
**Check:** Grain overlays, animated backgrounds, ticker tracks have `aria-hidden="true"`
**Fix:** → `elite-accessibility` / inclusive-aesthetics.md
**Test:** Check decorative elements in DOM for aria-hidden

### H-03: Heading hierarchy sequential
**Check:** h1 → h2 → h3, no level skips
**Fix:** → `elite-accessibility` / wcag-contrast.md
**Test:** DevTools > Elements > outline headings; verify sequence

### H-04: Skip-to-content link present
**Check:** First focusable element is a skip link targeting `#main-content`
**Fix:** → `elite-accessibility` / focus-keyboard.md
**Test:** Tab from page start; verify skip link appears

### H-05: Form errors use aria-live
**Check:** Dynamic error messages have `aria-live="polite"` or `role="alert"`
**Fix:** → `elite-accessibility` / wcag-contrast.md + `elite-ux-strategy` / forms-feedback.md
**Test:** Trigger form error; check DOM for aria-live attribute

### H-06: Dynamic type / text scaling supported
**Check:** Page remains readable at 200% browser zoom; no overflow or truncation
**Fix:** → `elite-accessibility` / wcag-contrast.md
**Test:** Ctrl+= to 200% zoom; verify layout doesn't break

### H-07: Landmark roles present
**Check:** Page uses `<header>`, `<nav>`, `<main>`, `<footer>` semantic elements
**Fix:** → `elite-accessibility` / wcag-contrast.md
**Test:** Inspect page structure; verify landmark elements used (not generic divs)

### H-08: Language attribute set
**Check:** `<html lang="en">` (or appropriate language) is present
**Fix:** → `elite-accessibility` / wcag-contrast.md
**Test:** Check opening `<html>` tag for lang attribute

---

## Touch & Interaction

### H-09: Safe areas respected on notched devices
**Check:** Fixed elements use `env(safe-area-inset-*)` padding
**Fix:** → `elite-accessibility` / touch-interaction.md
**Test:** DevTools responsive mode with iPhone notch simulation

### H-10: tap-delay removed
**Check:** `touch-action: manipulation` applied globally or on interactive elements
**Fix:** → `elite-accessibility` / touch-interaction.md
**Test:** Grep CSS for `touch-action: manipulation`

### H-11: Hover not required for functionality
**Check:** All interactions work via tap; hover is enhancement only
**Fix:** → `elite-accessibility` / touch-interaction.md
**Test:** Test full site on touch device; verify nothing requires hover

### H-12: Destructive action spacing ≥ 16px
**Check:** Delete/cancel buttons have extra spacing from safe actions
**Fix:** → `elite-accessibility` / touch-interaction.md
**Test:** Measure gap between destructive and non-destructive buttons

---

## Performance Loading

### H-13: Below-fold images use loading="lazy"
**Check:** All images outside initial viewport have `loading="lazy"`
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Check `<img>` tags; verify lazy attribute on non-hero images

### H-14: Images have explicit dimensions
**Check:** All `<img>` have `width`/`height` attributes or CSS `aspect-ratio`
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Inspect images; verify dimensions prevent CLS

### H-15: Critical CSS inlined
**Check:** Above-fold styles are inline in `<head>`; full CSS loaded async
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** View source; check for inline `<style>` block in head

### H-16: Scripts deferred
**Check:** Non-critical scripts use `defer` or `async`
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Check `<script>` tags for defer/async attributes

### H-17: content-visibility on below-fold sections
**Check:** Heavy below-fold sections use `content-visibility: auto` with `contain-intrinsic-size`
**Fix:** → `elite-performance` / SKILL.md
**Test:** Grep CSS for content-visibility; verify on major sections

### H-18: ScrollTrigger.batch() for 20+ items
**Check:** Grids with 20+ items use `ScrollTrigger.batch()` instead of individual triggers
**Fix:** → `elite-performance` / animation-performance.md
**Test:** Count grid items; if ≥ 20, verify batch() used

### H-19: Third-party scripts async/defer
**Check:** Analytics, chat widgets, tracking loaded with async or defer
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Check third-party script tags

### H-20: No render-blocking resources
**Check:** Lighthouse shows zero render-blocking resources in critical path
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Lighthouse > Performance > Eliminate render-blocking resources

---

## Image Optimization

### H-21: AVIF/WebP format used
**Check:** Images use AVIF or WebP with JPEG fallback via `<picture>`
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Check image requests in Network tab; verify modern formats

### H-22: Hero image < 200KB
**Check:** Largest hero image compressed below 200KB
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Network tab; check hero image size

### H-23: SVG used for icons
**Check:** Icons are SVG, not raster PNG/JPEG
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Inspect icon elements; verify SVG tags

### H-24: Responsive images with srcset
**Check:** Images serving multiple sizes use `srcset` and `sizes` attributes
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Inspect `<img>` tags; verify srcset provides multiple resolutions

---

## Font Loading

### H-25: font-display: swap on all custom fonts
**Check:** Every @font-face or @fontsource import includes font-display: swap
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Check @font-face declarations or @fontsource imports

### H-26: Critical fonts preloaded
**Check:** Primary heading + body fonts preloaded with `<link rel="preload">`
**Fix:** → `elite-performance` / asset-optimization.md
**Test:** Check `<head>` for font preload links

### H-27: Variable fonts for 3+ weights
**Check:** If using 3+ weights of same family, variable font used instead of static
**Fix:** → `elite-performance` / asset-optimization.md + `elite-design-core` / typography.md
**Test:** Check font files; variable = 1 file, static = multiple

---

## Layout & Responsive

### H-28: Mobile-first breakpoints
**Check:** Media queries use `min-width` (mobile-first), not `max-width`
**Fix:** → `elite-layouts` / SKILL.md
**Test:** Grep CSS for `@media`; verify min-width pattern

### H-29: 100dvh for full-screen sections
**Check:** Full-viewport sections use `min-height: 100dvh` (not `100vh`)
**Fix:** → `elite-layouts` / editorial-patterns.md
**Test:** Grep CSS for `100vh`; verify replaced with dvh (with fallback)

### H-30: Fixed elements offset content
**Check:** Fixed headers/footers add padding to body/main to prevent content overlap
**Fix:** → `elite-layouts` / editorial-patterns.md
**Test:** Scroll to bottom; verify content not hidden behind fixed bar

### H-31: No horizontal scroll on mobile
**Check:** No content overflows viewport width on mobile
**Fix:** → `elite-layouts` / SKILL.md
**Test:** DevTools responsive mode (375px); verify no horizontal scrollbar

### H-32: Container max-width set
**Check:** Content has max-width constraint on desktop (e.g., 1320px or 1440px)
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Widen browser to 1920px+; verify content doesn't stretch edge-to-edge

### H-33: Bento grid collapses gracefully
**Check:** Multi-column bento layouts stack to single column on mobile
**Fix:** → `elite-layouts` / bento-grids.md
**Test:** DevTools responsive mode (375px); verify grid items stack vertically

---

## Forms & Validation

### H-34: Every input has visible label
**Check:** No placeholder-only labels; all inputs have associated `<label>` with `for` attribute
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Inspect form inputs; verify `<label for="id">` matches input id

### H-35: Error messages near field
**Check:** Validation errors appear directly below the relevant input
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Submit invalid form; verify errors positioned per-field

### H-36: Focus moves to first error
**Check:** After submit with errors, focus programmatically moves to first invalid field
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Submit form with multiple errors; verify focus jumps to first

### H-37: Error summary for multi-field forms
**Check:** Forms with multiple errors show summary at top with anchor links to each field
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Submit form with 3+ errors; verify summary appears

### H-38: Confirmation before destructive actions
**Check:** Delete, cancel subscription, etc. require confirmation dialog
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Trigger destructive action; verify dialog appears first

### H-39: Inline validation on blur
**Check:** Fields validate when user tabs away, not only on submit
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Fill field with invalid data, tab out; verify error appears immediately

---

## Navigation

### H-40: Bottom nav icon + text label
**Check:** Mobile bottom navigation items show both icon and text (not icon-only)
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** View on mobile; verify labels visible under icons

### H-41: Active nav state indicated
**Check:** Current page/section highlighted in navigation (color, weight, or indicator)
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Navigate to different pages; verify active item changes

### H-42: Back behavior preserves state
**Check:** Browser back button restores scroll position, filters, and form input
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Navigate forward, modify state, go back; verify state preserved

### H-43: Drawer escape affordances
**Check:** Mobile drawer dismisses via: close button, tap on scrim, Escape key
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Open drawer; test all three dismissal methods

### H-44: Focus on route change
**Check:** After SPA navigation, focus moves to main content region
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Navigate via links; check focus position after transition

---

## Design System

### H-45: Design tokens used (not magic values)
**Check:** Colors, spacing, fonts reference CSS custom properties, not hardcoded hex/px
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Grep components for hardcoded values; verify tokens used

### H-46: Spacing follows scale
**Check:** All margins/padding use consistent increments (4px/8px base)
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Inspect computed spacing; verify multiples of base unit

### H-47: Consistent elevation scale
**Check:** Shadows use defined scale tokens (not arbitrary values)
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Grep for `box-shadow`; verify only token values used

### H-48: One primary CTA per screen
**Check:** Each view has exactly one dominant call-to-action; secondaries are visually subordinate
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Scan each page; identify the one primary button

---

## Conversion & Trust

### H-49: Hero communicates value in 5 seconds
**Check:** A first-time visitor understands what the site does within 5 seconds
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Show to someone unfamiliar; ask "what does this do?" after 5s

### H-50: CTA visible above fold
**Check:** Primary call-to-action is visible without scrolling
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Load page; verify CTA visible in initial viewport

### H-51: Security/trust signals near checkout
**Check:** Payment pages show SSL badge, payment logos, or trust indicators
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Navigate to checkout; verify trust signals present

### H-52: Video testimonials have captions
**Check:** Testimonial videos include captions (85% watch muted)
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Play testimonial video; verify captions available

### H-53: Guest checkout available
**Check:** E-commerce allows purchase without creating an account
**Fix:** → `elite-ux-strategy` / mobile-conversion.md
**Test:** Walk through checkout; verify guest option exists
