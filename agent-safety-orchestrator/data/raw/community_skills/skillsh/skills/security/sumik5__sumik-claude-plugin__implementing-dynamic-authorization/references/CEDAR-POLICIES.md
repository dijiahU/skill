# Cedar Policies（Cedarポリシー）

このファイルでは、Cedarポリシー言語の詳細構造、型システム、オペレータ、実装パターン、スキーマ設計、解析手法を解説します。

---

## Cedar概要

**なぜCedarか？**: Cedarは、**表現力・パフォーマンス・解析可能性・オープン性**を兼ね備えたポリシー言語です。

| 特徴 | 詳細 |
|------|------|
| **表現力** | RBAC・ReBAC・ABACすべてを統一的に表現 |
| **パフォーマンス** | サブミリ秒評価・数百〜数千ポリシーでもスケール |
| **解析可能性** | 静的解析・SMTソルバーによる形式検証 |
| **オープン** | オープンソース・組み込み可能（Rust/WASM） |

**開発元**: AWS（Amazon Verified Permissions/Verified Accessで使用）
**ライセンス**: Apache 2.0
**公式サイト**: [https://www.cedarpolicy.com](https://www.cedarpolicy.com)

---

## ポリシー構造

**すべてのCedarポリシーは、Effect・Scope・Conditionsの3要素で構成**されます。

### 1. Effect（効果）

**`permit`（許可）または`forbid`（拒否）のいずれか**:

```cedar
permit(...)  // 許可
forbid(...)  // 拒否（常にpermitをオーバーライド）
```

**評価ルール（deny-overrides）**:
1. `forbid`が適用 → **Deny**（他のpermitは無視）
2. `permit`が適用 → **Allow**
3. どちらも適用されない → **Deny**（implicit deny）

### 2. Scope（スコープ）

**誰が（Principal）、何を（Action）、どのリソースに（Resource）適用するか**:

```cedar
permit(
    principal in Employee::"eng-team",    // Principal: エンジニアチーム
    action == Action::"deploy",           // Action: デプロイ
    resource in System::"production"      // Resource: 本番システム
)
```

**スコープの利点**:
- **効率**: Cedarエンジンは、スコープマッチしたポリシーのみ評価
- **型安全**: スキーマで定義されたエンティティ・アクション以外は使用不可
- **可読性**: ポリシーの対象が一目瞭然

### 3. Conditions（条件）

**`when`（肯定条件）と`unless`（否定条件）**:

```cedar
when {
    context.device.managed == true        // デバイス管理下
    && context.time.hour >= 9             // 9時以降
    && context.time.hour < 17             // 17時前
}

unless {
    context.location == "restricted"      // 制限地域ではない
}
```

**条件は任意**（省略可能）。省略時はスコープのみで判定。

---

## PARCモデル

**PARC（Principal・Action・Resource・Context）は、認可リクエストの共通フレームワーク**です。

### リクエスト構造（JSON）

```json
{
  "principal": "Employee::\"alice\"",
  "action": "Action::\"deploy\"",
  "resource": "System::\"production\"",
  "context": {
    "device": { "managed": true },
    "time": { "hour": 10, "weekday": "Monday" }
  }
}
```

### PARCとポリシーの対応

| PARC要素 | ポリシー表現 | 評価方法 |
|---------|------------|---------|
| **Principal** | `principal in Employee::"alice"` | スコープでマッチング |
| **Action** | `action == Action::"deploy"` | スコープでマッチング |
| **Resource** | `resource in System::"production"` | スコープでマッチング |
| **Context** | `context.device.managed == true` | 条件で評価 |

### 評価フロー

1. **スコープマッチング**: Principal・Action・Resourceがスコープに合致するポリシーを選別
2. **条件評価**: 選別されたポリシーの`when`/`unless`を評価
3. **決定**: deny-overridesルールで最終決定

---

## ポリシー評価

### スコープマッチングの例

```cedar
// ポリシー
permit(
    principal in Group::"admins",
    action == Action::"delete",
    resource in Document::*
)
when { context.device.managed == true };

// リクエスト1: Alice（admins所属）が削除 → スコープマッチ → 条件評価
// リクエスト2: Bob（admins非所属）が削除 → スコープ不一致 → 評価スキップ
```

### 条件評価

**`when`はすべてtrueである必要、`unless`はすべてfalseである必要**:

```cedar
when {
    principal.clearance == "high"         // true必須
    && context.device.managed == true     // true必須
}
unless {
    context.time.hour < 9                 // false必須（9時以降）
    || context.time.hour >= 17            // false必須（17時前）
}
```

### Deny-overridesモデル

**例: デバイス制約の強制**

```cedar
// 1. 管理デバイスからのみアクセス許可（permit）
permit(
    principal in Employee::*,
    action,
    resource
)
when { context.device.managed == true };

// 2. 非管理デバイスは禁止（forbid）
forbid(
    principal in Employee::*,
    action,
    resource
)
when { context.device.managed == false };
```

**評価結果**:
- 管理デバイス → permitマッチ、forbid不一致 → **Allow**
- 非管理デバイス → forbidマッチ → **Deny**（permitは無視）

---

## Cedar型システム

**Cedarは強い型付けを持ち、スキーマで事前定義されたエンティティ・属性のみ使用可能**です。

### スキーマ例

```cedar
namespace ACME

entity Employee {
    attributes {
        department: String,
        clearance: optional { String },
        manager: Employee                 // エンティティ参照
    }
}

entity Document {
    attributes {
        owner: Employee,
        classification: String,
        readers_team: Team
    }
}

entity Team {
    attributes { name: String }
}

action "doc:view"
    appliesTo { principal: [Employee, Customer], resource: Document }

context {
    device: { managed: Bool },
    time: { hour: Long, weekday: String }
}
```

### 型の種類

| カテゴリ | 型 | 例 |
|---------|---|---|
| **プリミティブ** | Bool, String, Long（64bit整数） | `true`, `"finance"`, `100` |
| **拡張型** | datetime, duration, ipaddr, decimal | `datetime("2025-01-01T00:00:00Z")`, `duration("30d")` |
| **複合型** | Set, Record | `Set<String>`, `{ managed: Bool }` |
| **エンティティ** | Employee, Document, Team等 | `Employee::"alice"` |

### 名前空間（Namespace）

**すべてのエンティティ・アクションは名前空間で組織化**:

```cedar
namespace ACME

// エンティティ: ACME::Employee, ACME::Document
// アクション: ACME::Action::"doc:view"
```

**利点**:
- 衝突回避（異なるアプリで同名エンティティ）
- スコープ明確化（どのアプリのポリシーか）

---

## オペレータ一覧

### Boolean演算

```cedar
&& || !
例: principal.clearance == "high" && context.device.managed
```

### String演算

| オペレータ | 用途 | 例 |
|----------|------|---|
| `==`, `!=` | 完全一致 | `principal.department == "finance"` |
| `like` | ワイルドカード | `context.device.name like "corp-*"` |

### Long（整数）演算

```cedar
==, <, >, <=, >=, +, -, *
例: resource.size <= 1048576  // 1MB以下
```

### DateTime/Duration演算

```cedar
// 日時比較
context.requestTime >= datetime("2025-07-01T00:00:00Z")

// 期間比較
context.sessionDuration < duration("8h")
```

### IP Address演算

```cedar
// IPレンジチェック
ip(context.clientIp) in ip("10.0.0.0/8")
```

### Set演算

| オペレータ | 用途 | 例 |
|----------|------|---|
| `in` | メンバーシップ | `principal in Group::"admins"` |
| `.contains()` | 要素含有 | `principal.roles.contains("manager")` |
| `.containsAny()` | いずれか含有 | `principal.tags.containsAny(["sensitive", "restricted"])` |

### Entity演算

```cedar
// 型チェック
resource is Document

// エンティティ比較
resource.owner == principal
```

### Tag演算

```cedar
// タグ存在チェック
resource.hasTag("sensitive")

// タグ値取得
resource.getTag("classification") == "confidential"
```

---

## ポリシーパターン

### 1. Discretionary（自由裁量）

**リソース所有者が共有相手を決定**:

```cedar
permit(
    principal,
    action == Action::"doc:view",
    resource in Document::*
)
when {
    principal in resource.readers_team    // 所有者がチームに追加
};
```

**特徴**:
- UIで共有操作（Google Docs型）
- ポリシー変更不要（チームメンバーシップ変更で対応）

### 2. Membership（メンバーシップ）

**グループ・ロールベースのアクセス（RBAC型）**:

```cedar
permit(
    principal in Team::"legal",
    action in [Action::"doc:view", Action::"doc:edit"],
    resource in Document::*
)
when { resource.classification == "Legal" };
```

**特徴**:
- 部門・チーム単位の権限管理
- スコープで明示的にグループ指定

### 3. Relationship（関係ベース）

**関係トラバースによるアクセス（ReBAC型）**:

```cedar
permit(
    principal in Employee::*,
    action in [Action::"doc:view", Action::"doc:edit"],
    resource in Document::*
)
when {
    resource.owner.manager == principal    // マネージャー関係
};
```

**特徴**:
- 組織階層・所有権に基づく自動的な権限付与
- エンティティストアの関係グラフを利用

---

## スキーマ設計のベストプラクティス

### 1. アクション型付けを厳密に

**悪い例**:
```cedar
action "doc:view"
    appliesTo { principal: Any, resource: Any }
```

**良い例**:
```cedar
action "doc:view"
    appliesTo { principal: [Employee, Customer], resource: Document }
```

**理由**: `Any`は型安全性を失い、意図しないエンティティ型でポリシーが適用される。

### 2. 属性のオーバーロード回避

**悪い例**:
```cedar
entity Employee {
    attributes {
        dept_role: String  // "Eng-Manager"のような複合値
    }
}
```

**良い例**:
```cedar
entity Employee {
    attributes {
        department: String,
        role: String
    }
}
```

**理由**: 文字列パースが必要になり、ポリシーが複雑化。

### 3. 一貫した命名規則

**推奨規則**:
- エンティティ: PascalCase（`Employee`, `Document`）
- アクション: `namespace::action`形式（`doc:view`, `system:deploy`）
- 属性: snake_case（`owner_department`, `clearance_level`）

### 4. Context属性の明示

**すべてのコンテキスト属性をスキーマで定義**:

```cedar
context {
    device: { managed: Bool, ip: String },
    time: { hour: Long, weekday: String },
    location: String
}
```

**理由**: テスト時にコンテキストをシミュレート可能。

---

## ポリシーテンプレートとオーバーライド

### テンプレート

**再利用可能なポリシーパターンをパラメータ化**:

```cedar
// テンプレート定義
permit(
    principal in ?readers_team,
    action == Action::"doc:view",
    resource in Document::*
)
when { resource.owner == ?owner };

// インスタンス化
{ "readers_team": "Team::\"project-alpha\"", "owner": "Employee::\"alice\"" }
```

**利点**:
- 一貫性維持
- マルチテナントで同一ロジック適用

### オーバーライド

**組織全体の制約を`forbid`で強制**:

```cedar
// グローバル制約
forbid(
    principal,
    action,
    resource
)
when { context.device.managed == false };

// 個別permit（上記forbidが優先）
permit(
    principal in Employee::*,
    action,
    resource
);
```

---

## Cedarと他言語の比較

**スコープマッチングの有無**:

| 言語 | スコープマッチング | 評価方法 |
|-----|-----------------|---------|
| **Cedar** | ✅ あり | スコープフィルタ後に条件評価 |
| **OPA/Rego** | ❌ なし | すべての入力で全ルール評価 |

**Cedarの利点**:
- **パフォーマンス**: 無関係なポリシーをスキップ
- **可読性**: ポリシーのスコープが明示的
- **静的解析**: スコープで適用範囲を事前検証

---

## SMT解析とCedar Analysis

**Cedar Analysisは、SMTソルバー（Z3）を使用してポリシーを形式検証**します。

### 検証可能な項目

| 検証内容 | 詳細 |
|---------|------|
| **Satisfiability** | ポリシーが適用可能か？（デッドコード検出） |
| **Conflicts** | 複数ポリシー間の矛盾（permit vs forbid） |
| **Coverage** | 特定のリクエストがどのポリシーでカバーされるか |
| **Reachability** | 特定の条件下で到達可能な決定 |

### 使用例

```bash
# ポリシーセットの検証
cedar analyze --policies policy.cedar --schema schema.cedar

# 特定リクエストのカバレッジ確認
cedar analyze --request request.json --policies policy.cedar
```

**利点**:
- デプロイ前にバグ検出
- セキュリティギャップの発見
- リファクタリング時の安全性担保

---

## ポリシーテストの実装

### ユニットテスト例

```json
{
  "policies": "policy.cedar",
  "entities": "entities.json",
  "tests": [
    {
      "description": "Aliceはドキュメント所有者として編集可能",
      "principal": "Employee::\"alice\"",
      "action": "Action::\"doc:edit\"",
      "resource": "Document::\"doc1\"",
      "context": { "device": { "managed": true } },
      "expected": "Allow"
    },
    {
      "description": "Bobは非管理デバイスからアクセス不可",
      "principal": "Employee::\"bob\"",
      "action": "Action::\"doc:view\"",
      "resource": "Document::\"doc1\"",
      "context": { "device": { "managed": false } },
      "expected": "Deny"
    }
  ]
}
```

### CI/CD統合

```yaml
# .github/workflows/cedar-validation.yml
- name: Validate Cedar Policies
  run: cedar validate --policies policies/ --schema schema.cedar

- name: Run Cedar Tests
  run: cedar test --tests tests/policy-tests.json
```

---

## エンティティストアとの統合

**Cedarはエンティティストア（関係グラフ）と組み合わせて使用**します。

### エンティティデータ例（JSON）

```json
[
  {
    "uid": { "type": "Employee", "id": "alice" },
    "attrs": { "department": "eng", "clearance": "high" },
    "parents": [{ "type": "Team", "id": "eng-team" }]
  },
  {
    "uid": { "type": "Document", "id": "doc1" },
    "attrs": { "owner": { "type": "Employee", "id": "alice" } }
  }
]
```

### ポリシー評価時のデータフロー

```
[リクエスト] → [Cedar Engine]
                 ↓ ← [エンティティストア: 関係・属性取得]
                 ↓ ← [ポリシーセット]
             [決定: Allow/Deny]
```

**関係トラバース**:
```cedar
resource.owner.manager == principal
```
→ エンティティストアで `Document::doc1 --owner--> Employee::alice --manager--> Employee::carol` を辿る。

---

## まとめ: Cedar実装チェックリスト

- [ ] スキーマ設計完了（エンティティ・アクション・Context定義）
- [ ] アクション型付け厳密化（`Any`使用禁止）
- [ ] ポリシーパターン選定（Discretionary/Membership/Relationship）
- [ ] グローバル制約を`forbid`で定義
- [ ] テストケース作成（ユニットテスト・シナリオテスト）
- [ ] 静的解析実施（`cedar analyze`）
- [ ] CI/CD統合（バリデーション・テスト自動化）
- [ ] エンティティストア統合（関係グラフ・属性同期）

詳細なアーキテクチャパターンは [ARCHITECTURE-PATTERNS.md](ARCHITECTURE-PATTERNS.md)、他言語との比較は [POLICY-LANGUAGES.md](POLICY-LANGUAGES.md) を参照してください。
