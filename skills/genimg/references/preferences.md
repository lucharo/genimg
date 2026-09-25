# Recording the user's image preferences

The first time the user states a lasting preference for all their images (a style, a palette, "always sober"), create a `genimg-preferences` skill and record the preference in the user's words. Add later preferences to the same file; when one replaces or retracts an entry, edit or delete that entry so the file never contradicts itself. Create it only once the user has stated a preference; a guess about their taste stays out of it. A preference for one project or brand belongs in that project's own agent instructions.

Put it where the agent loads user-level skills, next to the installed `genimg` skill, even when genimg is installed in a project, so the preferences follow the user:

- Claude Code: `~/.claude/skills/genimg-preferences/SKILL.md`
- Agents that read `~/.agents/skills/`: `~/.agents/skills/genimg-preferences/SKILL.md`

Start the file with:

```markdown
---
name: genimg-preferences
description: "The user's lasting preferences for generated images. Load with genimg before every generation or edit."
---
```

The skill belongs to the user. genimg never ships it, so updating genimg never overwrites it.
