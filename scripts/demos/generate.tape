# One prompt, four takes: a REAL, paid generation (4 images, oai:gi2.5 medium 1K, about $0.05).
# The Sleep covers a slow run; render.sh then speeds up the wait and trims the idle tail.
# A new take needs new SPEEDUP times: read them off the frames in .vhs/generate-frames, then
#   SKIP_RECORD=1 SPEEDUP="<start> <end> <factor> <stop>" CROP_HEIGHT=<px> scripts/demos/render.sh generate
Output ".vhs/generate-frames/"
Set Width 1220
Set Height 1060
Source "scripts/demos/common.tape"

Type `genimg "a minimal fox logo, NOT a grid" \` Enter
Type `--model oai:gi2.5 \` Enter
Type `--num 4 \` Enter
Type `--deltas "line art, block print, brush stroke" \` Enter
Type `--output fox.png \` Enter
Type `--grid`
Sleep 800ms
Enter
Sleep 150s
