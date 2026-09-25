#!/usr/bin/env bash
# Record one docs demo and encode it: scripts/demos/render.sh dry-run
#
# Run from the repository root after `uv sync`. Needs vhs, ttyd, ffmpeg and cwebp.
# vhs 0.12.0 records fine but exits 0 without encoding anything
# (https://github.com/charmbracelet/vhs/issues/787), so each tape writes raw frames
# and this script composes the MP4 and its poster frame with ffmpeg.
#
# Optional environment:
#   SKIP_RECORD=1           re-encode the frames already in .vhs/<clip>-frames (no new run)
#   SPEEDUP="A B X END"     play seconds A..B at X times speed and stop at END (a long wait)
#   CROP_HEIGHT=N           keep only the top N pixels of the terminal (drop unused rows)
set -euo pipefail

name=${1:?usage: scripts/demos/render.sh <clip name, e.g. dry-run>}
frames=.vhs/$name-frames
out=docs/assets/demos/$name.mp4
poster=docs/assets/demos/$name.webp

if [[ -z ${SKIP_RECORD:-} ]]; then
  rm -rf "$frames"
  vhs "scripts/demos/$name.tape"
fi
test -s "$frames/frame-text-00001.png" || { echo "vhs wrote no frames to $frames" >&2; exit 1; }

# Text and cursor layers, a 28px border in the terminal background, H.264 for every browser.
edit=""
if [[ -n ${SPEEDUP:-} ]]; then
  read -r a b x end <<< "$SPEEDUP"
  edit="split=3[p][q][r];[p]trim=0:$a,setpts=PTS-STARTPTS[p1];"
  edit+="[q]trim=$a:$b,setpts=(PTS-STARTPTS)/$x[q1];[r]trim=$b:$end,setpts=PTS-STARTPTS[r1];"
  edit+="[p1][q1][r1]concat=n=3:v=1:a=0,fps=24,"
fi
if [[ -n ${CROP_HEIGHT:-} ]]; then
  edit+="crop=iw:$CROP_HEIGHT:0:0,"
fi
ffmpeg -v error -y \
  -framerate 24 -i "$frames/frame-text-%05d.png" \
  -framerate 24 -i "$frames/frame-cursor-%05d.png" \
  -filter_complex "[0][1]overlay,${edit}pad=ceil((iw+56)/2)*2:ceil((ih+56)/2)*2:28:28:color=0x1c1917,format=yuv420p" \
  -c:v libx264 -preset slow -crf 26 -movflags +faststart -an "$out"

# The last frame shows the finished command, so it doubles as the poster.
ffmpeg -v error -y -sseof -0.5 -i "$out" -frames:v 1 -update 1 "$frames/poster.png"
cwebp -quiet -q 85 "$frames/poster.png" -o "$poster"

ls -l "$out" "$poster"
