# List the models your credentials reach (free). Render: scripts/demos/render.sh models
Output ".vhs/models-frames/"
Set Width 1470
Set Height 760
Source "scripts/demos/common.tape"

Type "genimg models"
Sleep 800ms
Enter
Wait+Screen@30s /current default/
Sleep 7s
