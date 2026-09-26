# pi-top weather station

A weather station for the pi-top [4]'s 128×64 miniscreen, four buttons and speaker.
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

## Buttons

| Button | Does |
|---|---|
| Up / Down | Previous / next page |
| Select | Reads the current page aloud (press again to stop) |
| Cancel | Back to **Now** |
| Cancel, held 2 s | Quits and hands the screen back to the pi-top menu |

After 2 minutes without a button press, the screen switches to a small, slowly moving clock so
the OLED doesn't burn in. The first press only wakes the screen.

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
