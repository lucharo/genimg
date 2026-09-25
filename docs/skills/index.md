# Skills

```bash
# all of them (needs Node.js)
npx skills add lucharo/genimg
# only the ones you name
npx skills add lucharo/genimg --skill genimg genimg-visual-exploration
```

| Skill | Gives your agent |
| --- | --- |
| [`genimg`](https://github.com/lucharo/genimg/blob/main/skills/genimg/SKILL.md) (main) | Every flag, model choice, recipes, and how to get real variations. |
| [`genimg-infographic`](genimg-infographic.md) | Source material in, one structured infographic out. |
| [`genimg-visual-exploration`](genimg-visual-exploration.md) | Distinct directions in one grid, a Tournament to pick, then refine. |
| [`genimg-visual-review`](genimg-visual-review.md) | A one-page HTML review of what changed, with real evidence. |
| [`image-to-app`](image-to-app.md) | A visual interview from app idea to working app. |

## Your preferences

- Say a lasting preference once ("always sober", a house palette) and every later image follows it.

The agent saves it in a `genimg-preferences` skill in your own skills folder and reads it before
every image. genimg never ships or overwrites it.
