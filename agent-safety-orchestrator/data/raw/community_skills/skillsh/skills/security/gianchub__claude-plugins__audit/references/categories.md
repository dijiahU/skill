# Audit Categories

Use the checklists below to systematically evaluate the codebase. Each category contains specific items to inspect. Not every item applies to every language or framework; skip items that are irrelevant to the target codebase.

---

## 1. Security Vulnerabilities

- **SQL/NoSQL injection** — Identify string concatenation or template interpolation used to build database queries. Verify parameterized queries or ORM-safe APIs are used for all user-supplied input.
- **Command injection** — Check for user input passed to shell commands, `exec`, `system`, `subprocess`, `child_process`, or equivalent. Verify proper escaping or use of argument arrays.
- **Path traversal** — Look for user-controlled input in file paths without canonicalization or allowlist validation. Check for `../` sequences that could escape intended directories.
- **Authentication bypasses** — Inspect login flows, token validation, and session management for logic errors. Check for missing authentication on endpoints that require it.
- **Broken access control** — Verify authorization checks on every protected resource. Look for horizontal privilege escalation (accessing other users' data) and vertical escalation (accessing admin functions).
- **Privilege escalation** — Check for role checks that can be circumvented, writable role fields in user-facing APIs, or default admin accounts.
- **Hardcoded secrets, API keys, and tokens** — Scan for string literals that look like passwords, API keys, JWTs, connection strings, or private keys. Check configuration files, environment defaults, and test fixtures.
- **Insecure deserialization** — Identify use of `pickle`, `yaml.load` (without SafeLoader), `unserialize`, `JSON.parse` on untrusted input feeding object instantiation, or Java `ObjectInputStream` without type filtering.
- **SSRF (Server-Side Request Forgery)** — Check for user-controlled URLs passed to HTTP clients, DNS lookups, or redirect targets without allowlist validation.
- **XXE (XML External Entities)** — Verify XML parsers disable external entity resolution and DTD processing when handling untrusted input.
- **Missing input validation** — Identify endpoints, functions, or message handlers that accept external input without type, length, range, or format validation.
- **Insecure cryptography** — Flag use of MD5, SHA-1 for security purposes, ECB mode, static IVs, short key lengths, or custom crypto implementations. Verify secrets use constant-time comparison.
- **CORS misconfiguration** — Check for `Access-Control-Allow-Origin: *` with credentials, reflected origins without validation, or overly broad origin allowlists.
- **Missing security headers** — Verify presence of `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` on HTTP responses.

---

## 2. Race Conditions and Concurrency

- **Shared mutable state without synchronization** — Identify global or shared variables written from multiple threads, goroutines, coroutines, or processes without locks, atomics, or other synchronization primitives.
- **TOCTOU (Time-of-Check-Time-of-Use)** — Look for patterns where a condition is checked (e.g., file existence, permission, balance) and then acted upon in a separate step without holding a lock or using an atomic operation.
- **Missing locks or mutexes** — Check data structures accessed concurrently for proper lock discipline. Verify lock ordering is consistent to prevent deadlocks.
- **Async hazards** — Identify unhandled promises, fire-and-forget async calls, dangling coroutines, or missing `await` keywords. Check for shared state mutated across `await` boundaries without protection.
- **Database transaction isolation** — Verify transactions use appropriate isolation levels. Look for read-modify-write sequences outside transactions, or concurrent updates to the same row without optimistic/pessimistic locking.
- **Filesystem races** — Check for concurrent file creation, deletion, or renaming without atomic operations or advisory locks. Look for temp file creation with predictable names.
- **Signal handler safety** — Verify signal or interrupt handlers only call async-signal-safe functions. Check for locks held when a signal handler executes.

---

## 3. Dead Code

- **Unreachable branches** — Identify `if`/`else`, `switch`/`match`, or ternary branches where the condition is always true or always false. Look for code after unconditional `return`, `throw`, `break`, or `continue`.
- **Unused imports** — Flag imported modules, packages, or symbols that are never referenced in the file.
- **Unused variables** — Identify assigned variables that are never read. Include function parameters that are accepted but never used (where the language allows removal).
- **Unused functions and classes** — Find functions, methods, or classes that are defined but never called or instantiated from any reachable code path. Cross-reference with entry points and public API surface.
- **Commented-out code** — Flag blocks of commented-out source code (as opposed to explanatory comments). These indicate stale logic that should be removed or restored.
- **Unreferenced configuration** — Identify config keys, environment variables, or feature-flag entries that are defined but never read by application code.
- **Orphaned tests and fixtures** — Find test files or test helper fixtures that test functions/classes which no longer exist, or test files that are excluded from the test runner.
- **Always-on or always-off feature flags** — Identify feature flags whose value is hardcoded, always evaluates to the same branch, or has not been toggled in any reachable configuration.

---

## 4. Anti-Patterns and Code Smells

- **God objects** — Identify classes or modules with disproportionately many methods, fields, or responsibilities. These are candidates for decomposition.
- **Deep nesting (>3 levels)** — Flag functions or methods with more than three levels of nested control flow (loops, conditionals, try/catch). Suggest early returns, guard clauses, or extraction into helper functions.
- **Magic numbers and strings** — Identify literal numeric or string values embedded in logic without named constants or explanatory context.
- **Excessive coupling** — Look for modules or classes that depend on the internals of many other modules. Check for circular dependencies, oversized import lists, or knowledge of distant implementation details.
- **Copy-paste duplication** — Find near-identical code blocks (3+ lines or significant logic) appearing in multiple locations. Suggest extraction into shared functions or modules.
- **Inappropriate abstraction** — Identify abstractions that obscure rather than clarify: single-implementation interfaces, wrapper classes that add no behavior, overly generic utilities used in one place.
- **Single Responsibility Principle violations** — Flag functions, classes, or modules that handle multiple unrelated concerns (e.g., a function that validates input, queries a database, and sends email).
- **Mutable global state** — Identify module-level or global variables that are mutated at runtime. These complicate testing, concurrency, and reasoning about program behavior.

---

## 5. Performance

- **N+1 queries** — Identify loops that issue one database query per iteration when a single batch or joined query would suffice. Check ORM lazy-loading patterns.
- **Unnecessary allocations in hot paths** — Look for object creation, string concatenation, or collection building inside tight loops or frequently called functions where reuse or pre-allocation is possible.
- **Missing pagination** — Check APIs and database queries that return unbounded result sets. Verify pagination or streaming is used for potentially large collections.
- **Blocking in async contexts** — Identify synchronous I/O, CPU-heavy computation, or blocking sleep calls inside async event loops or coroutine contexts.
- **Algorithmic complexity issues** — Flag nested loops over large collections (O(n^2) or worse) where a hash-based or sorted approach would reduce complexity. Check for repeated linear searches.
- **Missing caching** — Identify expensive computations or I/O operations whose results are deterministic or change infrequently, and which lack caching or memoization.
- **Unnecessary serialization/deserialization** — Look for repeated JSON/XML/protobuf encode-decode cycles within the same request or data pipeline where passing structured objects would suffice.

---

## 6. Correctness

- **Off-by-one errors** — Check loop bounds, slice indices, range expressions, and fence-post conditions for boundaries that are one too few or one too many.
- **Null/undefined handling gaps** — Identify dereferences, property accesses, or method calls on values that could be null, nil, None, or undefined without prior checks or safe-navigation operators.
- **Integer overflow/underflow** — Look for arithmetic on fixed-width integers (especially user-supplied values) without bounds checking. Check for negative values in unsigned contexts.
- **Floating-point comparison** — Flag direct equality comparisons (`==`, `!=`) on floating-point numbers. Verify epsilon-based or tolerance-based comparison where needed.
- **Type coercion surprises** — Identify loose equality (`==` in JS), implicit string-to-number conversion, or truthy/falsy checks that behave unexpectedly for edge-case values (0, empty string, empty array).
- **Boundary conditions** — Check how the code handles empty collections, zero-length strings, maximum-size inputs, negative numbers, and other edge values at API and function boundaries.
- **Missing edge cases** — Trace critical paths and identify input combinations or state transitions that are not handled by any code branch or test.

---

## 7. Error Handling Gaps

- **Swallowed exceptions** — Identify empty `catch`, `except`, `rescue`, or `recover` blocks, or blocks that only log and continue without re-raising or returning an error. Evaluate whether silent continuation is intentional and safe.
- **Incorrect error propagation** — Verify that errors are re-raised, wrapped, or returned correctly up the call chain. Look for error codes silently replaced with generic errors, losing diagnostic context. Check for ignored return values from fallible operations.
- **Incomplete cleanup** — Verify that resources (files, connections, locks, temp files) are released in all code paths, including error paths. Check for missing `finally`, `defer`, `with`, or RAII patterns. Look for resource acquisition that lacks a corresponding cleanup block guaranteed to execute regardless of success or failure.
- **Error messages leaking internals** — Check that error responses sent to end users do not expose stack traces, file paths, SQL queries, internal hostnames, or software versions.
- **Missing retry and backoff** — Identify network calls, external API requests, or distributed operations that lack retry logic or use retry without exponential backoff and jitter.
- **Unhandled promise rejections** — In async/event-driven code, verify that all promises, futures, or deferred results have rejection/error handlers attached. Check for missing `.catch()` or `try/catch` around `await`.

---

## 8. Test Quality

- **Excessive mocking** — Identify tests that mock so many dependencies they are effectively testing the mocks, not the code. Flag cases where real dependencies could be used (e.g., in-memory databases, filesystem stubs) but mocks are used for convenience, hiding real integration issues.
- **Vacuous assertions** — Find tests that assert on truthy values, check only that "no error occurred" instead of verifying actual output, or use overly broad matchers that would pass for almost any value.
- **Missing failure path tests** — Check whether test suites only cover happy paths. Verify that error conditions, edge cases, boundary values, and invalid inputs are tested for critical code paths.
- **Test pollution** — Look for shared mutable state between tests, test order dependencies, missing teardown or cleanup, and global state mutations that cause flaky or non-deterministic test runs.
- **Snapshot overuse** — Identify snapshot tests used as a substitute for behavioral assertions. Flag snapshots that are large, frequently updated without review, or that test implementation details rather than observable behavior.
- **Duplicated test setup** — Find repeated setup code across test files that should be extracted into shared fixtures, factories, or helper functions.
- **Tests coupled to implementation** — Identify tests that depend on internal implementation details (private methods, internal state, specific call sequences) rather than observable behavior, making refactoring unnecessarily difficult and brittle.
- **Dead or skipped tests** — Find tests marked as skip, pending, disabled, or xfail that have been left in that state indefinitely without a linked issue or expiration. These represent either untested behavior or dead code.
- **Missing integration tests** — Check whether unit tests exist but no tests verify that components work together correctly across module boundaries, API layers, or service interfaces.
