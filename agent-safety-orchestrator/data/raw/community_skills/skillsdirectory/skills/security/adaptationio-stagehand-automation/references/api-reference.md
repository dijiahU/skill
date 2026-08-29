# Stagehand API Reference

## Core APIs

### act(options)
Execute natural language browser actions.

```typescript
await stagehand.act({
  action: "click the login button",
  modelName?: "claude-sonnet-4-20250514",  // optional override
  useVision?: true,  // use vision for action (default: false in v3)
});
```

**Action Examples:**
```typescript
// Clicking
await stagehand.act({ action: "click the submit button" });
await stagehand.act({ action: "click on 'Sign Up'" });

// Typing
await stagehand.act({ action: "type 'hello world' into the search box" });
await stagehand.act({ action: "fill the email field with 'user@example.com'" });

// Navigation
await stagehand.act({ action: "scroll down" });
await stagehand.act({ action: "go back to the previous page" });

// Selection
await stagehand.act({ action: "select 'United States' from the country dropdown" });
await stagehand.act({ action: "check the 'Remember me' checkbox" });
```

### extract(options)
Extract structured data from the page using Zod schemas.

```typescript
import { z } from "zod";

const data = await stagehand.extract({
  instruction: "get the product details",
  schema: z.object({
    name: z.string(),
    price: z.number(),
    inStock: z.boolean(),
  }),
  modelName?: "claude-sonnet-4-20250514",
  useVision?: false,
});
```

**Schema Examples:**
```typescript
// List extraction
const products = await stagehand.extract({
  instruction: "get all product names and prices",
  schema: z.object({
    products: z.array(z.object({
      name: z.string(),
      price: z.string(),
    })),
  }),
});

// Nested data
const userProfile = await stagehand.extract({
  instruction: "extract user profile information",
  schema: z.object({
    user: z.object({
      name: z.string(),
      email: z.string(),
      address: z.object({
        city: z.string(),
        country: z.string(),
      }),
    }),
  }),
});
```

### observe(options)
Get AI observations about the current page state.

```typescript
const observations = await stagehand.observe({
  instruction?: "what actions can I take?",
  useVision?: true,
});

// Returns array of possible actions
// [
//   { description: "Click login button", selector: "#login-btn" },
//   { description: "Fill search input", selector: "input[name='search']" },
// ]
```

## Initialization

### Constructor Options

```typescript
const stagehand = new Stagehand({
  // Environment: "LOCAL" for local Chrome, "BROWSERBASE" for cloud
  env: "LOCAL" | "BROWSERBASE",

  // Default model for AI operations
  modelName: "claude-sonnet-4-20250514" | "gpt-4o" | "gpt-4o-mini",

  // API key (uses ANTHROPIC_API_KEY or OPENAI_API_KEY env vars by default)
  modelClientOptions?: {
    apiKey: "your-api-key",
  },

  // Enable verbose logging
  verbose?: 0 | 1 | 2,

  // Enable DOM debugging
  debugDom?: boolean,

  // Headless mode (LOCAL only)
  headless?: boolean,

  // Custom logger
  logger?: (message: string) => void,
});
```

### Lifecycle Methods

```typescript
// Initialize browser
await stagehand.init();

// Get Playwright page for direct manipulation
const page = stagehand.page;
const context = stagehand.context;

// Close browser
await stagehand.close();
```

## Hybrid Usage with Playwright

```typescript
import { Stagehand } from "@browserbase/stagehand";

const stagehand = new Stagehand({ env: "LOCAL" });
await stagehand.init();

// Use Playwright for precise actions
await stagehand.page.goto("https://example.com");
await stagehand.page.waitForLoadState("networkidle");

// Use Stagehand for AI-powered actions
await stagehand.act({ action: "click the newsletter signup" });

// Back to Playwright
const title = await stagehand.page.title();
expect(title).toContain("Example");

// Extract with AI
const content = await stagehand.extract({
  instruction: "get the main heading text",
  schema: z.object({ heading: z.string() }),
});

await stagehand.close();
```

## Error Handling

```typescript
try {
  await stagehand.act({ action: "click non-existent button" });
} catch (error) {
  if (error.message.includes("Could not find element")) {
    // Element not found
  } else if (error.message.includes("Action failed")) {
    // Action could not be completed
  }
}
```

## Performance Tips

1. **Use specific instructions**: "click the blue Submit button in the form" > "click submit"
2. **Avoid useVision when possible**: Text-based actions are faster
3. **Batch extractions**: Extract multiple fields in one call
4. **Cache selectors**: Use `observe()` to get selectors, then use Playwright directly

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...      # For Claude models
OPENAI_API_KEY=sk-...             # For GPT models
BROWSERBASE_API_KEY=...           # For cloud browser
BROWSERBASE_PROJECT_ID=...        # For cloud browser
```
