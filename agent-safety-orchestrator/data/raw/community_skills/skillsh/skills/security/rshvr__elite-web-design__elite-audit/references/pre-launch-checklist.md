# Pre-Launch Checklist

Binary pass/fail. All items must pass before deployment. See full rules in critical-rules.md and high-rules.md for details.

---

## Must Pass (Blockers)

### Accessibility

- [ ] Text contrast >= 4.5:1
- [ ] Focus rings visible on all interactive elements
- [ ] Touch targets >= 44x44px
- [ ] `prefers-reduced-motion` alternative for every animation
- [ ] Alt text on meaningful images
- [ ] Heading hierarchy sequential (no skips)
- [ ] Skip-to-content link present
- [ ] `aria-live` on dynamic error messages

### Performance

- [ ] LCP <= 2.5s
- [ ] CLS <= 0.1
- [ ] INP <= 200ms
- [ ] Only transform/opacity/filter animated
- [ ] `gsap.context()` with `revert()` on all animation code
- [ ] Images have width/height or aspect-ratio (no CLS)
- [ ] Initial JS < 100KB gzipped

### Layout

- [ ] Viewport meta present (no user-scalable=no)
- [ ] No horizontal scroll on mobile
- [ ] Safe areas respected on notched devices
- [ ] Content readable in landscape orientation

### Forms

- [ ] Every input has visible label
- [ ] Mobile inputs >= 44px height
- [ ] Error messages state cause + how to fix

### Navigation

- [ ] Back button works predictably
- [ ] Active nav item visually indicated

### Brand

- [ ] Design tokens used (no magic hex/px values)
- [ ] Consistent font families (<= 2)

---

## Should Pass (Quality)

- [ ] Font loading: `font-display: swap`
- [ ] Below-fold images: `loading="lazy"`
- [ ] `100dvh` instead of `100vh`
- [ ] Toast: `aria-live="polite"`, auto-dismiss 3-5s
- [ ] Destructive actions require confirmation
- [ ] Error summary with anchor links (multi-field forms)
- [ ] Breadcrumbs for 3+ level hierarchies
- [ ] Bottom nav icon + label (not icon-only)
- [ ] Exit animations faster than enter
- [ ] `ScrollTrigger.batch()` for grids with 20+ items
