# SEO Metadata Tag Reference

Detailed audit checklists, scoring criteria, and common mistakes for all 10 HTML meta tags.

---

## Tag 1 — `<title>` (Page Title)

**SEO Impact:** ✅ Direct — accounts for ~15% of Google ranking factors
**Purpose:** Communicates the primary topic of the page to search engines and users.

**Audit Checks:**
- [ ] Is a `<title>` tag present?
- [ ] Is it unique per page (not duplicated across the site)?
- [ ] Is the length between **50–60 characters** (to avoid truncation in SERPs)?
- [ ] Does it include the **primary target keyword**, ideally near the beginning?
- [ ] Does it read naturally, as if written for a human first?
- [ ] Does it include the **brand name or domain** (recommended at end of title)?

**Common Mistakes:**
- Missing title tag
- Generic or duplicate titles across pages
- Title over 60 characters (truncated in search results)
- Keyword stuffing (unnatural)
- Brand name missing

**Scoring:** 0–5 points based on checks above.

---

## Tag 2 — `<meta name="description">` (Page Description)

**SEO Impact:** ❌ Not a direct ranking factor — but **directly affects CTR**
**Purpose:** Displayed in search results below the title; a well-written description increases click-through rate.

**Note:** If the user's search query matches a passage on the page, Google may display that passage instead of the meta description.

**Audit Checks:**
- [ ] Is a `<meta name="description">` tag present?
- [ ] Is the description unique per page?
- [ ] Is the length between **150–160 characters** (including spaces)?
- [ ] Does it contain the **primary keyword** naturally (not stuffed)?
- [ ] Does it communicate **clear value** and what the user will find on the page?
- [ ] Does it include a soft **call to action** (e.g., "Learn how to…", "Find the best…")?

**Common Mistakes:**
- Missing description (Google auto-generates one, which may be poor)
- Keyword stuffing
- Description too short or too long
- Same description reused across multiple pages

**Scoring:** 0–5 points based on checks above.

---

## Tag 3 — `<h1>` to `<h6>` (Heading Tags)

**SEO Impact:** 🔄 Indirect — helps Google understand content structure
**Purpose:** Outlines content hierarchy for both search engines and users.

**Audit Checks:**
- [ ] Is exactly **one `<h1>` tag** present on the page?
- [ ] Does the H1 clearly describe the page topic and include the primary keyword?
- [ ] Are H2–H6 tags used logically to structure subsections (not skipped randomly)?
- [ ] Do headings reflect the **content beneath them** (not generic chapter numbers)?
- [ ] Are keywords in headings used **naturally**, not stuffed?
- [ ] Is there a visible **table of contents** or heading outline for long pages?

**H1 vs Title:**
They can be the same or different. If you cannot write a distinct H1, matching the title is acceptable.

**Common Mistakes:**
- No H1 tag
- Multiple H1 tags
- H1 doesn't relate to page content
- All headings are generic ("Section 1", "Section 2")
- Keyword stuffing in headings

**Scoring:** 0–5 points based on checks above.

---

## Tag 4 — `<img alt="">` (Image Alt Text)

**SEO Impact:** 🔄 Indirect — enables image search visibility and accessibility
**Purpose:** Describes image content to search engines and screen readers.

**Audit Checks:**
- [ ] Do all images have an `alt` attribute?
- [ ] Is the alt text **descriptive and accurate** (not just a file name like `img1234.jpg`)?
- [ ] Are keywords included naturally where appropriate?
- [ ] Are the most prominent images (product images, infographics) prioritized?
- [ ] Are decorative images using `alt=""` (empty alt for non-content images)?

**Common Mistakes:**
- Missing alt attributes
- Alt text is the same for all images
- Alt text is just the file name
- Keyword stuffing in alt text

**Scoring:** 0–4 points based on checks above.

---

## Tag 5 — `rel="nofollow"` (Link Attribute)

**SEO Impact:** 🔄 Indirect — protects PageRank from leaking to uncontrolled links
**Purpose:** Tells search engines not to pass link equity (PageRank) to the linked page.

**Modern usage — three rel values:**
| Value | Purpose |
|---|---|
| `nofollow` | Don't pass PageRank to this link |
| `noopener` | Prevent new tab from accessing `window.opener` (security) |
| `noreferrer` | Don't send Referer header (privacy) |

Recommended combined usage: `rel="noopener noreferrer nofollow"`

**Audit Checks:**
- [ ] Are user-generated links (comments, forum posts) tagged with `nofollow`?
- [ ] Are paid/sponsored links tagged with `nofollow` or `rel="sponsored"`?
- [ ] Are internal links **free of nofollow** (internal links should pass equity)?
- [ ] Are trusted editorial outbound links left as `follow` (no unnecessary nofollow)?

**Common Mistakes:**
- Adding nofollow to internal links (wastes internal equity flow)
- Not adding nofollow to comment/UGC links (allows PageRank abuse)
- Not adding nofollow to paid links (violates Google guidelines)

**Scoring:** 0–4 points based on checks above.

---

## Tag 6 — `<meta name="robots">` (Robots Meta Tag)

**SEO Impact:** 🔄 Indirect — controls search engine crawl and indexing behavior
**Purpose:** Tells search engines whether to index a specific page and follow its links.

**Note:** This is **not** `robots.txt` — this tag applies to a **single page**, placed in its `<head>`.

**Common content values:**
| Value | Meaning |
|---|---|
| `index` | Allow search engines to index this page (default) |
| `noindex` | Do not index this page |
| `follow` | Follow links on this page (default) |
| `nofollow` | Do not follow links on this page |
| `noarchive` | Do not show cached version in search results |
| `noimageindex` | Do not index images on this page |

Reference: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag

**Audit Checks:**
- [ ] Is `noindex` applied correctly to pages that should NOT be indexed (admin pages, thin content, duplicate pages)?
- [ ] Are important pages **not accidentally** set to `noindex`?
- [ ] Is `noindex` used on pages that waste crawl budget (e.g., faceted navigation, internal search results)?
- [ ] Are staging/dev pages protected from indexing?

**Common Mistakes:**
- Accidentally noindexing important pages
- Forgetting to noindex thin or duplicate content pages
- Using robots.txt to block pages instead of noindex (robots.txt prevents crawling, not indexing)

**Scoring:** 0–4 points based on checks above.

---

## Tag 7 — `<link rel="canonical">` (Canonical Tag)

**SEO Impact:** ✅ Significant indirect impact — consolidates PageRank from duplicate URLs
**Purpose:** Tells search engines which URL is the definitive version of a page.

**HTML Syntax:**
```html
<!-- On the page itself -->
<link rel="canonical" href="https://example.com/blog/my-article">
```

**Why it matters:**
URLs with tracking parameters (e.g., `?r=reddit`, `?utm_source=newsletter`) appear as separate pages to search engines. Without a canonical tag, PageRank is split across all URL variants. With canonical, all link equity is concentrated to the specified URL.

**Audit Checks:**
- [ ] Does every page have a canonical tag?
- [ ] Does the canonical URL point to the **correct** page URL (not always the homepage)?
- [ ] Is the canonical a **self-referencing canonical** for pages with no duplicates?
- [ ] Are paginated pages handled correctly (not all pointing to page 1)?
- [ ] For cross-domain syndicated content, does the canonical point back to the original?

**Common Mistakes:**
- No canonical tag (especially on pages with tracking parameters)
- All pages canonicalizing to the homepage
- Canonical URL differs from the actual page URL (e.g., http vs https, trailing slash mismatch)
- Canonical pointing to a redirect chain

**Scoring:** 0–5 points based on checks above.

---

## Tag 8 — Schema Markup / Structured Data

**SEO Impact:** ✅ Direct — accounts for ~1% of ranking factors; enables Rich Results in SERPs
**Purpose:** Provides explicitly structured data to search engines, enabling rich result types (star ratings, FAQs, product info, etc.)

**Implementation:** JSON-LD script in `<head>` (Google's preferred format)

```html
<script type="application/ld+json">
{
  "@context": "http://schema.org",
  "@type": "Article",
  "name": "Page Title Here",
  "description": "Page description here."
}
</script>
```

**Common schema types:**
- Article / BlogPosting
- Product
- FAQPage
- LocalBusiness
- BreadcrumbList
- Organization / WebSite
- Review / AggregateRating

**Official tools:**
- Generator: https://www.google.com/webmasters/markup-helper/
- Documentation: https://developers.google.com/search/docs/appearance/structured-data/

**Audit Checks:**
- [ ] Is any structured data markup present on the page?
- [ ] Is the schema type appropriate for the page content?
- [ ] Does the schema validate without errors? (Use Google's Rich Results Test)
- [ ] Are required fields for the schema type all present?
- [ ] Is JSON-LD used (preferred over Microdata or RDFa)?

**Common Mistakes:**
- No structured data at all
- Wrong schema type for the page
- Missing required fields causing validation errors
- Structured data that doesn't match visible page content

**Scoring:** 0–5 points based on checks above.

---

## Tag 9 — Social Media Meta Tags (Open Graph / Twitter Cards)

**SEO Impact:** ❌ Not a direct ranking factor — affects social sharing appearance and referral traffic
**Purpose:** Controls how the page appears when shared on social platforms (title, description, image, URL).

#### Open Graph Tags (Facebook, LinkedIn, etc.)

```html
<meta property="og:title" content="Page Title Here"/>
<meta property="og:description" content="Page description here."/>
<meta property="og:url" content="https://example.com/page"/>
<meta property="og:type" content="website"/>
<meta property="og:image" content="https://example.com/image.jpg"/>
<meta property="og:image:alt" content="Image description"/>
<meta property="og:image:width" content="800"/>
<meta property="og:image:height" content="600"/>
```

#### Twitter Cards

```html
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="Page Title Here"/>
<meta name="twitter:description" content="Page description here."/>
<meta name="twitter:image" content="https://example.com/image.jpg"/>
```

Reference: https://developer.twitter.com/en/docs/twitter-for-websites/cards/guides/getting-started

**Audit Checks:**
- [ ] Are all core OG tags present: `og:title`, `og:description`, `og:url`, `og:image`, `og:type`?
- [ ] Is the OG image present and at the recommended size (minimum 1200×630px for best display)?
- [ ] Is `og:image:alt` present for accessibility?
- [ ] Are Twitter card tags present?
- [ ] Is `twitter:card` set (usually `summary_large_image`)?

**Common Mistakes:**
- Missing og:image (social share shows no preview image)
- Image too small (appears as tiny thumbnail)
- og:description same as meta description but not optimized for social context
- Missing twitter:card tag

**Scoring:** 0–5 points based on checks above.

---

## Tag 10 — `<meta name="viewport">` (Viewport Meta Tag)

**SEO Impact:** 🔄 Indirect — mobile-friendliness accounts for ~5% of Google ranking factors
**Purpose:** Controls how a page is scaled and displayed on mobile devices.

**Standard implementation:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1"/>
```

**Parameter meanings:**
- `width=device-width` — matches page width to the device's screen width in device-independent pixels
- `initial-scale=1` — sets 1:1 relationship between CSS pixels and device-independent pixels

**Audit Checks:**
- [ ] Is the viewport meta tag present in `<head>`?
- [ ] Does it include `width=device-width`?
- [ ] Does it include `initial-scale=1`?
- [ ] Is `user-scalable=no` avoided? (Disabling user zoom hurts accessibility)
- [ ] Does the page pass Google's Mobile-Friendly Test?

**Common Mistakes:**
- Missing viewport tag entirely (page renders as shrunken desktop version on mobile)
- Using fixed widths like `width=980` instead of `width=device-width`
- Setting `user-scalable=no` (hurts accessibility)

**Scoring:** 0–4 points based on checks above.

---

## Scoring Summary

| Tag | Max Score |
|---|---|
| Title | 5 |
| Description | 5 |
| Headings | 5 |
| Image Alt | 4 |
| Nofollow | 4 |
| Robots | 4 |
| Canonical | 5 |
| Schema | 5 |
| Social (OG/Twitter) | 5 |
| Viewport | 4 |
| **Total** | **46** |

| Score Range | Grade | Assessment |
|---|---|---|
| 40–46 | A | Excellent — production ready |
| 30–39 | B | Good — minor fixes needed |
| 20–29 | C | Fair — several important issues |
| 10–19 | D | Poor — significant gaps |
| 0–9 | F | Critical — metadata severely lacking |
