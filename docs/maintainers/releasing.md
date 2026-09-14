# Releasing

Releases are automated with [release-please](https://github.com/googleapis/release-please)
and PyPI Trusted Publishing (OIDC, no tokens). The workflow is `.github/workflows/release.yml`.

## Day to day

- Use Conventional Commit messages (`feat:`, `fix:`, `docs:`, `refactor:`, …). CI checks PR
  titles because merges are squashed, so the title becomes the changelog entry.
- release-please keeps a **Release PR** open that bumps the version in `pyproject.toml` and
  writes `CHANGELOG.md` from the commits since the last tag. It force-pushes that branch
  whenever `main` moves, so hand-edit the changelog on the PR only just before merging.
- Merging the Release PR tags `vX.Y.Z`, creates the GitHub release, builds with `uv build`
  and publishes with `uv publish --trusted-publishing always` in the same run.
- The version lives only in `pyproject.toml`; `genimg --version` reads installed metadata.

## One-off setup

- PyPI: a pending publisher on `pypi.org/manage/account/publishing/` with project `genimg`,
  owner `lucharo`, repository `genimg`, workflow `release.yml`, environment `pypi`. The first
  publish creates the project.
- GitHub: a `pypi` environment on the repository.
- Pages: enable it with "GitHub Actions" as the source. On a free plan this needs the repository
  to be public. Until then the Docs workflow still builds the site with `--strict` on every pull
  request; only its `deploy` job is skipped, and it starts publishing on the first push after the
  repository goes public.

## Before merging a Release PR

1. `main` is green on 3.11, 3.12 and 3.13.
2. `uv build` and a clean install of the wheel outside the checkout work: `genimg --version`,
   `genimg auth --modes`, `genimg skills path all`, one `--dry-run`.
3. The changelog reads as release notes; add a hand-written summary at the top of the
   version block if the commit list does not tell the story.
4. Docs build strictly: `uv run --only-group docs zensical build --strict`.

## After the release

- Check the PyPI page and `uv tool install genimg==X.Y.Z` in a fresh environment.
- The Friday 09:00 UTC auto-merge cron in `release.yml` is paused until the first release
  has been merged by hand; re-enable it by restoring the `schedule` trigger.
