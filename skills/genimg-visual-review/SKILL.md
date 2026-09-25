---
name: genimg-visual-review
description: "Hand back finished work as a one-page HTML review: before → after, real evidence (screenshots, diffs, terminal output), what stays unverified, and at most one action, optionally led by a genimg infographic. Use after building or changing something when the user asks to see it working, recap what shipped, walk through a PR, or get a visual diagnosis before fixes. Quick screenshot checks mid-task stay in chat."
---

# Visual review

A review lets a reader who arrives cold answer three questions in under a minute:

1. **What changed?** Before → after, in plain words.
2. **How do we know?** Real evidence beside each claim.
3. **Where does it stand?** Done, unverified, or one thing for the reader to do.

## 1. Frame

Write the headline: one sentence on what changed and why it matters. For a diagnosis before
fixes, frame each finding as observed behaviour → consequence → proposed fix, and label every
fix as not yet applied.

## 2. Capture evidence

Real artefacts only; a mockup or redrawn stand-in proves nothing.

- **UI**: screenshots of the running thing. Reload or clear state first, so the capture proves
  the cold load and not just the state your last action left. Look at each capture as you take
  it: a blank or mid-transition frame also reports success.
- **Code, CLI, config, docs**: the diff excerpt, the command with its real output, the test
  summary line.
- **Numbers**: one source per number, and every repeat of it on the page agrees.

Label each claim by what backs it: **observed** in the real thing, **tested** by a check that
ran and passed, or **unverified**. A fixture screenshot does not prove live data, and a passing
unit test does not prove the UI. The headline carries the weakest label it depends on.

Done when every item you plan to show has evidence or is labelled unverified.

## 3. Distil

Keep zero to six items. For each: before → after in plain words, its evidence, its label. Add a
trade-off only when a real cost changes how the reader should judge the change. Cut any section
that restates the headline or the infographic.

## 4. Infographic (optional)

When a picture would orient the reader faster than the table (several changes, a mechanism, a
before and after architecture), load the `genimg-infographic` skill and render one from the
distilled items. Give it the real names, versions and PR or issue numbers so the image labels
itself. Inspect it at full resolution before embedding it, and regenerate on any wrong label or
arrow. It orients; the evidence from step 2 still proves. For exact topology or precise labels,
inline SVG is often clearer.

## 5. Build one page

One self-contained HTML file that fits one screen (about 1280×720) by default:

- the headline and a status (done, mixed or blocked) with a text label beside its colour:
  green for done, amber for a pending action, red for a real problem;
- the infographic, if made;
- one table: item, before → after, evidence, label;
- an **Unverified** line, which says "nothing" when nothing is;
- one action band when the reader must do something, with a link and a time estimate;
  otherwise one line saying no action is needed.

Put full logs, extra screenshots and long diffs under `<details>`. Embed images as base64 data
URIs and terminal output as `<pre>`, so the file opens anywhere, offline. Follow the reader's
light or dark setting with `prefers-color-scheme`. End on what is done; a list of things you
could also do reads as homework.

Grow past one page only when the reader will walk someone else through several separable
artefacts. Then keep this page as the summary and link a longer companion from it.

## 6. Check and hand off

- Open the file from a fresh load at 1280×720:
  `document.documentElement.scrollHeight <= window.innerHeight` should hold.
- Every image painted, every repeated number agrees, and nothing reads "done" beside an open
  action.
- If anything changed after you captured the evidence, recapture it and update the headline,
  table and counts in the same pass.
- Hand back the file path as a clickable `file://` link, plus the action if there is one.

## Done when

- The page has a headline, one table, an Unverified line, and zero or one action.
- Every claim carries observed, tested or unverified, backed by real evidence.
- The file opens standalone and fits one screen, or links a companion for the rest.
