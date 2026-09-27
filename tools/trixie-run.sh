#!/bin/sh
# Run a command inside the Debian 13 (trixie) userland at /srv/trixie, as
# the calling user, sharing the host's sound (PipeWire socket), MIDI and
# audio devices (/dev), /home and /tmp. Localhost networking is shared too,
# so OSC between host and chroot just works.
#
#   trixie-run.sh ruby --version
#
# Sonic Pi v5's arm64 AppImage needs glibc 2.38; Bookworm has 2.36. This is
# the smallest way to give it a newer libc without touching the pi-top's OS.
# Remove it all with:  sudo umount -R /srv/trixie/*; sudo rm -rf /srv/trixie
set -e
ROOT=/srv/trixie
U=$(id -u)
G=$(id -g)

bind() {  # bind <host path> — idempotent
    mkdir -p "$1" 2>/dev/null || true
    sudo mkdir -p "$ROOT$1"
    mountpoint -q "$ROOT$1" || sudo mount --rbind "$1" "$ROOT$1"
}
mountpoint -q "$ROOT/proc" || sudo mount -t proc proc "$ROOT/proc"
bind /sys
bind /dev
bind /home
bind /tmp
bind "/run/user/$U"

# Real-time priority: going through sudo drops the user's RLIMIT_RTPRIO to
# 0, so Sonic Pi's audio thread (and PipeWire's thread inside it) couldn't
# get real-time scheduling and ran at normal priority - any busy moment
# elsewhere on the Pi made it miss its 2.7 ms deadline, which you hear as
# a crackle. Raise the limits as root, then drop to the user. 95 matches
# what the system gives the pipewire group.
# PITOP_NO_RT=1 skips this, only so tools/crackle_check.py can compare.
RT='ulimit -r 95 && ulimit -l unlimited && '
[ -n "$PITOP_NO_RT" ] && RT=''
exec sudo sh -c "$RT"'exec "$@"' sh \
    chroot --userspec="$U:$G" "$ROOT" /usr/bin/env -i \
    HOME="$HOME" USER="$(id -un)" LANG=C.UTF-8 \
    PATH=/usr/local/bin:/usr/bin:/bin \
    XDG_RUNTIME_DIR="/run/user/$U" \
    sh -c 'cd "$HOME" && exec "$@"' sh "$@"
