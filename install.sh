#!/bin/sh
# Run on the pi-top, from this folder:  ./install.sh
set -e
cd "$(dirname "$0")"

echo "== packages"
sudo apt-get install -y espeak-ng python3-pil

echo "== settings"
mkdir -p ~/.config
[ -f ~/.config/pitop-weather.ini ] || cp config.example.ini ~/.config/pitop-weather.ini

echo "== service"
mkdir -p ~/.config/systemd/user
cp pitop-weather.service ~/.config/systemd/user/
# keep the user service (and PipeWire, for the speaker) running without a login
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now pitop-weather.service
systemctl --user --no-pager status pitop-weather.service | head -5
