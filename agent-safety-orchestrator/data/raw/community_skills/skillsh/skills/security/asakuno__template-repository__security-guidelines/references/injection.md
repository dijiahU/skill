# Injection Vulnerabilities

インジェクション系脆弱性の詳細と対策。SQLインジェクション、OSコマンド・インジェクション、ディレクトリ・トラバーサルの3種類を扱う。

## Table of Contents

- [SQL Injection](#sql-injection)
  - [Threat & Impact](#threat--impact)
  - [Vulnerable Code Examples](#vulnerable-code-examples-laravel)
  - [Safe Code Examples](#safe-code-examples-laravel)
  - [Laravel Framework Protections](#laravel-framework-protections)
  - [Additional Protection](#additional-protection-defense-in-depth)
  - [Diagnosis Checklist](#diagnosis-checklist)
- [OS Command Injection](#os-command-injection)
  - [Threat & Impact](#threat--impact-1)
  - [Vulnerable Code Examples](#vulnerable-code-examples-laravel-1)
  - [Safe Code Examples](#safe-code-examples-laravel-1)
  - [Root Solution](#root-solution)
  - [Diagnosis Checklist](#diagnosis-checklist-1)
- [Directory Traversal](#directory-traversal)
  - [Threat & Impact](#threat--impact-2)
  - [Vulnerable Code Examples](#vulnerable-code-examples-laravel-2)
  - [Safe Code Examples](#safe-code-examples-laravel-2)
  - [Laravel Storage Facade](#laravel-storage-facade)
  - [File Upload Protection](#file-upload-protection)
  - [Diagnosis Checklist](#diagnosis-checklist-2)
- [Summary](#summary)
  - [Injection Prevention Principles](#injection-prevention-principles)
  - [Laravel Built-in Protection Summary](#laravel-built-in-protection-summary)
  - [Quick Reference](#quick-reference-safe-vs-unsafe)

---

## SQL Injection {#sql-injection}

### Threat & Impact

SQLインジェクションは、SQL文の組み立て方法に問題がある場合に発生する脆弱性で、**IPA届出件数の上位**を占める。攻撃者はデータベースの不正操作により、**個人情報漏洩、データ改ざん・消去、認証回避**を引き起こす可能性がある。

### Vulnerable Code Examples (Laravel)

```php
// ❌ 危険: 文字列連結によるSQL構築
$email = $request->input('email');
$results = DB::select("SELECT * FROM users WHERE email = '$email'");

// ❌ 危険: whereRaw での直接埋め込み
User::whereRaw('email = "' . $request->input('email') . '"')->get();

// ❌ 危険: orderByRaw での未検証カラム名
User::orderByRaw($request->input('sort'))->get();
```

**Attack Example**:
```
email=' OR '1'='1' --
→ SELECT * FROM users WHERE email = '' OR '1'='1' --'
→ 全ユーザーデータの取得
```

### Safe Code Examples (Laravel)

```php
// ✅ 安全: Eloquent ORM（自動的にパラメータバインディング）
$user = User::where('email', $email)->first();

// ✅ 安全: Query Builder のパラメータバインディング
$users = DB::table('users')->where('email', $email)->get();

// ✅ 安全: プリペアドステートメント（位置パラメータ）
$users = DB::select('SELECT * FROM users WHERE email = ?', [$email]);

// ✅ 安全: 名前付きバインディング
$users = DB::select(
    'SELECT * FROM users WHERE email = :email',
    ['email' => $email]
);

// ✅ 安全: whereRaw でのバインディング
User::whereRaw('email = ?', [$request->input('email')])->get();

// ✅ 安全: カラム名のホワイトリスト検証
$allowedColumns = ['name', 'email', 'created_at'];
$sortColumn = $request->input('sort');

if (in_array($sortColumn, $allowedColumns)) {
    User::orderBy($sortColumn)->get();
}
```

### Laravel Framework Protections

| 機能 | 説明 |
|------|------|
| **Eloquent ORM** | PDOパラメータバインディングを自動使用 |
| **Query Builder** | `where()`, `insert()`, `update()` 等は自動エスケープ |
| **DB::select()** | プレースホルダ(`?`)使用でSQLインジェクション防止 |
| **Validation** | 入力値の事前検証で不正データを排除 |

### Additional Protection (Defense in Depth)

**保険的対策**:
- データベースエラーメッセージを画面に表示しない（`APP_DEBUG=false`）
- データベースアカウントに最小限の権限を付与（SELECT, INSERT, UPDATE, DELETE のみ）
- WAF（Web Application Firewall）の導入検討

**本番環境 .env 設定**:
```env
APP_DEBUG=false
DB_DATABASE=production_db
DB_USERNAME=app_user  # 管理者アカウントは使用しない
DB_PASSWORD=strong_password
```

### Diagnosis Checklist

- [ ] Eloquent ORM または Query Builder を使用している
- [ ] Raw クエリを使用する場合はパラメータバインディング（`?` または `:name`）を実装している
- [ ] `whereRaw()`, `orderByRaw()` 等を使用する場合は必ずバインディングしている
- [ ] カラム名やテーブル名に外部入力を使用する場合はホワイトリスト検証を実装している
- [ ] 本番環境で `APP_DEBUG=false` に設定している
- [ ] DBアカウントは最小権限で設定している

---

## OS Command Injection {#os-command-injection}

### Threat & Impact

外部からの攻撃によりウェブサーバのOSコマンドを不正に実行される脆弱性。**サーバ内ファイルの閲覧・改ざん・削除、マルウェア感染、他システムへの攻撃の踏み台**となる危険がある。

### Vulnerable Code Examples (Laravel)

```php
// ❌ 危険: ユーザー入力を直接shell_exec
$ip = $request->input('ip');
$output = shell_exec("ping -c 4 " . $ip);
// 攻撃例: ip=127.0.0.1; cat /etc/passwd

// ❌ 危険: exec関数での直接使用
$domain = $request->input('domain');
exec('whois ' . $domain);
```

**Dangerous Functions**:
- `exec()`
- `shell_exec()`
- `system()`
- `passthru()`
- `proc_open()`
- `popen()`
- `pcntl_exec()`
- バッククォート演算子 `` `command` ``

### Safe Code Examples (Laravel)

```php
// ✅ 最良: シェルコマンドを使用しない（ライブラリ使用）
mkdir('/path/to/dir');  // system("mkdir /path/to/dir") の代わり
copy($source, $dest);   // shell_exec("cp ...") の代わり

// ✅ 安全: Laravelバリデーション + エスケープ
public function ping(Request $request)
{
    $request->validate([
        'ip' => 'required|ip'  // IPアドレス形式のみ許可
    ]);

    $ip = escapeshellarg($request->input('ip'));
    $output = shell_exec("ping -c 4 $ip");
    return view('result', ['output' => $output]);
}

// ✅ 推奨: Symfony Process コンポーネント使用
use Symfony\Component\Process\Process;

public function ping(Request $request)
{
    $request->validate(['ip' => 'required|ip']);

    $ip = $request->input('ip');
    $process = new Process(['ping', '-c', '4', $ip]);
    $process->run();

    return $process->getOutput();
}
```

### Root Solution

**原則: OSコマンド実行関数の使用を禁止**

必要な処理はPHP標準関数またはライブラリで実装する:

| OSコマンド | PHP標準関数 |
|-----------|-------------|
| `mkdir` | `mkdir()` |
| `cp` | `copy()` |
| `rm` | `unlink()` |
| `mv` | `rename()` |
| `cat` | `file_get_contents()` |

**やむを得ず使用する場合**:
1. Symfony Process コンポーネントの使用を必須とする
2. `escapeshellarg()` のみに依存しない
3. 入力値をホワイトリスト方式で検証する

### Diagnosis Checklist

- [ ] `exec()`, `shell_exec()`, `system()`, `passthru()` 等のOS コマンド実行関数を使用していない
- [ ] やむを得ず使用する場合は Symfony Process コンポーネントを使用している
- [ ] `escapeshellarg()` のみに依存せず、入力値をホワイトリスト方式で検証している
- [ ] PHP標準関数やライブラリで代替できる処理を探している
- [ ] バッククォート演算子 `` `command` `` を使用していない

---

## Directory Traversal {#directory-traversal}

### Threat & Impact

外部からのパラメータでファイル名を直接指定する実装において、任意のファイルにアクセスされる脆弱性。**/etc/passwd、.env等の機密ファイルの閲覧**や**認証情報の窃取**が発生する可能性がある。

### Vulnerable Code Examples (Laravel)

```php
// ❌ 危険: ユーザー入力をそのままパス構築
Route::get('/download', function(Request $request) {
    return response()->download(
        storage_path('app/' . $request->input('filename'))
    );
});
// 攻撃例: filename=../../.env

// ❌ 不十分: "../" の単純削除（回避可能）
$page = str_replace('../', '', $_GET['page']);
// 攻撃例: ....//....//etc/passwd → ../../../etc/passwd
```

### Safe Code Examples (Laravel)

**Method 1: Whitelist Approach (Most Secure)**

```php
// ✅ 安全: ホワイトリスト方式
$allowedFiles = ['manual.pdf', 'report.csv', 'readme.txt'];
$filename = $request->input('file');

if (!in_array($filename, $allowedFiles)) {
    abort(403, 'Unauthorized file access');
}

return Storage::download('documents/' . $filename);
```

**Method 2: basename() + Directory Restriction**

```php
// ✅ 安全: basename() でファイル名のみ取得
Route::get('/download', function(Request $request) {
    $filename = basename($request->input('filename'));
    $path = storage_path('app/files/' . $filename);

    if (file_exists($path)) {
        return response()->download($path);
    }
    abort(404);
});
```

**Method 3: realpath() + Path Validation**

```php
// ✅ 安全: realpath() + ディレクトリ検証
use Illuminate\Support\Str;

public function downloadFile(Request $request)
{
    $basePath = storage_path('app/files');
    $requestedPath = $basePath . '/' . $request->input('filename');

    // 実際のパスを取得
    $realPath = realpath($requestedPath);

    // パスが許可されたディレクトリ内か検証
    if ($realPath === false || !Str::startsWith($realPath, $basePath)) {
        abort(403, 'Unauthorized file access');
    }

    return response()->download($realPath);
}
```

### Laravel Storage Facade

**推奨: Storage Facade の使用**

```php
use Illuminate\Support\Facades\Storage;

// ✅ 安全: Storage::download() を使用
Route::get('/download', function(Request $request) {
    $filename = $request->input('filename');

    // Storageは自動的にベースディレクトリ内に制限
    if (!Storage::exists('files/' . $filename)) {
        abort(404);
    }

    return Storage::download('files/' . $filename);
});
```

### File Upload Protection

ファイルアップロード時の追加対策:

```php
public function upload(Request $request)
{
    $request->validate([
        'file' => [
            'required',
            'file',
            'max:2048',  // 2MB制限
            'mimes:pdf,jpg,png',  // MIMEタイプ制限
        ],
    ]);

    $file = $request->file('file');

    // ✅ ファイル名をランダム化（元のファイル名を使用しない）
    $path = $file->store('uploads', 'public');

    // ✅ 実行可能ファイルの保存を禁止
    $extension = $file->getClientOriginalExtension();
    $disallowedExtensions = ['php', 'exe', 'sh', 'bat'];

    if (in_array(strtolower($extension), $disallowedExtensions)) {
        abort(400, 'File type not allowed');
    }

    return response()->json(['path' => $path]);
}
```

### Diagnosis Checklist

- [ ] ファイル名の指定にホワイトリスト方式を使用している（推奨）
- [ ] `basename()` でファイル名のみ取得している
- [ ] `realpath()` + ベースディレクトリ検証を実装している
- [ ] Storage Facade を使用している
- [ ] ファイルタイプ（MIME type）のバリデーションを実装している
- [ ] ファイルサイズの制限を実装している
- [ ] アップロードファイル名をランダム化している
- [ ] `../` の単純削除のみに依存していない

---

## Summary

### Injection Prevention Principles

**共通原則**:
1. **外部入力を信頼しない**: すべての外部入力を検証
2. **ホワイトリスト方式**: 許可リストによる検証を優先
3. **フレームワーク機能の活用**: Laravel標準機能を正しく使用
4. **多層防御**: 根本的解決策 + 保険的対策

### Laravel Built-in Protection Summary

| 脆弱性 | Laravel標準機能 | 使用方法 |
|-------|----------------|---------|
| SQL Injection | Eloquent ORM | `User::where('email', $email)->first()` |
| SQL Injection | Query Builder | `DB::table('users')->where('email', $email)->get()` |
| OS Command | - | PHP標準関数使用（Symfony Processを推奨） |
| Directory Traversal | Storage Facade | `Storage::download('files/' . $filename)` |

### Quick Reference: Safe vs Unsafe

| 操作 | ❌ 危険 | ✅ 安全 |
|-----|--------|--------|
| **SQL** | 文字列連結 | Eloquent/パラメータバインディング |
| **OS Command** | `shell_exec($input)` | Symfony Process / PHP標準関数 |
| **File Access** | 直接パス結合 | basename() / realpath() / Storage Facade |
