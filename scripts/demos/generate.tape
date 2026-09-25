# One prompt, four takes: a REAL, paid generation (4 images, oai:gi2.5 medium 1K, about $0.05).
# The Sleep covers a slow run; render.sh then speeds up the wait and trims the idle tail.
# The committed take (25 Sep 2026) finished in 38.6 s and was encoded with
#   SKIP_RECORD=1 SPEEDUP="9 44.5 6 51" CROP_HEIGHT=680 scripts/demos/render.sh generate
# A new take needs new SPEEDUP times: read them off the frames in .vhs/generate-frames.
Output ".vhs/generate-frames/"
Set Width 1300
Set Height 860
Source "scripts/demos/common.tape"

Type `genimg "a minimal fox logo, NOT a grid" \` Enter
Type `-m oai:gi2.5 \` Enter
Type `-n 4 \` Enter
Type `--deltas "line art, block print, brush stroke" \` Enter
Type `-o fox.png \` Enter
Type `-g`
Sleep 800ms
Enter
Sleep 150s
