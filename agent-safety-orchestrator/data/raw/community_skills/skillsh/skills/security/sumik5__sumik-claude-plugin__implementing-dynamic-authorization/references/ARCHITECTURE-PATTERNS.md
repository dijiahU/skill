# Architecture Patterns（アーキテクチャパターン）

このファイルでは、認可リファレンスアーキテクチャ（PEP/PDP/PAP/PIP）の詳細、デプロイパターン、集中型vs分散型、ガバナンスについて解説します。

---

## 認可リファレンスアーキテクチャ詳細

**XACMLが提唱した4コンポーネントモデル（PEP/PDP/PAP/PIP）は、現代の認可システムの標準**です。

### 各コンポーネントの詳細

#### 1. PEP (Policy Enforcement Point)

**役割**: リクエストを捕捉し、PDPの決定を強制実行

| 配置場所 | 実装例 | 特徴 |
|---------|--------|------|
| **アプリケーション内** | アプリコードに組み込み | フルコンテキストアクセス・細粒度制御 |
| **API Gateway** | Kong, AWS API Gateway, Envoy | 一元管理・複数サービス横断 |
| **Sidecar** | Istio, Linkerd | サービスメッシュ・ゼロトラスト |

#### 2. PDP (Policy Decision Point)

**役割**: ポリシー評価と決定（Allow/Deny）

| 実装方式 | 詳細 |
|---------|------|
| **集中型PDP** | 単一PDPサービス・一貫性重視 |
| **分散型PDP** | 各サービスにPDP配置・低レイテンシ |
| **Authorization Client** | PEP+PDP+エンティティキャッシュのバンドル |

#### 3. PAP (Policy Administration Point)

**役割**: ポリシーの作成・管理・バージョニング・デプロイ

| 管理形態 | 実装例 |
|---------|--------|
| **バージョン管理** | Git（policy-as-code） |
| **専用ストア** | AWS Verified Permissions、専用PolicyDB |
| **UI** | Google Docs共有ボタン（ReBAC）、管理コンソール |

#### 4. PIP (Policy Information Point)

**役割**: 属性・コンテキストデータの提供

| 属性カテゴリ | 取得元例 |
|------------|---------|
| **Principal属性** | IdP（Okta, Auth0）、HRシステム |
| **Resource属性** | メタデータストア、関係グラフDB |
| **環境属性** | 時刻サーバー、MDM（デバイス信頼）、IPジオロケーション |

---

## PEPデプロイパターン

### 1. Embedded（アプリケーション内）

**アプリコード内で直接PEPを実装**します。

#### 実装例

```typescript
// TypeScript例
import { CedarPDP } from '@cedar/policy';

async function handleDocumentEdit(req: Request) {
    const decision = await CedarPDP.evaluate({
        principal: `Employee::"${req.userId}"`,
        action: "Action::\"doc:edit\"",
        resource: `Document::"${req.docId}"`,
        context: {
            device: { managed: req.headers['device-managed'] === 'true' },
            time: { hour: new Date().getHours() }
        }
    });

    if (decision === 'Deny') {
        return res.status(403).json({ error: 'Access Denied' });
    }

    // ビジネスロジック実行
}
```

#### 比較テーブル

| 観点 | 評価 | 詳細 |
|-----|------|------|
| **Pros** | ✅ フルコンテキストアクセス | アプリ内部状態（セッション・ローカル変数）を直接参照可能 |
| | ✅ 細粒度制御 | UI要素単位・フィールドレベルの権限チェック |
| | ✅ 低レイテンシ | ネットワークホップ不要 |
| **Cons** | ❌ 重複実装 | 複数サービスで同じPEPロジック |
| | ❌ 一元管理困難 | ポリシー更新時に全サービス再デプロイ必要 |
| | ❌ 保守コスト | 各サービスでテスト・バージョン管理 |

#### 適用場面

- **高セキュリティアプリ**: 金融決済、医療記録アクセス
- **細粒度制御**: UIフィールド単位、行レベルセキュリティ
- **モノリシックアプリ**: 単一サービスで完結

### 2. API Gateway（ゲートウェイ）

**API Gatewayでリクエストを捕捉し、PDPに問い合わせ**します。

#### アーキテクチャ図（概念）

```
[Client] → [API Gateway + PEP]
             ↓ (PDP問い合わせ)
             ↓
          [Service A] [Service B] [Service C]
```

#### 比較テーブル

| 観点 | 評価 | 詳細 |
|-----|------|------|
| **Pros** | ✅ 一元管理 | 全サービスで統一ポリシー適用 |
| | ✅ 簡単な更新 | ゲートウェイ側でポリシー更新完結 |
| | ✅ ログ集約 | すべてのリクエストを一箇所で監査 |
| **Cons** | ❌ 粗粒度制御 | API単位の制御（UI要素単位は困難） |
| | ❌ コンテキスト制約 | アプリ内部状態にアクセス不可 |
| | ❌ 単一障害点 | ゲートウェイダウンで全サービス影響 |

#### 適用場面

- **マイクロサービスAPI**: 複数サービスで統一ポリシー
- **SaaS APIプロダクト**: テナント単位のレート制限・権限管理
- **ゼロトラストゲートウェイ**: 外部公開APIの一元保護

### 3. Sidecar（サイドカー）

**各サービスポッドにSidecarコンテナとしてPEPを配置**します（サービスメッシュ）。

#### アーキテクチャ図（概念）

```
[Pod: Service A]
  ├─ [App Container]
  └─ [Sidecar PEP] → PDP

[Pod: Service B]
  ├─ [App Container]
  └─ [Sidecar PEP] → PDP
```

#### 比較テーブル

| 観点 | 評価 | 詳細 |
|-----|------|------|
| **Pros** | ✅ サービスメッシュ統合 | Istio/Linkerdと自然に統合 |
| | ✅ アプリ変更不要 | 既存アプリコード改修なし |
| | ✅ サービス間認可 | マイクロサービス間のゼロトラスト |
| **Cons** | ❌ 運用複雑化 | Sidecar管理・ネットワークポリシー |
| | ❌ キャッシュ鮮度 | ローカルキャッシュのタイムラグ |
| | ❌ リソース消費 | 各ポッドでPEPプロセス起動 |

#### 適用場面

- **Kubernetes環境**: サービスメッシュ採用済み
- **ゼロトラスト**: すべてのサービス間通信を認可
- **マイクロサービス**: 各サービスに個別ポリシー適用

---

## PEPデプロイパターン比較テーブル（統合）

| パターン | Pros | Cons | 適用場面 |
|---------|------|------|---------|
| **Embedded** | フルコンテキスト、細粒度制御 | 重複実装、一元管理困難 | 高セキュリティアプリ、UI要素制御 |
| **API Gateway** | 一元管理、ログ集約 | 粗粒度制御、コンテキスト制約 | マイクロサービスAPI、SaaS API |
| **Sidecar** | メッシュ統合、アプリ変更不要 | 運用複雑、リソース消費 | Kubernetes、ゼロトラスト |

---

## PDP集中型 vs 分散型

### 集中型PDP

**単一PDPサービスですべての決定を処理**します。

#### アーキテクチャ図（概念）

```
[PEP: App1] ↘
[PEP: App2] → [集中型PDP] → [PAP: ポリシーストア]
[PEP: App3] ↗                → [PIP: 属性ストア]
```

#### 特徴

| 観点 | 詳細 |
|-----|------|
| **Pros** | 一貫性（全サービスで同一ポリシー）、シンプル運用、ログ集約 |
| **Cons** | レイテンシ増加、単一障害点、スケーラビリティ制約 |
| **適用場面** | 社内システム、一貫性重視、トラフィック中程度 |

### 分散型PDP（Authorization Client）

**各サービスにPDP+エンティティキャッシュを配置**します。

#### アーキテクチャ図（概念）

```
[Service A]
  └─ [Authorization Client]
       ├─ PEP
       ├─ PDP（ローカル）
       └─ Entity Cache
           ↓ 定期同期
       [PAP] [PIP]

[Service B]
  └─ [Authorization Client]
       ├─ PEP
       ├─ PDP（ローカル）
       └─ Entity Cache
           ↓ 定期同期
       [PAP] [PIP]
```

#### 特徴

| 観点 | 詳細 |
|-----|------|
| **Pros** | 低レイテンシ（ローカル評価）、高可用性（PDP障害耐性）、スケーラビリティ |
| **Cons** | 運用複雑化（キャッシュ同期）、一貫性（一時的なズレ）、リソース消費 |
| **適用場面** | グローバル分散システム、低レイテンシ要求、高可用性要求 |

### 比較テーブル（集中型 vs 分散型）

| 観点 | 集中型PDP | 分散型PDP |
|-----|----------|-----------|
| **レイテンシ** | 高（ネットワークホップ） | 低（ローカル評価） |
| **一貫性** | 強い一貫性 | 結果整合性（キャッシュ遅延） |
| **可用性** | 単一障害点リスク | 高可用性（各サービス独立） |
| **運用複雑度** | シンプル | 複雑（キャッシュ同期） |
| **スケーラビリティ** | PDP垂直スケール | 水平スケール（サービス数） |

---

## アーキテクチャ選択ガイド（フィールドガイド）

**以下の質問で適切なパターンを選択**します（AskUserQuestionでの確認推奨）：

### 1. 強制実行ポイント（PEP）の選択

| 質問 | 選択肢 |
|-----|--------|
| **信頼境界はどこ？** | ・アプリ内（Embedded）<br>・エッジ（API Gateway）<br>・サービス間（Sidecar） |
| **制御粒度は？** | ・UI要素単位 → Embedded<br>・API単位 → Gateway<br>・サービス間 → Sidecar |
| **既存インフラは？** | ・Kubernetes → Sidecar候補<br>・API Gateway既存 → Gateway候補 |

### 2. 決定ポイント（PDP）の選択

| 質問 | 選択肢 |
|-----|--------|
| **レイテンシ要求は？** | ・サブミリ秒 → 分散型<br>・10ms以内 → 集中型可 |
| **一貫性 vs 可用性？** | ・一貫性重視 → 集中型<br>・可用性重視 → 分散型 |
| **トラフィック規模は？** | ・数千req/s以下 → 集中型可<br>・数万req/s以上 → 分散型推奨 |

### 3. コンテキスト取得（PIP）の選択

| 質問 | 対応 |
|-----|------|
| **必要な属性は？** | ・IdP、HRシステム、MDM、時刻サーバー等を特定 |
| **属性鮮度要求は？** | ・リアルタイム → 毎回取得<br>・キャッシュ可 → TTL設定 |
| **属性取得遅延は？** | ・高遅延 → キャッシュ必須<br>・低遅延 → リアルタイム可 |

### 4. ポリシー管理（PAP）の選択

| 質問 | 対応 |
|-----|------|
| **誰が管理？** | ・開発者 → Git（Policy as Code）<br>・ユーザー → UI（Policy as Data） |
| **変更頻度は？** | ・低頻度 → Git+CI/CD<br>・高頻度 → 専用UI |
| **監査要件は？** | ・厳格 → バージョン管理必須<br>・標準 → ログ記録 |

---

## ポリシーガバナンス

### ライフサイクル管理

**ポリシーは以下のライフサイクルで管理**します：

```
[Authoring] → [Validation] → [Distribution] → [Audit & Rollback]
```

#### 1. Authoring（作成）

| 担当 | 形式 | ツール |
|-----|------|--------|
| セキュリティチーム | Cedar/Rego | IDE、Git |
| アプリチーム | テンプレート | 専用UI |
| エンドユーザー（ReBAC） | 共有ボタン | アプリUI |

#### 2. Validation（検証）

| 検証項目 | 手法 |
|---------|------|
| **スキーマ準拠** | `cedar validate --schema` |
| **静的解析** | `cedar analyze`（SMT） |
| **ユニットテスト** | `cedar test` |
| **衝突検出** | permit vs forbid解析 |

#### 3. Distribution（配布）

| 方式 | 実装例 |
|-----|--------|
| **集中型PDP** | ポリシーストアから即時反映 |
| **分散型PDP** | push型配信 or pull型ポーリング |
| **キャッシュTTL** | 5分〜1時間（要件次第） |

#### 4. Audit & Rollback（監査・ロールバック）

| 機能 | 実装 |
|-----|------|
| **バージョン管理** | Git履歴、Policy DB履歴 |
| **決定ログ** | policy_id + 決定理由を記録 |
| **ロールバック** | 前バージョンに即時復旧 |

---

## マルチテナント認可

### 3層ポリシーモデル

**マルチテナントSaaSでは、3層のポリシーで管理**します：

```
[System Policy] ← プラットフォーム運用チーム
    ↓
[Application Policy] ← SaaS製品チーム
    ↓
[Tenant Policy] ← 各テナント管理者
```

#### レイヤー詳細

| レイヤー | 管理者 | 範囲 | 例 |
|---------|-------|------|---|
| **System** | プラットフォーム運用 | 全体インフラ | バックアップジョブの全テナントメタデータ読み取り許可 |
| **Application** | SaaS製品チーム | SaaSアプリ全体 | 社員のみクロステナントサポート操作可能・管理デバイス必須 |
| **Tenant** | テナント管理者 | テナント内コラボ | 同一ドメインユーザーのみ共有許可 |

### ポリシー評価順序

**外側から内側（System → Application → Tenant）の順で評価**します：

```
1. System forbid → 即Deny
2. Application forbid → 即Deny
3. Tenant forbid → 即Deny
4. いずれかのpermit → Allow
5. すべて不一致 → Deny（implicit deny）
```

**テナントポリシーは、上位層を緩和できない**（deny-by-defaultの保証）。

---

## ポリシーテンプレートによるテナント制御

### テンプレート例

**SaaS提供側が承認済みテンプレートを提供**します：

```cedar
// テンプレート: 外部共有制御
permit(
    principal,
    action == Action::"doc:share",
    resource in Document::*
)
when {
    resource.owner.tenant == context.tenant_id
    && context.target_email_domain in ?allowed_domains
};
```

### インスタンス化

**テナント管理者がパラメータを指定**:

```json
{
    "template_id": "external-sharing",
    "parameters": {
        "allowed_domains": ["example.com", "partner.com"]
    }
}
```

**生成されるポリシー**:

```cedar
permit(
    principal,
    action == Action::"doc:share",
    resource in Document::*
)
when {
    resource.owner.tenant == context.tenant_id
    && context.target_email_domain in ["example.com", "partner.com"]
};
```

### テンプレートの利点

| 観点 | 詳細 |
|-----|------|
| **安全性** | テナントが自由記述不可（検証済みロジックのみ） |
| **一貫性** | 全テナントで同一パターン適用 |
| **柔軟性** | パラメータでカスタマイズ可能 |

---

## アーキテクチャ決定記録（ADR）テンプレート

**重要なアーキテクチャ決定を記録**します：

```markdown
# ADR-001: PEP配置パターンの選定

## Status
Accepted

## Context
マイクロサービスアーキテクチャで、10個以上のサービスに統一ポリシーを適用する必要がある。
レイテンシ要求は10ms以内。既存のAPI Gatewayが存在。

## Decision
API GatewayにPEPを配置する。

## Consequences
- ✅ 一元管理・ログ集約
- ✅ 既存インフラ活用
- ❌ Gateway単一障害点リスク → HAクラスタで対応
- ❌ 細粒度制御不可 → 必要なサービスはEmbedded PEP併用
```

---

## まとめ: アーキテクチャ選定チェックリスト

- [ ] PEP配置決定（Embedded/Gateway/Sidecar）
- [ ] PDP方式決定（集中型/分散型）
- [ ] PIPソース特定（IdP/HRシステム/MDM等）
- [ ] PAP形式決定（Git/専用UI/ReBAC UI）
- [ ] ポリシーライフサイクル定義（Authoring→Validation→Distribution→Audit）
- [ ] マルチテナント対応（3層ポリシーモデル）
- [ ] テンプレート設計（テナントカスタマイズ範囲）
- [ ] ADR作成（重要決定の記録）

詳細なポリシー言語選定は [POLICY-LANGUAGES.md](POLICY-LANGUAGES.md)、Cedarの実装パターンは [CEDAR-POLICIES.md](CEDAR-POLICIES.md) を参照してください。
