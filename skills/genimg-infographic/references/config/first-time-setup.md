---
name: first-time-setup
description: First-time preference setup for genimg-infographic
---

# First-time setup

Complete this setup before analysing source content. Saved preferences change recommendations only; every generation still follows the confirmation gate in `SKILL.md`.

Ask with the runtime's structured user-input tool. Batch as many questions as the tool supports.

## Questions

1. **Preferred layout**
   - Auto-select (recommended)
   - `bento-grid`
   - `linear-progression`
   - `dense-modules`
2. **Preferred style**
   - Auto-select (recommended)
   - `craft-handmade`
   - `technical-schematic`
   - `morandi-journal`
3. **Preferred aspect**
   - Auto-select (recommended)
   - `landscape`
   - `portrait`
   - `square`
4. **Output language**
   - Auto-detect (recommended)
   - `en`
   - `zh`
5. **Save location**
   - Project: `.genimg/infographic/EXTEND.md`
   - User: `${XDG_CONFIG_HOME:-$HOME/.config}/genimg/infographic/EXTEND.md`

The runtime may add a free-text option. Read it as authoritative when it conflicts with a clicked choice.

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

Create the selected parent directory and save the file. Confirm its path, then continue with source analysis.
