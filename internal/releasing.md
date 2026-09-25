# Releasing runbook

release-please and PyPI trusted publishing, driven by `.github/workflows/release.yml`. The public
summary is in `docs/maintainers/index.md`.

## How a release happens

- Every push to `main` runs release-please. It keeps one Release PR open (label
  `autorelease: pending`) that bumps `version` in `pyproject.toml` and writes `CHANGELOG.md`.
- release-please force-pushes that branch whenever `main` moves. Hand-edit the changelog on the PR
  only just before merging. Anything committed to `CHANGELOG.md` on `main` is safe, because
  release-please only prepends.
- GitHub does not run `pull_request` workflows for a PR opened with `GITHUB_TOKEN`, so `release.yml`
  dispatches `ci.yml` on the Release PR's exact head.
- Merging the Release PR tags `vX.Y.Z`, creates the GitHub release, runs `uv build` on the tag and
  `uv publish --trusted-publishing always`, all in one run.
- The version lives only in `pyproject.toml`. `genimg --version` reads installed metadata.

## One-off setup

- PyPI pending publisher at `pypi.org/manage/account/publishing/`: project `genimg`, owner
  `lucharo`, repository `genimg`, workflow `release.yml`, environment `pypi`. The first publish
  creates the project.
- A `pypi` environment on the GitHub repository.
- GitHub Pages with "GitHub Actions" as the source. On a free plan the repository must be public.
  Until then `docs.yml` still builds with `--strict` on pull requests and skips only `deploy`.

## First release

- 0.1.0 shipped on 25 September 2026 by merging the first Release PR by hand.
- The Friday 09:00 UTC auto-merge (`schedule` in `release.yml`) is still commented out. Decide
  before restoring it: any `docs:` or `fix:` merge opens a patch Release PR (0.1.1 opened from a
  docs-only change), and the schedule would ship it.

## Before merging a Release PR

1. CI is green on the Release PR's exact head, on Python 3.11 to 3.14.
2. `uv build`, then install the wheel in a fresh environment outside the checkout and run
   `genimg --version`, `genimg auth --modes`, `genimg skills path all` and one `--dry-run`.
3. The changelog reads as release notes. Add a short summary at the top of the version block if
   the commit list does not tell the story.
4. Docs build strictly: `uv run --frozen --only-group docs zensical build --clean --strict`.
5. Scope and status match the [release checklist](https://github.com/lucharo/genimg/issues/2).

## After the release

- The run that published it is green, and the tag and GitHub release exist. A green workflow alone
  is not publication.
- PyPI shows the version, and `uv tool install genimg==X.Y.Z` works in a clean environment.
