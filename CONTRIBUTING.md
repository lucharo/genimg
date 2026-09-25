# Contributing

```bash
uv sync              # the project and its dev tools
uv run pytest        # tests
uv run ruff check .  # lint: pyflakes and import order
```

Give your pull request a [Conventional Commit](https://www.conventionalcommits.org/) title
(`feat:`, `fix:`, `docs:`). Merges are squashed, so the title becomes the changelog line.

The [maintainer docs](docs/maintainers/index.md) cover the code layout, how releases work,
[adding a provider](docs/maintainers/index.md#add-a-provider),
[adding a model](docs/maintainers/models.md) and the
[design decisions](docs/maintainers/decisions.md) to keep.
