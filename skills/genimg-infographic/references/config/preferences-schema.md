---
name: preferences-schema
description: EXTEND.md schema for genimg-infographic preferences
---

# Preferences schema

```yaml
---
version: 1
preferred_layout: null
preferred_style: null
preferred_aspect: null
language: null
preferred_model: auto
preferred_resolution: 2K
custom_styles:
  - name: my-brand
    description: "Short description shown in recommendations"
    prompt_fragment: "Traits appended to the generated prompt"
---
```

| Field | Default | Meaning |
| --- | --- | --- |
| `preferred_layout` | `null` | One of the 21 layouts, or automatic selection |
| `preferred_style` | `null` | One of the 22 styles, or automatic selection |
| `preferred_aspect` | `null` | `landscape`, `portrait`, `square`, a supported ratio, or automatic selection |
| `language` | `null` | Output language, or source-language detection |
| `preferred_model` | `auto` | A GenIMG alias such as `gdm:nb2`, `gdm:nbp`, or `oai:gi2` |
| `preferred_resolution` | `2K` | `1K`, `2K`, or `4K` when supported by the selected model |
| `custom_styles` | `[]` | Extra named styles whose configured `prompt_fragment` is used directly instead of loading `references/styles/<name>.md` |

Preferences guide automatic selection. If a preferred model is not currently working, fall back to live model selection and state the substitution before generation without pausing for approval.
