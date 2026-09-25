# Screenshot of the models your credentials reach (free). Render: STILL=1 CROP_HEIGHT=551 scripts/demos/render.sh models
Output ".vhs/models-frames/"
Set Width 1640
Set Height 700
Source "scripts/demos/common.tape"

Type "genimg models"
Sleep 800ms
Enter
Wait+Screen@30s /current default/
Sleep 7s
