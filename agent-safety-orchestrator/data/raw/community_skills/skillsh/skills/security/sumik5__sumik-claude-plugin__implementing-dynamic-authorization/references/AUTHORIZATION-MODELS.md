# Authorization Models（認可モデル）

このファイルでは、ACL、RBAC、ReBAC、ABAC、PBACの各モデルについて、仕組み・強み・制限・適用場面を詳細に解説します。

---

## ACL（Access Control List）

### 仕組み

**ACL（Access Control List）は、リソースごとに許可されたプリンシパル（ユーザー・グループ）とアクション（read/write/execute）のリストを保持します。**

- **構造**: `<Resource> → <List of (Principal, Action)>`
- **例**: Unixファイル権限
  - ファイル `report.txt` → `owner:alice:rwx, group:finance:r--, others:---`
- **決定方法**: リソースのACLを参照し、リクエスト主体がリストに含まれるか確認

### Strengths（強み）・Limitations（制限）テーブル

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| シンプルで直感的 | リソース数が増えるとリスト管理が困難 |
| 実装が容易 | リソースごとにリスト保持が必要（冗長） |
| 実行時パフォーマンス良好 | プリンシパルの属性・コンテキストを考慮不可 |
| 小規模システムに適する | スケーラビリティに欠ける（数千リソース以上で破綻） |

### 適切な使用場面

- **ファイルシステム**: Unix/Linux権限、基本的なファイル共有
- **単純なリソース保護**: 数十〜数百リソース程度の小規模システム
- **静的アクセス**: 権限変更が稀で、動的要因（時刻・場所等）を考慮不要

**使用を避けるべき場面**:
- マルチテナントSaaS
- 数千以上のリソース
- 動的コンテキスト（時刻・デバイス状態等）を考慮する必要がある場合

---

## RBAC（Role-Based Access Control）

### 仕組み

**RBACは、ユーザーにロール（役割）を割り当て、ロールにパーミッション（権限）を紐付けます。**

- **構造**: `User → Role → Permission`
- **例**:
  - ロール: `Manager`, `Engineer`, `Viewer`
  - マッピング: `Manager → [view, edit, delete]`, `Engineer → [view, edit]`
  - 割り当て: `Alice → Manager`, `Bob → Engineer`
- **決定方法**: ユーザーのロールを取得し、ロールが持つパーミッションを確認

### Strengths（強み）・Limitations（制限）テーブル

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 組織構造にマッピング可能 | **役割の爆発（Role Explosion）**: 例外・特殊ケースごとにロール増加 |
| ACLより管理が容易 | 動的コンテキスト（時刻・場所・デバイス）を考慮不可 |
| 監査が容易（誰がどのロール？） | クロスチーム・一時的アクセスで複雑化 |
| 中規模システムに適する | マルチテナント環境でスケールしにくい |

### 役割の爆発（Role Explosion）問題

**RBACの最大の課題は、例外・特殊ケースに対応するために役割が無限増殖すること**です：

| シナリオ | 対応策（RBAC） | 問題点 |
|---------|-------------|--------|
| プロジェクトマネージャーがチームAのみアクセス | `ProjectManager-TeamA`ロール作成 | チーム数分のロールが必要 |
| 外部委託者が特定ドキュメントのみ編集 | `Contractor-Editor-Doc123`ロール作成 | ドキュメントごとにロール増殖 |
| 営業が自地域の顧客データのみ参照 | `Sales-RegionUS`, `Sales-RegionEU`... | 地域×役割の組み合わせ爆発 |

**解決策**: ABAC（属性ベース）またはReBAC（関係ベース）に移行し、役割ではなく属性や関係で判定する。

### 適切な使用場面

- **社内システム**: 部門・職務が明確で変更頻度が低い
- **エンタープライズアプリケーション**: 社員数百〜数千程度
- **監査要件**: 「誰がどのロールか」を明確に追跡したい

**使用を避けるべき場面**:
- 動的コンテキスト（時刻・場所・デバイス状態）を考慮する必要がある
- マルチテナント・多様な組織構造
- プロジェクトベース・チームベースの権限が頻繁に変わる

---

## ReBAC（Relationship-Based Access Control）

### 関係グラフ

**ReBACは、プリンシパルとリソース間の関係をグラフで表現し、パスを辿ってアクセス決定**します。

#### 構造例

```
[User: Alice] --owner--> [Document: doc1]
[User: Carol] --manager--> [User: Alice]
[User: Bob] --viewer--> [Document: doc1]
```

#### 決定方法

- **ルール**: `permit view when principal has "viewer" or "owner" relationship to resource`
- **ルール**: `permit all when principal is "manager" of "owner"`
- Carolが `doc1` にアクセス → グラフを辿って `Carol --manager--> Alice --owner--> doc1` → **許可**

### Google Zanzibar

**Google Zanzibarは、ReBACの代表的実装**です：

- **タプルベース**: 関係を `<object>#<relation>@<subject>` 形式で保存
  - 例: `document:doc1#viewer@user:alice`
- **スキーマ定義**: 関係とパーミッションを定義
  - `type document { relations { viewer, owner }, permissions { view := viewer or owner } }`
- **高速評価**: 数百万リクエスト/秒をサポート
- **実装例**: [OpenFGA](https://openfga.dev), [Authzed](https://authzed.com), Google Docs/Drive

### 仕組み（静的ルール + 動的グラフ）

**ReBACのポリシーは静的（ほとんど変更しない）、グラフデータが動的（頻繁に変更）**:

| 要素 | 性質 | 管理方法 |
|-----|------|---------|
| **静的ルール** | 変更頻度: 低 | コードとして管理・デプロイ |
| **動的グラフ** | 変更頻度: 高 | UI操作・API呼び出しで更新 |

**例（ドキュメント共有システム）**:

```
静的ルール:
  permit view when principal has "viewer" or "owner" relation
  permit edit when principal has "editor" or "owner" relation
  permit all when principal is "manager" of "owner"

動的グラフ:
  document:doc1#owner@user:alice
  document:doc1#viewer@user:bob
  user:alice#manager@user:carol
```

Aliceがドキュメントをアリスに共有 → グラフに `document:doc1#viewer@user:bob` を追加 → **ポリシー変更不要**

### Strengths（強み）・Limitations（制限）テーブル

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 人間の関係・組織構造を自然に表現 | 時刻・デバイス状態等の動的コンテキスト非対応 |
| 委譲・共有が容易（UIで直接操作） | 大規模・複雑なグラフでデバッグ困難 |
| ポリシー変更不要（グラフ更新で対応） | グラフ管理ツール・パストレース機能が必要 |
| マルチテナント・コラボレーションに最適 | 条件付きアクセス（時間制限等）は外部処理 |

### 適切な使用場面

- **コラボレーションツール**: Google Docs、Slack、Notion
- **SaaS**: プロジェクト管理、チケットシステム、CRM
- **委譲が中心**: ドキュメント共有、ワークスペース管理
- **組織階層**: マネージャーが部下のリソースにアクセス

**使用を避けるべき場面**:
- 時刻・場所・デバイス等の動的コンテキストが必須
- 関係が少ない・シンプルなアクセス制御（ACL/RBACで十分）

---

## ABAC（Attribute-Based Access Control）

### 属性評価マトリクス

**ABACは、プリンシパル・リソース・環境の属性を評価して決定**します。

#### 例: デプロイシステムへのアクセス

| シナリオ | clearance_level | device_managed | hour_of_day | on_call | 決定 |
|---------|----------------|----------------|-------------|---------|------|
| Alice、22時、オンコール中 | high | true | 22 | true | ✅ Allow |
| Alice、22時、オンコール外 | high | true | 22 | false | ❌ Deny |
| Bob、14時、平日 | medium | true | 14 | false | ❌ Deny（clearance不足） |
| Carol、14時、平日 | high | true | 14 | false | ✅ Allow |
| Alice、10時、非管理デバイス | high | false | 10 | false | ❌ Deny（デバイス） |

#### ポリシー例（Cedar）

```cedar
permit(
    principal in Employee::*,
    action == Action::"deploy",
    resource in System::"production"
)
when {
    context.device.managed == true &&
    (
        (context.time.hour >= 9 && context.time.hour < 17 && principal.clearance == "high")
        || (principal.on_call == true && principal.clearance == "high")
    )
};
```

### Strengths（強み）・Limitations（制限）テーブル

| Strengths（強み） | Limitations（制限） |
|------------------|-------------------|
| 細粒度・動的コンテキスト対応 | ポリシーが複雑化しやすい |
| スケーラブル（属性の組み合わせ） | 属性取得の信頼性・鮮度が重要 |
| リアルタイム決定 | デバッグ困難（多数の属性・条件） |
| コンプライアンス対応（監査可能） | パフォーマンス最適化が必要（属性取得遅延） |

### 適切な使用場面

- **金融システム**: クリアランスレベル、時刻制限、リスクスコア評価
- **医療記録**: 患者同意、診療科、データ分類レベル
- **政府機関**: セキュリティクリアランス、地理的制限、監査要件
- **エンタープライズ**: 部門・役職・プロジェクト・時刻・デバイスの組み合わせ

**使用を避けるべき場面**:
- 関係・委譲が中心（ReBAC適用）
- 属性が単純（RBAC適用）
- 属性取得インフラが整備されていない

---

## PBAC（Policy-Based Access Control）

### ハイブリッドアプローチ

**PBACは、RBAC・ABAC・ReBACを統合する上位概念**です。ポリシーを外部化し、実行時に評価することで、柔軟かつ統一的な認可を実現します。

#### 統合例

| モデル | 入力データ | ポリシーでの使用 |
|-------|----------|---------------|
| **RBAC** | ロール（`principal in Group::"admin"`） | スコープまたは条件で参照 |
| **ReBAC** | 関係（`resource.owner.manager == principal`） | 条件で関係トラバース |
| **ABAC** | 属性（`context.device.managed`, `principal.clearance`） | 条件で動的評価 |

#### ポリシー例（複合）

```cedar
// 複合ポリシー: ロール + 関係 + 属性
permit(
    principal in Employee::*,       // スコープ: 全従業員
    action == Action::"edit",
    resource in Document::*
)
when {
    (
        resource.owner.manager == principal    // ReBAC: マネージャー関係
        || principal in Group::"legal"         // RBAC: 法務チーム
    )
    && context.device.managed == true          // ABAC: デバイス信頼
    && context.time.hour >= 9                  // ABAC: 時刻制限
};
```

### Policy as Code vs Policy as Data

| アプローチ | 形式 | 主な用途 | 管理方法 |
|-----------|------|---------|---------|
| **Policy as Code** | Cedar, Rego, XACML | ABAC中心・条件ロジック | バージョン管理・CI/CD |
| **Policy as Data** | 関係グラフ・タプル | ReBAC中心・委譲 | UI操作・グラフ更新 |

**PBACでは両方を組み合わせ可能**:

```cedar
// Policy as Code: 静的ルール
permit(
    principal,
    action == Action::"view",
    resource in Document::*
)
when {
    principal in resource.readers_team      // Policy as Data: 動的メンバーシップ
    && context.device.managed == true       // Policy as Code: 静的条件
};
```

### 適切な使用場面

- **マルチテナントSaaS**: テナントごとの柔軟なポリシー
- **エンタープライズ基盤**: 部門・プロジェクト・コンプライアンス要件の組み合わせ
- **複雑な要件**: 時刻・場所・関係・ロールすべてを考慮する必要がある

---

## 各モデルのリファレンスアーキテクチャマッピング

**すべてのモデルがPEP/PDP/PAP/PIPアーキテクチャに対応**します：

| モデル | PEP | PDP | PAP | PIP |
|-------|-----|-----|-----|-----|
| **ACL** | アプリ内 | ACLリスト参照 | ACL管理UI | ユーザーディレクトリ |
| **RBAC** | アプリ/Gateway | ロールマッピング評価 | ロール管理UI | IdP（ロール取得） |
| **ReBAC** | アプリ/Gateway | グラフトラバース | UI（共有ボタン等） | 関係グラフDB |
| **ABAC** | アプリ/Gateway/Sidecar | ポリシーエンジン | Git/ポリシーストア | IdP/HRシステム/デバイスMDM/時刻サーバー |
| **PBAC** | 上記すべて | Cedar/OPA等 | バージョン管理 + UI | 統合PIP（複数ソース） |

### ABACでのPIPの重要性

**ABACは、PIP（Policy Information Point）が最も重要**です：

| 属性カテゴリ | 取得元例 |
|------------|---------|
| **プリンシパル属性** | IdP（部門・役職）、HRシステム（クリアランス） |
| **リソース属性** | メタデータストア（分類・所有者） |
| **環境属性** | 時刻サーバー、MDM（デバイス信頼）、IPジオロケーション |

**属性の鮮度・信頼性が決定精度に直結**します。キャッシュ戦略・同期頻度が重要。

---

## モデル選定のフローチャート

```
動的コンテキスト（時刻・場所・デバイス）が必須？
  ├─ Yes → ABAC（属性ベース）
  └─ No
      ├─ 共有・委譲・コラボが中心？
      │   ├─ Yes → ReBAC（関係ベース）
      │   └─ No
      │       ├─ 組織ロールが明確？
      │       │   ├─ Yes → RBAC（ロールベース）
      │       │   └─ No → ACL（リソースごとリスト）
      └─ 複数要件の組み合わせ？
          └─ Yes → PBAC（統合型）
```

詳細な選定基準は [SKILL.md](../SKILL.md) の「認可モデル選定ガイド」を参照してください。
