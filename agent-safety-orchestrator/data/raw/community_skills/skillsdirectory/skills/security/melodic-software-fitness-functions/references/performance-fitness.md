# Performance Fitness Functions

## Overview

Performance fitness functions validate that the system meets runtime performance requirements. They test response times, memory usage, throughput, and other measurable characteristics.

## Types of Performance Tests

| Type | Measures | Example Threshold |
| --- | --- | --- |
| Response Time | Latency | p95 < 200ms |
| Throughput | Requests/second | > 1000 RPS |
| Memory | Allocation per operation | < 10KB/request |
| CPU | Processing time | < 50ms CPU time |
| Startup | Cold start time | < 5 seconds |

## Response Time Tests

### Basic Endpoint Test

```csharp
public class ResponseTimeTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public ResponseTimeTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    [Theory]
    [InlineData("/api/orders", 200)]
    [InlineData("/api/products", 150)]
    [InlineData("/health", 50)]
    public async Task Endpoint_ShouldRespondWithin_Threshold(string endpoint, int maxMs)
    {
        var client = _factory.CreateClient();

        // Warm up
        await client.GetAsync(endpoint);

        // Measure
        var stopwatch = Stopwatch.StartNew();
        var response = await client.GetAsync(endpoint);
        stopwatch.Stop();

        Assert.True(response.IsSuccessStatusCode);
        Assert.True(stopwatch.ElapsedMilliseconds < maxMs,
            $"{endpoint} took {stopwatch.ElapsedMilliseconds}ms, expected < {maxMs}ms");
    }
}
```

### Percentile Testing

```csharp
[Fact]
public async Task Api_P95ResponseTime_ShouldBeLessThan_200ms()
{
    var client = _factory.CreateClient();
    var times = new List<long>();

    // Warm up
    for (int i = 0; i < 10; i++)
        await client.GetAsync("/api/orders");

    // Collect samples
    for (int i = 0; i < 100; i++)
    {
        var sw = Stopwatch.StartNew();
        await client.GetAsync("/api/orders");
        sw.Stop();
        times.Add(sw.ElapsedMilliseconds);
    }

    times.Sort();
    var p95 = times[(int)(times.Count * 0.95)];

    Assert.True(p95 < 200, $"p95 was {p95}ms, expected < 200ms");
}
```

## Memory Allocation Tests

### Per-Operation Allocation

```csharp
[Fact]
public void Handler_ShouldAllocate_LessThan10KB_PerOperation()
{
    var handler = CreateHandler();
    var query = new GetOrderQuery(Guid.NewGuid());

    // Force GC to get clean baseline
    GC.Collect();
    GC.WaitForPendingFinalizers();
    GC.Collect();

    var before = GC.GetTotalMemory(true);

    const int iterations = 1000;
    for (int i = 0; i < iterations; i++)
    {
        handler.Handle(query, CancellationToken.None).GetAwaiter().GetResult();
    }

    var after = GC.GetTotalMemory(true);
    var bytesPerOperation = (after - before) / iterations;

    Assert.True(bytesPerOperation < 10_000,
        $"Allocated {bytesPerOperation} bytes/operation, expected < 10KB");
}
```

### No Large Object Heap Allocation

```csharp
[Fact]
public void Processing_ShouldNotAllocate_OnLargeObjectHeap()
{
    var before = GC.CollectionCount(2);  // Gen2 = LOH

    // Execute operation that should not allocate large objects
    var processor = new OrderProcessor();
    for (int i = 0; i < 1000; i++)
    {
        processor.Process(CreateSmallOrder());
    }

    var after = GC.CollectionCount(2);

    Assert.Equal(before, after);  // No Gen2/LOH collections
}
```

## Throughput Tests

### Requests Per Second

```csharp
[Fact]
public async Task Api_ShouldHandle_AtLeast1000RPS()
{
    var client = _factory.CreateClient();
    var targetRps = 1000;
    var duration = TimeSpan.FromSeconds(10);

    // Warm up
    await client.GetAsync("/api/health");

    var cts = new CancellationTokenSource(duration);
    var requestCount = 0;
    var errors = 0;
    var sw = Stopwatch.StartNew();

    var tasks = Enumerable.Range(0, 100).Select(async _ =>
    {
        while (!cts.IsCancellationRequested)
        {
            try
            {
                var response = await client.GetAsync("/api/health", cts.Token);
                if (response.IsSuccessStatusCode)
                    Interlocked.Increment(ref requestCount);
                else
                    Interlocked.Increment(ref errors);
            }
            catch (OperationCanceledException) { }
            catch { Interlocked.Increment(ref errors); }
        }
    });

    await Task.WhenAll(tasks);
    sw.Stop();

    var rps = requestCount / sw.Elapsed.TotalSeconds;
    Assert.True(rps >= targetRps,
        $"Achieved {rps:F0} RPS, expected >= {targetRps}");
    Assert.True(errors == 0, $"Had {errors} errors");
}
```

## Startup Time Tests

### Cold Start Measurement

```csharp
[Fact]
public void Application_ShouldStartWithin_5Seconds()
{
    var sw = Stopwatch.StartNew();

    using var factory = new WebApplicationFactory<Program>();
    var client = factory.CreateClient();

    // Wait for first successful health check
    var response = client.GetAsync("/health").GetAwaiter().GetResult();
    sw.Stop();

    Assert.True(sw.ElapsedMilliseconds < 5000,
        $"Startup took {sw.ElapsedMilliseconds}ms, expected < 5000ms");
    Assert.True(response.IsSuccessStatusCode);
}
```

## Database Query Tests

### Query Performance

```csharp
[Fact]
public async Task GetOrderById_ShouldExecuteWithin_50ms()
{
    await using var context = CreateDbContext();
    var orderId = await SeedTestOrder(context);

    var sw = Stopwatch.StartNew();
    var order = await context.Orders
        .Include(o => o.Items)
        .FirstOrDefaultAsync(o => o.Id == orderId);
    sw.Stop();

    Assert.NotNull(order);
    Assert.True(sw.ElapsedMilliseconds < 50,
        $"Query took {sw.ElapsedMilliseconds}ms");
}

[Fact]
public async Task ListOrders_WithPaging_ShouldScaleLinearly()
{
    await using var context = CreateDbContext();
    await SeedOrders(context, 10000);  // Large dataset

    var times = new List<(int skip, long ms)>();

    foreach (var skip in new[] { 0, 1000, 5000, 9000 })
    {
        var sw = Stopwatch.StartNew();
        var orders = await context.Orders
            .OrderBy(o => o.CreatedAt)
            .Skip(skip)
            .Take(50)
            .ToListAsync();
        sw.Stop();

        times.Add((skip, sw.ElapsedMilliseconds));
    }

    // All queries should be similar time (indexed pagination)
    var maxVariance = times.Max(t => t.ms) - times.Min(t => t.ms);
    Assert.True(maxVariance < 50,
        $"Query times varied by {maxVariance}ms - possible N+1 or index issue");
}
```

## Integration with CI/CD

### GitHub Actions Configuration

```yaml
name: Performance Tests

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '8.0.x'

      - name: Run Performance Tests
        run: dotnet test --filter "Category=Performance" --logger trx

      - name: Publish Results
        uses: actions/upload-artifact@v4
        with:
          name: performance-results
          path: '**/*.trx'
```

### Test Categorization

```csharp
[Trait("Category", "Performance")]
public class ResponseTimeTests
{
    // Tests here
}
```

## Best Practices

1. **Warm up before measuring** - First request is always slower
2. **Use statistical methods** - p95/p99, not just average
3. **Isolate tests** - Run in clean environment
4. **Set realistic thresholds** - Based on production requirements
5. **Track trends** - Performance degradation over time is signal

## Common Pitfalls

- **Testing on developer machines** - Use consistent CI environment
- **Ignoring GC pressure** - High allocation eventually causes pauses
- **Network latency** - Mock external services in tests
- **Database state** - Seed consistent test data

---

**Related:** `netarchtest-patterns.md`, `dependency-rules.md`
