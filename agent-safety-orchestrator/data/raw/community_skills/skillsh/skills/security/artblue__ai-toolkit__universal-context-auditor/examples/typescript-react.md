# TypeScript/React Example Audit

> **Illustrative example.** This before/after transformation is constructed to demonstrate the auditing principles — not taken from a real project. See the [examples README](README.md) for context, or run `/universal-context-auditor` on your own config to get actual results.

This example shows a typical React + TypeScript component library CLAUDE\.md before and after audit.

## Before: Original CLAUDE\.md

```markdown
# React Component Library

Modern React component library built with TypeScript.

## Stack
- React 19
- TypeScript 5.5
- Vite for bundling
- Vitest + Testing Library
- Storybook 8
- CSS Modules

## File Structure
```
src/
  components/
    Button/
      Button.tsx
      Button.module.css
      Button.test.tsx
      Button.stories.tsx
    Input/
      Input.tsx
      Input.module.css
      Input.test.tsx
      Input.stories.tsx
    Select/
      ...
  hooks/
    useClickOutside.ts
    useDebounce.ts
  utils/
    classNames.ts
    types.ts
```

## Guidelines

1. Use functional components with hooks
2. Write TypeScript properly
3. Add tests for everything
4. Use modern React patterns
5. forwardRef is not needed anymore in React 19
6. Make components accessible

## Component Structure
Each component should have:
- Main component file (.tsx)
- CSS module (.module.css)
- Test file (.test.tsx)
- Storybook file (.stories.tsx)

## Testing
Run `npm test` to run tests.
Make sure everything passes.
```

**Token count:** ~1,280 tokens (estimated)
**Estimated scores:**
- Fidelity: 42/100 (extremely vague, no concrete examples)
- Cache Efficiency: 70/100 (under 2K, but file tree bloat)
- Attention Architecture: 30/100 (no structure, random order)
- Task Success Rate: 35/100 (lacks actionable guidance)
- **Overall: 44/100**

## Audit Findings

### Issues Identified

1. **Critical Vagueness**
   - "Write TypeScript properly" - no specifics
   - "Use modern React patterns" - which ones?
   - "Make components accessible" - how?
   - These trigger thoroughness loops or ignored entirely

2. **Missing Correctness Guards**
   - React 19 ref forwarding mentioned but not emphasized
   - TypeScript 5.5 features not specified
   - No common mistake examples

3. **Discoverable File Structure**
   - Entire file tree (lines 9-26) visible via Glob
   - Saves zero tokens, adds noise

4. **No Structural Boundaries**
   - No XML encapsulation
   - All rules have equal weight (no hierarchy)

5. **Generic Testing Guidance**
   - "Add tests for everything" - what constitutes good coverage?
   - No patterns or anti-patterns shown

## After: Refactored CLAUDE\.md

```markdown
<architecture_rules>
React 19 + TypeScript 5.5 component library
CSS Modules for styling (no runtime CSS-in-JS)
Vite for dev + build (ESM-only output)
Accessible by default (WCAG 2.2 AA minimum)
</architecture_rules>

<correctness_guards>
**Version-Specific Syntax (Prevents Training Data Hallucination):**
- **React 19:** Use native `ref` prop directly NOT `React.forwardRef()` wrapper
- **TypeScript 5.5:** Use `satisfies` operator for type narrowing NOT type assertions
- **TypeScript 5.5:** Use `const` type parameters (`<const T>`) for literal inference
- **Vite/ESM:** Import CSS modules with `import styles from './Button.module.css'` (NOT require)
- **Testing Library:** Use `screen.getByRole()` NOT `getByTestId()` (accessibility-first)
- **Storybook 8:** Use CSF3 format (`export default { ... }` + `const Template: Story<Props>`)
</correctness_guards>

<agent_constraints>
- Never use `any` type (use `unknown` + type guards)
- Never use `React.FC` (explicit props + return type instead)
- Always run `npm run build` before marking component work complete
- Never commit without tests passing (`npm test`)
</agent_constraints>

## Component Patterns

**Reference implementation:** See `src/components/Button/` for complete example

**Required structure (all components):**
- Explicit TypeScript interface for props (no inline types)
- CSS Modules imported as `styles` object
- Vitest tests with Testing Library
- Storybook CSF3 stories with controls

**Non-obvious conventions:**
- Props interfaces named `<Component>Props` (not `I<Component>Props` or `<Component>Properties`)
- Event handlers prefixed `on*` (onClick, onChange) in props interface
- Use `ComponentPropsWithoutRef<'button'>` for extending native elements
- Spread `...props` after explicit props (allows override of defaults)

## TypeScript Patterns

### ✅ Modern Patterns (Use These)

```typescript
// React 19: Native ref (no forwardRef)
interface ButtonProps {
  variant?: 'primary' | 'secondary';
  ref?: React.Ref<HTMLButtonElement>;
}

export function Button({ variant = 'primary', ref, ...props }: ButtonProps) {
  return <button ref={ref} className={styles[variant]} {...props} />;
}

// TypeScript 5.5: satisfies operator
const config = {
  apiUrl: '/api',
  timeout: 5000,
} satisfies Config;  // Type-checked but preserves literal types

// Const type parameters for literal inference
function useState<const T>(initial: T): [T, (value: T) => void] { ... }
```

### ❌ Deprecated Patterns (Avoid These)

```typescript
// ❌ React 18 pattern (adds unnecessary wrapper)
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (props, ref) => { ... }
);

// ❌ Type assertion (loses type checking)
const config = {
  apiUrl: '/api',
} as Config;

// ❌ React.FC (deprecated, implicit children)
const Button: React.FC<ButtonProps> = (props) => { ... };
```

## Accessibility Requirements

**All interactive components MUST:**
- Use semantic HTML (`<button>` not `<div onClick>`)
- Have visible focus states (test with keyboard nav)
- Include ARIA labels where text content is insufficient
- Support keyboard interaction (Enter/Space for activation)
- Pass axe-core automated tests

**Testing pattern:**
```typescript
test('keyboard interaction', async () => {
  const user = userEvent.setup();
  render(<Button onClick={handleClick}>Click me</Button>);

  await user.tab();  // Focus button
  expect(screen.getByRole('button')).toHaveFocus();

  await user.keyboard('{Enter}');
  expect(handleClick).toHaveBeenCalled();
});
```

## Testing Requirements

**Minimum coverage per component:**
- Renders without errors
- Accepts all prop variations
- Handles user interactions (click, keyboard, focus)
- Passes axe accessibility audit
- Handles edge cases (undefined props, empty children)

**Use Testing Library queries in order:**
1. `getByRole()` - Accessibility-first (preferred)
2. `getByLabelText()` - Form elements
3. `getByText()` - Non-interactive content
4. `getByTestId()` - Last resort only

**Anti-pattern:**
```typescript
// ❌ Don't use testId as primary query
const button = getByTestId('submit-button');

// ✅ Use accessible role
const button = getByRole('button', { name: 'Submit' });
```

## CSS Module Patterns

**Naming convention:** BEM-inspired, camelCase in JS

```css
/* Button.module.css */
.button { /* Base styles */ }
.primary { /* Modifier */ }
.secondary { /* Modifier */ }
.icon { /* Element */ }
```

```typescript
// Button.tsx
<button className={clsx(styles.button, styles[variant])}>
  {icon && <span className={styles.icon}>{icon}</span>}
  {children}
</button>
```

**Utility:** Use `clsx` library for conditional classes (NOT string concatenation)

## Storybook Patterns

**CSF3 format (Storybook 8):**

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta = {
  title: 'Components/Button',
  component: Button,
  tags: ['autodocs'],
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: {
    variant: 'primary',
    children: 'Click me',
  },
};
```

**Required stories (minimum):**
- Default variant
- All prop variations
- Interactive states (hover, focus, disabled)
- With icon / without icon (if applicable)

## Build and Dev Commands

```bash
# Development
npm run dev              # Vite dev server (http://localhost:5173)
npm run storybook        # Storybook dev (http://localhost:6006)

# Testing
npm test                 # Vitest watch mode
npm run test:ci          # Single run + coverage
npm run test:a11y        # Axe accessibility tests

# Pre-commit
npm run build            # Type check + Vite build
npm run lint             # ESLint + Prettier
npm run type-check       # tsc --noEmit
```

## Common Mistakes

### Event Handlers

```typescript
// ❌ Wrong: React.MouseEvent without generic
onClick: (e: React.MouseEvent) => void;

// ✅ Correct: Specify element type
onClick: (e: React.MouseEvent<HTMLButtonElement>) => void;
```

### Props Spreading

```typescript
// ❌ Wrong: Spread first (can't override)
<button {...props} className={styles.button} />

// ✅ Correct: Spread last (allows className override)
<button className={styles.button} {...props} />
```

### State Updates

```typescript
// ❌ Wrong: Direct state mutation
const [items, setItems] = useState([1, 2, 3]);
items.push(4);  // Doesn't trigger re-render

// ✅ Correct: Immutable update
setItems([...items, 4]);
```
```

**Token count:** ~1,920 tokens (estimated)
**Projected scores:**
- Fidelity: 92/100 (concrete examples, anti-patterns shown)
- Cache Efficiency: 85/100 (under 2K, all static content)
- Attention Architecture: 90/100 (XML primacy, clear hierarchy)
- Task Success Rate: 94/100 (actionable, specific guidance)
- **Overall: 90/100**

## Summary of Changes

### ✅ Improvements

1. **Added Correctness Guards (Primacy Zone)**
   - React 19 ref forwarding at top (prevents forwardRef hallucination)
   - TypeScript 5.5 features emphasized
   - Testing Library best practices highlighted

2. **Replaced Vague Commands with Concrete Examples**
   - "Write TypeScript properly" → Specific patterns with code examples
   - "Use modern React patterns" → Before/after code snippets
   - "Make components accessible" → WCAG requirements + test patterns

3. **Added Anti-Pattern Examples**
   - Shows what NOT to do alongside correct approach
   - Explains WHY deprecated patterns are wrong
   - Prevents training data hallucination (React 18 patterns)

4. **Removed File Structure Tree**
   - Replaced with "See Button component for reference"
   - Saves ~150 tokens, improves signal-to-noise

5. **XML Structural Boundaries**
   - Critical rules in `<architecture_rules>` and `<correctness_guards>`
   - Prevents context bleeding
   - Creates cognitive hierarchy

### 📊 Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Token count | 1,280 | 1,920 | +640 (beneficial redundancy) |
| Fidelity | 42/100 | 92/100 | +119% |
| Cache efficiency | 70/100 | 85/100 | +21% |
| Attention architecture | 30/100 | 90/100 | +200% |
| Task success rate | 35/100 | 94/100 | +169% |
| **Overall** | **44/100** | **90/100** | **+105%** |

### 🎯 Key Takeaways

1. **Token count increased significantly, but value improved exponentially**
   - 640 additional tokens are code examples and anti-patterns
   - Prevents 90%+ of common mistakes
   - WET principle justified by zero hallucination to React 18 patterns

2. **Concrete > Abstract**
   - Every vague command replaced with specific code example
   - "Write TypeScript properly" → 12 specific patterns with code

3. **Anti-Patterns Prevent Hallucination**
   - Showing ❌ alongside ✅ reinforces correct patterns
   - AI training data is 80%+ React 18 patterns - guards prevent regression

4. **Accessibility Embedded, Not Afterthought**
   - WCAG requirements in architecture rules
   - Testing patterns enforce accessibility
   - Query hierarchy prefers semantic roles

## Real-World Impact

*These figures are illustrative estimates of the types of improvements this audit typically surfaces — not measurements from a specific project.*

**Before audit:**
- AI generated `React.forwardRef` in 67% of new components (React 19 doesn't need it)
- Used `React.FC` in 45% of components (deprecated pattern)
- Tests used `getByTestId` as first choice (accessibility last)
- Type assertions (`as Type`) in 30% of code (loses type safety)

**After audit:**
- Zero instances of `forwardRef` or `React.FC`
- All tests use `getByRole` first (accessibility-first)
- Type assertions reduced to <2% (only where TypeScript narrowing fails)
- Components accessible by default (keyboard + screen reader tested)

**Cost savings:**
- Cache hit rate: 18% → 88% (static content, under 2K tokens)
- Rework rate: 3.2 iterations/component → 1.1 iterations/component
- Accessibility bugs: 12/month → 0/month (enforced in tests)
- Build failures: 8% → <1% (TypeScript strict mode + concrete examples)
