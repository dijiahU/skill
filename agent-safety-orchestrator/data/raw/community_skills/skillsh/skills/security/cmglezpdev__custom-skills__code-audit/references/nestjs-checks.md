# NestJS Audit Checks

Patterns and anti-patterns specific to NestJS API applications.
Supplements the OWASP checks with NestJS framework-specific concerns.

---

## Table of Contents

1. [Bootstrap Security (`main.ts`)](#bootstrap-security)
2. [Authentication & Authorization](#authentication--authorization)
3. [Input Validation & DTOs](#input-validation--dtos)
4. [Database & ORM Security](#database--orm-security)
5. [Error Handling](#error-handling)
6. [File Upload Security](#file-upload-security)
7. [GraphQL Specific](#graphql-specific)
8. [Microservices & Messaging](#microservices--messaging)
9. [Configuration & Secrets](#configuration--secrets)

---

## Bootstrap Security

The `main.ts` bootstrap is the single most important file for baseline security. A missing
control here affects the entire application.

### Required security controls in `main.ts`

```typescript
// ALL of these should be present for a production NestJS app:

// 1. Global Validation Pipe — rejects unexpected/malformed input
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,           // strips unknown properties
  forbidNonWhitelisted: true, // throws on unknown properties
  transform: true,           // transforms payloads to DTO instances
}));

// 2. Helmet — sets security headers
app.use(helmet());

// 3. CORS — restrictive origin configuration
app.enableCors({
  origin: ['https://your-frontend.com'],  // NOT '*' or true
  credentials: true,
});

// 4. Rate limiting — via ThrottlerModule or middleware
// (verified in module imports)

// 5. Cookie parser with secret (if using cookies)
app.use(cookieParser(configService.get('COOKIE_SECRET')));

// 6. Request size limit
app.use(json({ limit: '10mb' }));  // Prevent payload bombs
```

### Severity mapping

| Missing Control | Severity |
|----------------|----------|
| No ValidationPipe | HIGH |
| ValidationPipe without `whitelist: true` | MEDIUM |
| No Helmet | MEDIUM |
| CORS `origin: '*'` | HIGH |
| No CORS configuration | MEDIUM |
| No rate limiting | HIGH (on auth endpoints), MEDIUM (general) |
| No request size limit | LOW |

### Search patterns
```bash
grep -rn "ValidationPipe\|whitelist\|forbidNonWhitelisted" src/main.ts
grep -rn "helmet" src/main.ts
grep -rn "enableCors\|cors(" src/main.ts
grep -rn "ThrottlerModule\|throttle\|rateLimit" src/ --include="*.ts" -l
grep -rn "cookieParser\|cookie-parser" src/main.ts
grep -rn "limit.*mb\|limit.*kb" src/main.ts
```

---

## Authentication & Authorization

### Guards

- Check for global auth guard (`APP_GUARD` with `AuthGuard`). Without a global guard,
  every controller must apply its own, and a single miss is a vulnerability.
  ```typescript
  // GOOD: Global auth guard in module, endpoints opt-out with @Public()
  providers: [{ provide: APP_GUARD, useClass: JwtAuthGuard }]
  ```
- Audit every `@Public()` usage. Each one is an intentional bypass — verify they're on
  endpoints that should genuinely be public.
- Check for controllers with NO guard applied (no `@UseGuards()` and no global guard).

### JWT Configuration

- JWT secret from environment (not hardcoded)
- Token expiration configured and reasonable (not `expiresIn: '365d'`)
- Refresh token rotation implemented
- Token blacklist for logout/revocation
- Algorithm explicitly specified (prevent `none` algorithm attack)

### Role-Based Access Control

- Roles checked server-side via decorators/guards, not inferred from JWT claims alone
- Admin endpoints have explicit role requirements
- Missing `@Roles('admin')` on admin-only controllers

### Search patterns
```bash
grep -rn "APP_GUARD" src/ --include="*.ts"
grep -rn "@UseGuards" src/ --include="*.ts" | head -30
grep -rn "@Public()" src/ --include="*.ts"
grep -rn "@Roles(" src/ --include="*.ts"
grep -rn "JwtModule\|JwtService" src/ --include="*.ts" | grep -i "secret\|sign\|expire"
find src/ -name "*.controller.ts" | xargs grep -L "UseGuards\|@Public\|APP_GUARD"
```

---

## Input Validation & DTOs

Proper input validation is the primary defense against injection and many other attack classes.

### What to check

- Every controller method receiving `@Body()`, `@Query()`, or `@Param()` should use a DTO
- DTOs must have `class-validator` decorators on every property
- Check for `@Body() body: any` or untyped bodies — these bypass validation entirely
- `@Param()` values used in DB queries should be validated (UUID format, numeric, etc.)
- Array/nested object DTOs need `@ValidateNested()` and `@Type()`
- File upload DTOs need size/type validation

```typescript
// BAD: no DTO, raw body
@Post()
create(@Body() body: any) { return this.service.create(body); }

// BAD: DTO without validators
export class CreateUserDto {
  name: string;    // no @IsString(), @MinLength(), etc.
  email: string;   // no @IsEmail()
}

// GOOD
export class CreateUserDto {
  @IsString()
  @MinLength(2)
  @MaxLength(100)
  name: string;

  @IsEmail()
  email: string;

  @IsStrongPassword()
  password: string;
}
```

### Search patterns
```bash
grep -rn "@Body()" src/ --include="*.controller.ts" | grep -i "any\|:\s*{" 
grep -rn "@Query()" src/ --include="*.controller.ts" | grep -i "any"
find src/ -name "*.dto.ts" | xargs grep -L "IsString\|IsNumber\|IsEmail\|IsNotEmpty\|IsUUID"
find src/ -name "*.controller.ts" | xargs grep -c "@Body\|@Query\|@Param" | grep -v ":0$"
```

---

## Database & ORM Security

### TypeORM

- Raw queries with string interpolation:
  ```typescript
  // BAD: SQL injection
  const users = await this.repo.query(`SELECT * FROM users WHERE name = '${name}'`);

  // GOOD: parameterized
  const users = await this.repo.query('SELECT * FROM users WHERE name = $1', [name]);
  ```
- `createQueryBuilder` with unsanitized `.where()` strings
- Missing `select` on queries returning sensitive fields (password hash, tokens)
- Relations loaded eagerly when not needed (data leakage)

### Mongoose / MongoDB

- `$where` with user input (JavaScript injection)
- Unvalidated `$regex` patterns (ReDoS)
- Missing schema validation
- Object injection via `req.body` passed directly to `.find()` or `.updateOne()`

### Prisma

- Raw queries via `$queryRaw` or `$executeRaw` with template literals
- Missing field selection (returning password hashes)
- No row-level security (ownership checks at application layer)

### General

- Database credentials hardcoded in config files
- Missing connection pool limits
- No query timeout configuration
- Migrations not in version control

### Search patterns
```bash
grep -rn "\.query(\|queryRaw\|executeRaw\|\$where\|\.raw(" src/ --include="*.ts"
grep -rn "createQueryBuilder" src/ --include="*.ts" | grep -v "node_modules"
grep -rn "select.*password\|select.*hash\|select.*token\|select.*secret" src/ --include="*.ts"
grep -rn "\$regex" src/ --include="*.ts"
grep -rn "DB_HOST\|DB_PASSWORD\|DATABASE_URL\|MONGO_URI" src/ --include="*.ts" | grep -v "process\.env\|configService"
```

---

## Error Handling

### Global Exception Filter

NestJS should have a global exception filter that:
- Catches all unhandled exceptions
- Returns safe error responses (no stack traces, no internal paths)
- Logs the full error server-side
- Differentiates between operational errors and programmer errors

```typescript
// Check for global filter in main.ts or module
app.useGlobalFilters(new AllExceptionsFilter());
// OR
providers: [{ provide: APP_FILTER, useClass: AllExceptionsFilter }]
```

### What to check

- Empty catch blocks (`catch (e) {}` or `catch {}`)
- Catch blocks that return `error.message` or `error.stack` to the client
- Missing `try-catch` around DB operations in services
- Unhandled promise rejections (async methods without `.catch()` or `try-catch`)
- Error responses leaking entity names, table names, or column names

### Search patterns
```bash
grep -rn "APP_FILTER\|useGlobalFilters\|ExceptionFilter" src/ --include="*.ts" -l
grep -rn "catch\s*{" src/ --include="*.ts"
grep -rn "error\.message\|error\.stack\|err\.message\|err\.stack" src/ --include="*.ts" | grep -i "res\.\|response\.\|return\|throw.*Http"
grep -rn "\.catch(\s*(\s*)\s*=>" src/ --include="*.ts"
```

---

## File Upload Security

- Missing file type validation (accept any file)
- No file size limits
- User-controlled filenames used for storage (path traversal)
- Files stored in publicly accessible location without auth check
- Missing virus/malware scanning
- Image processing without size limits (zip bomb via SVG/image)

### Search patterns
```bash
grep -rn "FileInterceptor\|FilesInterceptor\|multer\|upload" src/ --include="*.ts" -l
grep -rn "fileFilter\|mimetype\|fileSize\|limits" src/ --include="*.ts"
grep -rn "originalname\|filename" src/ --include="*.ts" | grep -v "node_modules"
```

---

## GraphQL Specific

If the NestJS app uses GraphQL (`@nestjs/graphql`):

- Missing query depth limiting (DoS via deeply nested queries)
- No query complexity analysis
- Missing field-level authorization
- Introspection enabled in production
- Batching attacks allowed (multiple auth attempts in one request)

### Search patterns
```bash
grep -rn "GraphQLModule\|@nestjs/graphql" src/ --include="*.ts" -l
grep -rn "introspection\|playground\|debug" src/ --include="*.ts" | grep -i "graphql"
grep -rn "depthLimit\|queryComplexity\|maxDepth\|maxComplexity" src/ --include="*.ts"
```

---

## Microservices & Messaging

If the app uses NestJS microservices (message brokers, gRPC, etc.):

- Missing message validation (messages from queues are untrusted input)
- No authentication between services
- Sensitive data in message payloads without encryption
- Missing dead letter queues for failed messages
- Event handlers without idempotency (replay attacks)

### Search patterns
```bash
grep -rn "@MessagePattern\|@EventPattern\|ClientProxy" src/ --include="*.ts" -l
grep -rn "Transport\.\|microservice" src/ --include="*.ts" | head -10
```

---

## Configuration & Secrets

- `ConfigModule` not using validation schema (Joi or class-validator)
- Missing `.env.example` file (unclear which env vars are required)
- Secrets accessible via unprotected config endpoints
- Default values for secrets in code (fallback to insecure defaults)
  ```typescript
  // BAD: insecure default
  const secret = configService.get('JWT_SECRET') || 'default-secret';

  // GOOD: fail if missing
  const secret = configService.getOrThrow('JWT_SECRET');
  ```
- Environment variables logged at startup

### Search patterns
```bash
grep -rn "getOrThrow\|get(" src/ --include="*.ts" | grep -i "configService" | grep "||.*['\"]"
grep -rn "Joi\|validationSchema\|validate.*env\|envValidation" src/ --include="*.ts" -l
cat .env.example 2>/dev/null || echo "No .env.example found"
grep -rn "console.*process\.env\|log.*process\.env\|Logger.*env" src/ --include="*.ts"
```
