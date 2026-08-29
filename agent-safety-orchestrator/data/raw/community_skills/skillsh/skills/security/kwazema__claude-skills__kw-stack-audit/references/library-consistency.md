# Library Consistency Audit

Detect duplicates and conflicts. For each category, search `package.json` and report **only if there is a conflict**:

## Toast / notifications
- Check for coexistence of `sonner`, `@radix-ui/react-toast`, `react-hot-toast`, `react-toastify`.
- If they coexist: grep in `src/` to show which components use each one.
- Recommend standardizing on `sonner` (simpler, no provider needed).

## Date libraries
- Check for coexistence of `date-fns`, `dayjs`, `moment`, `luxon`.

## Icon libraries
- Check for coexistence of `lucide-react`, `react-icons`, `@heroicons/react`, `@phosphor-icons/react`.

## Form libraries
- Check for coexistence of `react-hook-form` and `formik`.

## HTTP / fetch
- Check for coexistence of `axios` with native fetch (`fetch(` in `src/`).

## State management
- Check for coexistence of `@tanstack/react-query` with `swr`, `@apollo/client`.
- Check for coexistence of `zustand`, `redux`, `jotai`, `valtio`.

## Routing
- Check for coexistence of `react-router-dom` with `wouter`, `@tanstack/react-router`.

## Styling
- Check for coexistence of `tailwindcss` with `styled-components`, `@emotion/react`,
  CSS modules (`*.module.css` files in `src/`).

## Apply workflow

For each inconsistency:
1. Show affected files (grep results).
2. Show a before/after migration example in one representative file.
3. Wait for confirmation.
4. Apply the change across all files.
5. Verify build (`npm run build` or equivalent).

If a category is clean, report as a pass.
