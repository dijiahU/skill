# Error Handling Guide

Comprehensive error handling strategies for API clients.

---

## Error Categories

### 4xx Client Errors
**Meaning**: Request problem, client must fix

**Common Codes**:
- 400 Bad Request - Invalid request format
- 401 Unauthorized - Authentication failed
- 403 Forbidden - No permission
- 404 Not Found - Resource doesn't exist
- 429 Too Many Requests - Rate limit exceeded

**Handling**: Don't retry, fix request

---

### 5xx Server Errors
**Meaning**: Server problem, may be temporary

**Common Codes**:
- 500 Internal Server Error - Server problem
- 502 Bad Gateway - Upstream error
- 503 Service Unavailable - Temporary outage
- 504 Gateway Timeout - Upstream timeout

**Handling**: Retry with exponential backoff

---

## Retry Strategy

### Exponential Backoff

```javascript
async function retryRequest(fn, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === retries - 1) throw error;

      const delay = Math.pow(2, i) * 1000; // 1s, 2s, 4s
      await sleep(delay);
    }
  }
}
```

---

**Last Updated**: October 25, 2025
