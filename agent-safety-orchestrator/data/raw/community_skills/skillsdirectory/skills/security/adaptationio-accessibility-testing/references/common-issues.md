# Common Accessibility Issues and Fixes

## 1. Missing Alt Text on Images

**Impact**: Critical - Screen reader users can't understand images

**Detection**:
```typescript
const results = await new AxeBuilder({ page })
  .withRules(['image-alt'])
  .analyze();
```

**Bad**:
```html
<img src="product.jpg">
```

**Good**:
```html
<!-- Informative image -->
<img src="product.jpg" alt="Red running shoes, Nike Air Max">

<!-- Decorative image -->
<img src="divider.png" alt="" role="presentation">
```

---

## 2. Low Color Contrast

**Impact**: Serious - Users with low vision can't read text

**Detection**:
```typescript
const results = await new AxeBuilder({ page })
  .withRules(['color-contrast'])
  .analyze();
```

**Requirements**:
- Normal text: 4.5:1 ratio
- Large text (18pt+): 3:1 ratio
- UI components: 3:1 ratio

**Fix**:
```css
/* Bad - gray on white */
.text { color: #999; }

/* Good - darker gray */
.text { color: #595959; }
```

**Tool**: [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

---

## 3. Missing Form Labels

**Impact**: Critical - Users can't identify form fields

**Detection**:
```typescript
const results = await new AxeBuilder({ page })
  .withRules(['label'])
  .analyze();
```

**Bad**:
```html
<input type="email" placeholder="Email">
```

**Good Options**:
```html
<!-- Visible label -->
<label for="email">Email</label>
<input id="email" type="email">

<!-- Hidden label (visually) -->
<label for="email" class="sr-only">Email</label>
<input id="email" type="email" placeholder="email@example.com">

<!-- aria-label -->
<input type="email" aria-label="Email address">
```

**Screen reader only class**:
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
```

---

## 4. Missing Button/Link Text

**Impact**: Critical - Users can't understand interactive elements

**Detection**:
```typescript
const results = await new AxeBuilder({ page })
  .withRules(['button-name', 'link-name'])
  .analyze();
```

**Bad**:
```html
<button><i class="icon-search"></i></button>
<a href="/profile"><img src="avatar.png"></a>
```

**Good**:
```html
<button aria-label="Search"><i class="icon-search"></i></button>
<a href="/profile">
  <img src="avatar.png" alt="">
  <span class="sr-only">View profile</span>
</a>
```

---

## 5. Keyboard Traps

**Impact**: Critical - Users can't navigate page

**Detection**:
```typescript
test('no keyboard trap in modal', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-open-modal]');

  // Should be able to close with Escape
  await page.keyboard.press('Escape');
  await expect(page.locator('.modal')).not.toBeVisible();
});
```

**Fix**:
```typescript
// Modal should trap focus while open
// But allow Escape to close
dialog.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeDialog();
  }

  if (e.key === 'Tab') {
    // Keep focus within dialog
    const focusables = dialog.querySelectorAll('button, input, a');
    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      last.focus();
      e.preventDefault();
    } else if (!e.shiftKey && document.activeElement === last) {
      first.focus();
      e.preventDefault();
    }
  }
});
```

---

## 6. Missing Focus Indicators

**Impact**: Serious - Keyboard users can't see current focus

**Detection**:
```typescript
test('focus visible on buttons', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');

  const focused = page.locator(':focus');
  const outline = await focused.evaluate(el =>
    window.getComputedStyle(el).outline
  );

  expect(outline).not.toBe('none');
});
```

**Bad**:
```css
*:focus { outline: none; }
```

**Good**:
```css
:focus {
  outline: 2px solid #005fcc;
  outline-offset: 2px;
}

/* Better - focus-visible for keyboard only */
:focus:not(:focus-visible) {
  outline: none;
}

:focus-visible {
  outline: 2px solid #005fcc;
  outline-offset: 2px;
}
```

---

## 7. Missing Page Language

**Impact**: Serious - Screen readers use wrong pronunciation

**Detection**:
```typescript
const results = await new AxeBuilder({ page })
  .withRules(['html-has-lang', 'html-lang-valid'])
  .analyze();
```

**Fix**:
```html
<html lang="en">
<!-- or -->
<html lang="es">
```

---

## 8. Improper Heading Structure

**Impact**: Moderate - Users can't navigate by headings

**Detection**:
```typescript
const results = await new AxeBuilder({ page })
  .withRules(['heading-order'])
  .analyze();
```

**Bad**:
```html
<h1>Site Title</h1>
<h3>Section</h3>  <!-- Skipped h2 -->
<h5>Subsection</h5>  <!-- Skipped h4 -->
```

**Good**:
```html
<h1>Site Title</h1>
<h2>Section</h2>
<h3>Subsection</h3>
```

---

## 9. Missing Skip Link

**Impact**: Moderate - Keyboard users must tab through nav every page

**Detection**:
```typescript
test('skip link works', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');

  const skipLink = page.locator('a[href="#main"]');
  await expect(skipLink).toBeFocused();
});
```

**Implementation**:
```html
<body>
  <a href="#main" class="skip-link">Skip to main content</a>
  <nav>...</nav>
  <main id="main">...</main>
</body>
```

```css
.skip-link {
  position: absolute;
  top: -100px;
  left: 0;
  background: #000;
  color: #fff;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
```

---

## 10. Auto-playing Media

**Impact**: Serious - Disrupts screen readers, startles users

**Detection**:
```typescript
test('no autoplay video', async ({ page }) => {
  await page.goto('/');

  const autoplaying = await page.evaluate(() => {
    const videos = document.querySelectorAll('video');
    return Array.from(videos).some(v => !v.paused && !v.muted);
  });

  expect(autoplaying).toBe(false);
});
```

**Fix**:
```html
<!-- No autoplay -->
<video src="video.mp4" controls></video>

<!-- If autoplay needed, mute it -->
<video src="hero.mp4" autoplay muted loop></video>
```

---

## Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| Missing alt | Add `alt="description"` or `alt=""` for decorative |
| Low contrast | Use [contrast checker](https://webaim.org/resources/contrastchecker/) |
| Missing label | Add `<label for="id">` or `aria-label` |
| No button text | Add `aria-label` or visible text |
| Keyboard trap | Ensure Escape closes, Tab wraps |
| No focus style | Add `:focus-visible` styles |
| No lang | Add `lang="en"` to `<html>` |
| Skipped headings | Use sequential heading levels |
| No skip link | Add hidden skip link |
| Autoplay | Remove or add `muted` |
