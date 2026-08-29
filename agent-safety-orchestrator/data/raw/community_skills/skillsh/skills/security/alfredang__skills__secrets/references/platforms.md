# Platform-Specific .env Loading Patterns

## Table of Contents
- [Node.js / JavaScript / TypeScript](#nodejs--javascript--typescript)
- [Python](#python)
- [Ruby](#ruby)
- [Go](#go)
- [Java / Kotlin (Spring Boot)](#java--kotlin-spring-boot)
- [PHP / Laravel](#php--laravel)
- [Rust](#rust)
- [Swift / iOS](#swift--ios)
- [Android / Kotlin](#android--kotlin)
- [Flutter / Dart](#flutter--dart)
- [C# / .NET](#c--net)
- [Docker & Docker Compose](#docker--docker-compose)
- [CI/CD Platforms](#cicd-platforms)

---

## Node.js / JavaScript / TypeScript

### Install
```bash
npm install dotenv
```

### Load (.env at project root)
```js
// Load at the very top of entry file (before any other imports that use env vars)
require('dotenv').config();
// or ES modules:
import 'dotenv/config';
```

### Access
```js
const apiKey = process.env.API_KEY;
const dbUrl = process.env.DATABASE_URL;
```

### Frameworks
- **Next.js**: Built-in `.env.local` support. Prefix with `NEXT_PUBLIC_` for client-side exposure.
- **Vite**: Built-in `.env` support. Prefix with `VITE_` for client-side exposure via `import.meta.env.VITE_*`.
- **Create React App**: Built-in. Prefix with `REACT_APP_` for client-side.
- **Nuxt**: Built-in `runtimeConfig` reads from `.env`. Use `NUXT_` prefix.
- **Remix**: Use `dotenv` in `entry.server.ts`. Never expose secrets to client loaders.
- **Express**: `require('dotenv').config()` at top of `app.js` / `server.js`.
- **NestJS**: Use `@nestjs/config` with `ConfigModule.forRoot()`.

---

## Python

### Install
```bash
pip install python-dotenv
```

### Load
```python
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env from current directory or parents
```

### Access
```python
api_key = os.getenv("API_KEY")
db_url = os.environ["DATABASE_URL"]  # raises KeyError if missing
```

### Frameworks
- **Django**: Add `load_dotenv()` in `manage.py` and `wsgi.py` before `django.setup()`.
- **Flask**: `load_dotenv()` before `app = Flask(__name__)`.
- **FastAPI**: `load_dotenv()` in main or use `pydantic-settings` with `BaseSettings`.

---

## Ruby

### Install
```bash
gem install dotenv
# or in Gemfile:
gem 'dotenv-rails', groups: [:development, :test]  # for Rails
```

### Load
```ruby
require 'dotenv/load'
```

### Access
```ruby
api_key = ENV['API_KEY']
db_url = ENV.fetch('DATABASE_URL')  # raises if missing
```

---

## Go

### Install
```bash
go get github.com/joho/godotenv
```

### Load
```go
import "github.com/joho/godotenv"

func init() {
    godotenv.Load() // loads .env
}
```

### Access
```go
apiKey := os.Getenv("API_KEY")
```

---

## Java / Kotlin (Spring Boot)

Spring Boot natively reads from `application.properties` or `application.yml`, but `.env` files can be used:

### Using spring-dotenv
```xml
<dependency>
    <groupId>me.paulschwarz</groupId>
    <artifactId>spring-dotenv</artifactId>
    <version>4.0.0</version>
</dependency>
```

### application.properties
```properties
api.key=${API_KEY}
spring.datasource.url=${DATABASE_URL}
```

### Access
```java
@Value("${api.key}")
private String apiKey;
```

---

## PHP / Laravel

Laravel has built-in `.env` support via `vlucas/phpdotenv`.

### Access
```php
$apiKey = env('API_KEY');
$dbUrl = config('database.connections.mysql.host'); // via config, preferred
```

### Other PHP frameworks
```bash
composer require vlucas/phpdotenv
```
```php
$dotenv = Dotenv\Dotenv::createImmutable(__DIR__);
$dotenv->load();
$apiKey = $_ENV['API_KEY'];
```

---

## Rust

### Install
```toml
[dependencies]
dotenvy = "0.15"
```

### Load & Access
```rust
use dotenvy::dotenv;
use std::env;

fn main() {
    dotenv().ok();
    let api_key = env::var("API_KEY").expect("API_KEY must be set");
}
```

---

## Swift / iOS

iOS does not use `.env` files at runtime. Use Xcode configuration files instead:

### .xcconfig approach
1. Create `Secrets.xcconfig` (add to `.gitignore`)
2. Reference in Info.plist: `$(API_KEY)`
3. Access:
```swift
let apiKey = Bundle.main.infoDictionary?["API_KEY"] as? String
```

### For server-side Swift (Vapor)
```swift
// Vapor reads .env automatically
let apiKey = Environment.get("API_KEY")
```

---

## Android / Kotlin

### Using local.properties (gitignored by default)
```properties
# local.properties
API_KEY=your-key-here
```

### build.gradle.kts
```kotlin
val localProperties = Properties().apply {
    load(rootProject.file("local.properties").inputStream())
}
android {
    defaultConfig {
        buildConfigField("String", "API_KEY", "\"${localProperties["API_KEY"]}\"")
    }
}
```

### Access
```kotlin
val apiKey = BuildConfig.API_KEY
```

---

## Flutter / Dart

### Install
```bash
flutter pub add flutter_dotenv
```

### Load
```dart
import 'package:flutter_dotenv/flutter_dotenv.dart';

Future main() async {
  await dotenv.load(fileName: ".env");
  runApp(MyApp());
}
```

### Access
```dart
final apiKey = dotenv.env['API_KEY'];
```

### pubspec.yaml
```yaml
assets:
  - .env
```
**Warning**: `.env` is bundled into the app. For sensitive secrets in mobile, use a backend proxy.

---

## C# / .NET

### Install
```bash
dotnet add package DotNetEnv
```

### Load
```csharp
DotNetEnv.Env.Load();
```

### Access
```csharp
var apiKey = Environment.GetEnvironmentVariable("API_KEY");
```

### ASP.NET Core (built-in)
Use User Secrets for development:
```bash
dotnet user-secrets set "API_KEY" "your-key"
```
Access via `IConfiguration`:
```csharp
var apiKey = configuration["API_KEY"];
```

---

## Docker & Docker Compose

### Dockerfile
```dockerfile
# NEVER put secrets in Dockerfile
# Pass at runtime:
# docker run --env-file .env myapp
```

### docker-compose.yml
```yaml
services:
  app:
    env_file:
      - .env
    # or individual vars:
    environment:
      - API_KEY=${API_KEY}
```

---

## CI/CD Platforms

Never commit secrets. Use platform secret stores:

- **GitHub Actions**: Settings > Secrets > Actions. Access via `${{ secrets.API_KEY }}`
- **GitLab CI**: Settings > CI/CD > Variables. Access via `$API_KEY`
- **Vercel**: Project Settings > Environment Variables
- **Netlify**: Site Settings > Environment Variables
- **AWS**: Parameter Store, Secrets Manager
- **GCP**: Secret Manager
- **Azure**: Key Vault
- **Heroku**: Config Vars via `heroku config:set API_KEY=value`
