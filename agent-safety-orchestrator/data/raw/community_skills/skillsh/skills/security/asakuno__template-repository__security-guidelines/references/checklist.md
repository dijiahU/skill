# Security Implementation Checklist

コード実装時およびコードレビュー時に使用する包括的なセキュリティチェックリスト。すべての項目をクリアすることを必須とする。

## Table of Contents

- [SQL Injection Prevention](#1-sql-injection-prevention)
- [OS Command Injection Prevention](#2-os-command-injection-prevention)
- [Directory Traversal Prevention](#3-directory-traversal-prevention)
- [XSS Prevention (Laravel/Blade)](#4-xss-prevention-laravelblade)
- [XSS Prevention (React)](#5-xss-prevention-react)
- [CSRF Prevention](#6-csrf-prevention)
- [Session Management](#7-session-management)
- [HTTP Header Injection Prevention](#8-http-header-injection-prevention)
- [Mail Header Injection Prevention](#9-mail-header-injection-prevention)
- [Clickjacking Prevention](#10-clickjacking-prevention)
- [Security Headers Configuration](#11-security-headers-configuration)
- [Access Control & Authorization](#12-access-control--authorization)
- [Authentication & Password Management](#13-authentication--password-management)
- [Production Environment Configuration](#14-production-environment-configuration)
- [Dependencies & Libraries](#15-dependencies--libraries)
- [Code Review Perspectives](#code-review-perspectives)
- [Security Incident Response](#security-incident-response)
- [Environment Configuration Templates](#environment-configuration-templates)
- [Checklist Usage Guidelines](#checklist-usage-guidelines)

---

## 1. SQL Injection Prevention

- [ ] Eloquent ORM または Query Builder を使用している
- [ ] Raw クエリを使用する場合はパラメータバインディング（`?` または `:name`）を実装している
- [ ] `whereRaw()`, `orderByRaw()` 等を使用する場合は必ずバインディングしている
- [ ] カラム名やテーブル名に外部入力を使用する場合はホワイトリスト検証を実装している
- [ ] 本番環境で `APP_DEBUG=false` に設定している
- [ ] DBアカウントは最小権限で設定している（SELECT, INSERT, UPDATE, DELETE のみ）
- [ ] 文字列連結によるSQL構築を行っていない

---

## 2. OS Command Injection Prevention

- [ ] `exec()`, `shell_exec()`, `system()`, `passthru()` 等のOS コマンド実行関数を使用していない
- [ ] やむを得ず使用する場合は Symfony Process コンポーネントを使用している
- [ ] `escapeshellarg()` のみに依存せず、入力値をホワイトリスト方式で検証している
- [ ] PHP標準関数やライブラリで代替できる処理を探している
- [ ] バッククォート演算子 `` `command` `` を使用していない

---

## 3. Directory Traversal Prevention

- [ ] ファイル名の指定にホワイトリスト方式を使用している（推奨）
- [ ] `basename()` でファイル名のみ取得している
- [ ] `realpath()` + ベースディレクトリ検証を実装している
- [ ] Storage Facade を使用している
- [ ] ファイルタイプ（MIME type）のバリデーションを実装している
- [ ] ファイルサイズの制限を実装している
- [ ] アップロードファイル名をランダム化している
- [ ] `../` の単純削除のみに依存していない

---

## 4. XSS Prevention (Laravel/Blade)

- [ ] Bladeテンプレートで `{{ }}` を使用している
- [ ] `{!! !!}` を使用する場合は HTMLPurifier でサニタイズしている
- [ ] HTML属性値がダブルクォートで囲まれている
- [ ] JavaScript内で変数を出力する場合は `@json()` を使用している
- [ ] HTMLPurifier の `CleanHtml` キャストを使用している（HTML許可時）
- [ ] CSPヘッダーが適切に設定されている

---

## 5. XSS Prevention (React)

- [ ] JSXのデフォルト動作（自動エスケープ）を活用している
- [ ] `dangerouslySetInnerHTML` 使用時に DOMPurify でサニタイズしている
- [ ] DOMPurify の `ALLOWED_TAGS` と `ALLOWED_ATTR` を明示的に指定している
- [ ] ユーザー入力のURLに `javascript:` スキームが含まれていないか検証している
- [ ] URL検証には `new URL()` でパースして protocol をチェックしている
- [ ] インラインイベントハンドラ（`onclick` 等）を使用していない

---

## 6. CSRF Prevention

- [ ] POST/PUT/PATCH/DELETEフォームに `@csrf` ディレクティブを使用している
- [ ] AJAX/APIリクエストでX-XSRF-TOKENヘッダーを送信している
- [ ] React SPAで `withCredentials: true` を設定している
- [ ] React SPAで `withXSRFToken: true` を設定している
- [ ] ログイン前に `/sanctum/csrf-cookie` にアクセスしている
- [ ] 外部Webhook以外でCSRF検証を除外していない
- [ ] API認証にLaravel Sanctum を使用している（SPA認証）

---

## 7. Session Management

- [ ] ログイン成功後に `session()->regenerate()` でセッションIDを再生成している
- [ ] ログアウト時に `session()->invalidate()` でセッションを無効化している
- [ ] ログアウト時に `session()->regenerateToken()` でトークンを再生成している
- [ ] CookieにSecure属性が設定されている（`SESSION_SECURE_COOKIE=true`）
- [ ] CookieにHttpOnly属性が設定されている（`http_only: true`）
- [ ] SameSite属性が適切に設定されている（`same_site: 'lax'` または `'strict'`）
- [ ] セッションドライバは本番環境で `database` または `redis` を使用している
- [ ] セッションの有効期限が適切に設定されている（推奨: 120分）
- [ ] `SANCTUM_STATEFUL_DOMAINS` が正しく設定されている（SPA認証使用時）

---

## 8. HTTP Header Injection Prevention

- [ ] ヘッダ出力には Laravel の `redirect()` や `response()` を使用している
- [ ] 外部入力から改行コード（`\r`, `\n`）を削除している
- [ ] URLリダイレクトにはホワイトリスト検証を実装している
- [ ] リダイレクト先のホスト名を検証している
- [ ] 生のヘッダ出力（`header()` 関数）を使用していない

---

## 9. Mail Header Injection Prevention

- [ ] メール送信に Laravel の Mailable クラスを使用している
- [ ] メールヘッダに外部入力を直接使用していない
- [ ] 外部入力を件名等に使用する場合、改行コード・制御文字を削除している
- [ ] メールアドレスのバリデーションに `email:rfc,dns` を使用している
- [ ] 生の `mail()` 関数を使用していない

---

## 10. Clickjacking Prevention

- [ ] X-Frame-Options ヘッダを設定している（`SAMEORIGIN`）
- [ ] Content-Security-Policy の `frame-ancestors` を設定している
- [ ] SecurityHeadersMiddleware を実装している
- [ ] すべてのレスポンスにセキュリティヘッダが適用されている

---

## 11. Security Headers Configuration

- [ ] X-Content-Type-Options: nosniff を設定している
- [ ] Strict-Transport-Security（HSTS）を本番環境で設定している
- [ ] Content-Security-Policy（CSP）を適切に設定している
- [ ] Referrer-Policy を設定している（`strict-origin-when-cross-origin`）
- [ ] X-Powered-By, Server ヘッダを削除している
- [ ] Permissions-Policy を設定している
- [ ] SecurityHeadersMiddleware がすべてのレスポンスに適用されている

---

## 12. Access Control & Authorization

- [ ] 全ての保護リソースに対してサーバーサイドで認可チェックを実装している
- [ ] Laravel Policy を使用してリソースアクセスを制御している
- [ ] URLパラメータからユーザーIDを取得していない
- [ ] セッションから認証済みユーザー情報を取得している（`auth()->user()`）
- [ ] 所有リソースへのアクセスはスコープを使用している（`user()->posts()`）
- [ ] Controller で `$this->authorize()` を使用している
- [ ] フロントエンドの認可チェックのみに依存していない

---

## 13. Authentication & Password Management

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

## 14. Production Environment Configuration

### .env File

- [ ] `APP_ENV=production` に設定している
- [ ] `APP_DEBUG=false` に設定している
- [ ] `SESSION_DRIVER=database` または `redis` に設定している
- [ ] `SESSION_SECURE_COOKIE=true` に設定している
- [ ] `SESSION_SAME_SITE=lax` に設定している
- [ ] `HASH_DRIVER=argon2id` に設定している（推奨）
- [ ] `SANCTUM_STATEFUL_DOMAINS` を本番ドメインに設定している
- [ ] `SESSION_DOMAIN` をドメイン全体に設定している（`.example.com`）

### CORS Configuration

- [ ] `allowed_origins` を明示的に指定している（`*` を使用していない）
- [ ] `supports_credentials: true` を設定している（SPA認証使用時）
- [ ] `paths` に必要なエンドポイントのみを指定している

---

## 15. Dependencies & Libraries

- [ ] すべてのライブラリを最新バージョンに更新している
- [ ] `composer audit` でセキュリティ脆弱性をチェックしている
- [ ] `npm audit` でセキュリティ脆弱性をチェックしている
- [ ] 未使用のライブラリを削除している
- [ ] HTMLPurifier をインストールしている（HTML許可時）
- [ ] DOMPurify をインストールしている（React使用時）

---

## Code Review Perspectives

コードレビュー時は以下の観点で必ず確認する:

### 1. Input Validation

- [ ] すべての外部入力（URL, POST, Cookie, Header）を検証しているか
- [ ] ホワイトリスト方式を使用しているか
- [ ] Laravel Validation を使用しているか

### 2. Output Escaping

- [ ] Blade で `{{ }}` を使用しているか
- [ ] React で JSX のデフォルト動作を活用しているか
- [ ] HTML許可時に HTMLPurifier / DOMPurify を使用しているか

### 3. Authentication & Authorization

- [ ] セッションから認証済みユーザーを取得しているか
- [ ] Laravel Policy で認可チェックを実装しているか
- [ ] URLパラメータからユーザーIDを取得していないか

### 4. Secure API/Function Usage

- [ ] Eloquent ORM / Query Builder を使用しているか
- [ ] `Hash::make()` でパスワードをハッシュ化しているか
- [ ] Symfony Process を使用しているか（OSコマンド実行時）
- [ ] Storage Facade を使用しているか（ファイル操作時）

### 5. Security Headers

- [ ] SecurityHeadersMiddleware が適用されているか
- [ ] すべてのレスポンスにセキュリティヘッダが含まれているか

---

## Security Incident Response

セキュリティインシデント発生時は以下の手順で対応する:

1. **即座にサービス停止** - 被害拡大を防ぐ
2. **ログの保全** - 攻撃の痕跡を保存
3. **脆弱性の特定と修正** - 根本原因の解決
4. **セキュリティパッチの適用** - 修正版のデプロイ
5. **影響範囲の調査** - データ漏洩等の確認
6. **関係者への報告** - 管理者・ユーザーへの通知
7. **再発防止策の実施** - プロセス改善

---

## Environment Configuration Templates

### Production .env

```env
APP_ENV=production
APP_DEBUG=false

SESSION_DRIVER=database
SESSION_LIFETIME=120
SESSION_SECURE_COOKIE=true
SESSION_SAME_SITE=lax
SESSION_DOMAIN=.example.com

SANCTUM_STATEFUL_DOMAINS=example.com,www.example.com,app.example.com

HASH_DRIVER=argon2id
```

### React Axios Configuration

```javascript
// axios設定
const apiClient = axios.create({
    baseURL: process.env.REACT_APP_API_URL,
    withCredentials: true,
    withXSRFToken: true,
});
```

---

## Checklist Usage Guidelines

### When to Use This Checklist

1. **実装完了時**: 新機能実装後の自己チェック
2. **コードレビュー時**: PR レビューの必須項目
3. **リリース前**: 本番デプロイ前の最終確認
4. **定期監査**: 月次または四半期ごとのセキュリティ監査

### How to Use This Checklist

1. **該当カテゴリの特定**: 実装した機能に関連するカテゴリを選択
2. **全項目の確認**: 該当カテゴリのすべての項目をチェック
3. **不合格項目の修正**: チェックが入らない項目を修正
4. **再確認**: 修正後、再度チェックリストを実行

### Continuous Improvement

本チェックリストは定期的に見直し、新たな脅威や対策を追加する。プロジェクトの成長に合わせて、カスタマイズと拡張を推奨する。

---

本チェックリストをすべてクリアすることで、IPAガイドライン準拠のセキュアなWebアプリケーションを実現する。
