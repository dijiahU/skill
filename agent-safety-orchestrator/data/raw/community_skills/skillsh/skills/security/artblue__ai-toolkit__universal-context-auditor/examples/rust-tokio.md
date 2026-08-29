# Rust/Tokio Example Audit

> **Illustrative example.** This before/after transformation is constructed to demonstrate the auditing principles — not taken from a real project. See the [examples README](README.md) for context, or run `/universal-context-auditor` on your own config to get actual results.

This example shows a typical async Rust project CLAUDE\.md before and after audit.

## Before: Original CLAUDE\.md

# Async Web Server

High-performance async web server built with Rust.

## Stack
- Rust 2024 edition
- Tokio runtime
- Axum web framework
- SQLx for database
- Tower middleware

## Project Structure
```
src/
  main.rs
  lib.rs
  handlers/
    user.rs
    auth.rs
  models/
    user.rs
  db/
    pool.rs
    migrations/
  middleware/
    auth.rs
    logging.rs
```

## Best Practices

1. Use async/await properly
2. Handle errors with Result types
3. Write good tests
4. Follow Rust idioms
5. Use lifetimes correctly
6. Don't block the runtime
7. Make it safe and fast

## Running
```
cargo run
cargo test
```

**Token count:** ~950 tokens (estimated)
**Estimated scores:**
- Fidelity: 35/100 (extremely vague, no specifics)
- Cache Efficiency: 60/100 (under 2K but wasteful structure)
- Attention Architecture: 22/100 (no organization)
- Task Success Rate: 28/100 (no actionable guidance)
- **Overall: 36/100**

## Audit Findings

### Issues Identified

1. **Critically Vague Advice**
   - "Use async/await properly" - what does this mean?
   - "Use lifetimes correctly" - which patterns?
   - "Don't block the runtime" - how to avoid?
   - These are ignored or cause confusion

2. **Missing Rust-Specific Guards**
   - No async runtime blocking patterns
   - No ownership/borrowing anti-patterns
   - No error handling specifics (? operator, thiserror, anyhow)
   - No Send/Sync trait implications

3. **File Tree Noise**
   - Discoverable via cargo or file system
   - Wastes tokens

4. **No Async-Specific Guidance**
   - Tokio runtime blocking (critical mistake)
   - spawn vs spawn_blocking confusion
   - No .await positioning best practices

5. **Missing Rust Edition Features**
   - Rust 2024 mentioned but no specific features
   - No async fn in traits guidance
   - No RPITIT patterns

## After: Refactored CLAUDE\.md

```markdown
<architecture_rules>
Rust 2024 edition async web server
Tokio 1.x runtime (multi-threaded)
Axum 0.7 for routing + handlers
SQLx 0.7 with compile-time query checking
Tower middleware stack
</architecture_rules>

<correctness_guards>
**Rust 2024 Edition Specific (Prevents Hallucination to Rust 2021 Patterns):**
- **Async in Traits:** Use `async fn` in traits directly (AFIT stable in 2024)
- **Error Handling:** Use `thiserror` for library errors, `anyhow` for application errors
- **Tokio Blocking:** Use `tokio::task::spawn_blocking` for CPU-intensive work NOT regular spawn
- **Database Queries:** Use `sqlx::query!` macro for compile-time checking NOT `query()`
- **Handler Extractors:** Axum extractors ordered: State first, then Path/Query, then body
- **Trait Bounds:** Prefer `+ Send + 'static` explicitly for spawned tasks
- **Arc Pattern:** Use `Arc<State>` for shared app state NOT `Arc<Mutex<State>>`
- **Cloning into Async:** Clone outside async block, NOT inside (ownership clarity)
</correctness_guards>

<agent_constraints>
- Never use `.unwrap()` or `.expect()` in production code (return Result)
- Never block Tokio runtime (use spawn_blocking for CPU work)
- Always use `sqlx::query!` for type safety (not query())
- Never commit without `cargo clippy` passing
- Always run `cargo test` before marking work complete
</agent_constraints>

## Error Handling Patterns

### Library Code: thiserror

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum UserError {
    #[error("user not found: {0}")]
    NotFound(String),

    #[error("invalid email format: {0}")]
    InvalidEmail(String),

    #[error("database error")]
    Database(#[from] sqlx::Error),
}

// Usage
pub async fn get_user(id: i64) -> Result<User, UserError> {
    let user = sqlx::query_as!(User, "SELECT * FROM users WHERE id = $1", id)
        .fetch_one(&pool)
        .await
        .map_err(|_| UserError::NotFound(id.to_string()))?;

    Ok(user)
}
```

### Application Code: anyhow

```rust
use anyhow::{Context, Result};

// Handler function (application layer)
pub async fn create_user(
    State(state): State<AppState>,
    Json(req): Json<CreateUserRequest>,
) -> Result<Json<User>, AppError> {
    let user = state.user_service
        .create(req)
        .await
        .context("failed to create user")?;  // anyhow context

    Ok(Json(user))
}
```

### Anti-Patterns

```rust
// ❌ Wrong: unwrap in production
let user = get_user(id).await.unwrap();

// ❌ Wrong: using anyhow in libraries (leaks implementation)
pub async fn get_user(id: i64) -> anyhow::Result<User> { ... }

// ❌ Wrong: generic error messages
Err(anyhow::anyhow!("error"))

// ✅ Correct: specific error types + context
.context(format!("failed to get user {}", id))?
```

## Async Runtime Patterns

### Tokio Blocking Rules

**Critical:** Never block the Tokio runtime!

```rust
// ❌ WRONG: Blocks async runtime (kills throughput)
async fn process_image(data: Vec<u8>) -> Result<Image> {
    let img = image::load_from_memory(&data)?;  // Synchronous CPU work
    img.resize(100, 100);  // Blocks thread
    Ok(img)
}

// ✅ CORRECT: Use spawn_blocking for CPU work
async fn process_image(data: Vec<u8>) -> Result<Image> {
    tokio::task::spawn_blocking(move || {
        let img = image::load_from_memory(&data)?;
        img.resize(100, 100);
        Ok(img)
    })
    .await?
}

// ❌ WRONG: File I/O on async thread (blocks)
async fn read_config() -> Result<Config> {
    let content = std::fs::read_to_string("config.toml")?;  // Blocking!
    Ok(toml::from_str(&content)?)
}

// ✅ CORRECT: Use tokio::fs for async I/O
async fn read_config() -> Result<Config> {
    let content = tokio::fs::read_to_string("config.toml").await?;
    Ok(toml::from_str(&content)?)
}
```

### Spawn vs Spawn Blocking

```rust
// Use spawn for async work
tokio::spawn(async move {
    let result = api_client.fetch().await;  // .await is fine
    process(result).await;
});

// Use spawn_blocking for CPU-intensive or blocking I/O
tokio::task::spawn_blocking(move || {
    expensive_computation(data)  // No .await here
});
```

## Axum Handler Patterns

### Extractor Ordering

**Rule:** State → Path/Query → Body (last)

```rust
// ✅ Correct: State first, Path second, body last
async fn update_user(
    State(state): State<AppState>,
    Path(user_id): Path<i64>,
    Json(req): Json<UpdateUserRequest>,
) -> Result<Json<User>, AppError> {
    // ...
}

// ❌ Wrong: body before path (won't compile)
async fn update_user(
    Json(req): Json<UpdateUserRequest>,
    Path(user_id): Path<i64>,
) -> Result<Json<User>, AppError> {
    // ...
}
```

### Error Response Pattern

```rust
// Application error type that implements IntoResponse
pub struct AppError(anyhow::Error);

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": self.0.to_string() })),
        )
            .into_response()
    }
}

// Automatic conversion from anyhow::Error
impl From<anyhow::Error> for AppError {
    fn from(err: anyhow::Error) -> Self {
        Self(err)
    }
}
```

## Database Patterns (SQLx)

### Compile-Time Query Checking

```rust
// ✅ CORRECT: Compile-time checked (sqlx::query!)
let user = sqlx::query_as!(
    User,
    r#"
    SELECT id, email, created_at
    FROM users
    WHERE id = $1
    "#,
    user_id
)
.fetch_one(&pool)
.await?;

// ❌ WRONG: Runtime-only checking (query())
let user = sqlx::query("SELECT * FROM users WHERE id = $1")
    .bind(user_id)
    .fetch_one(&pool)
    .await?;
```

**Setup:** Requires `DATABASE_URL` in `.env` for compile-time checking

### Transaction Pattern

```rust
async fn transfer_funds(
    pool: &PgPool,
    from_id: i64,
    to_id: i64,
    amount: i64,
) -> Result<()> {
    let mut tx = pool.begin().await?;

    sqlx::query!(
        "UPDATE accounts SET balance = balance - $1 WHERE id = $2",
        amount,
        from_id
    )
    .execute(&mut *tx)
    .await?;

    sqlx::query!(
        "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
        amount,
        to_id
    )
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;
    Ok(())
}
```

## Ownership & Borrowing in Async

### Clone Before Async Block

```rust
// ❌ WRONG: Clone inside async (ownership unclear)
let handler = tokio::spawn(async move {
    let state_clone = state.clone();
    process(state_clone).await
});

// ✅ CORRECT: Clone outside async (clear ownership)
let state_clone = state.clone();
let handler = tokio::spawn(async move {
    process(state_clone).await
});
```

### Arc for Shared State

```rust
// ✅ CORRECT: Arc for read-mostly shared state
#[derive(Clone)]
struct AppState {
    db: PgPool,
    config: Arc<Config>,  // Config is read-only
    cache: Arc<Cache>,
}

// ❌ WRONG: Arc<Mutex<T>> for read-heavy workloads
struct AppState {
    config: Arc<Mutex<Config>>,  // Unnecessary contention
}

// ⚠️ USE: Arc<RwLock<T>> if writes are rare
struct AppState {
    cache: Arc<RwLock<Cache>>,  // Allows concurrent reads
}
```

## Testing Patterns

### Async Test Setup

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_user() {
        // Setup
        let pool = setup_test_db().await;

        // Execute
        let result = create_user(&pool, "test@example.com").await;

        // Assert
        assert!(result.is_ok());
        let user = result.unwrap();
        assert_eq!(user.email, "test@example.com");

        // Cleanup
        cleanup_test_db(&pool).await;
    }

    #[tokio::test]
    #[should_panic(expected = "duplicate key")]
    async fn test_duplicate_email() {
        // Test constraint violation
    }
}
```

### Integration Test Pattern

```rust
// tests/integration_test.rs
use axum::http::StatusCode;
use tower::ServiceExt;  // for oneshot()

#[tokio::test]
async fn test_get_user_endpoint() {
    let app = create_app(test_state()).await;

    let response = app
        .oneshot(
            Request::builder()
                .uri("/users/1")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
}
```

## Send + Sync Bounds

**Rule:** All types in spawned tasks must be `Send + 'static`

```rust
// ✅ CORRECT: Explicit bounds
async fn background_job<T>(data: T)
where
    T: Send + 'static,
{
    tokio::spawn(async move {
        process(data).await;
    });
}

// ❌ WRONG: Rc is not Send (won't compile)
use std::rc::Rc;
async fn broken(data: Rc<String>) {
    tokio::spawn(async move {
        println!("{}", data);  // Compile error: Rc is not Send
    });
}

// ✅ CORRECT: Use Arc instead
use std::sync::Arc;
async fn fixed(data: Arc<String>) {
    tokio::spawn(async move {
        println!("{}", data);  // Works: Arc is Send
    });
}
```

## Async Trait Patterns (Rust 2024)

```rust
// ✅ CORRECT: async fn in traits (stable in Rust 2024)
trait UserRepository {
    async fn get_user(&self, id: i64) -> Result<User>;
    async fn create_user(&self, email: String) -> Result<User>;
}

// Implementation
impl UserRepository for PostgresRepo {
    async fn get_user(&self, id: i64) -> Result<User> {
        sqlx::query_as!(User, "SELECT * FROM users WHERE id = $1", id)
            .fetch_one(&self.pool)
            .await
            .map_err(Into::into)
    }

    async fn create_user(&self, email: String) -> Result<User> {
        // ...
    }
}

// ❌ OLD: async-trait crate (pre-2024, no longer needed)
#[async_trait]
trait UserRepository {
    async fn get_user(&self, id: i64) -> Result<User>;
}
```

## Middleware Pattern (Tower)

```rust
use tower::ServiceBuilder;
use tower_http::{
    trace::TraceLayer,
    cors::CorsLayer,
    timeout::TimeoutLayer,
};

let middleware = ServiceBuilder::new()
    .layer(TraceLayer::new_for_http())
    .layer(TimeoutLayer::new(Duration::from_secs(10)))
    .layer(CorsLayer::permissive());

let app = Router::new()
    .route("/users", get(list_users))
    .layer(middleware);
```

## Project Structure

**Reference:** See `src/handlers/user.rs` for complete handler example

**Layering:**
- `handlers/` - HTTP handlers (Axum extractors → service calls)
- `services/` - Business logic (orchestration)
- `repositories/` - Data access (SQLx queries)
- `models/` - Domain types (structs, enums)
- `middleware/` - Tower middleware (auth, logging)

## Common Commands

```bash
# Development
cargo run
cargo watch -x run              # Auto-reload

# Testing
cargo test
cargo test --test integration   # Integration tests only
RUST_LOG=debug cargo test       # With logging

# Pre-commit
cargo fmt
cargo clippy -- -D warnings     # Fail on warnings
cargo test

# Database
sqlx database create
sqlx migrate run
cargo sqlx prepare              # Cache query metadata for CI
```

## Required Tools

- `cargo-watch` - Auto-reload on changes
- `sqlx-cli` - Database migrations
- `cargo-nextest` - Faster test runner (optional)
```

**Token count:** ~1,995 tokens (estimated)
**Projected scores:**
- Fidelity: 94/100 (exhaustive async patterns, ownership clarity)
- Cache Efficiency: 90/100 (just under 2K, all static)
- Attention Architecture: 92/100 (XML primacy, logical flow)
- Task Success Rate: 96/100 (prevents common Rust + async mistakes)
- **Overall: 93/100**

## Summary of Changes

### ✅ Improvements

1. **Async Runtime Blocking Prevention**
   - "Don't block the runtime" → Specific spawn vs spawn_blocking examples
   - Shows exact anti-patterns (file I/O, CPU work)
   - Prevents the #1 Tokio mistake

2. **Rust 2024 Edition Features**
   - Async fn in traits (stable, no more async-trait crate)
   - Shows old vs new patterns (prevents training data hallucination)

3. **Error Handling Clarity**
   - thiserror vs anyhow (when to use each)
   - Library vs application error patterns
   - Concrete examples with derives

4. **SQLx Compile-Time Checking**
   - query! vs query() emphasized
   - Shows why (type safety at compile time)
   - Setup requirements mentioned

5. **Ownership Patterns in Async**
   - Clone before async block (ownership clarity)
   - Arc vs Arc<Mutex> vs Arc<RwLock>
   - Send + Sync trait bounds explained

### 📊 Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Token count | 950 | 1,995 | +1,045 (beneficial redundancy) |
| Fidelity | 35/100 | 94/100 | +169% |
| Cache efficiency | 60/100 | 90/100 | +50% |
| Attention architecture | 22/100 | 92/100 | +318% |
| Task success rate | 28/100 | 96/100 | +243% |
| **Overall** | **36/100** | **93/100** | **+158%** |

### 🎯 Key Takeaways

1. **Async Rust Is Non-Trivial**
   - Generic advice ("use async properly") is useless
   - Specific patterns (spawn_blocking, .await placement) prevent runtime blocking

2. **Ownership + Async = Complex**
   - Send + Sync bounds non-obvious for newcomers
   - Arc patterns need explicit guidance
   - Clone-before-spawn clarifies ownership

3. **Edition Matters**
   - Rust 2024 has async fn in traits
   - Training data is mix of 2018, 2021, 2024 patterns
   - Guards prevent hallucination to async-trait crate

4. **SQLx Compile-Time Checking Underutilized**
   - Many developers don't know about query! macro
   - Requires DATABASE_URL setup
   - Huge safety benefit when used correctly

## Real-World Impact

*These figures are illustrative estimates of the types of improvements this audit typically surfaces — not measurements from a specific project.*

**Before audit:**
- AI used blocking I/O in async handlers in 45% of code (killed throughput)
- Used `async-trait` crate in 60% of trait definitions (unnecessary in 2024)
- Generic `query()` instead of `query!` in 80% of database code
- `.unwrap()` in 30% of production code

**After audit:**
- Zero blocking I/O on async runtime (all use spawn_blocking)
- Zero async-trait dependencies (native async fn in traits)
- 95% of queries use `query!` macro (compile-time checked)
- <1% `.unwrap()` usage (explicit error handling)

**Cost savings:**
- Cache hit rate: 8% → 87% (static content, <2K tokens)
- Runtime blocking incidents: 12/month → 0/month
- Type-related database bugs: 8/month → 0/month (sqlx::query!)
- Refactoring for Send bounds: Common → Rare (explicit from start)
- Production panics: 4/month → 0/month (no unwrap/expect)
