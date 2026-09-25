# Preview a four-take run without calling the API (free). Render: scripts/demos/render.sh dry-run
Output ".vhs/dry-run-frames/"
Set Width 1220
Set Height 740
Source "scripts/demos/common.tape"

Type `genimg "a minimal fox logo, NOT a grid" \` Enter
Type `--model oai:gi2.5 \` Enter
Type `--num 4 \` Enter
Type `--deltas "line art, block print, brush stroke" \` Enter
Type `--output fox.png \` Enter
Type `--grid \` Enter
Type `--dry-run`
Sleep 800ms
Enter
Wait+Screen@20s /dry-run: no API call made/
Sleep 6s
