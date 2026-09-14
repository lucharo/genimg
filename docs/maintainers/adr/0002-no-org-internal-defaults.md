# No organization-internal defaults

**Status:** accepted

genimg ships no organization-specific defaults. The Vertex GCP project is resolved from the user's own environment — `--project` → `config.gcp_project` → `GOOGLE_CLOUD_PROJECT` → the `project_id` embedded in the service-account JSON (or gcloud's active project for ADC) — and errors clearly if none resolves, rather than falling back to a hardcoded project.

Consequences:
- Project selection has no hardcoded organization-specific fallback.
- Compatibility credential aliases are implementation details, not part of the public setup contract.

Why: a hardcoded project or credential is wrong for every user but its author, and silently routes requests to the wrong place (a confusing `403`/`404`) instead of telling the user what to set.
