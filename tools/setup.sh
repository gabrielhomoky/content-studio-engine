#!/usr/bin/env bash
# setup.sh - make sure ffmpeg/ffprobe exist (used by tools/media.py).
# Idempotent, quiet, and ALWAYS exits 0 so a session never fails to start.
# Runs from the SessionStart hook in .claude/settings.json.

if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  echo "setup: ffmpeg ready"
  exit 0
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "setup: ffmpeg missing and apt-get unavailable; reels will be analysed from thumbnails only"
  exit 0
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    SUDO="sudo -n"
  else
    echo "setup: ffmpeg missing and no root access; reels will be analysed from thumbnails only"
    exit 0
  fi
fi

export DEBIAN_FRONTEND=noninteractive
if $SUDO apt-get -qq update >/dev/null 2>&1 \
   && $SUDO apt-get -qq install -y --no-install-recommends ffmpeg >/dev/null 2>&1; then
  echo "setup: ffmpeg installed"
else
  echo "setup: ffmpeg install failed; reels will be analysed from thumbnails only"
fi
exit 0
