# Cross-Site Scripting (XSS) Prevention

XSS（クロスサイト・スクリプティング）対策の詳細。Laravel/Blade とReact の両方の対策を提供する。

## Table of Contents

- [XSS Overview](#xss-overview)
  - [Threat & Impact](#threat--impact)
  - [XSS Types](#xss-types)
- [Laravel / Blade XSS Prevention](#laravel--blade-xss-prevention)
  - [Vulnerable Code Examples](#vulnerable-code-examples)
  - [Safe Code Examples](#safe-code-examples)
  - [Blade Escaping Rules](#blade-escaping-rules)
  - [HTML Purifier](#html-purifier-when-html-is-allowed)
- [React XSS Prevention](#react-xss-prevention)
  - [Vulnerable Code Examples](#vulnerable-code-examples-1)
  - [Safe Code Examples](#safe-code-examples-1)
  - [DOMPurify Installation & Configuration](#dompurify-installation--configuration)
  - [URL Validation](#url-validation-javascript-scheme-prevention)
- [Content Security Policy (CSP)](#content-security-policy-csp)
  - [Laravel Middleware Implementation](#laravel-middleware-implementation)
  - [Middleware Registration](#middleware-registration)
  - [CSP Directives Reference](#csp-directives-reference)
  - [CSP with External Resources](#csp-with-external-resources)
  - [CSP Report-Only Mode](#csp-report-only-mode)
- [XSS Prevention Summary](#xss-prevention-summary)
  - [Diagnosis Checklist](#diagnosis-checklist)
  - [Quick Reference](#quick-reference)

---

## XSS Overview

### Threat & Impact

XSSは**IPA届出件数の約5割を占める最も多い脆弱性**。攻撃者はスクリプトを挿入し、**偽ページ表示、Cookie窃取によるセッションハイジャック、マルウェア感染**を引き起こす。

### XSS Types

| タイプ | 特徴 | 例 |
|--------|------|-----|
| **Reflected XSS** | URLパラメータから即座に反映 | 検索結果画面、エラー表示 |
| **Stored XSS** | DBに保存され全員に影響 | 掲示板、コメント機能 |
| **DOM-based XSS** | クライアントサイドで完結 | innerHTML操作 |

---

## Laravel / Blade XSS Prevention

### Vulnerable Code Examples

```blade
{{-- ❌ 危険: エスケープなしの出力 --}}
<div>{!! $content !!}</div>

{{-- ❌ 危険: 属性値のクォートなし --}}
<input type="text" value={{ $text }}>

{{-- ❌ 危険: JavaScript内での不適切な出力 --}}
<button onclick="test({{$text}})">ボタン</button>
```

### Safe Code Examples

```blade
{{-- ✅ 安全: Bladeの自動エスケープ（{{ }}） --}}
<div>{{ $content }}</div>
{{-- 自動的にhtmlentities()が適用される --}}

{{-- ✅ 安全: 属性値の適切なクォート --}}
<input type="text" value="{{ $text }}">

{{-- ✅ 安全: JavaScript内での安全な出力 --}}
<script>
const data = @json($data);
</script>

{{-- ✅ 安全: @json ディレクティブ --}}
<button onclick="test(@json(['text' => $text]))">
    ボタン
</button>
```

### Blade Escaping Rules

| コンテキスト | エスケープ方法 | 例 |
|------------|--------------|-----|
| **HTML Body** | `{{ }}` | `<div>{{ $content }}</div>` |
| **HTML Attributes** | `{{ }}` + クォート | `<input value="{{ $text }}">` |
| **JavaScript** | `@json()` | `const data = @json($data);` |
| **URL** | `{{ }}` + `rawurlencode()` | `href="{{ rawurlencode($url) }}"` |

### HTML Purifier (When HTML is Allowed)

**Installation**:
```bash
composer require mews/purifier
```

**Basic Usage**:
```php
// Controller での使用
$cleanHtml = Purifier::clean($dirtyHtml);
```

**Eloquent Model Cast (Recommended)**:
```php
use Mews\Purifier\Casts\CleanHtml;

class Post extends Model
{
    protected $casts = [
        'body' => CleanHtml::class,  // 入出力時に自動サニタイズ
    ];
}
```

**Blade Template**:
```blade
{{-- HTMLPurifier でサニタイズ済みのみ {!! !!} 使用可 --}}
<div>{!! Purifier::clean($userContent) !!}</div>

{{-- または Eloquent Cast で自動サニタイズされた場合 --}}
<div>{!! $post->body !!}</div>
```

**Configuration** (`config/purifier.php`):
```php
return [
    'default' => [
        'HTML.Allowed' => 'p,h1,h2,h3,ul,ol,li,a[href],img[src|alt],strong,em',
        'CSS.AllowedProperties' => '',
        'AutoFormat.RemoveEmpty' => true,
    ],
];
```

---

## React XSS Prevention

### Vulnerable Code Examples

```jsx
// ❌ 極めて危険: サニタイズなしのdangerouslySetInnerHTML
function UnsafeComponent({ htmlContent }) {
  return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
}

// ❌ 危険: javascript: URLスキーム
function LinkComponent({ userUrl }) {
  return <a href={userUrl}>Click me</a>;
}
// 攻撃例: userUrl = "javascript:alert('XSS')"
```

### Safe Code Examples

```jsx
// ✅ 安全: JSXの自動エスケープ（デフォルト）
function SafeComponent({ userInput }) {
  // <script>タグは文字列として表示される
  return <div>{userInput}</div>;
}

// ✅ 安全: DOMPurifyによるサニタイズ
import DOMPurify from 'dompurify';

interface SafeHTMLProps {
  content: string;
}

export function SafeHTML({ content }: SafeHTMLProps) {
  const sanitizedContent = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: ['p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'img'],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title']
  });

  return <div dangerouslySetInnerHTML={{ __html: sanitizedContent }} />;
}
```

### DOMPurify Installation & Configuration

**Installation**:
```bash
npm install dompurify
npm install --save-dev @types/dompurify
```

**Safe HTML Component**:
```tsx
import DOMPurify from 'dompurify';

interface SafeHTMLProps {
  content: string;
  allowedTags?: string[];
  allowedAttributes?: string[];
}

export function SafeHTML({
  content,
  allowedTags = ['p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'img'],
  allowedAttributes = ['href', 'src', 'alt', 'title']
}: SafeHTMLProps) {
  const sanitizedContent = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: allowedAttributes
  });

  return <div dangerouslySetInnerHTML={{ __html: sanitizedContent }} />;
}
```

### URL Validation (javascript: Scheme Prevention)

```tsx
// ✅ 安全: URLの検証（javascript:スキーム対策）
interface SafeLinkProps {
  userUrl: string;
  children: React.ReactNode;
}

export function SafeLink({ userUrl, children }: SafeLinkProps) {
  const getSafeUrl = (url: string): string => {
    try {
      const parsed = new URL(url);
      // http:, https: のみ許可
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        return '#';
      }
      return url;
    } catch (e) {
      return '#';  // 無効なURLは#にフォールバック
    }
  };

  return <a href={getSafeUrl(userUrl)}>{children}</a>;
}
```

**Usage**:
```tsx
// ✅ 安全な使用例
<SafeLink userUrl={userProvidedUrl}>
  クリックしてください
</SafeLink>
```

---

## Content Security Policy (CSP)

CSPは、XSS攻撃を軽減するための追加的なセキュリティレイヤー。

### Laravel Middleware Implementation

```php
// app/Http/Middleware/AddContentSecurityPolicy.php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class AddContentSecurityPolicy
{
    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        $csp = $this->buildContentSecurityPolicy();
        $response->headers->set('Content-Security-Policy', $csp);

        return $response;
    }

    private function buildContentSecurityPolicy(): string
    {
        $policies = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  // Tailwind CSS用
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "frame-ancestors 'self'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ];

        return implode('; ', $policies);
    }
}
```

### Middleware Registration

```php
// bootstrap/app.php (Laravel 11)
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->append(\App\Http\Middleware\AddContentSecurityPolicy::class);
    })
    ->create();
```

### CSP Directives Reference

| ディレクティブ | 推奨設定 | 目的 |
|--------------|---------|------|
| `default-src` | `'self'` | デフォルトで同一オリジンのみ許可 |
| `script-src` | `'self'` | スクリプトは同一オリジンのみ |
| `style-src` | `'self' 'unsafe-inline'` | インラインスタイル許可（Tailwind CSS用） |
| `img-src` | `'self' data: https:` | 画像はdata URIとHTTPS許可 |
| `frame-ancestors` | `'self'` | iframe埋め込み制限 |
| `object-src` | `'none'` | Flash等のプラグイン禁止 |
| `base-uri` | `'self'` | `<base>` タグのURL制限 |

### CSP with External Resources

CDNなど外部リソース使用時の設定例:

```php
private function buildContentSecurityPolicy(): string
{
    $policies = [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https:",
    ];

    return implode('; ', $policies);
}
```

### CSP Report-Only Mode

本番環境導入前にReport-Onlyモードで動作確認:

```php
// 違反をレポートするが、ブロックはしない
$response->headers->set('Content-Security-Policy-Report-Only', $csp);
```

---

## XSS Prevention Summary

### Laravel/Blade

| 環境 | 基本対策 | HTML許可時 | JavaScript |
|------|---------|-----------|-----------|
| **Blade** | `{{ }}` 使用 | HTMLPurifier | `@json()` |

### React

| 環境 | 基本対策 | HTML許可時 | URL検証 |
|------|---------|-----------|---------|
| **React** | JSX自動エスケープ | DOMPurify | protocol検証 |

### Diagnosis Checklist

**Laravel/Blade**:
- [ ] Bladeテンプレートで `{{ }}` を使用している
- [ ] `{!! !!}` を使用する場合は HTMLPurifier でサニタイズしている
- [ ] HTML属性値がダブルクォートで囲まれている
- [ ] JavaScript内で変数を出力する場合は `@json()` を使用している
- [ ] HTMLPurifier の `CleanHtml` キャストを使用している（HTML許可時）

**React**:
- [ ] JSXのデフォルト動作（自動エスケープ）を活用している
- [ ] `dangerouslySetInnerHTML` 使用時に DOMPurify でサニタイズしている
- [ ] DOMPurify の `ALLOWED_TAGS` と `ALLOWED_ATTR` を明示的に指定している
- [ ] ユーザー入力のURLに `javascript:` スキームが含まれていないか検証している
- [ ] URL検証には `new URL()` でパースして protocol をチェックしている
- [ ] インラインイベントハンドラ（`onclick` 等）を使用していない

**CSP**:
- [ ] CSPヘッダーが適切に設定されている
- [ ] `'unsafe-inline'` と `'unsafe-eval'` は必要最小限に抑えている
- [ ] 本番環境導入前に Report-Only モードで動作確認している

### Quick Reference

| 操作 | ❌ 危険 | ✅ 安全 |
|-----|--------|--------|
| **Blade HTML** | `{!! $content !!}` | `{{ $content }}` |
| **Blade HTML許可** | `{!! $html !!}` | `{!! Purifier::clean($html) !!}` |
| **React HTML** | `dangerouslySetInnerHTML` | `DOMPurify.sanitize()` + `dangerouslySetInnerHTML` |
| **React URL** | `<a href={userUrl}>` | `<SafeLink userUrl={userUrl}>` |
