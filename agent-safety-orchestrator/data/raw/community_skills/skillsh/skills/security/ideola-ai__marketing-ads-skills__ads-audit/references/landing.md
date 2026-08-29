# Landing Page Audit Framework

## Core Web Vitals (Google Standards)

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP (Largest Contentful Paint) | <2.5s | 2.5-4s | >4s |
| FID (First Input Delay) | <100ms | 100-300ms | >300ms |
| CLS (Cumulative Layout Shift) | <0.1 | 0.1-0.25 | >0.25 |

## Technical Performance

### Load Time Benchmarks
| Connection Type | Target Load Time |
|-----------------|------------------|
| 4G Mobile | <3 seconds |
| WiFi | <2 seconds |
| Desktop | <1.5 seconds |

**Testing Tools:**
- Google PageSpeed Insights
- GTmetrix
- WebPageTest

### Common Performance Issues
1. **Uncompressed images** - Use WebP, lazy loading
2. **Excessive scripts** - Minify, defer non-critical
3. **No CDN** - Use CDN for static assets
4. **Large hero videos** - Compress, poster image first
5. **Too many redirects** - Simplify path

## Mobile Optimization

### Responsive Design Checklist
- [ ] Text readable without zoom (16px+)
- [ ] Touch targets 44x44px minimum
- [ ] No horizontal scrolling
- [ ] Viewport meta tag configured
- [ ] Mobile navigation usable
- [ ] Forms easy to complete on mobile

### Mobile-First Considerations
| Element | Desktop | Mobile |
|---------|---------|--------|
| Navigation | Horizontal | Hamburger menu |
| Forms | Multi-column | Single column |
| CTAs | In-line | Sticky footer |
| Images | Large galleries | Horizontal scroll |

## Conversion Elements

### CTA Best Practices

| Aspect | Best Practice |
|--------|---------------|
| Placement | Above fold, repeated after content |
| Size | Large enough, but not overwhelming |
| Color | High contrast, stands out from page |
| Copy | Action-oriented, specific |
| Urgency | When appropriate, not overused |
| Count | One primary CTA per section |

### CTA Copy Examples

| Weak | Strong |
|------|--------|
| "Submit" | "Get Your Free Guide" |
| "Click here" | "Start 30-Day Trial" |
| "Learn more" | "See How It Works" |
| "Buy now" | "Claim 50% Off Today" |

## Trust Signals

### Essential Trust Elements
- [ ] Professional design (not scammy)
- [ ] Contact information visible
- [ ] Privacy policy link
- [ ] Terms of service link
- [ ] Security badges (SSL, payment)
- [ ] Social proof (testimonials, reviews)
- [ ] Company information
- [ ] Refund/return policy

### Social Proof Types
| Type | When to Use |
|------|-------------|
| Customer testimonials | All pages |
| Star ratings | Product/service pages |
| Case studies | B2B, high-consideration |
| Client logos | Above fold, credibility |
| User count | Shows scale |
| Media mentions | Third-party validation |

## Form Optimization

### Form Length Guidelines
| Goal | Optimal Fields |
|------|----------------|
| Lead magnet | Name + Email only |
| Demo request | 3-5 fields |
| Quote request | 5-7 fields |
| Purchase | As needed for checkout |

### Form Best Practices
- Single column layout
- Clear field labels (not placeholders)
- Inline validation (immediate feedback)
- Progress indicator for multi-step
- Submit button states (loading, success)
- Minimal required fields

### Friction Reduction
| Friction Point | Solution |
|----------------|----------|
| Too many fields | Ask only what's essential |
| No format guidance | Show example format |
| Errors unclear | Inline, specific error messages |
| No progress | Add progress bar |
| Long forms | Break into steps |

## Content Optimization

### Above the Fold
- Clear headline matching the ad
- Supporting value proposition
- Hero image/video showing product/benefit
- Primary CTA visible
- Trust signal (logo, rating, count)

### Headline Guidelines
| Weak | Strong |
|------|--------|
| "Welcome to Our Site" | "Get 50% More Leads in 30 Days" |
| "Our Product" | "The Tool That Helped 10,000+ Teams" |
| "Features" | "Stop Wasting Time on Manual Tasks" |

### Value Proposition
- Clear benefit, not just features
- Specific, measurable outcome
- Differentiation from competitors
- Written in customer language

## A/B Test Priorities

1. **Headline** - Highest impact
2. **CTA button** - Color, copy, placement
3. **Hero image** - Product vs. lifestyle
4. **Form length** - Fields count
5. **Social proof** - Testimonials vs. none
6. **Page length** - Short vs. long-form

## Landing Page Audit Checklist

### Technical
- [ ] Load time under 3 seconds (mobile)
- [ ] No broken links
- [ ] SSL certificate active
- [ ] Mobile-responsive
- [ ] Tracking pixels firing

### UX/Design
- [ ] Clear visual hierarchy
- [ ] Consistent branding
- [ ] Readable typography
- [ ] Adequate whitespace
- [ ] No distracting elements

### Conversion
- [ ] Clear headline matches ad promise
- [ ] Value proposition above fold
- [ ] Primary CTA visible without scroll
- [ ] Form fields minimized
- [ ] Trust signals present

### Content
- [ ] Benefits-focused, not feature-focused
- [ ] Social proof visible
- [ ] Scannable (headings, bullets)
- [ ] No jargon
- [ ] Address objections

## Common Issues & Impact

| Issue | Impact | Fix Effort |
|-------|--------|------------|
| Slow load time | High | Medium |
| Weak headline | High | Low |
| Unclear CTA | High | Low |
| No trust signals | Medium | Low |
| Too many form fields | High | Low |
| Not mobile-friendly | High | Medium |
| Broken tracking | Critical | Low |
| Cluttered design | Medium | High |
