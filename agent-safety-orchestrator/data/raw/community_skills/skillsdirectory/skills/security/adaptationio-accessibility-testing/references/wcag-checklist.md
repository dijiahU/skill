# WCAG 2.1 Compliance Checklist

## Level A (Minimum)

### Perceivable

| Rule | Description | Test |
|------|-------------|------|
| 1.1.1 Non-text Content | Images have alt text | `withRules(['image-alt'])` |
| 1.2.1 Audio-only/Video-only | Provide alternatives | Manual check |
| 1.2.2 Captions | Videos have captions | Manual check |
| 1.2.3 Audio Description | Video has audio description | Manual check |
| 1.3.1 Info and Relationships | Proper semantic structure | `withRules(['aria-valid-attr'])` |
| 1.3.2 Meaningful Sequence | Logical reading order | Manual check |
| 1.3.3 Sensory Characteristics | Don't rely only on shape/color | Manual check |
| 1.4.1 Use of Color | Color not sole indicator | `withRules(['color-contrast'])` |
| 1.4.2 Audio Control | Can pause/stop audio | Manual check |

### Operable

| Rule | Description | Test |
|------|-------------|------|
| 2.1.1 Keyboard | All functionality via keyboard | Tab through page |
| 2.1.2 No Keyboard Trap | Can navigate away | Test focus management |
| 2.2.1 Timing Adjustable | Can extend time limits | Manual check |
| 2.2.2 Pause, Stop, Hide | Can control moving content | Manual check |
| 2.3.1 Three Flashes | No content flashes >3/sec | Manual check |
| 2.4.1 Bypass Blocks | Skip link exists | `page.locator('[href="#main"]')` |
| 2.4.2 Page Titled | Pages have titles | `expect(page).toHaveTitle()` |
| 2.4.3 Focus Order | Logical tab order | Test tab sequence |
| 2.4.4 Link Purpose | Links are descriptive | `withRules(['link-name'])` |

### Understandable

| Rule | Description | Test |
|------|-------------|------|
| 3.1.1 Language of Page | `lang` attribute present | `withRules(['html-has-lang'])` |
| 3.2.1 On Focus | No unexpected changes on focus | Manual check |
| 3.2.2 On Input | No unexpected changes on input | Manual check |
| 3.3.1 Error Identification | Errors clearly described | Manual check |
| 3.3.2 Labels or Instructions | Form fields labeled | `withRules(['label'])` |

### Robust

| Rule | Description | Test |
|------|-------------|------|
| 4.1.1 Parsing | Valid HTML | HTML validator |
| 4.1.2 Name, Role, Value | ARIA used correctly | `withTags(['cat.aria'])` |

## Level AA (Standard - Most Common Requirement)

### Perceivable

| Rule | Description | Test |
|------|-------------|------|
| 1.3.4 Orientation | Works in both orientations | Test portrait/landscape |
| 1.3.5 Identify Input Purpose | Input autocomplete attributes | Check `autocomplete` |
| 1.4.3 Contrast (Minimum) | 4.5:1 for text, 3:1 for large | `withRules(['color-contrast'])` |
| 1.4.4 Resize Text | Works at 200% zoom | Test with zoom |
| 1.4.5 Images of Text | Avoid text in images | Manual check |
| 1.4.10 Reflow | No horizontal scroll at 320px | Test at 320px width |
| 1.4.11 Non-text Contrast | UI components 3:1 | Manual check |
| 1.4.12 Text Spacing | Works with increased spacing | Test with bookmarklet |
| 1.4.13 Content on Hover | Tooltips dismissible | Test hover content |

### Operable

| Rule | Description | Test |
|------|-------------|------|
| 2.4.5 Multiple Ways | Multiple navigation methods | Check nav + search |
| 2.4.6 Headings and Labels | Descriptive headings | Check heading structure |
| 2.4.7 Focus Visible | Focus indicator visible | Check `:focus` styles |

### Understandable

| Rule | Description | Test |
|------|-------------|------|
| 3.1.2 Language of Parts | Parts in other languages marked | Check `lang` on elements |
| 3.2.3 Consistent Navigation | Navigation consistent | Compare across pages |
| 3.2.4 Consistent Identification | Components consistent | Compare across pages |
| 3.3.3 Error Suggestion | Suggest fixes for errors | Test form errors |
| 3.3.4 Error Prevention | Confirm important actions | Test delete/submit |

## Level AAA (Enhanced)

*Usually not required unless specifically mandated*

| Rule | Description |
|------|-------------|
| 1.4.6 Contrast (Enhanced) | 7:1 for text, 4.5:1 for large |
| 2.1.3 Keyboard (No Exception) | ALL functionality via keyboard |
| 2.2.3 No Timing | No time limits |
| 2.2.4 Interruptions | Can postpone/suppress |
| 2.4.8 Location | Breadcrumbs/location indicator |
| 2.4.9 Link Purpose (Link Only) | Link text alone is descriptive |
| 2.4.10 Section Headings | Content organized with headings |
| 3.1.3 Unusual Words | Definitions for jargon |
| 3.1.4 Abbreviations | Expansions for abbreviations |
| 3.1.5 Reading Level | Simplified version available |
| 3.2.5 Change on Request | Changes only on user request |
| 3.3.5 Help | Context-sensitive help |
| 3.3.6 Error Prevention (All) | Review before any submission |

## Automated vs Manual Testing

### Can Automate (~30% of issues)

```typescript
// These can be tested with axe-core
const automatableRules = [
  'image-alt',
  'label',
  'color-contrast',
  'link-name',
  'button-name',
  'html-has-lang',
  'valid-lang',
  'aria-*',
  'document-title',
  'duplicate-id',
  'form-field-multiple-labels',
  'frame-title',
  'heading-order',
  'input-button-name',
  'input-image-alt',
  'meta-viewport',
  'tabindex',
];
```

### Must Test Manually (~70% of issues)

- Keyboard navigation flow
- Focus management in modals/SPAs
- Screen reader announcements
- Content meaning and context
- Alternative text quality
- Video captions accuracy
- Error message clarity
- Cognitive load

## Test Implementation

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Level A compliance
test('WCAG 2.1 Level A', async ({ page }) => {
  await page.goto('/');

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag21a'])
    .analyze();

  expect(results.violations).toEqual([]);
});

// Level AA compliance (includes A)
test('WCAG 2.1 Level AA', async ({ page }) => {
  await page.goto('/');

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  expect(results.violations).toEqual([]);
});
```

## Resources

- [WCAG 2.1 Spec](https://www.w3.org/WAI/WCAG21/quickref/)
- [axe-core Rules](https://dequeuniversity.com/rules/axe/)
- [WebAIM Checklist](https://webaim.org/standards/wcag/checklist)
