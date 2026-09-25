# Preview a four-take run without calling the API (free). Render: scripts/demos/render.sh dry-run
Output ".vhs/dry-run-frames/"
Set Width 1000
Set Height 590
Source "scripts/demos/common.tape"

Type `genimg "a minimal fox logo, NOT a grid" \` Enter
Type `-m oai:gi2.5 \` Enter
Type `-n 4 \` Enter
Type `--deltas "line art, block print, brush stroke" \` Enter
Type `-o fox.png \` Enter
Type `-g \` Enter
Type `--dry-run`
Sleep 800ms
Enter
Wait+Screen@20s /dry-run: no API call made/
Sleep 6s
