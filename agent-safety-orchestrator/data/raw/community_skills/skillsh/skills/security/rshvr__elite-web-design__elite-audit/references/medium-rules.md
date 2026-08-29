# Medium Rules

Polish and best practices. These improve perceived quality but are not deployment blockers.

## Table of Contents

1. [Animation UX Timing](#animation-ux-timing)
2. [Animation Production Quality](#animation-production-quality)
3. [Typography Comfort](#typography-comfort)
4. [CSS Visual Effects](#css-visual-effects)
5. [Form Feedback](#form-feedback)
6. [Navigation Polish](#navigation-polish)
7. [Mobile UX](#mobile-ux)
8. [Social Proof & Trust](#social-proof--trust)
9. [Brand Consistency](#brand-consistency)
10. [Design Philosophy](#design-philosophy)
11. [Copywriting](#copywriting)
12. [Testing & Benchmarks](#testing--benchmarks)
13. [Data Visualization](#data-visualization-if-applicable)
14. [Empty States](#empty-states)

---

## Animation UX Timing

### M-01: Micro-interaction duration 100-200ms
**Check:** Button press, toggle, icon rotation completes in 100-200ms
**Fix:** → `elite-gsap` / utility-library.md (Duration Budget)
**Test:** Time button/toggle interactions

### M-02: State transition duration 200-300ms
**Check:** Hover, focus, accordion, tab switch completes in 200-300ms
**Fix:** → `elite-gsap` / utility-library.md (Duration Budget)
**Test:** Time hover and state change transitions

### M-03: Reveal/entrance duration 300-500ms
**Check:** Scroll reveals, modal entrances complete in 300-500ms
**Fix:** → `elite-gsap` / utility-library.md (Duration Budget)
**Test:** Time scroll-triggered reveals

### M-04: No animation exceeds 800ms
**Check:** No single animation duration is longer than 800ms
**Fix:** → `elite-gsap` / utility-library.md (Duration Budget)
**Test:** Grep for duration values; flag any > 0.8s / 800ms

### M-05: Exit animations 60-70% of enter
**Check:** Modal/panel exit duration is 60-70% of its enter duration
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Compare enter vs exit durations in code

### M-06: Ease-out for entering, ease-in for exiting
**Check:** Entering elements use ease-out curves; exiting use ease-in
**Fix:** → `elite-gsap` / utility-library.md
**Test:** Check easing values; verify directional consistency

### M-07: No linear easing for UI transitions
**Check:** UI transitions don't use `linear` or `ease: 'none'` (except scroll-scrub)
**Fix:** → `elite-gsap` / SKILL.md
**Test:** Grep for `ease: 'none'` or `linear`; verify only on scrub animations

### M-08: Stagger timing 30-50ms per item
**Check:** List/grid entrance staggers each item by 30-50ms
**Fix:** → `elite-gsap` / utility-library.md
**Test:** Check stagger values; verify within range

### M-09: Animations interruptible
**Check:** `gsap.killTweensOf()` called before starting new animation on same element
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Grep for killTweensOf or overwrite: true patterns

### M-10: Scale feedback 0.95-1.05 on press
**Check:** Tappable cards/buttons use scale within 0.95-1.05 on press
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Check press interaction code; verify scale range

### M-11: No opacity below 0.2 during transitions
**Check:** Fading elements don't linger below opacity 0.2
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Observe fade animations; verify quick transition through low opacity

### M-12: Modal animates from trigger source
**Check:** Modals scale/fade from the button that opened them (not center of screen)
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Open modal; verify it originates from trigger position

### M-13: Navigation direction consistent
**Check:** Forward navigation enters from right/below; backward from left/above
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Navigate forward and back; verify directional consistency

### M-14: Hierarchy motion vertical
**Check:** Deeper content enters from below; returning to parent enters from above
**Fix:** → `elite-gsap` / utility-library.md (Hierarchy Motion)
**Test:** Navigate deeper/shallower; verify vertical direction

### M-15: Crossfade for content replacement
**Check:** In-container content swaps use crossfade (not hard cut)
**Fix:** → `elite-gsap` / utility-library.md (Animation UX Rules)
**Test:** Observe tab/content switches; verify smooth crossfade

### M-16: Gesture-driven animations track finger
**Check:** Drag/swipe provides real-time visual response following the finger
**Fix:** → `elite-gsap` / utility-library.md (Gesture-Driven Animation)
**Test:** Test drag interactions; verify 1:1 finger tracking

---

## Animation Production Quality

### M-17: Easing uses cubic-bezier (not just keywords)
**Check:** Production animations use custom cubic-bezier values for precision
**Fix:** → `elite-css-animations` / visual-effects.md (Key Easing Values)
**Test:** Check easing values; verify custom curves used for key animations

### M-18: Spring easing for playful brands only
**Check:** `back.out`, `elastic`, bounce easing used only for Warm/Inclusive or Modern/Bold brands
**Fix:** → `elite-gsap` / utility-library.md
**Test:** Verify easing matches brand archetype

### M-19: Parallax subtle and purposeful
**Check:** Parallax effects are subtle (speed 0.1-0.3) and serve a purpose
**Fix:** → `elite-gsap` / utility-library.md
**Test:** Check parallax speed values; verify not distracting

---

## Typography Comfort

### M-20: Type scale with consistent ratio
**Check:** Font sizes follow a mathematical progression (1.25 ratio recommended)
**Fix:** → `elite-design-core` / typography.md
**Test:** List all font sizes; verify progression

### M-21: Fluid typography with clamp()
**Check:** Headings use `clamp()` for smooth responsive scaling
**Fix:** → `elite-design-core` / typography.md
**Test:** Grep for heading font-size; verify clamp() used

### M-22: Body line-height >= 1.5
**Check:** Body paragraph line-height is 1.5-1.75
**Fix:** → `elite-design-core` / typography.md
**Test:** Check computed line-height on body text

### M-23: Body text max-width 65ch
**Check:** Paragraphs constrained to ~65 characters per line
**Fix:** → `elite-accessibility` / inclusive-aesthetics.md
**Test:** Check p/article max-width; verify ch-based constraint

### M-24: Headings use text-wrap: balance
**Check:** h1-h3 use `text-wrap: balance` to prevent awkward line breaks
**Fix:** → `elite-accessibility` / inclusive-aesthetics.md
**Test:** Grep for text-wrap on headings

### M-25: Tabular figures for data
**Check:** Prices, numbers, data columns use `font-variant-numeric: tabular-nums`
**Fix:** → `elite-design-core` / data-visualization.md
**Test:** Check number alignment in tables/data displays

### M-26: Letter-spacing appropriate per role
**Check:** Display text tight (-0.02 to -0.03em), uppercase labels wide (0.1-0.15em)
**Fix:** → `elite-design-core` / typography.md
**Test:** Inspect letter-spacing on headings and labels

### M-27: Maximum 2 font families
**Check:** Site uses at most 2 distinct font families
**Fix:** → `elite-brand-design` / brand-typography.md
**Test:** Count unique font-family declarations

---

## CSS Visual Effects

### M-28: backdrop-filter has @supports fallback
**Check:** Glass/blur effects include `@supports not (backdrop-filter)` fallback
**Fix:** → `elite-css-animations` / visual-effects.md
**Test:** Grep for backdrop-filter; verify @supports block

### M-29: Shimmer skeleton for loading >300ms
**Check:** Content loading >300ms shows shimmer skeleton, not blank space or spinner
**Fix:** → `elite-performance` / asset-optimization.md + `elite-css-animations` / visual-effects.md
**Test:** Throttle network; verify skeleton appears during load

### M-30: Hover-lift uses transform only
**Check:** Card hover elevation uses `translateY` and `box-shadow`, not margin/padding
**Fix:** → `elite-css-animations` / visual-effects.md
**Test:** Inspect hover animations; verify GPU properties only

### M-31: Ticker/marquee has reduced-motion fallback
**Check:** Infinite scroll tickers stop when prefers-reduced-motion is active
**Fix:** → `elite-css-animations` / visual-effects.md
**Test:** Enable reduced motion; verify ticker is static

### M-32: Accordion uses grid-template-rows
**Check:** Accordion height animation uses `grid-template-rows: 0fr -> 1fr` (not JS height)
**Fix:** → `elite-css-animations` / visual-effects.md
**Test:** Inspect accordion; verify grid-based animation

---

## Form Feedback

### M-33: Toast auto-dismiss 3-5s
**Check:** Toast notifications disappear automatically within 3-5 seconds
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Trigger toast; time the dismissal

### M-34: Toast doesn't steal focus
**Check:** Toast appears without moving focus from current element
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Trigger toast while typing; verify cursor stays in input

### M-35: Undo action on destructive toasts
**Check:** Delete/remove toasts include "Undo" action button
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Delete an item; verify undo option in toast

### M-36: Destructive button uses danger color
**Check:** Delete/remove buttons are red/danger colored, separated from primary
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Inspect destructive actions; verify danger color applied

### M-37: Verb-based confirmation buttons
**Check:** Dialog buttons say "Delete" not "OK", "Cancel subscription" not "Yes"
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Review dialog button text; verify descriptive verbs

### M-38: Disabled state visible
**Check:** Disabled elements use opacity 0.4, cursor: not-allowed, and semantic `disabled`
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Inspect disabled elements; verify visual + semantic state

### M-39: Read-only distinct from disabled
**Check:** Read-only fields are selectable/focusable, visually different from disabled
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Compare read-only vs disabled fields; verify distinction

### M-40: Multi-step progress indicator
**Check:** Multi-step forms show step indicator with current position
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Enter multi-step flow; verify progress bar/steps visible

### M-41: Autosave for long forms
**Check:** Forms with 5+ fields auto-save drafts to prevent data loss
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Fill half a long form; navigate away and return; verify data preserved

### M-42: Password toggle present
**Check:** Password fields include show/hide toggle
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Check password inputs for toggle button

### M-43: Input type matches keyboard
**Check:** Email inputs use `type="email"`, phone use `type="tel"`, numbers use `inputmode="numeric"`
**Fix:** → `elite-ux-strategy` / mobile-conversion.md
**Test:** Focus inputs on mobile; verify correct keyboard appears

### M-44: Success feedback after actions
**Check:** Completed actions show brief confirmation (checkmark, toast, color flash)
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Submit form; verify success state appears

---

## Navigation Polish

### M-45: Bottom nav <= 5 items
**Check:** Mobile bottom navigation has at most 5 tabs
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Count bottom nav items on mobile

### M-46: Breadcrumbs for 3+ level hierarchies
**Check:** Sites with 3+ levels of nesting include breadcrumb trail
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Navigate to deep page; verify breadcrumbs present

### M-47: Breadcrumb current page uses aria-current="page"
**Check:** Last breadcrumb item has `aria-current="page"` attribute
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Inspect last breadcrumb; verify aria-current

### M-48: Deep linking — all screens have URLs
**Check:** Every key page has a unique, shareable URL with state in query params
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Navigate to filtered/sorted view; check URL reflects state

### M-49: Drawer width responsive
**Check:** Navigation drawer width is `min(320px, 85vw)`
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Open drawer on mobile; verify appropriate width

### M-50: Modals not used for primary flows
**Check:** Checkout, onboarding, settings are full pages — not modals
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Verify primary flows use page navigation, not modal overlays

### M-51: Navigation consistent across pages
**Check:** Nav placement and structure stays the same on every page
**Fix:** → `elite-ux-strategy` / navigation-patterns.md
**Test:** Navigate multiple pages; verify nav doesn't change position

---

## Mobile UX

### M-52: Thumb zone awareness
**Check:** Primary CTA positioned in easy-reach zone (bottom center on mobile)
**Fix:** → `elite-ux-strategy` / mobile-conversion.md
**Test:** Hold phone naturally; verify primary button reachable with thumb

### M-53: Mobile primary CTA height 48-56px
**Check:** Main action buttons at least 48-56px tall on mobile
**Fix:** → `elite-ux-strategy` / mobile-conversion.md
**Test:** Inspect mobile CTA; verify height

### M-54: Mobile bottom bar for service businesses
**Check:** Service sites (legal, medical) have fixed bottom call/book bar on mobile
**Fix:** → `elite-ux-strategy` / mobile-conversion.md
**Test:** View service site on mobile; verify fixed bottom bar present

### M-55: Sticky add-to-cart on product pages
**Check:** E-commerce product pages show sticky ATC when main CTA scrolls away
**Fix:** → `elite-ux-strategy` / mobile-conversion.md
**Test:** Scroll past main CTA; verify sticky bar appears

---

## Social Proof & Trust

### M-56: Trust strip with greyscale logos
**Check:** Client/partner logos shown in greyscale with hover colorization
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Inspect logo wall; verify filter: grayscale(100%)

### M-57: Testimonials include name + role + photo
**Check:** All testimonials identify the person (never anonymous)
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Review testimonials; verify attribution

### M-58: Social proof near decision points
**Check:** Testimonials/logos appear near pricing, CTA, or checkout — not just page bottom
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Check positioning of social proof relative to conversion points

### M-59: Case study structure: Problem -> Solution -> Results
**Check:** Case studies follow narrative arc with measurable outcomes
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Review case study pages for structure

### M-60: Scarcity badges use real data
**Check:** Low-stock indicators reflect actual inventory with tiered urgency
**Fix:** → `elite-ux-strategy` / social-proof-trust.md
**Test:** Verify scarcity numbers match real data source

---

## Brand Consistency

### M-61: Spacing follows 4/8px scale
**Check:** All margins, padding, gaps use multiples of 4px or 8px
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Inspect computed spacing values; verify scale adherence

### M-62: No emoji icons
**Check:** All icons are SVG (Heroicons, Lucide, Phosphor) — never emoji
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Search for emoji characters in templates

### M-63: Consistent icon stroke width
**Check:** All icons share same stroke width (e.g., 1.5px or 2px)
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Compare icon SVGs; verify stroke-width matches

### M-64: Consistent icon style (filled vs outline)
**Check:** Same hierarchy level uses same icon style; not mixing filled and outline
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Visual review of icon usage across pages

### M-65: Hover/pressed/disabled states distinct
**Check:** Every interactive element has visually different states for hover, pressed, and disabled
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Test each state on buttons, links, cards

### M-66: Selection color matches brand
**Check:** `::selection` uses brand palette (not browser default blue)
**Fix:** → `elite-design-core` / color-theory.md
**Test:** Select text; verify custom selection color

### M-67: Brand-tinted shadows
**Check:** Shadows use brand-colored rgba (not pure black) for cohesion
**Fix:** → `elite-accessibility` / inclusive-aesthetics.md
**Test:** Inspect shadow values; verify brand-tinted rgba

### M-68: Grain overlay if brand uses texture
**Check:** Grain/noise SVG overlay applied with correct opacity for brand
**Fix:** → `elite-design-core` / design-tokens.md
**Test:** Verify .grain-overlay::after with appropriate opacity

### M-69: Brand archetype rules followed
**Check:** If brand is Authoritative -> sharp corners; Warm -> soft corners; etc.
**Fix:** → `elite-brand-design` / SKILL.md
**Test:** Compare implementation against brand archetype expectations

---

## Design Philosophy

### M-70: Every animation serves a purpose
**Check:** Each animation clarifies, guides attention, or provides feedback — not decorative
**Fix:** → `elite-design-core` / SKILL.md
**Test:** For each animation, answer "what does this help the user understand?"

### M-71: Whitespace intentional
**Check:** Empty space organizes content hierarchy; sections are not overcrowded
**Fix:** → `elite-design-core` / SKILL.md
**Test:** Scan page for cramped sections; verify breathing room

### M-72: One focal point per section
**Check:** Each section has a clear visual hierarchy — user knows where to look
**Fix:** → `elite-design-core` / SKILL.md
**Test:** Squint test — can you identify the primary element in each section?

### M-73: Maximum 1-2 animated elements per viewport
**Check:** No more than 2 elements animating simultaneously in any viewport
**Fix:** → `elite-design-core` / SKILL.md
**Test:** Scroll through page; count simultaneously animating elements

---

## Copywriting

### M-74: Headlines use benefit language
**Check:** Headlines focus on outcomes, not features ("Save 10 hours" not "Automated scheduling")
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Review headlines; verify benefit-focused

### M-75: CTAs avoid generic words
**Check:** CTAs say "Start free trial" not "Submit" or "Click here"
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Review all CTA button text

### M-76: Microcopy anticipates questions
**Check:** Helper text, button labels, and error messages answer "what happens next?"
**Fix:** → `elite-brand-design` / brand-tone-voice.md
**Test:** Review form helper text and button microcopy

### M-77: Error messages include fix instructions
**Check:** Errors say "Email must include @" not just "Invalid email"
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Trigger various errors; verify actionable messages

---

## Testing & Benchmarks

### M-78: Landing page conversion tracked
**Check:** Conversion rate measurement in place (2-15% benchmark)
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Verify analytics tracking on conversion events

### M-79: Mobile vs desktop gap < 1.5x
**Check:** Mobile conversion rate is within 1.5x of desktop
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Compare mobile vs desktop conversion in analytics

### M-80: A/B tests for major changes
**Check:** Headlines, CTAs, pricing tested before permanent deployment
**Fix:** → `elite-ux-strategy` / SKILL.md
**Test:** Verify testing framework in place for key elements

### M-81: Lighthouse performance >= 90
**Check:** Lighthouse performance score is 90 or above on mobile
**Fix:** → `elite-performance` / SKILL.md
**Test:** Run Lighthouse audit; check performance score

### M-82: Lighthouse accessibility >= 95
**Check:** Lighthouse accessibility score is 95 or above
**Fix:** → `elite-accessibility` / SKILL.md
**Test:** Run Lighthouse audit; check accessibility score

### M-83: Lighthouse best practices >= 90
**Check:** Lighthouse best practices score is 90 or above
**Fix:** → `elite-performance` / SKILL.md
**Test:** Run Lighthouse audit; check best practices score

### M-84: Real device testing on iOS + Android
**Check:** Site tested on at least one real iOS and one real Android device
**Fix:** → `elite-performance` / SKILL.md
**Test:** Confirm real device testing in QA checklist

---

## Data Visualization (if applicable)

### M-85: Chart type matches data relationship
**Check:** Trend -> line, comparison -> bar, proportion -> donut (<= 5 categories)
**Fix:** → `elite-design-core` / data-visualization.md
**Test:** Verify chart type selection logic

### M-86: Legend visible and near chart
**Check:** Legend positioned adjacent to chart, not below scroll fold
**Fix:** → `elite-design-core` / data-visualization.md
**Test:** Check legend placement

### M-87: Data table alternative available
**Check:** Charts have accessible table fallback (toggle or screen reader)
**Fix:** → `elite-design-core` / data-visualization.md
**Test:** Check for table alternative or aria-label summary

### M-88: Chart empty state shows guidance
**Check:** "No data yet" + guidance shown when chart has no data (not blank)
**Fix:** → `elite-design-core` / data-visualization.md
**Test:** Test with empty data; verify helpful message

### M-89: No pie chart for >5 categories
**Check:** Pie/donut charts limited to 5 or fewer slices
**Fix:** → `elite-design-core` / data-visualization.md
**Test:** Count pie chart segments

---

## Empty States

### M-90: Empty state has illustration/icon
**Check:** Empty lists show visual indicator, not just text
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** View empty list; verify visual present

### M-91: Empty state includes action CTA
**Check:** "Create your first project" button present in empty state
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** View empty state; verify action available

### M-92: Empty state explains context
**Check:** Message explains what would appear and how to populate
**Fix:** → `elite-ux-strategy` / forms-feedback.md
**Test:** Read empty state copy; verify it's helpful
