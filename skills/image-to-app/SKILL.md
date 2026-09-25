---
name: image-to-app
description: "Visual interview that turns an app idea into a chosen design, then a working app. Show distinct visual directions for a mobile or web app, let the user pick one, break it into its views, iterate, then build and verify against the images. Use for image-to-app or image-to-web work, exploring UI directions with genimg before coding, or turning mockups into an app."
---

# Image to app

A visual interview. You show, the user picks, you narrow. Every round puts images on screen before it asks anything. The accepted images are design evidence; the code still owns accessibility, interaction, real data and state.

## Set up the interview

Load `genimg` for the CLI mechanics. The interview itself is Matt Pocock's `grill-with-docs`. It is user-invoked only, so do what it does and load its two parts: `grilling` (numbered rounds, each question with your recommended answer) and `domain-modeling` (the app's vocabulary in `CONTEXT.md`, each hard-to-reverse decision as an ADR). If they are not installed, ask the user to install them, then continue:

```bash
npx skills add mattpocock/skills -s grill-with-docs grilling domain-modeling
```

Open with one grilling round: what the app is for, who uses it, and whether it is a **mobile app** or a **web app**. Settle the platform before the first image; it fixes the frame for every render (`-a 9:16` for a phone screen, `-a 16:9` for a desktop window; `oai:gi2` needs `-r 2K` for both). Render with a model the user can run (their saved default, or one `genimg models` lists for their credentials); the commands below use `oai:gi2` as an example, and the `genimg` skill lists each model's sizes.

## The loop

### 1. Directions

If the user brings mockups or an already chosen design, treat those as the accepted images: record them in `selection-manifest.md`, ask whether they want alternatives, and otherwise go straight to Views.

Render three to five visual directions of the app's main screen, each one a whole design system: palette, type, density, component language. Write one direction per line in `directions.txt` and run a single `-n` call; #1 keeps the plain base prompt.

```bash
genimg "a SINGLE mobile app home screen for <app>, one phone screen filling the frame, NOT a grid" \
  -m oai:gi2 -a 9:16 -r 2K -n 4 --deltas @directions.txt -o directions.png
genimg grid directions_*.png -o directions.html --open
```

Give each direction a stable name (`quiet-ledger`, `night-market`) and record prompt, model and index in `selection-manifest.md`. With the grid open, ask the pick as a grilling round, then copy the accepted image to `<name>-01-home.png`. When the answer combines directions, write the synthesis out: which shell, components, type and spacing come from which direction.

### 2. Views

Agree the view set in a grilling round, with your recommended list (for example home, detail, create, settings, empty state). Then render each view in the chosen system, passing the accepted image as a reference after the prompt so the style holds:

```bash
genimg "the item detail screen of the same app, same palette, type and components as the reference, one phone screen, NOT a grid" \
  quiet-ledger-01-home.png -m oai:gi2 -a 9:16 -r 2K -o quiet-ledger-02-detail.png
```

Name files `<direction>-<NN>-<view>.png` and show the whole set in one grid. Audit each image against the agreed views and label any departure **Preserve**, **Reinterpret** or **Reject**: an extra tab or a missing state is a defect, however good it looks.

### 3. Iterate

Each round: show the current set, ask one grilling round, apply the answers. Use `-i <view>.png` for a small fix to one view; regenerate from a corrected full prompt when the structure is wrong. Change one decision per round so any drift has one cause. As decisions settle, `domain-modeling` records them.

The interview is done when every agreed view has an accepted image, the grilling frontier is empty, and the user confirms the set.

## Build

Hand the implementer the accepted images, the synthesis, `CONTEXT.md`, the ADRs and the expected interactions, using [implementation-handoff.md](references/implementation-handoff.md). Ask for a working app with realistic states, not a screenshot recreation. Name every fixture, the real interface it stands in for, and how it is retired.

## Verify

Run the functional checks, then compare the running app with the accepted images side by side, in the same states: the main viewport and one narrow one for a web app, the target device for a mobile app. Use [visual-qa.md](references/visual-qa.md). Label each claim with its rung on this ladder; no rung proves the one above it:

1. **Visual direction**: the accepted images.
2. **Fixture-backed prototype**: layout and interaction on declared substitute data.
3. **Live integration**: real data, refresh, empty and error states.
4. **Installed runtime**: the packaged app, cold start, persistence.

Fix the largest mismatch first. Stop after two or three review rounds unless a gap breaks the accepted design.

## Done when

- Every agreed view has an accepted image and the user confirmed the set.
- `CONTEXT.md` and the ADRs record the decisions.
- The app matches the images at the platform's sizes (desktop and narrow for a web app, the target device for a mobile app), interactions work with realistic state, and persisted state survives a cold reload.
- The evidence rung agreed with the user was reached (a mobile app needs **Installed runtime**), and the report names it and any fixture-backed part.
