# A fixed "latest release" download URL

Goal: a link you can put in a README, a blog post or a manual that always downloads the newest build:

```
https://github.com/OWNER/REPO/releases/latest/download/ASSET_NAME
```

It works only if both are true:

1. **There is a "latest" release.** GitHub's latest is the most recent release that is neither a
   pre-release nor a draft (`GET /repos/{o}/{r}/releases/latest` answers 404 otherwise).
2. **ASSET_NAME is identical in every release.** `app-1.2.0-win64.zip` changes name each release, so the
   link breaks on the next one. `app-win64.zip` does not.

`python3 scripts/solo.py links OWNER/REPO` tells you which of these fails and prints the working URLs.

## 1. Only pre-releases

If every release is marked "Pre-release" there is no latest and the URL answers 404.

Promote the newest build:

```bash
gh release edit v1.2.0 --prerelease=false --latest -R OWNER/REPO
```

If your workflow creates releases, stop it from marking them as pre-releases:

- `gh release create "$TAG" ... ` → drop `--prerelease`.
- `softprops/action-gh-release` → `prerelease: false` (and `make_latest: true`).

Keep using pre-releases for betas if you like: they are simply invisible to `/latest`.

## 2. Version in the asset name

Keep the versioned file (people like it) and upload an additional version-less copy of the same file.

```bash
VER=1.2.0
cp "dist/app-$VER-win64.zip" dist/app-win64.zip
gh release upload "v$VER" dist/app-win64.zip --clobber -R OWNER/REPO
```

Now `.../releases/latest/download/app-win64.zip` always resolves to the newest stable release. The upload
duplicates the bytes; that is the price of a stable name (GitHub has no redirect/alias feature for assets).

## Workflow example

Publishes versioned + version-less assets on a tag, as a normal (non-pre) release. Pin the action SHAs to
the versions you use (`actions-pinning` check).

```yaml
name: release
on:
  push:
    tags: ["v*"]          # tag-only trigger: pushing to main does not release
permissions:
  contents: write         # needed to create the release
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-sha>   # vX.Y.Z
      - name: Build
        run: ./build.sh                     # produces dist/app-${GITHUB_REF_NAME#v}-win64.zip
      - name: Add version-less copies
        run: |
          VER="${GITHUB_REF_NAME#v}"
          cp "dist/app-$VER-win64.zip" dist/app-win64.zip
      - name: Publish
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release create "$GITHUB_REF_NAME" dist/*.zip --title "$GITHUB_REF_NAME" --generate-notes
```

Triggering on tags rather than on pushes to `main` also keeps `github-solo`'s `release-workflow` warning quiet:
committing `dependabot.yml` / `SECURITY.md` to `main` then cannot create a release.

## When the URL still 404s

- The release is a draft (drafts are invisible to `/latest`).
- The newest release is a pre-release and an older stable one exists: `/latest` points at the older stable one.
  Its assets may have different names.
- The repo is private: `/releases/latest/download/...` needs authentication, so it is not a public link.
- The asset name has spaces or special characters: URL-encode it (`solo.py links` does this).
- GitHub's "latest" is chosen by creation date, not by version number. Publishing an old version later makes it "latest";
  `gh release edit TAG --latest` repairs that.
