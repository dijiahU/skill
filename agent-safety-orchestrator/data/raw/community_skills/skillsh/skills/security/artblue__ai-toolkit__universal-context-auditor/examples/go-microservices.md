# Go Microservices Example Audit

> **Illustrative example.** This before/after transformation is constructed to demonstrate the auditing principles — not taken from a real project. See the [examples README](README.md) for context, or run `/universal-context-auditor` on your own config to get actual results.

This example shows a typical Go microservices project CLAUDE\.md before and after audit.

## Before: Original CLAUDE\.md

```markdown
# Payment Processing Service

Microservice for handling payments via Stripe.

## Tech
- Go 1.22
- gRPC
- PostgreSQL
- Redis
- Docker

## Structure
```
cmd/
  server/
    main.go
internal/
  api/
    grpc/
      payment_service.go
    http/
      handlers.go
  domain/
    payment.go
    transaction.go
  repository/
    postgres/
      payment_repo.go
  service/
    payment_service.go
pkg/
  stripe/
    client.go
```

## Best Practices

1. Use context properly
2. Handle errors correctly
3. Write good tests
4. Follow Go idioms
5. Use interfaces
6. Don't forget to close resources
7. Make it concurrent where it makes sense

## Testing
Run `go test ./...`
Make sure coverage is good.

## Running
```
docker-compose up
```
```

**Token count:** ~1,100 tokens (estimated)
**Estimated scores:**
- Fidelity: 38/100 (extremely generic advice)
- Cache Efficiency: 65/100 (under 2K but file tree bloat)
- Attention Architecture: 25/100 (no structure)
- Task Success Rate: 32/100 (lacks actionable guidance)
- **Overall: 40/100**

## Audit Findings

### Issues Identified

1. **Extremely Generic Advice**
   - "Use context properly" - how?
   - "Handle errors correctly" - what's correct?
   - "Follow Go idioms" - which ones matter most?
   - These are ignored or cause confusion

2. **Missing Go-Specific Guards**
   - No error handling patterns (critical in Go)
   - No context usage examples (common mistake)
   - No interface sizing guidance (frequent over-engineering)
   - No concurrency patterns (goroutines, channels)

3. **File Structure Bloat**
   - Full tree visible via `find` or file explorer
   - Adds zero value, wastes ~200 tokens

4. **No Concurrency Guidance**
   - "Make it concurrent where it makes sense" is vague
   - No patterns for goroutines, channels, sync primitives

5. **Missing Critical Patterns**
   - Error wrapping (Go 1.13+)
   - Context propagation
   - Resource cleanup patterns
   - Testing patterns (table tests, mocks)

## After: Refactored CLAUDE\.md

```markdown
<architecture_rules>
Go 1.22 gRPC microservice (payment processing)
PostgreSQL for transactional data + Redis for caching
Stripe SDK for payment processing
Hexagonal architecture (domain → service → repository)
</architecture_rules>

<correctness_guards>
**Go 1.22 Specific Patterns (Prevents Hallucination to Go 1.18 Patterns):**
- **Error Handling:** Use `errors.Is()` and `errors.As()` NOT `==` comparison
- **Error Wrapping:** Use `fmt.Errorf("context: %w", err)` NOT `errors.Wrap` (third-party)
- **Context:** Always first parameter, never in structs (lint rule: `contextcheck`)
- **Interface Sizing:** Keep interfaces small (1-3 methods), define at usage site
- **gRPC Errors:** Use `status.Error(codes.X, msg)` NOT `errors.New()` in handlers
- **Database Transactions:** Use `pgx` with `BeginTx(ctx, ...)` NOT `database/sql` default
- **Goroutines:** Always ensure termination path (context cancellation or channel close)
</correctness_guards>

<agent_constraints>
- Never ignore errors (if err != nil check required)
- Never use `panic()` in production code (return errors up the stack)
- Always propagate context through call chains
- Never commit without tests passing (`go test ./... -race`)
- Always run `go mod tidy` before marking work complete
</agent_constraints>

## Error Handling Patterns

### ✅ Correct Patterns

```go
// Sentinel errors (package-level)
var ErrPaymentNotFound = errors.New("payment not found")
var ErrInsufficientFunds = errors.New("insufficient funds")

// Error wrapping with context
func (s *Service) ProcessPayment(ctx context.Context, id string) error {
    payment, err := s.repo.Get(ctx, id)
    if err != nil {
        return fmt.Errorf("failed to get payment %s: %w", id, err)
    }
    // ...
}

// Error checking (Go 1.13+)
if errors.Is(err, ErrPaymentNotFound) {
    // Handle not found
}

// Type assertion for error details
var validationErr *ValidationError
if errors.As(err, &validationErr) {
    // Handle validation error
}
```

### ❌ Anti-Patterns

```go
// ❌ String comparison (fragile)
if err.Error() == "payment not found" { ... }

// ❌ Direct comparison with wrapped errors (fails)
if err == ErrPaymentNotFound { ... }

// ❌ Ignoring errors (lint failure)
_ = repo.Save(ctx, payment)

// ❌ Panic in production code
if err != nil {
    panic(err)  // Use return instead
}
```

## Context Propagation

**Rules:**
1. Context is always first parameter: `func Foo(ctx context.Context, ...)`
2. Never store context in structs (creates lifetime issues)
3. Always check `ctx.Err()` in loops
4. Timeout at boundaries (HTTP handlers, gRPC servers)

**Example:**

```go
// ✅ Correct: context propagation
func (s *Service) ProcessPayment(ctx context.Context, req *PaymentRequest) error {
    // Set timeout for external API call
    ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
    defer cancel()

    charge, err := s.stripeClient.CreateCharge(ctx, req.Amount)
    if err != nil {
        return fmt.Errorf("stripe charge failed: %w", err)
    }

    // Propagate context to repository
    if err := s.repo.SaveTransaction(ctx, charge.ID); err != nil {
        return fmt.Errorf("failed to save transaction: %w", err)
    }

    return nil
}

// ❌ Wrong: context in struct
type Service struct {
    ctx context.Context  // Never do this
    db  *sql.DB
}
```

## Interface Design

**Go philosophy:** Small interfaces at usage site (not package-level)

```go
// ✅ Correct: Small interface, defined where used
type paymentGetter interface {
    Get(ctx context.Context, id string) (*Payment, error)
}

func ProcessRefund(ctx context.Context, getter paymentGetter, id string) error {
    payment, err := getter.Get(ctx, id)
    // ...
}

// ❌ Wrong: Large interface, all methods
type PaymentRepository interface {
    Get(ctx context.Context, id string) (*Payment, error)
    List(ctx context.Context, filter Filter) ([]*Payment, error)
    Save(ctx context.Context, payment *Payment) error
    Delete(ctx context.Context, id string) error
    Update(ctx context.Context, payment *Payment) error
    // ... 10 more methods
}
```

**Rule:** If interface has >3 methods, split it or make it concrete.

## Concurrency Patterns

### Worker Pool Pattern

```go
func (s *Service) ProcessBatch(ctx context.Context, paymentIDs []string) error {
    numWorkers := 5
    jobs := make(chan string, len(paymentIDs))
    results := make(chan error, len(paymentIDs))

    // Start workers
    for i := 0; i < numWorkers; i++ {
        go func() {
            for id := range jobs {
                results <- s.ProcessPayment(ctx, id)
            }
        }()
    }

    // Send jobs
    for _, id := range paymentIDs {
        select {
        case jobs <- id:
        case <-ctx.Done():
            return ctx.Err()
        }
    }
    close(jobs)

    // Collect results
    var errs []error
    for range paymentIDs {
        if err := <-results; err != nil {
            errs = append(errs, err)
        }
    }

    return errors.Join(errs...)  // Go 1.20+
}
```

### Common Mistakes

```go
// ❌ Goroutine leak (no termination path)
go func() {
    for {
        work := <-ch  // Blocks forever if ch never closes
    }
}()

// ✅ Correct: context-aware termination
go func() {
    for {
        select {
        case work := <-ch:
            // Process
        case <-ctx.Done():
            return
        }
    }
}()
```

## Testing Patterns

### Table-Driven Tests

```go
func TestProcessPayment(t *testing.T) {
    tests := []struct {
        name    string
        req     *PaymentRequest
        want    *Payment
        wantErr error
    }{
        {
            name: "successful payment",
            req:  &PaymentRequest{Amount: 1000, Currency: "USD"},
            want: &Payment{ID: "pay_123", Status: "succeeded"},
        },
        {
            name:    "insufficient funds",
            req:     &PaymentRequest{Amount: 999999},
            wantErr: ErrInsufficientFunds,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := service.ProcessPayment(context.Background(), tt.req)
            if !errors.Is(err, tt.wantErr) {
                t.Errorf("got error %v, want %v", err, tt.wantErr)
            }
            // ... assertions
        })
    }
}
```

### Repository Mocking

```go
// Define minimal interface for test
type mockPaymentRepo struct {
    getFunc func(context.Context, string) (*Payment, error)
}

func (m *mockPaymentRepo) Get(ctx context.Context, id string) (*Payment, error) {
    return m.getFunc(ctx, id)
}

// Use in test
repo := &mockPaymentRepo{
    getFunc: func(ctx context.Context, id string) (*Payment, error) {
        return &Payment{ID: id}, nil
    },
}
```

## gRPC Patterns

**Error codes:** Use `google.golang.org/grpc/status` package

```go
// ✅ Correct: gRPC status errors
func (s *Server) GetPayment(ctx context.Context, req *pb.GetPaymentRequest) (*pb.Payment, error) {
    payment, err := s.service.Get(ctx, req.Id)
    if errors.Is(err, ErrPaymentNotFound) {
        return nil, status.Error(codes.NotFound, "payment not found")
    }
    if err != nil {
        return nil, status.Errorf(codes.Internal, "failed to get payment: %v", err)
    }
    return toProto(payment), nil
}

// ❌ Wrong: returning Go errors directly
func (s *Server) GetPayment(ctx context.Context, req *pb.GetPaymentRequest) (*pb.Payment, error) {
    return s.service.Get(ctx, req.Id)  // Client gets generic "unknown" code
}
```

## Database Patterns (pgx)

```go
// Transaction pattern
func (r *Repository) TransferFunds(ctx context.Context, from, to string, amount int) error {
    tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)  // Safe to call even after commit

    if err := r.debit(ctx, tx, from, amount); err != nil {
        return err
    }
    if err := r.credit(ctx, tx, to, amount); err != nil {
        return err
    }

    if err := tx.Commit(ctx); err != nil {
        return fmt.Errorf("commit tx: %w", err)
    }
    return nil
}
```

## Project Structure

**Reference implementation:** See `internal/service/payment_service.go`

**Layering (strict):**
- `domain/` - Pure business logic (no external dependencies)
- `service/` - Use case orchestration (composes repositories)
- `repository/` - Data access (PostgreSQL, Redis)
- `api/` - Transport layer (gRPC, HTTP)

**Anti-pattern:** Domain models importing repository interfaces.

## Common Commands

```bash
# Development
go run cmd/server/main.go
go run -race cmd/server/main.go  # With race detector

# Testing
go test ./...                    # All tests
go test ./... -race              # With race detector (always in CI)
go test ./... -cover             # With coverage
go test -v -run TestProcessPayment  # Specific test

# Pre-commit
go fmt ./...
go vet ./...
golangci-lint run
go mod tidy

# Build
go build -o bin/server cmd/server/main.go
```

## Required Tools

- `golangci-lint` - Linter aggregator (required in CI)
- `buf` - Protobuf management (for gRPC)
- `mockgen` - Interface mocking (if not using manual mocks)
```

**Token count:** ~1,980 tokens (estimated)
**Projected scores:**
- Fidelity: 90/100 (concrete patterns, anti-patterns, code examples)
- Cache Efficiency: 88/100 (under 2K, all static)
- Attention Architecture: 88/100 (XML primacy, clear sections)
- Task Success Rate: 93/100 (specific, actionable, proven patterns)
- **Overall: 90/100**

## Summary of Changes

### ✅ Improvements

1. **Go-Specific Correctness Guards**
   - Error handling patterns (errors.Is/As)
   - Context propagation rules
   - Interface sizing philosophy
   - gRPC error codes

2. **Concrete Error Handling Examples**
   - "Handle errors correctly" → 8 specific patterns with code
   - Shows sentinel errors, wrapping, checking
   - Anti-patterns alongside correct patterns

3. **Context Usage Clarified**
   - "Use context properly" → 4 specific rules + examples
   - Common mistakes shown (context in structs)
   - Timeout patterns at boundaries

4. **Concurrency Patterns Added**
   - Worker pool pattern with context
   - Goroutine leak prevention
   - Channel patterns with select

5. **Removed File Tree**
   - Replaced with reference to key files
   - Saves ~200 tokens

### 📊 Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Token count | 1,100 | 1,980 | +880 (beneficial redundancy) |
| Fidelity | 38/100 | 90/100 | +137% |
| Cache efficiency | 65/100 | 88/100 | +35% |
| Attention architecture | 25/100 | 88/100 | +252% |
| Task success rate | 32/100 | 93/100 | +191% |
| **Overall** | **40/100** | **90/100** | **+125%** |

### 🎯 Key Takeaways

1. **Generic Advice Is Worthless**
   - "Use context properly" has infinite interpretations
   - Concrete rules + code examples enforce patterns

2. **Go Error Handling Is Critical**
   - Most common mistake area in Go
   - Extensive examples prevent sentinel error comparison bugs
   - Training data has mix of Go 1.8, 1.13, 1.20 patterns

3. **Concurrency Patterns Prevent Leaks**
   - Goroutine leaks are silent (no compiler error)
   - Context-aware termination patterns prevent production issues

4. **Interface Philosophy Matters**
   - Coming from Java/C# backgrounds leads to over-engineering
   - "Small interfaces at usage site" prevents this explicitly

## Real-World Impact

*These figures are illustrative estimates of the types of improvements this audit typically surfaces — not measurements from a specific project.*

**Before audit:**
- AI used `==` for error comparison in 78% of code (breaks with wrapped errors)
- Context stored in structs in 23% of services (lifetime bugs)
- Goroutine leaks in 15% of concurrent code (no termination path)
- Large repository interfaces (10+ methods) in all services

**After audit:**
- Zero `==` error comparisons (all use `errors.Is/As`)
- Zero context-in-struct instances
- All goroutines have context-aware termination
- Interfaces average 1.8 methods (defined at usage site)

**Cost savings:**
- Cache hit rate: 12% → 85% (static content, under 2K)
- Production goroutine leak incidents: 3/month → 0/month
- Error handling bugs: 18/month → 1/month
- Interface refactoring cycles: Common → Rare
