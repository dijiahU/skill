# Implementing Dynamic Authorization

## 概要

動的認可（Dynamic Authorization）は、静的なロールやパーミッションではなく、**実行時の属性・関係・コンテキストに基づいてアクセス決定を行うアプローチ**です。従来のACL（Access Control List）やRBAC（Role-Based Access Control）が抱える以下の課題を解決します：

- **スケーラビリティ**: 数万の静的リストを管理する困難
- **柔軟性**: 時刻・場所・デバイス状態などの動的コンテキストに対応できない
- **メンテナンス性**: リソース・ロールの変更に追従するための人的・システム的コスト
- **監査性**: 誰が何にアクセスできるかを追跡困難
- **セキュリティ**: 不要な権限の残存による情報漏洩リスク

**動的認可は、ポリシー（Policy）を実行時に評価し、現在の状態・属性・関係に基づいて許可・拒否を決定します。** これにより、以下の利点が得られます：

- **コンテキスト対応**: 時刻・場所・デバイス信頼度などの動的要因を考慮
- **リアルタイム**: ロールやリソースの変更に即座に対応
- **明確な監査トレイル**: ポリシーとログで決定根拠を追跡可能
- **柔軟な権限委譲**: 組織・チーム・プロジェクト構造の変化に追従

---

## 認可モデル選定ガイド

**適切な認可モデルは、アプリケーションの要件とユースケースによって決まります。** 以下のテーブルで判断できます：

| モデル | 適用場面 | 主な特徴 | 使用例 |
|--------|---------|---------|--------|
| **ACL** | 単純なファイル/リソース単位のアクセス制御 | リソースごとに許可リスト | Unixファイル権限、基本的なファイル共有 |
| **RBAC** | 組織の職務に基づく権限管理 | ロール→パーミッションのマッピング | 社内システムの部門別アクセス |
| **ReBAC** | コラボレーション・共有・委譲が中心 | 関係グラフでアクセス決定 | Google Docs、Slack、チームコラボツール |
| **ABAC** | 動的コンテキスト・属性ベースの細粒度制御 | 属性評価によるリアルタイム判定 | 金融システム、医療記録、政府機関 |
| **PBAC** | 複数モデルの統合的運用 | ロール・属性・関係の組み合わせ | マルチテナントSaaS、エンタープライズ基盤 |

**ユーザー確認が必要な判断ポイント（AskUserQuestion使用）**:

1. **認可モデルの選定**: ReBAC vs ABAC vs PBAC のどれを採用するか？
   - 共有・委譲が中心 → ReBAC
   - コンテキスト・属性重視 → ABAC
   - 複数要件の組み合わせ → PBAC

2. **ポリシー言語の選定**: Cedar vs OPA/Rego vs OpenFGA
   - 詳細は [POLICY-LANGUAGES.md](./references/POLICY-LANGUAGES.md) 参照

3. **アーキテクチャパターン**: PEPの配置方法（Embedded/Gateway/Sidecar）、PDP集中型 vs 分散型
   - 詳細は [ARCHITECTURE-PATTERNS.md](./references/ARCHITECTURE-PATTERNS.md) 参照

---

## PBACの統一アプローチ

**Policy-Based Access Control（PBAC）は、RBAC・ABAC・ReBACを統合する上位概念**です。ポリシーをコードまたはデータとして外部化し、実行時に評価することで、柔軟かつ統一的な認可を実現します。

### Policy as Code（ポリシーをコードとして管理）

**ポリシーを実行可能なコードとして記述し、バージョン管理・テスト・デプロイする手法**です（ABACの主流アプローチ）。

- **形式**: Cedar、Rego（OPA）、XACML等の宣言的言語
- **特徴**:
  - 属性・条件に基づく細粒度ロジック
  - CI/CDパイプラインで管理
  - 静的解析・テスト可能
- **適用例**: 時刻制限、デバイス信頼度チェック、クリアランスレベル評価

### Policy as Data（ポリシーをデータとして管理）

**ポリシーを関係グラフやメタデータとして保存し、静的ルールで動的に評価する手法**です（ReBACの主流アプローチ）。

- **形式**: 関係グラフ（Zanzibar, OpenFGA）、タプル（`user:alice#viewer@doc:123`）
- **特徴**:
  - 関係の追加・削除でアクセス変更
  - ポリシーロジックは固定、データが動的
  - UIから直接操作可能（例: Google Docsの共有ボタン）
- **適用例**: ドキュメント共有、チームメンバーシップ、所有権ベース制御

**PBACは、両方のアプローチを必要に応じて組み合わせます。**

---

## 認可リファレンスアーキテクチャ概要

**XACMLが提唱した4コンポーネントモデル（PEP/PDP/PAP/PIP）は、現代の認可システムの標準アーキテクチャ**です。

### コンポーネント概要

| コンポーネント | 役割 | 実装例 |
|--------------|------|--------|
| **PEP** (Policy Enforcement Point) | リクエストを捕捉し、決定を強制 | アプリコード、API Gateway、Sidecar |
| **PDP** (Policy Decision Point) | ポリシー評価と決定 | Cedar Engine、OPA、AWS IAM |
| **PAP** (Policy Administration Point) | ポリシー管理・バージョニング | Git、専用ポリシーストア |
| **PIP** (Policy Information Point) | 属性・コンテキスト提供 | IdP、HRシステム、デバイス管理、時刻サーバー |

### 決定フロー

```
[ユーザー] → [PEP: リクエスト捕捉]
              ↓
         [PDP: ポリシー評価]
              ↓ ← [PAP: ポリシー取得]
              ↓ ← [PIP: 属性取得]
              ↓
         [決定: Allow/Deny]
              ↓
         [PEP: 強制実行]
```

**関心の分離が重要**:
- **保守性**: ポリシーをアプリコードから独立管理
- **一貫性**: 複数サービスで同一ポリシー適用
- **透明性**: 決定根拠をポリシーとログで追跡
- **スケーラビリティ**: PDP分散配置でボトルネック回避

詳細は [ARCHITECTURE-PATTERNS.md](./references/ARCHITECTURE-PATTERNS.md) 参照。

---

## Cedar言語クイックスタート

**Cedar**は、AWS発のオープンソース・ポリシー言語で、**表現力・パフォーマンス・解析可能性・オープン性**を兼ね備えています。

### Cedarポリシーの構造

すべてのCedarポリシーは **Effect（効果）、Scope（スコープ）、Conditions（条件）** の3要素で構成されます：

```cedar
permit(                                    // Effect: 許可
    principal in Employee::"eng-team",    // Scope: プリンシパル
    action == Action::"deploy",           // Scope: アクション
    resource in System::"production"      // Scope: リソース
)
when {                                     // Conditions: 条件
    context.device.managed == true        // デバイス管理下
    && context.time.hour >= 9             // 9時以降
    && context.time.hour < 17             // 17時前
};
```

**forbid（拒否）ポリシーは常にpermitをオーバーライドします**（deny-overridesモデル）。

### PARCモデル

**PARC（Principal・Action・Resource・Context）は、認可リクエストの共通フレームワーク**です：

| 要素 | 意味 | Cedar表現例 |
|-----|------|-----------|
| **Principal** | リクエスト主体 | `Employee::"alice"`, `Service::"api-gateway"` |
| **Action** | 実行したい操作 | `Action::"view"`, `Action::"edit"` |
| **Resource** | 対象オブジェクト | `Document::"doc123"`, `Database::"prod-db"` |
| **Context** | 動的コンテキスト | `context.time`, `context.device.ip`, `context.location` |

### Cedar型システム

**Cedarは強い型付け**を持ち、スキーマで事前定義されたエンティティ・属性のみ使用可能：

- **プリミティブ型**: Bool, String, Long（64bit整数）
- **拡張型**: datetime, duration, ipaddr, decimal
- **複合型**: Set, Record
- **エンティティ参照**: `resource.owner == principal`（関係の直接評価）

### オペレータ一覧

| カテゴリ | オペレータ | 用途 |
|---------|----------|------|
| Boolean | `&&`, `||`, `!` | 論理演算 |
| String | `==`, `!=`, `like` | 文字列比較・ワイルドカード |
| Long | `==`, `<`, `>`, `<=`, `>=`, `+`, `-`, `*` | 数値比較・算術 |
| Datetime/Duration | `==`, `<`, `<=`, `>`, `>=`, `datetime()`, `duration()` | 時刻・期間制約 |
| IP Address | `==`, `in`, `ip()` | IPアドレス範囲チェック |
| Set | `in`, `.contains()`, `.containsAny()` | メンバーシップ判定 |
| Entity | `is`, 型修飾子 | エンティティ型チェック |
| Tag | `.hasTag()`, `.getTag()` | タグベース制御 |

詳細は [CEDAR-POLICIES.md](./references/CEDAR-POLICIES.md) 参照。

---

## ポリシー言語選定ガイド

**主要なポリシー言語の比較**（PARCモデルとの対応）:

| 言語 | Principal | Action | Resource | Context | 主な特徴 |
|-----|-----------|--------|----------|---------|---------|
| **Cedar** | 構造的スコープ | 構造的スコープ | 構造的スコープ | when/unless | 型安全・静的解析・高速 |
| **OPA/Rego** | input.principal | input.action | input.resource | input.context | 汎用的・Datalog由来・柔軟 |
| **OpenFGA** | タプル（user:alice） | パーミッション（can_view） | タプル（doc:123） | 非対応（外部処理） | Zanzibar由来・ReBAC特化 |
| **XACML** | 属性ベース | 属性ベース | 属性ベース | environment属性 | 歴史的標準・XML冗長 |
| **AWS IAM** | aws:PrincipalTag | Action名（s3:GetObject） | ARN | aws:条件キー | AWS固有・タグベース |

### 言語選定質問（AskUserQuestion使用）

以下の質問でポリシー言語を選定します：

1. **適用範囲**: AWS専用か、マルチクラウド/オンプレミスか？
   - AWS専用 → AWS IAM
   - 汎用 → Cedar/OPA/OpenFGA

2. **主要パターン**: 関係ベース vs 属性ベース？
   - 共有・委譲中心 → OpenFGA（ReBAC）
   - コンテキスト・条件中心 → Cedar/OPA（ABAC）

3. **型安全性**: 静的解析・スキーマ検証が必要か？
   - 必要 → Cedar
   - 不要（柔軟性重視） → OPA/Rego

4. **既存インフラ**: Kubernetes環境か、サーバーレスか？
   - Kubernetes → OPA（実績豊富）
   - AWS中心 → Cedar（Verified Permissions統合）

詳細な選定基準とPARCマッピングは [POLICY-LANGUAGES.md](./references/POLICY-LANGUAGES.md) 参照。

---

## ユーザー確認の原則（AskUserQuestion）

**曖昧さがある場合、必ずAskUserQuestionツールで確認してください。** 以下のポイントで判断が必要です：

### 1. 認可モデル選定

```python
AskUserQuestion(
    questions=[{
        "question": "どの認可モデルを採用しますか？",
        "header": "認可モデル選定",
        "options": [
            {
                "label": "ReBAC（関係ベース）",
                "description": "共有・委譲・コラボレーションが中心（Google Docs型）"
            },
            {
                "label": "ABAC（属性ベース）",
                "description": "時刻・場所・デバイス等の動的コンテキスト重視"
            },
            {
                "label": "PBAC（統合型）",
                "description": "ロール・属性・関係を組み合わせて運用"
            }
        ],
        "multiSelect": False
    }]
)
```

### 2. ポリシー言語選定

```python
AskUserQuestion(
    questions=[{
        "question": "どのポリシー言語を使用しますか？",
        "header": "ポリシー言語",
        "options": [
            {"label": "Cedar", "description": "型安全・高速・静的解析可能（AWS Verified Permissions統合）"},
            {"label": "OPA/Rego", "description": "汎用的・Kubernetes実績豊富・柔軟"},
            {"label": "OpenFGA", "description": "ReBAC特化・Zanzibar由来・関係グラフ"},
            {"label": "AWS IAM", "description": "AWS専用・タグベース"}
        ],
        "multiSelect": False
    }]
)
```

### 3. PEPデプロイパターン

```python
AskUserQuestion(
    questions=[{
        "question": "PEP（Policy Enforcement Point）をどこに配置しますか？",
        "header": "PEP配置",
        "options": [
            {"label": "Embedded（アプリ内）", "description": "アプリ内部で細粒度制御・フルコンテキスト"},
            {"label": "API Gateway", "description": "一元管理・複数サービス横断・ログ集約"},
            {"label": "Sidecar", "description": "サービスメッシュ・ゼロトラスト・インフラ層"}
        ],
        "multiSelect": False
    }]
)
```

### 4. PDP集中型 vs 分散型

```python
AskUserQuestion(
    questions=[{
        "question": "PDP（Policy Decision Point）のアーキテクチャを選択してください",
        "header": "PDPアーキテクチャ",
        "options": [
            {"label": "集中型", "description": "単一PDP・一貫性重視・シンプル運用"},
            {"label": "分散型", "description": "各サービスにPDP配置・低レイテンシ・高可用性"}
        ],
        "multiSelect": False
    }]
)
```

---

## サブファイルへのナビゲーション

**詳細情報は以下のファイルを参照してください：**

- **[AUTHORIZATION-MODELS.md](./references/AUTHORIZATION-MODELS.md)**: ACL/RBAC/ReBAC/ABAC/PBACの詳細比較、strengths/limitations、適用場面
- **[CEDAR-POLICIES.md](./references/CEDAR-POLICIES.md)**: Cedarポリシー構造、型システム、オペレータ、パターン、スキーマ設計、解析手法
- **[ARCHITECTURE-PATTERNS.md](./references/ARCHITECTURE-PATTERNS.md)**: PEP/PDP/PAP/PIPの詳細、デプロイパターン、集中型vs分散型、ガバナンス
- **[POLICY-LANGUAGES.md](./references/POLICY-LANGUAGES.md)**: XACML/OPA/OpenFGA/AWS IAM/Cedarの詳細比較、PARCマッピング、選定基準

---

## 重要な実装原則

1. **スキーマ設計を最優先**: ポリシー記述前にエンティティ・アクション・属性を定義
2. **deny-by-defaultを徹底**: 明示的な許可がない限り拒否
3. **forbidで全体制約**: 組織横断ルール（デバイス管理必須等）はforbidで強制
4. **テストファースト**: ポリシーは必ずテスト・静的解析を実施
5. **ポリシーをコードとして管理**: バージョン管理・CI/CD・レビュー・ロールバック

詳細な実装パターンは [CEDAR-POLICIES.md](./references/CEDAR-POLICIES.md) を参照してください。
