// Performance Test Template
// Generated scaffold for performance fitness functions
// Customize endpoints, thresholds, and assertions for your project

using System.Diagnostics;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace YourSolution.PerformanceTests;

/// <summary>
/// Performance fitness functions to validate runtime characteristics.
/// Run these tests to ensure performance requirements are met.
/// </summary>
[Trait("Category", "Performance")]
public class PerformanceTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;
    private readonly HttpClient _client;

    public PerformanceTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    #region Response Time Tests

    [Theory]
    [InlineData("/api/health", 50)]
    [InlineData("/api/orders", 200)]
    [InlineData("/api/products", 150)]
    public async Task Endpoint_ShouldRespondWithin_Threshold(string endpoint, int maxMs)
    {
        // Warm up
        await _client.GetAsync(endpoint);

        // Measure
        var stopwatch = Stopwatch.StartNew();
        var response = await _client.GetAsync(endpoint);
        stopwatch.Stop();

        Assert.True(response.IsSuccessStatusCode,
            $"{endpoint} returned {response.StatusCode}");
        Assert.True(stopwatch.ElapsedMilliseconds < maxMs,
            $"{endpoint} took {stopwatch.ElapsedMilliseconds}ms, expected < {maxMs}ms");
    }

    [Fact]
    public async Task Api_P95ResponseTime_ShouldBeLessThan_200ms()
    {
        const int sampleSize = 100;
        const int warmUpCount = 10;
        const int p95Threshold = 200;

        var times = new List<long>();

        // Warm up
        for (int i = 0; i < warmUpCount; i++)
            await _client.GetAsync("/api/orders");

        // Collect samples
        for (int i = 0; i < sampleSize; i++)
        {
            var sw = Stopwatch.StartNew();
            await _client.GetAsync("/api/orders");
            sw.Stop();
            times.Add(sw.ElapsedMilliseconds);
        }

        times.Sort();
        var p95Index = (int)(times.Count * 0.95);
        var p95 = times[p95Index];

        Assert.True(p95 < p95Threshold,
            $"p95 response time was {p95}ms, expected < {p95Threshold}ms");
    }

    #endregion

    #region Throughput Tests

    [Fact]
    public async Task Api_ShouldHandle_AtLeast1000RPS()
    {
        const int targetRps = 1000;
        const int durationSeconds = 10;
        const int concurrency = 100;

        var duration = TimeSpan.FromSeconds(durationSeconds);
        var cts = new CancellationTokenSource(duration);
        var requestCount = 0;
        var errors = 0;

        // Warm up
        await _client.GetAsync("/api/health");

        var sw = Stopwatch.StartNew();

        var tasks = Enumerable.Range(0, concurrency).Select(async _ =>
        {
            while (!cts.IsCancellationRequested)
            {
                try
                {
                    var response = await _client.GetAsync("/api/health", cts.Token);
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
        Assert.True(errors == 0,
            $"Had {errors} errors during throughput test");
    }

    #endregion

    #region Memory Allocation Tests

    [Fact]
    public void Handler_ShouldAllocate_LessThan10KB_PerOperation()
    {
        const int iterations = 1000;
        const long maxBytesPerOperation = 10_000; // 10KB

        // TODO: Replace with your actual handler
        // var handler = CreateHandler();
        // var query = new GetOrderQuery(Guid.NewGuid());

        // Force GC to get clean baseline
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();

        var before = GC.GetTotalMemory(true);

        for (int i = 0; i < iterations; i++)
        {
            // TODO: Replace with your handler invocation
            // handler.Handle(query, CancellationToken.None).GetAwaiter().GetResult();

            // Placeholder: simulate some work
            var _ = new byte[1000];
        }

        var after = GC.GetTotalMemory(true);
        var bytesPerOperation = (after - before) / iterations;

        Assert.True(bytesPerOperation < maxBytesPerOperation,
            $"Allocated {bytesPerOperation} bytes/operation, expected < {maxBytesPerOperation}");
    }

    [Fact]
    public void Processing_ShouldNotAllocate_OnLargeObjectHeap()
    {
        var gen2Before = GC.CollectionCount(2);

        // TODO: Replace with your processing logic
        for (int i = 0; i < 1000; i++)
        {
            // Your processing that should not allocate large objects (>85KB)
            var _ = new byte[1000]; // Small allocation
        }

        var gen2After = GC.CollectionCount(2);

        Assert.Equal(gen2Before, gen2After);
    }

    #endregion

    #region Startup Time Tests

    [Fact]
    public void Application_ShouldStartWithin_5Seconds()
    {
        const int maxStartupMs = 5000;

        var sw = Stopwatch.StartNew();

        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        // Wait for first successful health check
        var response = client.GetAsync("/health").GetAwaiter().GetResult();
        sw.Stop();

        Assert.True(sw.ElapsedMilliseconds < maxStartupMs,
            $"Startup took {sw.ElapsedMilliseconds}ms, expected < {maxStartupMs}ms");
        Assert.True(response.IsSuccessStatusCode);
    }

    #endregion

    #region Database Query Performance Tests

    // TODO: Uncomment and configure for your DbContext
    /*
    [Fact]
    public async Task GetOrderById_ShouldExecuteWithin_50ms()
    {
        const int maxQueryMs = 50;

        await using var context = CreateDbContext();
        var orderId = await SeedTestOrder(context);

        var sw = Stopwatch.StartNew();
        var order = await context.Orders
            .Include(o => o.Items)
            .FirstOrDefaultAsync(o => o.Id == orderId);
        sw.Stop();

        Assert.NotNull(order);
        Assert.True(sw.ElapsedMilliseconds < maxQueryMs,
            $"Query took {sw.ElapsedMilliseconds}ms, expected < {maxQueryMs}ms");
    }

    [Fact]
    public async Task ListOrders_WithPaging_ShouldScaleLinearly()
    {
        const int maxVarianceMs = 50;

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
        Assert.True(maxVariance < maxVarianceMs,
            $"Query times varied by {maxVariance}ms - possible N+1 or index issue");
    }
    */

    #endregion

    #region Concurrent Request Tests

    [Fact]
    public async Task Api_ShouldHandle_ConcurrentRequests_WithoutErrors()
    {
        const int concurrentRequests = 50;

        var tasks = Enumerable.Range(0, concurrentRequests)
            .Select(_ => _client.GetAsync("/api/orders"));

        var responses = await Task.WhenAll(tasks);

        Assert.All(responses, r => Assert.True(r.IsSuccessStatusCode,
            $"Request failed with {r.StatusCode}"));
    }

    [Fact]
    public async Task Api_ShouldMaintainResponseTime_UnderLoad()
    {
        const int concurrentRequests = 100;
        const int maxAverageMs = 500;

        var times = new List<long>();

        var tasks = Enumerable.Range(0, concurrentRequests).Select(async _ =>
        {
            var sw = Stopwatch.StartNew();
            await _client.GetAsync("/api/orders");
            sw.Stop();
            return sw.ElapsedMilliseconds;
        });

        var results = await Task.WhenAll(tasks);
        var average = results.Average();

        Assert.True(average < maxAverageMs,
            $"Average response time under load was {average:F0}ms, expected < {maxAverageMs}ms");
    }

    #endregion

    #region Resource Usage Tests

    [Fact]
    public void ConnectionPool_ShouldNotExhaust_UnderLoad()
    {
        // This test validates that connection pooling works correctly
        // TODO: Configure with your actual database connection string

        const int parallelOperations = 100;
        var exceptions = new List<Exception>();

        Parallel.For(0, parallelOperations, i =>
        {
            try
            {
                // TODO: Replace with actual database operation
                // using var connection = new NpgsqlConnection(connectionString);
                // connection.Open();
                // using var cmd = connection.CreateCommand();
                // cmd.CommandText = "SELECT 1";
                // cmd.ExecuteScalar();
            }
            catch (Exception ex)
            {
                lock (exceptions)
                {
                    exceptions.Add(ex);
                }
            }
        });

        Assert.Empty(exceptions);
    }

    #endregion
}

#region Test Utilities

/// <summary>
/// Helper methods for performance testing.
/// </summary>
public static class PerformanceTestUtilities
{
    /// <summary>
    /// Calculate percentile from a sorted list of values.
    /// </summary>
    public static long Percentile(List<long> sortedValues, double percentile)
    {
        var index = (int)(sortedValues.Count * percentile);
        return sortedValues[Math.Min(index, sortedValues.Count - 1)];
    }

    /// <summary>
    /// Calculate standard deviation.
    /// </summary>
    public static double StandardDeviation(IEnumerable<long> values)
    {
        var avg = values.Average();
        var sumOfSquares = values.Sum(v => Math.Pow(v - avg, 2));
        return Math.Sqrt(sumOfSquares / values.Count());
    }
}

#endregion
