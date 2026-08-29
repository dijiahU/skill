# HTTP Header Vulnerabilities

HTTPヘッダ系脆弱性の対策。HTTPヘッダ・インジェクション、メールヘッダ・インジェクション、クリックジャッキング、およびセキュリティヘッダの包括的な実装を提供する。

## Table of Contents

- [HTTP Header Injection](#http-header-injection)
  - [Threat & Impact](#threat--impact)
  - [Safe Redirect Implementation](#safe-redirect-implementation)
  - [Diagnosis Checklist](#diagnosis-checklist)
- [Mail Header Injection](#mail-header-injection)
  - [Threat & Impact](#threat--impact-1)
  - [Safe Mail Implementation](#safe-mail-implementation-laravel-mailable)
  - [Mailable Class Example](#mailable-class-example)
  - [Diagnosis Checklist](#diagnosis-checklist-1)
- [Clickjacking](#clickjacking)
  - [Threat & Impact](#threat--impact-2)
  - [Security Headers Middleware](#security-headers-middleware-comprehensive)
  - [Middleware Registration](#middleware-registration)
- [Security Headers Reference](#security-headers-reference)
  - [Header Priorities](#header-priorities)
  - [CSP Directive Details](#csp-directive-details)
  - [CSP with External Resources](#csp-with-external-resources)
  - [CSP Report-Only Mode](#csp-report-only-mode)
- [Diagnosis Checklist](#diagnosis-checklist-2)
  - [General](#general)
  - [Clickjacking](#clickjacking-1)
  - [Security Headers](#security-headers)
  - [HTTP Header Injection](#http-header-injection-1)
  - [Mail Header Injection](#mail-header-injection-1)
- [Quick Reference](#quick-reference)

---

## HTTP Header Injection {#http-header-injection}

### Threat & Impact

HTTPレスポンスヘッダのフィールド値を外部パラメータから動的に生成する際に発生し、**XSSと同等の脅威、任意のCookie発行、キャッシュサーバの汚染**を引き起こす。

### Safe Redirect Implementation

```php
public function safeRedirect(Request $request)
{
    $url = $request->input('url');

    // ✅ 改行コードを削除
    $url = str_replace(["\r", "\n", "\r\n"], '', $url);

    // ✅ URLホワイトリストによる検証
    $allowedHosts = ['example.com', 'app.example.com'];
    $parsedUrl = parse_url($url);

    if (!isset($parsedUrl['host']) ||
        !in_array($parsedUrl['host'], $allowedHosts)) {
        return redirect('/');
    }

    // ✅ Laravelのredirect()を使用（内部で安全に処理）
    return redirect($url);
}
```

### Diagnosis Checklist

- [ ] ヘッダ出力には Laravel の `redirect()` や `response()` を使用している
- [ ] 外部入力から改行コード（`\r`, `\n`）を削除している
- [ ] URLリダイレクトにはホワイトリスト検証を実装している
- [ ] リダイレクト先のホスト名を検証している
- [ ] 生のヘッダ出力（`header()` 関数）を使用していない

---

## Mail Header Injection {#mail-header-injection}

### Threat & Impact

メール送信機能において、外部入力がメールヘッダに反映される場合、**スパムメールの踏み台利用、フィッシングメールの送信**が発生する。

### Safe Mail Implementation (Laravel Mailable)

```php
public function send(Request $request)
{
    $validated = $request->validate([
        'name' => 'required|string|max:100',
        'email' => 'required|email:rfc,dns',
        'subject' => 'required|string|max:200',
        'body' => 'required|string|max:5000',
    ]);

    // ✅ 改行コードを削除（件名に対して）
    $subject = preg_replace('/[\r\n\x00-\x1F\x7F]/', '', $validated['subject']);

    // ✅ Mailableクラスを使用した安全なメール送信
    Mail::to('admin@example.com')
        ->send(new ContactMail([
            'subject' => $subject,
            'name' => $validated['name'],
            'body' => $validated['body'],
        ]));

    return back()->with('success', 'お問い合わせを送信しました。');
}
```

### Mailable Class Example

```php
namespace App\Mail;

use Illuminate\Mail\Mailable;

class ContactMail extends Mailable
{
    public function __construct(
        private array $data
    ) {}

    public function build()
    {
        return $this->subject($this->data['subject'])
                    ->view('emails.contact')
                    ->with('data', $this->data);
    }
}
```

### Diagnosis Checklist

- [ ] メール送信は Mailable クラスを使用している
- [ ] メールヘッダに外部入力を直接使用していない
- [ ] 外部入力を件名等に使用する場合、改行コード・制御文字を削除している
- [ ] メールアドレスのバリデーションに `email:rfc,dns` を使用している
- [ ] 生の `mail()` 関数を使用していない

---

## Clickjacking {#clickjacking}

### Threat & Impact

透明化されたiframe内にターゲットサイトを埋め込み、ユーザーを視覚的に騙して**意図しないクリック操作**をさせる攻撃。

### Security Headers Middleware (Comprehensive)

すべてのセキュリティヘッダを一元管理するミドルウェア:

```php
// app/Http/Middleware/SecurityHeadersMiddleware.php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class SecurityHeadersMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        // ✅ クリックジャッキング対策
        $response->headers->set('X-Frame-Options', 'SAMEORIGIN');

        // ✅ CSP（クリックジャッキング + XSS対策）
        $csp = $this->buildContentSecurityPolicy();
        $response->headers->set('Content-Security-Policy', $csp);

        // ✅ MIMEスニッフィング防止
        $response->headers->set('X-Content-Type-Options', 'nosniff');

        // ✅ XSSフィルター（レガシーブラウザ向け）
        $response->headers->set('X-XSS-Protection', '1; mode=block');

        // ✅ HTTPS強制（本番環境のみ）
        if (app()->environment('production')) {
            $response->headers->set(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains; preload'
            );
        }

        // ✅ リファラーポリシー
        $response->headers->set(
            'Referrer-Policy',
            'strict-origin-when-cross-origin'
        );

        // ✅ Permissions-Policy（機能制限）
        $response->headers->set(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=()'
        );

        // ✅ サーバー情報の隠蔽
        $response->headers->remove('X-Powered-By');
        $response->headers->remove('Server');

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
        // ✅ セキュリティヘッダをすべてのレスポンスに適用
        $middleware->append(\App\Http\Middleware\SecurityHeadersMiddleware::class);
    })
    ->create();
```

---

## Security Headers Reference

### Header Priorities

| ヘッダ名 | 目的 | 推奨値 | 優先度 |
|---------|------|--------|--------|
| **X-Frame-Options** | クリックジャッキング対策 | `SAMEORIGIN` | 高 |
| **Content-Security-Policy** | XSS・リソース制御 | アプリに応じて設定 | 高 |
| **X-Content-Type-Options** | MIMEスニッフィング防止 | `nosniff` | 高 |
| **Strict-Transport-Security** | HTTPS強制 | `max-age=31536000; includeSubDomains` | 高（本番） |
| **Referrer-Policy** | リファラー情報制御 | `strict-origin-when-cross-origin` | 中 |
| **X-XSS-Protection** | XSSフィルター（レガシー） | `1; mode=block` | 低 |
| **Permissions-Policy** | ブラウザ機能制限 | `geolocation=(), microphone=()` | 中 |

### CSP Directive Details

| ディレクティブ | 推奨設定 | 説明 |
|--------------|---------|------|
| `default-src` | `'self'` | デフォルトで同一オリジンのみ許可 |
| `script-src` | `'self'` | スクリプトは同一オリジンのみ |
| `style-src` | `'self' 'unsafe-inline'` | インラインスタイル許可（Tailwind用） |
| `img-src` | `'self' data: https:` | 画像はdata URIとHTTPS許可 |
| `frame-ancestors` | `'self'` | iframe埋め込み制限 |
| `form-action` | `'self'` | フォーム送信先制限 |
| `base-uri` | `'self'` | `<base>` タグのURL制限 |
| `object-src` | `'none'` | Flash等のプラグイン禁止 |

### CSP with External Resources

CDN等外部リソース使用時:

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

本番環境導入前の動作確認:

```php
// 違反をレポートするが、ブロックはしない
$response->headers->set('Content-Security-Policy-Report-Only', $csp);
```

---

## Diagnosis Checklist

### General

- [ ] SecurityHeadersMiddleware を実装している
- [ ] すべてのレスポンスにセキュリティヘッダが適用されている

### Clickjacking

- [ ] X-Frame-Options: SAMEORIGIN を設定している
- [ ] Content-Security-Policy の `frame-ancestors` を設定している

### Security Headers

- [ ] X-Content-Type-Options: nosniff を設定している
- [ ] Strict-Transport-Security を本番環境で設定している（HTTPS必須）
- [ ] Content-Security-Policy を適切に設定している
- [ ] Referrer-Policy を設定している
- [ ] X-Powered-By, Server ヘッダを削除している

### HTTP Header Injection

- [ ] リダイレクト時に改行コードを削除している
- [ ] URLリダイレクトにはホワイトリスト検証を実装している

### Mail Header Injection

- [ ] メール送信は Mailable クラスを使用している
- [ ] メールの件名から改行コードを削除している

---

## Quick Reference

| 操作 | ❌ 危険 | ✅ 安全 |
|-----|--------|--------|
| **Redirect** | `header("Location: $url")` | `redirect($url)` + ホワイトリスト検証 |
| **Mail** | `mail($to, $subject)` | `Mail::to($to)->send(new Mailable)` |
| **Headers** | 個別設定 | SecurityHeadersMiddleware |
| **CSP** | なし | `Content-Security-Policy` ヘッダ設定 |
