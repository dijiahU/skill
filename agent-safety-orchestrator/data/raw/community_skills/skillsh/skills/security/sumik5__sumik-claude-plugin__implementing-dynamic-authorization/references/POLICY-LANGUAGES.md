# Policy Languages（ポリシー言語）

このファイルでは、主要なポリシー言語（XACML、OPA/Rego、OpenFGA、AWS IAM、Cedar）のPARCモデルマッピング、強度比較、選定基準を解説します。

---

## 各言語のPARCモデルマッピング

**PARC（Principal・Action・Resource・Context）は、すべてのポリシー言語で共通する認可リクエストのフレームワーク**です。

### 比較テーブル

| 言語 | Principal | Action | Resource | Context |
|-----|-----------|--------|----------|---------|
| **XACML** | subject属性 | action:id属性 | resource属性 | environment属性 |
| **OPA/Rego** | input.principal | input.action | input.resource | input.context |
| **OpenFGA** | タプル（user:alice） | パーミッション（can_view） | タプル（doc:123） | 非対応（外部処理） |
| **AWS IAM** | aws:PrincipalTag | Action名（s3:GetObject） | ARN | aws:条件キー（RequestTime等） |
| **Cedar** | 構造的スコープ | 構造的スコープ | 構造的スコープ | when/unless |

---

## XACML: 歴史的標準

### 概要

**XACML（eXtensible Access Control Markup Language）は、2003年にOASISが標準化**した最初の包括的ポリシー言語です。

| 項目 | 詳細 |
|-----|------|
| **開発元** | OASIS（標準化団体） |
| **バージョン** | 3.0（2013年） |
| **形式** | XML |
| **アーキテクチャ** | PEP/PDP/PAP/PIPモデルの提唱元 |

### XML構文

**例: 同一部門のみアクセス許可**

```xml
<Policy PolicyId="ConfidentialDocAccess" RuleCombiningAlgId="permit-overrides">
  <Target>
    <Subjects>
      <AnySubject/>
    </Subjects>
    <Resources>
      <Resource>
        <Attribute AttributeId="resource:type" DataType="string">
          <AttributeValue>confidential-doc</AttributeValue>
        </Attribute>
      </Resource>
    </Resources>
  </Target>

  <Rule RuleId="PermitSameDept" Effect="Permit">
    <Condition>
      <Apply FunctionId="string-equal">
        <AttributeDesignator AttributeId="subject:department" Category="access-subject" DataType="string"/>
        <AttributeDesignator AttributeId="resource:owner-department" Category="resource" DataType="string"/>
      </Apply>
    </Condition>
  </Rule>
</Policy>
```

**Cedar等価コード**:

```cedar
permit(principal, action, resource)
when {
    resource.confidential == true &&
    principal.department == resource.owner.department
};
```

### ALFA: XACMLの簡略構文

**ALFA（Abbreviated Language for Authorization）は、XACMLのXML冗長性を解消**します：

```
namespace acme
policy ConfidentialDocAccess {
    target clause resource.confidential == true;
    apply permit if principal.department == resource.owner.department;
}
```

**特徴**:
- XACML 3.0にコンパイル可能
- プログラミング言語風の構文
- Axiomatics社開発・OASIS標準化

### PARCマッピング

| PARC要素 | XACML表現 | 特徴 |
|---------|-----------|------|
| **Principal** | `<AttributeDesignator AttributeId="subject:xxx" Category="access-subject">` | 属性のみ（エンティティ参照なし） |
| **Action** | `<AttributeDesignator AttributeId="action:id">` | 文字列値（型システムなし） |
| **Resource** | `<AttributeDesignator AttributeId="resource:xxx" Category="resource">` | 属性のみ（階層構造なし） |
| **Context** | `<AttributeDesignator Category="environment">` | 時刻・場所等の環境要因 |

### Strengths & Limitations

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 標準化（政府・規制業界での実績） | XML冗長・記述困難 |
| 包括的アーキテクチャ定義 | ツール不足・開発体験悪い |
| 属性ベース細粒度制御 | パフォーマンス課題 |

### 適用場面・不適な場面

| 適用場面 | 不適な場面 |
|---------|----------|
| レガシーシステム（XACML既存） | 新規プロジェクト |
| 規制要件（標準準拠必須） | クラウドネイティブ環境 |
| | 開発者体験重視 |

---

## OPA/Rego: クラウドネイティブ汎用エンジン

### 概要

**OPA（Open Policy Agent）は、Kubernetes・マイクロサービス向け汎用ポリシーエンジン**です。

| 項目 | 詳細 |
|-----|------|
| **開発元** | Styra（現CNCF卒業プロジェクト） |
| **言語** | Rego（Datalog由来） |
| **用途** | 認可・Kubernetesアドミッション制御・設定検証 |
| **特徴** | 汎用的・柔軟・高学習コスト |

### Regoポリシー例

**例: 同一部門のみアクセス許可**

```rego
package acme.authz

import rego.v1

default allow := false

allow if {
  input.resource.confidential == true
  input.principal.department == input.resource.owner.department
}
```

**Cedar等価コード**:

```cedar
permit(principal, action, resource)
when {
    resource.confidential == true &&
    principal.department == resource.owner.department
};
```

### CedarとRegoの構造的違い

**Cedarはスコープフィルタリングを持つ、Regoは持たない**:

| 言語 | スコープフィルタ | 評価方法 |
|-----|----------------|---------|
| **Cedar** | ✅ あり | Principal・Action・Resourceでポリシー事前選別 |
| **Rego** | ❌ なし | すべてのポリシーを全入力で評価 |

**影響**:
- **Cedar**: 無関係なポリシーをスキップ → 高速
- **Rego**: 柔軟だが手動で条件記述 → 低速化リスク

### PARCマッピング

| PARC要素 | Rego表現 | 特徴 |
|---------|---------|------|
| **Principal** | `input.principal.*` | ユーザー定義構造（型制約なし） |
| **Action** | `input.action` | 文字列等（型なし） |
| **Resource** | `input.resource.*` | 任意JSON構造 |
| **Context** | `input.context.*` | 柔軟（ネスト・配列可） |

### Strengths & Limitations

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 汎用的（認可以外も対応） | 認可専用ではない（構造なし） |
| Kubernetes実績豊富 | 学習コスト高（Datalog） |
| 柔軟な入力構造 | 型安全性なし |
| CNCF標準 | スコープフィルタなし（パフォーマンス） |

### 適用場面・不適な場面

| 適用場面 | 不適な場面 |
|---------|----------|
| Kubernetesアドミッション制御 | 認可専用（Cedar等が適） |
| 設定検証・コンプライアンス | 型安全性必須 |
| インフラポリシー | 学習コスト許容できない |

---

## OpenFGA: Zanzibar由来ReBAC特化

### 概要

**OpenFGAは、Google Zanzibarをベースとした関係ベース認可システム**です。

| 項目 | 詳細 |
|-----|------|
| **開発元** | Auth0（現Okta）、オープンソース |
| **モデル** | ReBAC（Relationship-Based Access Control） |
| **形式** | タプル + スキーマ |
| **特徴** | 関係グラフトラバース・委譲・共有に最適 |

### スキーマ例

**例: ドキュメントアクセス制御**

```
type user
  relations
    define manager: [user]

type document
  relations
    define viewer: [user]
    define owner: [user]
    define can_access as viewer or owner or owner->manager
```

### タプル例

**関係データ**:

```
document:doc1#owner@user:alice
user:alice#manager@user:carol
```

**意味**:
- Aliceはdoc1の所有者
- CarolはAliceのマネージャー

### パーミッションチェック

**リクエスト**:

```json
{
  "user": "user:carol",
  "relation": "can_access",
  "object": "document:doc1"
}
```

**評価**:
1. `can_access = viewer or owner or owner->manager`
2. Aliceはownerだが、Carolは直接関係なし
3. `owner->manager`を辿る → CarolはAliceのmanager → **許可**

### PARCマッピング

| PARC要素 | OpenFGA表現 | 特徴 |
|---------|-------------|------|
| **Principal** | `user:alice` | タプル形式（属性なし） |
| **Action** | `can_view`, `can_edit`等 | パーミッション名（スキーマ定義） |
| **Resource** | `document:doc1` | タプル形式 |
| **Context** | 非対応 | 時刻・デバイス等は外部処理 |

### Strengths & Limitations

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 関係・委譲を自然に表現 | Context属性非対応（時刻・デバイス等） |
| UI統合容易（共有ボタン） | 条件ロジック不可（ABACには不向き） |
| Zanzibar実績 | ポリシー = データ（コード管理不可） |
| 高速グラフトラバース | デバッグ困難（大規模グラフ） |

### 適用場面・不適な場面

| 適用場面 | 不適な場面 |
|---------|----------|
| コラボレーションツール（Google Docs型） | 時刻・デバイス制約必須 |
| ドキュメント共有・チケット管理 | 複雑な条件ロジック |
| マルチテナントSaaS | 属性ベース細粒度制御 |

---

## AWS IAM: AWS固有

### 概要

**AWS IAMは、AWS専用の細粒度認可システム**です。

| 項目 | 詳細 |
|-----|------|
| **開発元** | Amazon Web Services |
| **形式** | JSON |
| **適用範囲** | AWSサービス専用 |
| **評価規模** | 毎秒5億以上のリクエスト |

### ポリシー例

**例: 同一部門のみS3オブジェクトアクセス許可（タグベース）**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::acme-docs/*",
      "Condition": {
        "StringEquals": {
          "aws:PrincipalTag/department": "${s3:ExistingObjectTag/owner-department}"
        },
        "StringEqualsIfExists": {
          "s3:ExistingObjectTag/confidential": "true"
        }
      }
    }
  ]
}
```

**特徴**:
- **タグto タグ比較**: プリンシパルタグとリソースタグを動的比較
- **条件キー**: `aws:PrincipalTag`, `s3:ExistingObjectTag`, `aws:RequestTime`等

### PARCマッピング

| PARC要素 | AWS IAM表現 | 特徴 |
|---------|------------|------|
| **Principal** | `aws:PrincipalTag/*`, IAMロール | IAM Identity Center統合でタグ自動同期 |
| **Action** | `s3:GetObject`, `dynamodb:PutItem`等 | AWSサービスAPI名 |
| **Resource** | ARN（`arn:aws:s3:::bucket/key`） | AWS固有識別子 |
| **Context** | `aws:RequestTime`, `aws:SourceIp`等 | AWS条件キー |

### Strengths & Limitations

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| AWS統合（ネイティブ） | AWS専用（他クラウド不可） |
| タグベース細粒度制御 | JSON冗長 |
| 超高パフォーマンス | 学習コスト（AWS固有概念） |
| 豊富な条件キー | ポータビリティなし |

### 適用場面・不適な場面

| 適用場面 | 不適な場面 |
|---------|----------|
| AWSワークロード全般 | マルチクラウド |
| S3・DynamoDB等の細粒度制御 | オンプレミス |
| Identity Center連携 | AWS外のアプリ |

---

## Cedar: 型安全・構造的スコープ・静的解析

### 概要

**Cedarは、AWS発のオープンソース・型安全ポリシー言語**です。

| 項目 | 詳細 |
|-----|------|
| **開発元** | AWS（オープンソース化） |
| **ライセンス** | Apache 2.0 |
| **特徴** | 型安全・構造的スコープ・静的解析・高速 |
| **統合** | Amazon Verified Permissions/Verified Access |

### ポリシー例

**例: 同一部門・管理デバイス・営業時間のみアクセス許可**

```cedar
permit(
    principal in Employee::*,
    action == Action::"doc:view",
    resource in Document::*
)
when {
    resource.confidential == true &&
    principal.department == resource.owner.department &&
    context.device.managed == true &&
    context.time.hour >= 9 &&
    context.time.hour < 17
};
```

### PARCマッピング

| PARC要素 | Cedar表現 | 特徴 |
|---------|----------|------|
| **Principal** | `principal in Employee::"alice"` | 構造的スコープ・エンティティ参照 |
| **Action** | `action == Action::"view"` | スキーマ定義・型安全 |
| **Resource** | `resource in Document::*` | エンティティ型・階層対応 |
| **Context** | `context.device.managed`, `context.time.hour` | スキーマ定義・型付き |

### Strengths & Limitations

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 型安全・スキーマ強制 | 新興言語（2023年公開） |
| 構造的スコープ（高速） | エコシステム発展中 |
| 静的解析（SMTソルバー） | AWS以外の実装少ない |
| RBAC/ReBAC/ABAC統合 | 正規表現非対応（意図的） |

### 適用場面・不適な場面

| 適用場面 | 不適な場面 |
|---------|----------|
| 型安全性必須 | 既存XACML/OPA資産活用 |
| 複数モデル統合（PBAC） | 超柔軟性必要（Rego） |
| 静的解析・形式検証 | AWS外の専用実装不要 |
| AWS Verified Permissions利用 | |

---

## 言語選定基準テーブル

### 機能比較

| 言語 | 型安全 | スコープフィルタ | 静的解析 | ReBAC | ABAC | 学習コスト |
|-----|-------|----------------|---------|-------|------|----------|
| **XACML** | ❌ | ❌ | ❌ | ❌ | ✅ | 高 |
| **OPA/Rego** | ❌ | ❌ | ❌ | △ | ✅ | 高 |
| **OpenFGA** | ✅ | ✅ | ❌ | ✅ | ❌ | 中 |
| **AWS IAM** | △ | △ | ❌ | ❌ | ✅ | 高（AWS固有） |
| **Cedar** | ✅ | ✅ | ✅ | ✅ | ✅ | 中 |

### パフォーマンス比較

| 言語 | 評価速度 | スケーラビリティ | 備考 |
|-----|---------|---------------|------|
| **XACML** | 低 | 低 | XML解析オーバーヘッド |
| **OPA/Rego** | 中〜高 | 高 | スコープなし→全評価 |
| **OpenFGA** | 高 | 高 | グラフトラバース最適化 |
| **AWS IAM** | 超高 | 超高 | AWS専用最適化 |
| **Cedar** | 高 | 高 | スコープフィルタ+静的最適化 |

---

## 強度マップ（PARC要素 + ポータビリティ）

**各言語がPARCの各要素をどの程度サポートするか**:

| 言語 | Principal | Action | Resource | Context | Portability |
|-----|-----------|--------|----------|---------|-------------|
| **XACML** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **OPA/Rego** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **OpenFGA** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
| **AWS IAM** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **Cedar** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

**評価基準**:
- ⭐ = 基本的サポート
- ⭐⭐⭐⭐⭐ = 最高レベル（型安全・構造化・拡張性）

---

## 選定質問リスト（AskUserQuestion推奨）

### 1. 適用範囲

**質問**: どのプラットフォーム・環境で使用しますか？

| 回答 | 推奨言語 |
|-----|---------|
| AWS専用 | AWS IAM（第一候補）、Cedar（Verified Permissions利用） |
| マルチクラウド | Cedar、OPA/Rego |
| オンプレミス | Cedar、OPA/Rego |
| Kubernetes中心 | OPA/Rego（実績豊富） |

### 2. 主要パターン

**質問**: 認可の中心は何ですか？

| 回答 | 推奨言語 |
|-----|---------|
| 関係・共有・委譲 | OpenFGA、Cedar（ReBAC対応） |
| 属性・コンテキスト | Cedar、OPA/Rego |
| ロール中心（単純） | Cedar（RBACパターン）、AWS IAM（IAMロール） |

### 3. 型安全性

**質問**: 型安全性・静的解析は必須ですか？

| 回答 | 推奨言語 |
|-----|---------|
| 必須 | Cedar（SMT解析対応） |
| 柔軟性優先 | OPA/Rego |

### 4. 既存システム

**質問**: 既存の認可システムはありますか？

| 回答 | 推奨言語 |
|-----|---------|
| XACML既存 | XACML継続（ALFA導入検討）、または段階的にCedar移行 |
| OPA既存 | OPA継続、または新規部分にCedar |
| なし | Cedar（モダン・型安全）またはOPA（汎用） |

### 5. 開発リソース

**質問**: 学習コストをどこまで許容できますか？

| 回答 | 推奨言語 |
|-----|---------|
| 低学習コスト重視 | Cedar（構文シンプル） |
| 高学習コスト許容 | OPA/Rego（柔軟性最大） |

---

## ハイブリッドアプローチ: Topaz

**Topaz**は、OPA/RegoとZanzibar型グラフを統合したサービスです：

| 要素 | 詳細 |
|-----|------|
| **ポリシーエンジン** | OPA/Rego（条件ロジック） |
| **関係ストア** | Zanzibar型グラフ（ReBAC） |
| **利点** | ABAC + ReBACを単一システムで実現 |
| **適用場面** | 複雑な要件（時刻制限 + 関係ベース権限） |

**公式サイト**: [https://www.topaz.sh](https://www.topaz.sh)

---

## まとめ: ポリシー言語選定フローチャート

```
AWS専用？
  ├─ Yes → AWS IAM（第一候補）
  └─ No
      ├─ 関係・共有が中心？
      │   ├─ Yes → OpenFGA
      │   └─ No
      │       ├─ 型安全性必須？
      │       │   ├─ Yes → Cedar
      │       │   └─ No
      │       │       ├─ Kubernetes？
      │       │       │   ├─ Yes → OPA/Rego
      │       │       │   └─ No → Cedar（汎用推奨）
      │       └─ レガシー（XACML既存）？
      │           └─ Yes → XACML + ALFA検討
      └─ 複数モデル統合（PBAC）？
          └─ Yes → Cedar（RBAC/ReBAC/ABAC統合）
```

詳細な実装パターンは [CEDAR-POLICIES.md](CEDAR-POLICIES.md)、アーキテクチャは [ARCHITECTURE-PATTERNS.md](ARCHITECTURE-PATTERNS.md) を参照してください。
