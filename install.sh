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

echo "== Bluetooth MIDI"
# bluetoothd must load its midi plugin (pi-top's leftover drop-in only allows gatt,hostname)
if [ ! -f /etc/systemd/system/bluetooth.service.d/20-midi.conf ]; then
    sudo mkdir -p /etc/systemd/system/bluetooth.service.d
    sudo cp bluetooth-midi.conf /etc/systemd/system/bluetooth.service.d/20-midi.conf
    sudo systemctl daemon-reload && sudo systemctl restart bluetooth
fi
cp btmidi-autoconnect.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now btmidi-autoconnect.service
systemctl --user --no-pager status pitop-weather.service | head -5
