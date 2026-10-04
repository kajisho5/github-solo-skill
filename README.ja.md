<p align="center"><strong>github-solo</strong></p>

<h1 align="center">github-solo-skill</h1>

<p align="center"><strong>エージェントに、1人開発向けの GitHub 設定チェックを。</strong></p>

<p align="center">
  診断 · 安全な自動設定 · 無料機能のみ · Python 標準ライブラリのみ<br>
  Claude Code · Codex · Cursor · Copilot · <code>SKILL.md</code> / <code>AGENTS.md</code> を読む、または MCP に対応するエージェント
</p>

<p align="center">
  <a href="https://github.com/kajisho5/github-solo-skill/actions/workflows/test.yml"><img src="https://github.com/kajisho5/github-solo-skill/actions/workflows/test.yml/badge.svg" alt="tests"></a>
  <a href="https://github.com/kajisho5/github-solo-skill/stargazers"><img src="https://img.shields.io/github/stars/kajisho5/github-solo-skill" alt="GitHub stars"></a>
  <a href="https://github.com/kajisho5/github-solo-skill/commits/main"><img src="https://img.shields.io/github/last-commit/kajisho5/github-solo-skill" alt="last commit"></a>
  <img src="https://img.shields.io/badge/python-3.9%20%7C%203.13-blue" alt="Python 3.9 and 3.13 tested">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"></a>
  <a href="https://github.com/sponsors/kajisho5"><img src="https://img.shields.io/badge/sponsor-%E2%9D%A4-ea4aaa?logo=githubsponsors" alt="Sponsor"></a>
</p>

```bash
npx skills add kajisho5/github-solo-skill
```

[English](README.md) · 日本語

エージェントに「リポジトリの設定を確認して」と頼む（またはスクリプトを直接実行する）と、現状を診断し、足りないものだけを設定します。

```text
github-solo 診断: you/your-app (公開, デフォルトブランチ: main)

セキュリティ
  ⚠️  dependabot-alerts            無効  -> apply: dependabot-alerts
  ⚠️  dependabot-security-updates  無効  -> apply: dependabot-security-updates
  ✅ secret-scanning              有効
  ✅ push-protection              有効
  ⚠️  private-vuln-reporting       無効  -> apply: private-vuln-reporting
  ⚠️  codeql                       default setup 未設定 (c-cpp)  -> apply: codeql
  ⚠️  dependabot-config            未作成。検出: github-actions  -> apply: dependabot-config
       同梱コード third_party/ は Dependabot の追跡対象外 （それ以外の場所の実マニフェストのみ対象）
  ✅ actions-pinning              すべての action がコミット SHA で固定済み
  ⚠️  workflow-permissions         GITHUB_TOKEN のデフォルト権限が write （任意の修正。write に依存するワークフローが壊れる可能性）  -> apply: workflow-permissions

1人開発
  ✅ solo-blocker                 承認必須ルールなし: main
  ⚠️  guardrail                    main は削除 / force push できます  -> apply: guardrail
  ⚠️  tag-guard                    リリースタグ (v*) を削除 / 移動できます （任意: --only tag-guard）  -> apply: tag-guard
  ⚠️  delete-branch-on-merge       マージ済みブランチが残る  -> apply: delete-branch-on-merge
  ⚠️  discussions                  無効（任意: --only discussions）  -> apply: discussions

配布
  ⚠️  release-workflow             push: main リリースを作る可能性が高い (.github/workflows/release.yml) - ここへファイルをコミットすると発火しうる
       .github/workflows/release.yml (gh release create)
  ⚠️  pages                        未設定。公開予定: / of main (index.html なし: README がトップページとして表示されます) （任意: --only pages）  -> apply: pages
  ⚠️  releases                     2 件のリリース, すべて Pre-release: /releases/latest は 404 になります （solo.py links 参照）
  ⚠️  release-notes-config         .github/release.yml がありません  -> apply: release-notes-config

メタ情報
  ✅ description                  set
  ✅ topics                       topics: audio
  ✅ license                      MIT
  ✅ security-policy              SECURITY.md
  ✅ social-preview               social preview 設定済み
  ⚠️  labels                       missing labels: breaking-change (opt-in: --only labels)  -> apply: labels
  ⚠️  community-files              missing: .github/pull_request_template.md, .github/ISSUE_TEMPLATE/bug_report.md, .github/ISSUE_TEMPLATE/feature_request.md, CONTRIBUTING.md (opt-in: --only community-files)  -> apply: community-files

サマリー: 9 OK, 16 推奨, 0 要対応, 0 対象外   スコア: 68/100
次の手順: solo.py apply you/your-app   （ドライラン。実行するには --yes）
```

*（公開 C++ アプリを想定したテスト用 fixture に対する `solo.py audit` の実際の出力。`apply` はまず計画を表示し、`--yes` を付けたときだけ書き込みます。）*

## チーム向け skill との違い（自分の PR がマージできなくならない）

チーム向けに作られた GitHub 設定 skill（例：`netresearch/github-project-skill`）は、**承認必須**のブランチ保護
（さらに CODEOWNERS レビュー必須、`enforce_admins` など）を入れます。メンテナが自分1人だと承認できる人がいないため、
**自分の PR をマージできなくなります**。

`github-solo` は逆の原則で作っています。

| | チーム向け skill | github-solo |
|---|---|---|
| 承認必須 / CODEOWNERS レビュー必須 / `enforce_admins` | 追加する | **絶対に追加しない**。コミッターが自分だけのリポに既にあれば ❌ として検出し、外すコマンドを提示（自動では変更しない） |
| デフォルトブランチの保護 | PR 必須 | ruleset `solo-guard`：削除と force push のみ禁止。直接 push も自分でのマージも今まで通り |
| 有料機能 | 前提にする | 無料機能のみ。private リポの有料項目（Secret Protection / Code Security）は ➖ で理由を表示してスキップ |
| `apply` がデフォルトで変えるもの | 全部 | 外から見えず、すぐ戻せる項目だけ。公開面（Pages・Discussions・homepage・topics）とワークフローへの影響（Actions のデフォルト権限）は `--only` の明示指定が必要 |
| 既存のファイル・設定 | 上書きされうる | 削除も上書きもしない |

## 特長

- **まず診断。** 1コマンドで全項目を ✅ OK / ⚠️ 推奨 / ❌ 要対応 / ➖ 対象外 で表示。理由と対応する `apply` id 付き。❌ があれば終了コード 1（CI で使える）。
- **デフォルトはドライラン、冪等。** `apply` は実行する API 呼び出しをそのまま表示。`--yes` で実行。2回目は何も書き込みません。
- **配布まわりも対応。** `links` は固定 URL `/releases/latest/download/<asset>` を出力。使えない場合（Pre-release のみ、アセット名にバージョン入り）は理由と対処を表示。
- **元に戻せる。** `apply --yes` のたびに変更内容を保存し（`~/.local/state/github-solo/`、Windows は `%LOCALAPPDATA%\github-solo`、`SOLO_STATE_DIR` で変更可）、`restore` がその分だけ戻します。生成したファイルは自分で削除してください。
- **依存ゼロ。** `scripts/solo.py` は Python 3.9+ 標準ライブラリだけの単一ファイル。GitHub の REST/GraphQL API を直接呼びます。
- **ネットワーク不要のテスト。** 実スクリプトをモック GitHub API サーバーに向けて実行（`python -m unittest`）。

## クイックスタート

```bash
# 1. skill をインストール（他の方法は「インストール」参照）
npx skills add kajisho5/github-solo-skill

# 2. 診断（トークン：GH_TOKEN、GITHUB_TOKEN、または `gh auth login`）
python3 scripts/solo.py audit OWNER/REPO          # --json で機械可読。❌ があれば終了コード 1

# 3. 変更内容を確認してから実行
python3 scripts/solo.py apply OWNER/REPO          # ドライラン
python3 scripts/solo.py apply OWNER/REPO --yes    # デフォルト項目のみ

# 4. 公開面に関わる項目は1つずつ明示指定
python3 scripts/solo.py apply OWNER/REPO --yes --only pages --pages-path /docs
python3 scripts/solo.py apply OWNER/REPO --yes --only topics --topics audio,streaming
```

clone の中では `OWNER/REPO` を省略でき、`git remote origin` から推定します。
`--profile app|library|site|docs` でリポの種類に合わせて、当てはまらないチェックを非表示にします（サイトにリリースノートは不要、ライブラリはアセット名を気にしない、など）。audit は毎回 0〜100 点のスコアを表示します（✅=1、⚠️=½、❌=0、➖は除外）。ドライランの計画は各変更を `変更前 -> 変更後` で表示します。GitHub Enterprise Server は `SOLO_API_BASE=https://HOST/api/v3` を指定します（GraphQL は `/api/graphql` へ向けます）。
`--lang ja`（または `SOLO_LANG=ja`、日本語の `$LANG`）でテキスト出力を日本語にします。`--json` は常に英語です。

| コマンド | 内容 |
|---|---|
| `audit [OWNER/REPO] [--json] [--quiet] [--ignore ids] [--fail-on warn] [--github-annotations]` | 診断。❌ があれば終了コード 1（`--fail-on warn` で ⚠️ でも 1）。`--quiet` は ✅/➖ を非表示、`--ignore` は指定チェックを除外、`--github-annotations` は CI 用に `::warning` / `::error` も出力 |
| `audit --all-repos OWNER [--json]` | オーナーの全リポ（アーカイブ・fork 除く）を1行ずつ要約 |
| `apply [OWNER/REPO] [--yes] [--only ids] [--skip ids] [--pages-path / \| /docs] [--topics a,b] [--commit-files] [--accept-release-risk] [--json]` | ドライランで計画表示、`--yes` で実行。`--json` は計画と実行ログを出力 |
| `links [OWNER/REPO] [--markdown]` | 最新版の固定ダウンロード URL（`--markdown` で Markdown のリスト形式。使えない場合は理由） |
| `links --workflow` | リリースワークフローの雛形を出力（タグで発火、バージョン無しアセットも同時アップロード）。API 呼び出しなし |
| `badges [OWNER/REPO]` | README 用バッジの Markdown（ワークフローごと、license、最新リリース、last commit、stars） |
| `ci-template` | 週1回の audit を行う GitHub Actions ワークフローの雛形を出力（Administration: read のトークンを secret に登録）。API 呼び出しなし |
| `explain CHECK_ID` | チェック1件の説明（理由・API・戻し方）を表示。オフラインで動作 |
| `dependabot [OWNER/REPO]` | `dependabot.yml` を生成して標準出力へ（monthly、エコシステムごとに1 PR へ集約） |
| `doctor [OWNER/REPO] [--json]` | 実行場所（クラウドコンテナ / 手元の Claude Code / 通常のシェル）の判定、python/git/gh の有無、使われるトークン（値は表示しない）、API への到達、リポジトリと各管理系エンドポイントへのアクセスを事前に確認 |
| `restore [OWNER/REPO] [--yes] [--snapshot FILE]` | 直前の `apply --yes` が変更した内容を元に戻す（`--yes` なしはドライラン） |

エージェントにはこう頼めます。

> 「自分のリポの GitHub 設定を確認して、足りないものを設定して」
> 「自分のPRがマージできない。ブランチ保護を見て」
> 「最新版の固定ダウンロードリンクを出して」

## チェック項目

各項目の API と戻し方：[references/checks.md](references/checks.md)

| カテゴリ | チェック | `apply` |
|---|---|---|
| セキュリティ | Dependabot alerts / security updates、secret scanning、push protection、private vulnerability reporting、CodeQL default setup（public のみ）、`dependabot.yml`（エコシステム自動検出、同梱 `third_party/`・`vendor/` は対象外）、Actions の SHA 固定（報告のみ）、`GITHUB_TOKEN` のデフォルト権限（既存の `dependabot.yml` はディレクトリ単位でも確認） | デフォルト（トークン権限は opt-in） |
| 1人開発 | **solo-blocker**（❌ 検出のみ）、`solo-guard` ruleset、`v*` タグ用 `solo-tag-guard` ruleset、マージ後のブランチ自動削除、Discussions | デフォルト（タグ保護・Discussions は opt-in） |
| 配布 | GitHub Pages（opt-in）、リリース / latest / アセット名（報告）、push でリリースが走るワークフローの警告（報告）、`.github/release.yml` | デフォルト（Pages は opt-in） |
| メタ情報 | description、topics（opt-in）、license（自動生成しない）、`SECURITY.md`、`release.yml` が使うラベル（opt-in）、Issue / PR テンプレートと `CONTRIBUTING.md`（opt-in）、social preview（API 不可：設定画面の URL を提示） | デフォルト（topics・ラベル・コミュニティファイルは opt-in） |

### 生成ファイルと「push でリリースが走る」警告

`dependabot.yml` / `release.yml` / `SECURITY.md` は、存在しない場合だけ生成します。

- **clone の中：** ローカルに書き出すだけ。内容を確認してコミットしてください。
- **clone でない場合：** `--commit-files` を付けたときだけ Contents API でデフォルトブランチへ直接コミット。
- デフォルトブランチへの push で動き、かつリリースを作りそうなワークフロー（`gh release create`、`softprops/action-gh-release`、`release-please`、`contents: write` など）を検出すると、書き込み前に警告します。`--commit-files` は `--accept-release-risk` を付けない限り拒否されます。検出はテキストベースの簡易判定です（[references/checks.md](references/checks.md#release-workflow-report-only)）。

## トークンの権限

トークンは `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth token` の順で取得します。

- **classic PAT：** `repo`（public リポのみなら code scanning のエンドポイントは `public_repo` で足ります。他の管理系エンドポイントは `repo` として記載されています）。
- **fine-grained PAT**（Repository permissions、[GitHub ドキュメント](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)より）：

| 権限 | レベル | 用途 |
|---|---|---|
| Metadata | Read | リポ情報、コラボレーター一覧 |
| Administration | Read and write | Dependabot、private vulnerability reporting、code scanning default setup、rulesets、ブランチ保護（読み取り）、Actions の workflow 権限、リポ設定（`PATCH`：secret scanning・Discussions・ブランチ自動削除・topics・homepage） |
| Contents | Read（audit）/ Read and write（`--commit-files`） | git tree、ファイル取得、生成ファイルのコミット |
| Pages | Read and write | `--only pages` |

多くの設定にはリポの admin 権限が必要です。403/404 やプランの制限：[references/troubleshooting.md](references/troubleshooting.md)

## インストール

```bash
# Skills CLI（Claude Code、Cursor、Codex など）
npx skills add kajisho5/github-solo-skill

# またはエージェントの skills ディレクトリへ clone
git clone https://github.com/kajisho5/github-solo-skill ~/.claude/skills/github-solo   # Claude Code
git clone https://github.com/kajisho5/github-solo-skill ~/.cursor/skills/github-solo   # Cursor
git clone https://github.com/kajisho5/github-solo-skill ~/.agents/skills/github-solo   # Codex（Cursor もここを読みます）
```

### 他の AI エージェント（Codex、Cursor、Copilot、Gemini CLI など）

| エージェント | 方法 |
|---|---|
| **Codex** | skill：`~/.agents/skills/github-solo`（ユーザー）または `<repo>/.agents/skills/github-solo`（リポジトリ）へ clone（[Codex skills ドキュメント](https://learn.chatgpt.com/docs/build-skills)）。MCP：`codex mcp add github-solo -- python3 /path/to/github-solo/scripts/solo_mcp.py`、または `~/.codex/config.toml` に `[mcp_servers.github-solo]`（`command`・`args`）（[ドキュメント](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)）。`AGENTS.md` も読みます。**Codex デスクトップアプリ（Windows）：** *Settings → MCP servers → Add server → STDIO*、command に `python`、引数に `scripts\solo_mcp.py` のフルパス（ドキュメントでは CLI と `config.toml` を共有。Windows のパスは明記されておらず、アプリでは未検証）。 |
| **Claude Code** | skill（上記）、plugin（下記）、または MCP：`claude mcp add github-solo -- python3 /path/to/github-solo/scripts/solo_mcp.py` |
| **Cursor** | skills ディレクトリ `~/.cursor/skills/github-solo`（姉妹プロジェクト [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) の記載に従ったパス。`~/.agents/skills` も読みます）。Cursor 自身のドキュメントでは未確認です。 |
| **GitHub Copilot** | このリポジトリの `AGENTS.md` と `.github/copilot-instructions.md` を読みます（[ドキュメント](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)）。 |
| **その他のエージェント** | MCP stdio サーバー `python3 scripts/solo_mcp.py`（ツール：`solo_doctor`、`solo_audit`、`solo_apply_plan`、`solo_apply`、`solo_restore`、`solo_links`、`solo_dependabot`、`solo_badges`、`solo_explain`）、または `python3 scripts/solo.py ...` を直接実行。エージェントには `AGENTS.md` を読ませてください。 |

MCP サーバーは [MCP stdio トランスポート](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)（改行区切りの JSON-RPC、プロトコル 2025-06-18 / 2025-03-26 / 2024-11-05）に従います。検証は自作のクライアントと Claude Code 自身のクライアント（`claude mcp list` で接続成功）で行いました。Codex と Cursor では試していません。`solo_apply` と `solo_restore` は `confirm` が `true` でない限り何も変更しません。

Claude Code plugin として（このリポジトリが marketplace を兼ねます）：

```bash
claude plugin marketplace add kajisho5/github-solo-skill
claude plugin install github-solo@github-solo-skill
```

エージェント無しでも `python3 scripts/solo.py --help` で使えます。clone は `git pull` で更新します。他のインストーラーが作ったコピーは自動更新されません。

## 動作要件

- Python 3.9+（標準ライブラリのみ）、`git`（`OWNER/REPO` の推定と clone 判定のみ）、`gh`（トークン取得元としてのみ・任意）
- 上記の権限を持つ GitHub トークン

## 開発

```bash
python -m unittest           # 全テスト。ネットワーク不要（モック GitHub API サーバーを内部で起動）
python -m unittest tests.test_solo.VoiceboothScenario -v

# 実 API で検証（自分の使い捨てリポジトリの設定を変更し、そのあと元に戻します）。
# 2026-10-04 の実行：11項目が RESULT: PASS（カバー範囲は ROADMAP.md）:
python3 tests/live_check.py YOU/scratch-repo --confirm YOU/scratch-repo
```

テストシナリオ（`tests/test_solo.py`、fixture は `tests/fixtures.py`、サーバーは `tests/mock_github.py`）：push でリリースが走る公開 C++ アプリ（voicebooth 型）、承認必須で詰んだ1人開発リポ、private（無料プラン）リポ、設定済みリポ（書き込みゼロ）。各シナリオで audit の判定、ドライランの計画、モックが受けた書き込みリクエスト（メソッド・パス・ボディ）を検証します。CI は Python 3.9 と 3.13 で実行（`.github/workflows/test.yml`、actions は SHA 固定、`permissions: contents: read`）。

**リリース**は [release-please](https://github.com/googleapis/release-please) で自動化しています。Conventional Commits（`feat:`、`fix:`、`docs:` など）を `main` にマージすると、release-please がリリース PR（`plugin.json`・`scripts/solo.py` のバージョンと changelog）を更新し、その PR をマージするとタグと GitHub Release が作られます。**メジャーバージョンは自動では上げません**：0.x のまま運用し（`bump-minor-pre-major`）、破壊的変更（`feat!:`）でもマイナーが上がります。1.0.0 は意図的なリリースです（コミットフッターに `Release-As: 1.0.0`）。リリース PR を作るには、*Settings → Actions → General → "Allow GitHub Actions to create and approve pull requests"* を有効にしておく必要があります。

## ドキュメント

| | |
|---|---|
| [SKILL.md](SKILL.md) | エージェントが読む手順とルール |
| [references/checks.md](references/checks.md) | 各チェックの理由・API・戻し方 |
| [references/release-latest.md](references/release-latest.md) | 最新版の固定リンク、Pre-release、バージョン無しアセット名、ワークフロー例 |
| [references/troubleshooting.md](references/troubleshooting.md) | 403 エラー、スコープ不足、private リポの有料機能 |
| [ROADMAP.md](ROADMAP.md) | 今後の予定と、意図的にやらないこと |
| [SECURITY.md](SECURITY.md) | 脆弱性の報告方法 |

## サポート

役に立ったら [GitHub Sponsors](https://github.com/sponsors/kajisho5) で支援できます。Issue・PR も歓迎です。

## ライセンス

[MIT](LICENSE)
