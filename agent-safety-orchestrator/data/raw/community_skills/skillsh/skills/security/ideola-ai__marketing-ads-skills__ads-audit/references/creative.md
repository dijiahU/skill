# Creative Audit Framework (2026)

## Technical Specifications by Platform

### Google Ads - Responsive Search Ads (RSA)

**Text Limits (2026):**
| Component | Min Qty | Max Qty | Character Limit |
|-----------|---------|---------|-----------------|
| Headlines | 3 | 15 | 30 chars |
| Descriptions | 2 | 4 | 90 chars |
| Path 1 & 2 | 0 | 2 | 15 chars each |

**Dynamic Insertion Syntax:**
| Syntax | Purpose | Validation |
|--------|---------|------------|
| {KeyWord:Default Text} | Keyword insertion | Substituted text ≤30 chars |
| {COUNTDOWN(yyyy-MM-dd HH:mm:ss, daysBefore)} | Countdown timer | Date must be in future |
| {LOCATION(City)} | Location insertion | Requires geo-targeting |

**Ad Strength Levels:**
| Rating | Meaning | Performance Impact |
|--------|---------|---------------------|
| Excellent | Max assets, high diversity | +12% more conversions |
| Good | Solid baseline | - |
| Average | Meets minimums | Optimization needed |
| Poor | Missing basics | Limited impression share |

**Best Practice:** 8-10 headlines, 3-4 descriptions, <20% pinning rate

---

### Google Ads - Performance Max (PMax) Assets

**Asset Group Requirements:**
| Asset Type | Dimensions | Min | Max | File Size | Critical |
|------------|------------|-----|-----|-----------|----------|
| Marketing Image | 1200x628 (1.91:1) | 1 | 20 | 5 MB | High |
| Square Image | 1200x1200 (1:1) | 1 | 20 | 5 MB | High |
| Portrait Image | 960x1200 (4:5) | 1 | 20 | 5 MB | **Critical** |
| Logo | 1200x1200 (1:1) | 1 | 5 | 5 MB | Medium |
| Landscape Video | 1920x1080 (16:9) | 0 | 5 | 256 GB | **Critical** |
| Vertical Video | 1080x1920 (9:16) | 0 | 5 | 256 GB | **Critical** |

**Critical:** Missing 4:5 portrait or 9:16 vertical video = excluded from Discover/Shorts inventory

---

### Meta Ads - Image Specifications (2026)

| Placement | Resolution | Aspect Ratio | File Type | Max Size | Text Rule |
|-----------|------------|--------------|-----------|----------|-----------|
| **Feed (Preferred)** | 1080x1350 | **4:5** | JPG, PNG | 30 MB | No 20% rule (AI penalizes clutter) |
| Feed (Square) | 1080x1080 | 1:1 | JPG, PNG | 30 MB | Same |
| **Stories/Reels** | 1080x1920 | **9:16** | JPG, PNG | 30 MB | Safe zones apply |
| Right Column | 1200x1200 | 1:1 | JPG, PNG | 30 MB | Desktop only |
| Marketplace | 1080x1080 | 1:1 | JPG, PNG | 30 MB | |
| Instant Article | 1200x628 | 1.91:1 | JPG, PNG | 30 MB | |

**Character Limits (2026):**
| Field | Characters | Notes |
|-------|------------|-------|
| Primary Text | 125 | Truncates at ~125 on mobile |
| Headline | 27-40 | Truncates at ~40 on desktop |
| Description | 30 | For carousel cards |
| Reels Primary | 72 | Reels-specific |

---

### Meta Ads - Video Specifications (2026)

| Format | Resolution | Aspect Ratio | Duration | File Spec | Safe Zones |
|--------|------------|--------------|----------|-----------|-----------|
| Feed Video | 1080x1350 | 4:5 (Rec) | 1s-241m | MP4, MOV | Standard UI |
| **Stories** | 1080x1920 | 9:16 | 1s-60s | H.264, 4GB | Top: 250px, Bot: 350px |
| **Reels** | 1080x1920 | 9:16 | 1s-15m | MP4, MOV | Right: 120px, Bot: 35% |
| In-Stream | 1920x1080 | 16:9 | 5s-10m | MP4, MOV | - |
| Collection Cover | 1:1 or 16:9 | - | Video or Image | - | - |

**Reels Safe Zone (Strict):**
- **Safe Content Area:** Center 1080 x 1300 px
- Right 15% (120px) reserved for engagement buttons
- Bottom 35% obscured by handle/caption

---

### TikTok Ads - Video Specifications (2026)

| Spec | Spark Ads (Pull) | Non-Spark (Push) | TopView |
|-----|-------------------|-------------------|---------|
| **Resolution** | Native (1080x1920) | ≥540x960 (540p) | ≥720x1280 (720p) |
| **Ratio** | **9:16 (Vertical)** | 9:16 (Rec), 1:1, 16:9 | 9:16 (Vertical) |
| **Duration** | Unlimited (organic) | 5s-60s (Rec: 9-15s) | 5s-60s |
| **File Size** | N/A (Hosted) | ≤500 MB | ≤500 MB |
| **Bitrate** | N/A | ≥516 kbps | **≥2500 kbps** |

**Safe Zone Dimensions (1080x1920 canvas):**
| Zone | Pixels (from edge) | UI Element |
|------|-------------------|------------|
| Top | 0-150px | "Following" button |
| Right | 0-140px | Profile, Like, Comment, Share |
| Bottom | 0-450px | Account, Caption, Music, CTA |
| **Safe Box** | **X: 40-940, Y: 150-1470** | - |

**Caption Limits:**
- Latin scripts: 100 characters
- Asian scripts: 50 characters

---

### YouTube Ads - Video Specifications (2026)

| Format | Resolution | Aspect Ratio | Duration | Safe Zone |
|--------|------------|--------------|----------|-----------|
| **Skippable In-Stream** | 1920x1080 | 16:9 | Min: 5s / Rec: <3m | Bottom-left: 300x60 overlay |
| **Non-Skippable** | 1920x1080 | 16:9 | 15s or 20s (region dependent) | - |
| **Bumper** | 1920x1080 | 16:9 | **Max 6s** (6.1s fails) | - |
| **Shorts** | 1080x1920 | 9:16 | 5s-60s | Bottom 25% for captions/music |
| **Masthead** | 1920x1080 | 16:9 | Max 30s (Autoplay) | Audio defaults mute |

**Shorts Safe Zone (Critical):**
- Bottom 25% (480px) reserved for captions/music
- All text should be in center 1080 x 1420 px area

---

### LinkedIn Ads - Specifications (2026)

**Static Ads:**
| Format | Character Limits | Image Spec | Max Size |
|--------|-----------------|------------|----------|
| Single Image | Intro: 150/600, Headline: 70/200 | 1200x627 (1.91:1) | 5 MB |
| Text Ad | Headline: 25, Desc: 75 | 100x100 | - |
| Carousel | Intro: 255, Card: 45 | 1080x1080 | 5 MB |

**Video Ads:**
| Spec | Requirement | Notes |
|------|-------------|-------|
| Format | MP4 | |
| File Size | 75 KB - 500 MB | Lower than industry standard |
| Duration | 3s - 30 mins | Best: <15s |
| Ratios | 16:9, 1:1, 4:5, 9:16 | 9:16 only on mobile app |
| Audio | AAC/MPEG4, <64 KHz | |

**Messaging Ads:**
| Format | Limit |
|--------|-------|
| Message Ad Subject | 60 chars |
| Message Ad Body | 1500 chars |
| Conversation Ad Message | 500 chars |

---

### Microsoft Ads - Specifications (2026)

**RSA Text:**
| Component | Limit | Dynamic Syntax |
|-----------|-------|----------------|
| Headline | 30 chars (15 max) | {keyword}, {param1-3} |
| Description | 90 chars (4 max) | - |
| Path | 15 chars | - |

**Multimedia Ad Images:**
| Ratio | Resolution | Notes |
|-------|------------|-------|
| 1.91:1 | Landscape | Primary |
| 1:1 | Square | Required |
| 1:2 | Vertical | Optional |
| 4:1 | Banner | Optional |

---

## Universal Safe Zone Guide

For cross-platform creative (Shorts, Reels, TikTok):

**Universal Safe Zone (1920x1080 equivalent):**
- **Vertical Bounds:** Y: 450 to 1450 (on 1920 height)
- **Horizontal Bounds:** X: 40 to 940 (on 1080 width)
- **Result:** 900x1000px center box is safe on all platforms

**Platform-Specific Overlays:**

| Platform | Top Overlay | Bottom Overlay | Right Overlay |
|----------|-------------|----------------|---------------|
| YouTube Shorts | 25% | 25% | - |
| Meta Reels | 13% | 35% | 11% |
| TikTok | 8% | 23% | 13% |

---

## Character Count Normalization

For cross-platform compatibility:

| Element | Safe Baseline | Platform Max |
|---------|---------------|--------------|
| Headlines | **30 chars** | Google/Microsoft 30, Meta 40 |
| Descriptions | **90 chars** | Google 90, Meta 125, LinkedIn 150 |

---

## File Encoding Standards

| Element | Standard | Notes |
|---------|----------|-------|
| Video Codec | H.264 High Profile | Safest across platforms |
| Audio Codec | AAC | -14 LUFS normalization recommended |
| Alternative Video | H.265 (HEVC) | May have compatibility issues |

---

## Creative Quality Scoring (2026)

### Google Ad Strength Algorithm

**Components (4 dimensions):**
1. **Headlines:** Quantity (8-10+), uniqueness (Levenshtein distance)
2. **Descriptions:** 3-4 present, keywords included
3. **Keywords:** Match ad group keywords
4. **Asset Diversity:** Images, sitelinks present

### Meta Quality Ranking (Andromeda)

**Total Value = Bid × Estimated Action Rate + User Value**

**Quality Rankings:**
1. **Quality Ranking:** Feedback (hides vs. likes)
2. **Engagement Rate Ranking:** Expected vs. competitors
3. **Conversion Rate Ranking:** Expected probability

### TikTok Creative Diagnostics

| Score Factor | Good | Poor |
|--------------|------|------|
| Key Frame (2s) | High impact | Low visual impact |
| Sound-On | 93%+ watch with sound | Muted content |
| Duration | >30% completion | <30% completion |
| Aspect Ratio | 9:16 native | 1:1 or 16:9 penalty |

---

## Creative Fatigue Detection

### Fatigue Indicators by Platform

| Signal | Meta | TikTok | Google |
|--------|------|--------|--------|
| **Frequency Threshold** | >3.0 prospecting | N/A | N/A |
| **CTR Decline** | -15% early, -30% advanced | -30% from peak | N/A |
| **CPA Increase** | +20% early, +50% advanced | +50% from baseline | N/A |

### Refresh Cadence (2026)

| Platform | Refresh Frequency | Signal |
|----------|-------------------|--------|
| TikTok | **Weekly** | Fatigue index >0.6 |
| Meta Stories | 1-2 weeks | Frequency >3.0 |
| Meta Feed | 2-4 weeks | CTR decline -15% |
| Google Search | Monthly | Performance drop |
| YouTube | Monthly | View rate decline |
| LinkedIn | 3-4 weeks | Engagement drop |

---

## Hook Formulas That Work (2026)

### TikTok Hooks
- "POV: [relatable situation]"
- "Stop doing [X], try [Y] instead"
- "The secret to [benefit]..."
- "I tried [X] for [time] and..."
- "This [product] changed [aspect]..."

### Meta Hooks
- Question format (curiosity gap)
- Bold statement (challenge belief)
- Specific numbers/results
- "How to" promises
- "Stop doing" warnings

### YouTube Hooks (ABCD Framework)
- **Attract:** Tight framing, 2+ shots in first 5s
- **Brand:** Logo, audio, or product in first 5s
- **Connect:** Education, humor, emotion
- **Direct:** Clear CTA

---

## Copy Length Benchmarks (2026)

| Platform | Optimal Length | Max Length | Notes |
|----------|----------------|------------|-------|
| Meta Feed | ≤125 chars | 125 | Truncates on mobile at ~125 |
| Meta Stories | ≤40 chars | 40 | Rapid consumption |
| Google Headline | ≤30 chars | 30 | Hard limit |
| Google Description | ≤90 chars | 90 | Hard limit |
| TikTok Caption | 1-2 sentences | 100 (Latin) | 50 (Asian) |
| YouTube | 2-3 sentences | - | Before video |
| LinkedIn Feed | ≤150 chars | 600/150 | Mobile truncates at ~150 |

---

## CTA Best Practices

| CTA Type | Example | When to Use |
|----------|---------|-------------|
| **Direct** | Shop Now | E-commerce |
| **Educational** | Learn More | Consideration |
| **Urgency** | Limited Time | Offers |
| **Soft** | See How | Awareness |
| **Engagement** | Comment Below | Social content |

---

## A/B Test Categories (2026)

### Visual Tests
1. Product-only vs. lifestyle
2. Single product vs. product group
3. UGC style vs. polished
4. Color palette variations
5. With vs. without people

### Copy Tests
1. Question hook vs. statement hook
2. Short vs. long copy
3. Benefit-first vs. feature-first
4. Price reveal vs. price hidden
5. Urgent vs. relaxed tone

### Format Tests
1. Image vs. carousel vs. video
2. Square vs. vertical
3. Static vs. animated
4. Sound on vs. sound off

---

## Creative Quality Scorecard (2026)

| Dimension | Weight | Scoring Criteria |
|-----------|--------|------------------|
| Visual Appeal | 20% | Professional, on-brand, high quality |
| Brand Clarity | 15% | Clear logo/branding present |
| Message Clarity | 20% | Single focus, understandable |
| Hook Strength | 20% | Stops scroll, first 3 seconds |
| CTA Effectiveness | 15% | Clear, compelling action |
| Platform Fit | 10% | Correct specs, native feel |

**Total Score:**
- **8-10:** Scale budget
- **6-7:** Monitor closely
- **4-5:** Refresh or pause
- **1-3:** Immediately pause

---

## Common Creative Mistakes (2026)

1. **Too much text** - People don't read ads
2. **No clear CTA** - User doesn't know what to do
3. **Weak hook** - Scrolled past in <1 second
4. **Off-brand** - Inconsistent with other touchpoints
5. **Poor mobile optimization** - Not designed for small screens
6. **Slow video start** - No action in first 3 seconds
7. **Generic stock** - Looks like an ad, not content
8. **Single format** - Not testing variations
9. **Wrong safe zones** - Text covered by UI (2026 critical issue)
10. **Missing vertical video** - Excluded from key inventory

---

## 2026-Specific Recommendations

### For Meta Ads
1. **Use 4:5 ratio** - Occupies 25% more vertical pixels
2. **Native/UGC style** - Andromeda rewards social-native content
3. **Multiple formats** - Image + Video minimum requirement
4. **Test weekly** - Creative fatigue accelerates in 2026

### For TikTok
1. **9:16 only** - Other ratios receive quality penalties
2. **Sound ON mandatory** - 93% watch with sound
3. **Trending audio** - Check Creative Center weekly
4. **Vertical video first** - Native format preferred

### For Google
1. **Maximize RSA assets** - 8-10 headlines, 3-4 descriptions
2. **Add vertical video to PMax** - Required for Shorts/Discover
3. **Enable Brand Guidelines** - Prevent AI hallucination
4. **Structured data on LP** - Required for AI Max

### For LinkedIn
1. **Thought Leader Ads** - 1.7x higher CTR, 1.6x more engagement
2. **Document ads** - B2B educational content performs well
3. **Lead Gen Forms** - 13% CVR (3.25x vs. landing pages)
4. **Native language** - Professional but conversational

---

## Asset Diversity Requirements (2026)

### For PMax/Demand Gen
| Asset Type | High Diversity | Medium | Low |
|------------|----------------|--------|-----|
| Visual Concepts | 5+ different | 3-4 | <3 |
| Color Schemes | 3+ variations | 2 | 1 |
| Product Angles | 4+ variations | 2-3 | <2 |
| People/Models | 3+ different | 2 | 1 or none |

### For Social Platforms
| Asset Type | High Diversity | Medium | Low |
|------------|----------------|--------|-----|
| Hook/Opening Concepts | 5+ different | 3-4 | <3 |
| Music/Audio Tracks | 4+ different | 2-3 | <2 |
| Video Lengths | 3+ (15s, 30s, 60s) | 2 | 1 |
| CTAs | 3+ variations | 2 | 1 |

**Low Diversity Signal:** Same creative running >1 week without change (TikTok), >4 weeks (Meta)

---

## Video Production Best Practices (2026)

### Resolution Standards
| Platform | Minimum | Recommended | Maximum |
|----------|---------|-------------|----------|
| TikTok | 540p | 1080p | N/A |
| YouTube Shorts | 720p | 1080p | N/A |
| Meta Reels | - | 1080p | N/A |
| LinkedIn Feed | - | 1080p | N/A |

### Bitrate Requirements
| Use Case | Minimum Bitrate |
|----------|-----------------|
| Standard (TikTok) | ≥516 kbps |
| TopView (TikTok) | ≥2500 kbps |
| YouTube | - (flexible) |
| Meta | H.264, 4GB max |

### Audio Normalization
- **Target:** -14 LUFS
- **Deviation:** May affect quality score on TikTok/Reels
- **Format:** AAC or MPEG4

---

## Image Specifications Summary (2026)

| Platform | Preferred Ratio | Minimum Resolution | Max File Size |
|----------|-----------------|-------------------|---------------|
| Meta Feed | **4:5** | 600x600 | 30 MB |
| Meta Stories/Reels | **9:16** | 600x1067 | 30 MB |
| TikTok | **9:16 only** | 540x960 | 500 MB |
| YouTube Shorts | **9:16** | 720x1280 | 256 GB |
| LinkedIn | 1.91:1, 1:1, 4:5, 9:16 | Varies | 5 MB |
| Google PMax | All (1:1, 1.91:1, 4:5) | Varies | 5 MB |

---

## Common Technical Failures to Avoid

1. **Wrong aspect ratio** - 16:9 for Reels/Stories (letterboxing)
2. **Text in safe zones** - Covered by UI elements
3. **Low resolution** - <720p for video
4. **Exceeding file size** - Upload failures
5. **Wrong codec** - H.265 compatibility issues
6. **Missing alt text** - Accessibility and policy compliance
7. **Character limits exceeded** - Automatic truncation
8. **No vertical video** - Excluded from key placements
