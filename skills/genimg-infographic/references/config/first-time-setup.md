---
name: first-time-setup
description: Automatic defaults and optional preference persistence for genimg-infographic
---

# Automatic defaults

Do not run a first-time questionnaire. When no `EXTEND.md` exists, use the template below in memory and continue with automatic selection. Do not create a preferences file unless the user explicitly asks to persist preferences.

The automatic defaults are:

- Layout: infer from content structure.
- Style: infer from tone and audience.
- Aspect: infer from layout and target surface.
- Language: use the user's language when it differs from the source; otherwise preserve the source language.
- Model: `auto`, resolved through live availability.
- Resolution: `2K` unless the selected model or requested output requires another supported value.

## Template

```yaml
---
version: 1
preferred_layout: null
preferred_style: null
preferred_aspect: null
language: null
preferred_model: auto
preferred_resolution: 2K
custom_styles: []
---
```

If the user asks to save preferences, write only their explicit choices into the first supported `EXTEND.md` location and leave all unspecified fields at the automatic defaults. Report the saved path, then continue without another generation-choice gate.
