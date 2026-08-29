# Access Control & Authentication

アクセス制御・認可制御（IDOR対策）と認証・パスワード管理のベストプラクティス。

## Table of Contents

- [Access Control & IDOR Prevention](#access-control--idor-prevention)
  - [Threat & Impact](#threat--impact)
  - [Vulnerable Code Examples](#vulnerable-code-examples)
  - [Safe Code Examples](#safe-code-examples)
  - [Laravel Policy Implementation](#laravel-policy-implementation)
  - [React SPA Access Control](#react-spa-access-control)
- [Password Management](#password-management)
  - [Password Hashing (Laravel)](#password-hashing-laravel)
  - [Argon2id Configuration (Recommended)](#argon2id-configuration-recommended)
  - [Password Validation](#password-validation)
  - [Rate Limiting (Brute Force Prevention)](#rate-limiting-brute-force-prevention)
  - [Multi-Factor Authentication (MFA)](#multi-factor-authentication-mfa)
- [Diagnosis Checklist](#diagnosis-checklist)
  - [Access Control](#access-control)
  - [Password Management](#password-management-1)
- [Quick Reference](#quick-reference)

---

## Access Control & IDOR Prevention {#idor}

### Threat & Impact

利用者IDをURLやPOSTパラメータに埋め込んでいる実装では、**IDOR（Insecure Direct Object Reference）**により、他のユーザーのデータに不正アクセスされる危険がある。

---

### Vulnerable Code Examples

```php
// ❌ 脆弱: 認可制御なし - IDORの脆弱性
public function show($id)
{
    // URLパラメータのIDをそのまま使用
    $post = Post::find($id);
    return view('posts.show', compact('post'));
}

// ❌ 脆弱: ユーザーIDをリクエストから取得
public function showProfile(Request $request)
{
    $userId = $request->input('user_id'); // 外部入力をそのまま使用
    $user = User::find($userId);
    return view('profile', compact('user'));
}
```

**Attack Example**:
```
GET /api/posts/123 → 自分の投稿
GET /api/posts/456 → 他人の投稿にもアクセス可能（脆弱性）
```

---

### Safe Code Examples

```php
// ✅ 安全: Policyによる認可チェック
public function show(Post $post)
{
    $this->authorize('view', $post);
    return view('posts.show', compact('post'));
}

// ✅ 安全: セッションから認証済みユーザーを取得
public function showProfile()
{
    $user = auth()->user();
    return view('profile', compact('user'));
}

// ✅ 安全: スコープを使用して所有リソースのみアクセス
public function showOrder($orderId)
{
    $order = auth()->user()->orders()->findOrFail($orderId);
    return view('orders.show', compact('order'));
}
```

---

### Laravel Policy Implementation

**Policy Creation**:

```php
// app/Policies/PostPolicy.php
namespace App\Policies;

use App\Models\Post;
use App\Models\User;
use Illuminate\Auth\Access\Response;

class PostPolicy
{
    /**
     * ✅ 管理者は全てのアクションを許可
     */
    public function before(User $user, string $ability): ?bool
    {
        if ($user->is_admin) {
            return true;
        }
        return null;
    }

    /**
     * ✅ 投稿の閲覧権限
     */
    public function view(User $user, Post $post): bool
    {
        // 公開済みまたは自分の投稿のみ閲覧可能
        return $post->is_published || $user->id === $post->user_id;
    }

    /**
     * ✅ 投稿の更新権限
     */
    public function update(User $user, Post $post): bool
    {
        return $user->id === $post->user_id;
    }

    /**
     * ✅ 投稿の削除権限
     */
    public function delete(User $user, Post $post): Response
    {
        if ($user->id === $post->user_id) {
            return Response::allow();
        }

        return Response::deny('この投稿を削除する権限がありません。');
    }
}
```

**Controller Usage**:

```php
// ✅ authorize() メソッドで認可チェック
public function update(Request $request, Post $post)
{
    $this->authorize('update', $post);

    // 認可が通った場合のみ実行される
    $post->update($request->validated());

    return redirect()->route('posts.show', $post);
}

// ✅ can() メソッドで条件分岐
public function show(Post $post)
{
    if (auth()->user()->can('view', $post)) {
        return view('posts.show', compact('post'));
    }

    abort(403, 'この投稿を閲覧する権限がありません。');
}
```

---

### React SPA Access Control

**ProtectedRoute Component**:

```tsx
// src/components/ProtectedRoute.tsx
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  requiredPermission?: string;
  requiredRole?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  requiredPermission,
  requiredRole,
}) => {
  const { isAuthenticated, isLoading, hasPermission, hasRole } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (requiredRole && !hasRole(requiredRole)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
};
```

**Usage Example**:

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* 認証が必要なルート */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
        </Route>

        {/* 管理者のみアクセス可能 */}
        <Route element={<ProtectedRoute requiredRole="admin" />}>
          <Route path="/admin" element={<AdminDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

**CRITICAL**: フロントエンドの認可チェックは**UI表示制御のみ**であり、**バックエンドでの認可チェックが必須**。

---

## Password Management {#password-management}

### Password Hashing (Laravel)

```php
use Illuminate\Support\Facades\Hash;

// ✅ パスワードのハッシュ化
$user = User::create([
    'name' => $request->name,
    'email' => $request->email,
    'password' => Hash::make($request->password),
]);

// ✅ パスワード検証
if (Hash::check($plainPassword, $user->password)) {
    // パスワードが一致
}
```

### Argon2id Configuration (Recommended)

```php
// config/hashing.php
return [
    'driver' => 'argon2id',  // ✅ bcrypt より安全

    'argon' => [
        'memory' => 65536,
        'threads' => 4,
        'time' => 4,
    ],
];
```

**.env**:
```env
HASH_DRIVER=argon2id
```

---

### Password Validation

```php
use Illuminate\Validation\Rules\Password;

$request->validate([
    'password' => [
        'required',
        'confirmed',
        Password::min(8)
            ->mixedCase()        // 大文字小文字を含む
            ->numbers()          // 数字を含む
            ->symbols()          // 記号を含む
            ->uncompromised(),   // 漏洩パスワードチェック（Have I Been Pwned API）
    ],
]);
```

**Custom Password Rules**:

```php
// プロジェクト固有のルール
Password::min(12)
    ->mixedCase()
    ->numbers()
    ->symbols()
    ->uncompromised(3);  // 3回以上漏洩していないこと
```

---

### Rate Limiting (Brute Force Prevention)

**Basic Rate Limiting**:

```php
// routes/web.php
Route::post('/login', [LoginController::class, 'login'])
    ->middleware('throttle:5,1'); // 1分間に5回まで
```

**Custom Rate Limiter**:

```php
// app/Providers/AppServiceProvider.php
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;

public function boot(): void
{
    RateLimiter::for('login', function (Request $request) {
        return Limit::perMinute(5)->by(
            $request->input('email') . '|' . $request->ip()
        )->response(function () {
            return response()->json([
                'message' => 'ログイン試行回数が多すぎます。しばらくお待ちください。'
            ], 429);
        });
    });
}
```

**Controller Usage**:

```php
Route::post('/login', [LoginController::class, 'login'])
    ->middleware('throttle:login');
```

---

### Multi-Factor Authentication (MFA)

**Laravel Fortify MFA**:

```bash
composer require laravel/fortify
```

**config/fortify.php**:

```php
'features' => [
    Features::twoFactorAuthentication([
        'confirm' => true,
        'confirmPassword' => true,
    ]),
],
```

---

## Diagnosis Checklist

### Access Control

- [ ] 全ての保護リソースに対してサーバーサイドで認可チェックを実装している
- [ ] Laravel Policy を使用してリソースアクセスを制御している
- [ ] URLパラメータからユーザーIDを取得していない
- [ ] セッションから認証済みユーザー情報を取得している（`auth()->user()`）
- [ ] 所有リソースへのアクセスはスコープを使用している（`user()->posts()`）
- [ ] Controller で `$this->authorize()` を使用している
- [ ] フロントエンドの認可チェックのみに依存していない

### Password Management

- [ ] パスワードは `Hash::make()` でハッシュ化している
- [ ] ハッシュアルゴリズムは bcrypt または Argon2id を使用している
- [ ] パスワードポリシーを適用している（最小8文字、大小英数記号）
- [ ] `Password::min(8)->mixedCase()->numbers()->symbols()` を使用している
- [ ] `Password::uncompromised()` で漏洩パスワードをチェックしている
- [ ] ログインエンドポイントにレート制限を適用している（5回/分）
- [ ] カスタムレートリミッターでメールアドレス+IPアドレスで制限している
- [ ] 本番環境では多要素認証（MFA）を導入している（推奨）
- [ ] パスワードを平文で保存していない
- [ ] MD5やSHA1でパスワードをハッシュ化していない

---

## Quick Reference

| 操作 | ❌ 危険 | ✅ 安全 |
|-----|--------|--------|
| **User ID** | `$request->input('user_id')` | `auth()->user()->id` |
| **Resource Access** | `Post::find($id)` | `$this->authorize('view', $post)` |
| **Owned Resource** | `Post::find($id)` | `auth()->user()->posts()->find($id)` |
| **Password Hash** | `md5($password)` | `Hash::make($password)` |
| **Password Check** | `$user->password === $input` | `Hash::check($input, $user->password)` |
| **Login Protection** | なし | `->middleware('throttle:5,1')` |
