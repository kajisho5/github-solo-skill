<p align="center"><strong>github-solo</strong></p>

<h1 align="center">github-solo-skill</h1>

<p align="center"><strong>エージェントに、1人開発向けの GitHub 設定チェックを。</strong></p>

<p align="center">
  診断 · 安全な自動設定 · 無料機能のみ · Python 標準ライブラリのみ<br>
  Claude Code · Cursor · Codex · <code>SKILL.md</code> を読むエージェント
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
github-solo audit: you/your-app (public, default branch: main)

Security
  ⚠️  dependabot-alerts            disabled  -> apply: dependabot-alerts
  ⚠️  dependabot-security-updates  disabled  -> apply: dependabot-security-updates
  ✅ secret-scanning              enabled
  ✅ push-protection              enabled
  ⚠️  private-vuln-reporting       disabled  -> apply: private-vuln-reporting
  ⚠️  codeql                       default setup not configured (c-cpp)  -> apply: codeql
  ⚠️  dependabot-config            missing; detected: github-actions  -> apply: dependabot-config
       bundled code under third_party/ is not tracked by Dependabot (it only reads real manifests outside those dirs)
  ✅ actions-pinning              all actions pinned to a commit SHA
  ⚠️  workflow-permissions         default GITHUB_TOKEN permission is write (opt-in fix; may break workflows that rely on it)  -> apply: workflow-permissions

Solo development
  ✅ solo-blocker                 no approval-required rule on main
  ⚠️  guardrail                    main can be deleted / force-pushed  -> apply: guardrail
  ⚠️  delete-branch-on-merge       merged branches are kept  -> apply: delete-branch-on-merge
  ⚠️  discussions                  disabled (opt-in: --only discussions)  -> apply: discussions

Distribution
  ⚠️  release-workflow             a push to main will likely create a release (.github/workflows/release.yml) - committing files there can trigger it
       .github/workflows/release.yml (gh release create)
  ⚠️  pages                        not set up; would publish / of main (no index.html: the README is rendered as the top page) (opt-in: --only pages)  -> apply: pages
  ⚠️  releases                     2 release(s), all pre-releases: /releases/latest returns 404 (see: solo.py links)
  ⚠️  release-notes-config         .github/release.yml missing  -> apply: release-notes-config

Metadata
  ✅ description                  set
  ✅ topics                       topics: audio
  ✅ license                      MIT
  ✅ security-policy              SECURITY.md
  ✅ social-preview               custom social preview image set

Summary: 9 ok, 13 recommended, 0 action needed, 0 n/a
Next: solo.py apply you/your-app   (dry run; add --yes to execute)
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
`--lang ja`（または `SOLO_LANG=ja`、日本語の `$LANG`）でテキスト出力を日本語にします。`--json` は常に英語です。

| コマンド | 内容 |
|---|---|
| `audit [OWNER/REPO] [--json] [--github-annotations]` | 診断。❌ があれば終了コード 1。`--github-annotations` は CI 用に `::warning` / `::error` も出力 |
| `audit --all-repos OWNER [--json]` | オーナーの全リポ（アーカイブ・fork 除く）を1行ずつ要約 |
| `apply [OWNER/REPO] [--yes] [--only ids] [--skip ids] [--pages-path / \| /docs] [--topics a,b] [--commit-files] [--accept-release-risk] [--json]` | ドライランで計画表示、`--yes` で実行。`--json` は計画と実行ログを出力 |
| `links [OWNER/REPO] [--markdown]` | 最新版の固定ダウンロード URL（`--markdown` で Markdown のリスト形式。使えない場合は理由） |
| `dependabot [OWNER/REPO]` | `dependabot.yml` を生成して標準出力へ（monthly、エコシステムごとに1 PR へ集約） |
| `doctor [OWNER/REPO] [--json]` | python/git/gh の有無、使われるトークン（値は表示しない）、API への到達、リポジトリと各管理系エンドポイントへのアクセスを事前に確認 |
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
| メタ情報 | description、topics（opt-in）、license（自動生成しない）、`SECURITY.md`、social preview（API 不可：設定画面の URL を提示） | デフォルト（topics は opt-in） |

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

# またはエージェントの skills ディレクトリへ clone（Claude Code の例）
git clone https://github.com/kajisho5/github-solo-skill ~/.claude/skills/github-solo
```

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

# 実 API で検証（自分の使い捨てリポジトリの設定を変更し、そのあと元に戻します）:
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
