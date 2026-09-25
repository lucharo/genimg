# Shared look and hidden setup for the genimg docs demos. Sourced by each clip tape.
# Record a clip from the repository root with scripts/demos/render.sh <clip>.
Set Shell bash
Set FontFamily "JetBrains Mono"
Set FontSize 22
Set Padding 28
Set Framerate 24
Set TypingSpeed 35ms
Set Theme { "name": "genimg", "background": "#1c1917", "foreground": "#f5efe6", "cursor": "#e8703a", "selection": "#3a332e", "black": "#1c1917", "red": "#f2705a", "green": "#b5c47a", "yellow": "#f0b35a", "blue": "#7fa7c9", "magenta": "#d99ac2", "purple": "#d99ac2", "cyan": "#7fc4b8", "white": "#e8e0d4", "brightBlack": "#8a7d72", "brightRed": "#ff8a70", "brightGreen": "#c8d68e", "brightYellow": "#ffc978", "brightBlue": "#9bbde0", "brightMagenta": "#eab3d4", "brightPurple": "#eab3d4", "brightCyan": "#9ad8cc", "brightWhite": "#fbf7ee" }

# Use this checkout's genimg, a short prompt, and a fresh empty directory so output paths stay short.
Hide
Type `export PATH="$PWD/.venv/bin:$PATH" PS1="$ " PS2="  " PYTHONWARNINGS=ignore` Enter
Type `cd "$(mktemp -d)" && clear` Enter
Show
