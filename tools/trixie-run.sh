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

exec sudo chroot --userspec="$U:$G" "$ROOT" /usr/bin/env -i \
    HOME="$HOME" USER="$(id -un)" LANG=C.UTF-8 \
    PATH=/usr/local/bin:/usr/bin:/bin \
    XDG_RUNTIME_DIR="/run/user/$U" \
    sh -c 'cd "$HOME" && exec "$@"' sh "$@"
