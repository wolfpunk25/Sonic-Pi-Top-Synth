# pi-top weather station and sound-walk recorder

A weather station and sound-walk recorder for the pi-top [4]'s 128×64 miniscreen, four buttons and speaker.
The forecast comes from [Open-Meteo](https://open-meteo.com), which is free and needs no API key.

## Pages

| Page | Shows |
|---|---|
| **Now** | Temperature, "feels like" temperature, conditions, one line about the next few hours |
| **Next hours** | The next three hours: icon, temperature, chance of rain |
| **Rain radar** | Rainfall in 15-minute steps over the next two hours, with "rain in ~N min" |
| **Wind** | Compass arrow, speed, gusts, direction |
| **Sun** | Sun position along the horizon arc, daylight left, UV |
| **Pressure** | hPa, 3-hour trend in shipping-forecast words, chart from 3 h ago to 6 h ahead |
| **Tomorrow** | Conditions, high and low, chance of rain |
| **Device** | Battery, time left, IP address, time since the last update |
| **Record** | Sound-walk recorder: microphone name, the weather the next clip will be tagged with, free space |
| **Clips** | Your recordings, newest first |

Record and Clips come straight after **Now**, so they're one press away on a walk.

## Buttons

| Button | Does |
|---|---|
| Up / Down | Previous / next page |
| Select | Reads the current page aloud (press again to stop); on Record it records, on Clips it opens the list |
| Cancel | Back to **Now** |
| Cancel, held 2 s | Quits and hands the screen back to the pi-top menu |

After 2 minutes without a button press, the screen switches to a small, slowly moving clock so
the OLED doesn't burn in. The first press only wakes the screen.

## Sound walks

Plug in any USB microphone. The Record page finds it by itself within a few seconds.

- **Record page, Select:** starts a clip. It stops by itself at 60 s, or press Select (or Cancel) to stop sooner.
  While recording, the screen shows a timer and a level meter. The meter has a peak mark, and **LOUD** appears near clipping.
  The other buttons do nothing during a recording, so a stray press can't cut it short.
- **Clips page, Select:** opens the list. Up and Down move through it, Select plays or stops the highlighted clip
  through the speaker, and Cancel goes back.
- **Nothing speaks during a recording.** Rain and battery alerts wait until the clip has finished.

Each clip is a 48 kHz mono WAV in `~/soundwalks/<date>/`, named after its time and weather
(e.g. `071204-light-rain-14c.wav`). A `.json` file next to it records the time, weather, battery and microphone.

**The weather tag is honest about where it came from.** Out on a walk there's usually no Wi-Fi. A forecast
fetched in the last 30 minutes gives `"source": "observed"`; otherwise the tag is the saved forecast for that hour
(`"source": "forecast"`, shown with a `~` on screen). The location is the weather station's home town, not a GPS fix.

Copying the clips to the Mac:

```
rsync -av darren@192.168.68.53:soundwalks/ ~/Music/Sound\ walks/
```

## Alerts

The box speaks without being asked in two cases. Both are silent during quiet hours (22:00–08:00)
but still switch the page.

- **Rain due within 30 minutes.** It warns once per dry spell.
- **Battery falling through 20 % and then 10 %.** Charging re-arms the warnings.

## Files

- `pitop_weather/`: the app (forecast, pages, speech, main loop)
- `sim.py`: renders every page to PNGs in `sim-out/`, using the same code as the OLED.
  `python3 sim.py --live "Town"` does this with today's real forecast.
- `tests/`: `python3 -m unittest discover tests`
- `install.sh`: run on the Pi. It installs espeak-ng and a user systemd service that starts at boot.

## On the Pi

```
systemctl --user restart pitop-weather    # after editing ~/.config/pitop-weather.ini
systemctl --user start pitop-weather      # bring it back after a Cancel-hold
journalctl --user -u pitop-weather -f     # logs
```

Fonts: DejaVu Sans (`pitop_weather/fonts/LICENSE`).
