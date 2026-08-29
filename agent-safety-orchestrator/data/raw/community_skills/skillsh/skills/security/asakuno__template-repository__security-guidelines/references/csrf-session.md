# CSRF & Session Management

CSRF（クロスサイト・リクエスト・フォージェリ）対策とセッション管理のベストプラクティス。

## Table of Contents

- [CSRF (Cross-Site Request Forgery)](#csrf-cross-site-request-forgery)
  - [Threat & Impact](#threat--impact)
  - [Laravel Blade CSRF Protection](#laravel-blade-csrf-protection)
  - [React SPA CSRF Protection](#react-spa-csrf-protection)
- [Session Management](#session-management)
  - [Threat & Impact](#threat--impact-1)
  - [Laravel Session Configuration](#laravel-session-configuration)
  - [Session Fixation Attack Prevention](#session-fixation-attack-prevention)
  - [Laravel Sanctum Configuration](#laravel-sanctum-configuration-spa-authentication)
- [Cookie Security Attributes](#cookie-security-attributes)
  - [Required Attributes](#required-attributes)
  - [SameSite Attribute Options](#samesite-attribute-options)
- [Session Driver Selection](#session-driver-selection)
  - [Driver Comparison](#driver-comparison)
  - [Database Driver Setup](#database-driver-setup)
  - [Redis Driver Setup](#redis-driver-setup)
- [Session Lifetime Configuration](#session-lifetime-configuration)
  - [Recommended Lifetimes](#recommended-lifetimes)
  - [Remember Me Implementation](#remember-me-implementation)
- [Diagnosis Checklist](#diagnosis-checklist)
  - [CSRF](#csrf)
  - [Session Management](#session-management-1)
  - [Quick Reference](#quick-reference)

---

## CSRF (Cross-Site Request Forgery) {#csrf}

### Threat & Impact

ログインした利用者からのリクエストが意図したものかを識別できない場合、**不正な送金、意図しない商品購入、パスワード変更、掲示板への不適切な書き込み**が発生する可能性がある。

---

### Laravel Blade CSRF Protection

#### Basic Usage

```blade
{{-- ✅ 安全: @csrfディレクティブ使用 --}}
<form method="POST" action="/transfer">
    @csrf
    <input type="text" name="amount" />
    <button type="submit">送金</button>
</form>
```

#### VerifyCsrfToken Middleware Configuration

外部Webhook等でCSRF検証を除外する場合のみ設定:

```php
// bootstrap/app.php (Laravel 11)
->withMiddleware(function (Middleware $middleware) {
    $middleware->validateCsrfTokens(except: [
        'stripe/*',      // Stripe webhook
        'webhook/*',     // 外部システムからのWebhook
    ]);
})
```

**Important**: 除外設定は必要最小限に限定し、安易な除外は避ける。

---

### React SPA CSRF Protection

#### Axios Configuration

```javascript
// src/services/api.js
import axios from 'axios';

const apiClient = axios.create({
    baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    },
    // ✅ クレデンシャル（Cookie）を含める
    withCredentials: true,
    // ✅ XSRFトークンを自動送信
    withXSRFToken: true,
});

export default apiClient;
```

#### Authentication Flow

```typescript
// src/services/auth.ts
import apiClient from './api';

// CSRFトークンの取得
export const getCsrfToken = async (): Promise<void> => {
    await apiClient.get('/sanctum/csrf-cookie');
};

// ログイン処理
export const login = async (email: string, password: string): Promise<User> => {
    // ✅ 最初にCSRFトークンを取得
    await getCsrfToken();

    await apiClient.post('/login', { email, password });
    return await getUser();
};
```

**Critical**: ログイン前に必ず `/sanctum/csrf-cookie` にアクセスする。

---

## Session Management {#session-management}

### Threat & Impact

セッションIDの発行・管理に不備がある場合、**セッションIDの推測・盗用・固定化攻撃**により、なりすましアクセスが発生する。

---

### Laravel Session Configuration

#### config/session.php

```php
return [
    // セッションドライバ（本番環境ではdatabase/redis推奨）
    'driver' => env('SESSION_DRIVER', 'database'),

    // セッション有効期限（分）
    'lifetime' => env('SESSION_LIFETIME', 120),

    // ブラウザ終了時にセッション破棄
    'expire_on_close' => true,

    // セッションデータの暗号化
    'encrypt' => true,

    // ✅ HTTPS通信のみでCookieを送信
    'secure' => env('SESSION_SECURE_COOKIE', true),

    // ✅ JavaScriptからのアクセスを禁止
    'http_only' => true,

    // ✅ SameSite属性（Strict/Lax/None）
    'same_site' => 'lax',
];
```

#### .env Configuration (Production)

```env
SESSION_DRIVER=database
SESSION_LIFETIME=120
SESSION_SECURE_COOKIE=true
SESSION_DOMAIN=.example.com
```

---

### Session Fixation Attack Prevention

#### Login Implementation

```php
// ✅ 安全: ログイン成功後にセッションID再生成
public function login(Request $request)
{
    $credentials = $request->only('email', 'password');

    if (Auth::attempt($credentials)) {
        // ✅ セッション固定化攻撃対策
        $request->session()->regenerate();

        return redirect()->intended('dashboard');
    }

    return back()->withErrors(['email' => 'Invalid credentials']);
}
```

#### Logout Implementation

```php
// ✅ ログアウト時のセッション無効化
public function logout(Request $request)
{
    Auth::logout();

    // ✅ セッションを無効化し、新しいトークンを生成
    $request->session()->invalidate();
    $request->session()->regenerateToken();

    return redirect('/');
}
```

**Critical Points**:
1. ログイン成功後: `session()->regenerate()`
2. ログアウト時: `session()->invalidate()` + `session()->regenerateToken()`

---

### Laravel Sanctum Configuration (SPA Authentication)

#### config/sanctum.php

```php
return [
    // ✅ ステートフルドメインの設定（SPA認証に必須）
    'stateful' => explode(',', env('SANCTUM_STATEFUL_DOMAINS', sprintf(
        '%s%s',
        'localhost,localhost:3000,127.0.0.1,127.0.0.1:8000',
        env('APP_URL') ? ',' . parse_url(env('APP_URL'), PHP_URL_HOST) : ''
    ))),
];
```

#### .env File (Production)

```env
SANCTUM_STATEFUL_DOMAINS=example.com,www.example.com,app.example.com
SESSION_DOMAIN=.example.com
SESSION_SECURE_COOKIE=true
```

#### config/cors.php

```php
return [
    'paths' => ['api/*', 'sanctum/csrf-cookie', 'login', 'logout'],

    // ✅ フロントエンドのオリジンを明示的に指定
    'allowed_origins' => [env('FRONTEND_URL', 'http://localhost:3000')],

    // ✅ 重要: Cookie送信に必須
    'supports_credentials' => true,
];
```

**Important**: `supports_credentials: true` がないとCookieが送信されない。

---

## Cookie Security Attributes

### Required Attributes

| 属性 | 設定値 | 目的 |
|------|--------|------|
| `Secure` | `true` | HTTPS通信のみでCookie送信（本番環境必須） |
| `HttpOnly` | `true` | JavaScriptからのアクセス禁止（XSS対策） |
| `SameSite` | `Lax` / `Strict` | CSRF対策（クロスサイトリクエスト制限） |

### SameSite Attribute Options

| 値 | 動作 | 使用ケース |
|----|------|-----------|
| `Strict` | クロスサイトリクエストで一切送信しない | 高セキュリティ要求 |
| `Lax` | トップレベルナビゲーション（GET）のみ送信 | **推奨設定** |
| `None` | 常に送信（Secureと併用必須） | 外部サイトからの埋め込み |

---

## Session Driver Selection

### Driver Comparison

| 環境 | 推奨ドライバ | 理由 |
|------|------------|------|
| 開発環境 | `file` | シンプル・設定不要 |
| 本番環境（単一サーバ） | `database` | 永続化・監査ログ対応 |
| 本番環境（複数サーバ） | `redis` | 高速・負荷分散対応 |

### Database Driver Setup

**Migration**:
```bash
php artisan session:table
php artisan migrate
```

**.env**:
```env
SESSION_DRIVER=database
```

### Redis Driver Setup

**Installation**:
```bash
composer require predis/predis
```

**.env**:
```env
SESSION_DRIVER=redis
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=null
REDIS_PORT=6379
```

---

## Session Lifetime Configuration

### Recommended Lifetimes

| アプリケーション種別 | 推奨ライフタイム |
|-------------------|----------------|
| 一般的なWebアプリ | 120分（2時間） |
| 金融・医療システム | 15-30分 |
| 管理画面 | 30-60分 |
| 「ログイン状態を保持」機能 | `remember_token` 使用（セッションは短く） |

### Remember Me Implementation

```php
// ✅ 「ログイン状態を保持」機能
public function login(Request $request)
{
    $credentials = $request->only('email', 'password');
    $remember = $request->boolean('remember');

    if (Auth::attempt($credentials, $remember)) {
        $request->session()->regenerate();
        return redirect()->intended('dashboard');
    }

    return back()->withErrors(['email' => 'Invalid credentials']);
}
```

---

## Diagnosis Checklist

### CSRF

- [ ] POST/PUT/PATCH/DELETEフォームに `@csrf` を使用している
- [ ] React SPAで `withCredentials: true` と `withXSRFToken: true` を設定している
- [ ] ログイン前に `/sanctum/csrf-cookie` にアクセスしている
- [ ] 外部Webhook以外でCSRF検証を除外していない

### Session Management

- [ ] ログイン成功後に `session()->regenerate()` でセッションIDを再生成している
- [ ] ログアウト時に `session()->invalidate()` でセッションを無効化している
- [ ] ログアウト時に `session()->regenerateToken()` でトークンを再生成している
- [ ] CookieにSecure属性が設定されている（`SESSION_SECURE_COOKIE=true`）
- [ ] CookieにHttpOnly属性が設定されている（`http_only: true`）
- [ ] SameSite属性が適切に設定されている（`same_site: 'lax'` または `'strict'`）
- [ ] セッションドライバは本番環境で `database` または `redis` を使用している
- [ ] セッションの有効期限が適切に設定されている（推奨: 120分）
- [ ] `SANCTUM_STATEFUL_DOMAINS` が正しく設定されている（SPA認証使用時）
- [ ] CORS設定で `supports_credentials: true` を設定している（SPA認証使用時）

### Quick Reference

| 操作 | ❌ 危険 | ✅ 安全 |
|-----|--------|--------|
| **CSRF Blade** | `<form>` のみ | `<form>@csrf</form>` |
| **CSRF React** | デフォルト設定 | `withCredentials: true`, `withXSRFToken: true` |
| **Login** | そのまま認証 | `session()->regenerate()` |
| **Logout** | そのまま終了 | `session()->invalidate()` + `regenerateToken()` |
| **Cookie** | デフォルト | `Secure`, `HttpOnly`, `SameSite` 設定 |
