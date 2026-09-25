# genimg-visual-review

After the agent builds or fixes something, you get one HTML page that shows it works.

> Show me what changed in this PR.

The page fits one screen:

| Part | Shows |
| --- | --- |
| Headline | what changed and whether it is done, mixed or blocked |
| Infographic | optional, drawn by [genimg-infographic](genimg-infographic.md) |
| Table | each change, before → after, with its evidence |
| Unverified | what nobody has checked yet |
| Action | at most one thing for you to do, or "none" |

Evidence is real: screenshots of the running thing, diffs, command output. Each claim is
labelled observed, tested or unverified.

[Read the skill](https://github.com/lucharo/genimg/blob/main/skills/genimg-visual-review/SKILL.md).
