# Stagehand Troubleshooting Guide

## Common Issues

### 1. "Could not find element" Error

**Symptoms:**
```
Error: Could not find element matching action "click the login button"
```

**Solutions:**
1. **Wait for page load:**
   ```typescript
   await stagehand.page.waitForLoadState("networkidle");
   await stagehand.act({ action: "click the login button" });
   ```

2. **Be more specific:**
   ```typescript
   // Instead of
   await stagehand.act({ action: "click button" });
   // Use
   await stagehand.act({ action: "click the blue 'Sign In' button in the header" });
   ```

3. **Enable vision for complex UIs:**
   ```typescript
   await stagehand.act({
     action: "click the login button",
     useVision: true
   });
   ```

4. **Check if element is in iframe:**
   ```typescript
   const frame = stagehand.page.frameLocator('#iframe-id');
   // Stagehand doesn't auto-handle iframes, use Playwright
   await frame.locator('button').click();
   ```

### 2. Extraction Returns Empty/Wrong Data

**Symptoms:**
- `extract()` returns null or unexpected data
- Schema validation fails

**Solutions:**
1. **Wait for content to load:**
   ```typescript
   await stagehand.page.waitForSelector('.product-list');
   const data = await stagehand.extract({...});
   ```

2. **Use more specific instructions:**
   ```typescript
   // Instead of
   await stagehand.extract({ instruction: "get products" });
   // Use
   await stagehand.extract({
     instruction: "get all product cards from the main product grid, including name and price"
   });
   ```

3. **Make schema optional where needed:**
   ```typescript
   schema: z.object({
     price: z.string().optional(),  // May not always exist
     discount: z.number().nullable(),
   })
   ```

### 3. Browser Won't Start (LOCAL mode)

**Symptoms:**
```
Error: Failed to launch browser
Error: Executable doesn't exist at /path/to/chrome
```

**Solutions:**
1. **Install Playwright browsers:**
   ```bash
   npx playwright install chromium
   ```

2. **WSL2: Use Windows Chrome:**
   ```typescript
   const stagehand = new Stagehand({
     env: "LOCAL",
     localBrowserLaunchOptions: {
       executablePath: "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
       args: ["--remote-debugging-port=9222"],
     },
   });
   ```

3. **Check for conflicting Chrome instances:**
   ```bash
   pkill -f chrome
   # Then retry
   ```

### 4. API Key Errors

**Symptoms:**
```
Error: Missing API key
Error: Invalid API key
```

**Solutions:**
1. **Set environment variable:**
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   # or
   export OPENAI_API_KEY="sk-..."
   ```

2. **Pass directly in options:**
   ```typescript
   const stagehand = new Stagehand({
     modelClientOptions: {
       apiKey: process.env.MY_API_KEY,
     },
   });
   ```

### 5. Slow Performance

**Symptoms:**
- Actions take 5+ seconds
- Tests timeout

**Solutions:**
1. **Disable vision when not needed:**
   ```typescript
   await stagehand.act({
     action: "click submit",
     useVision: false  // Default in v3, but explicit is clear
   });
   ```

2. **Use Playwright for known selectors:**
   ```typescript
   // Instead of AI for everything
   await stagehand.act({ action: "type email" });
   // Use Playwright directly when you know the selector
   await stagehand.page.fill('#email', 'test@example.com');
   ```

3. **Use faster model for simple actions:**
   ```typescript
   await stagehand.act({
     action: "click next",
     modelName: "gpt-4o-mini",  // Faster, cheaper
   });
   ```

### 6. Actions Fail on Dynamic Content

**Symptoms:**
- Element found but action fails
- "Element is not clickable" errors

**Solutions:**
1. **Wait for animations:**
   ```typescript
   await stagehand.page.waitForTimeout(500);
   await stagehand.act({ action: "click menu" });
   ```

2. **Wait for specific state:**
   ```typescript
   await stagehand.page.waitForSelector('.modal', { state: 'visible' });
   await stagehand.act({ action: "click confirm in the modal" });
   ```

3. **Scroll element into view:**
   ```typescript
   await stagehand.act({ action: "scroll down to the footer" });
   await stagehand.act({ action: "click the contact link" });
   ```

### 7. Stagehand + Playwright Test Integration Issues

**Symptoms:**
- Tests don't share browser state
- Context lost between operations

**Solutions:**
```typescript
import { test } from '@playwright/test';
import { Stagehand } from '@browserbase/stagehand';

// DON'T create new Stagehand per test
// DO share across test file
let stagehand: Stagehand;

test.beforeAll(async () => {
  stagehand = new Stagehand({ env: "LOCAL" });
  await stagehand.init();
});

test.afterAll(async () => {
  await stagehand.close();
});

test('my test', async () => {
  await stagehand.page.goto('https://example.com');
  await stagehand.act({ action: "click login" });
});
```

## Debug Mode

Enable verbose logging:
```typescript
const stagehand = new Stagehand({
  verbose: 2,  // 0=off, 1=info, 2=debug
  debugDom: true,  // Highlights elements being interacted with
});
```

## Getting Help

- GitHub Issues: https://github.com/browserbase/stagehand/issues
- Discord: Browserbase community
- Documentation: https://docs.browserbase.com/stagehand
