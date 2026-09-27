# pi-top weather station, sound-walk recorder and Sonic Pi player

A weather station, sound-walk recorder and Sonic Pi sketch player for the pi-top [4]'s 128×64 miniscreen, four buttons and speaker.
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
| **Sonic Pi** | Plays your Sonic Pi sketches; shows the MIDI keyboard and the output in use |

Record, Clips and Sonic Pi come straight after **Now**, so they're one press away on a walk.

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
rsync -av <user>@<pi-address>:soundwalks/ ~/Music/Sound\ walks/
```

## Sonic Pi

Sonic Pi 5 runs headless, with no editor. The pi-top screen is the front panel, and a USB MIDI keyboard is the instrument.

- **Sonic Pi page, Select:** opens the list. Sonic Pi starts if it isn't running; it's ready in about 3 s,
  and a sketch picked before then (shown with `~`) plays as soon as it is.
- **The list has two levels.** At the top are the categories (Keys, Sequencers, Grooves, Ambient, with counts) and
  **Output**. Select opens a category; Select on a sketch plays it (replacing whatever was playing, marked `>`).
  Up and Down wrap round.
- **Cancel** inside a category goes back up to the categories and the music keeps playing. At the top, Cancel stops the
  music, and a second Cancel leaves the list. The music also carries on while you look at other pages.
- **Output** switches Sonic Pi between the headphones (USB card) and the pi-top's speaker. It moves only Sonic Pi;
  the weather voice stays on the speaker (`[voice] output`).
- Errors in a sketch appear in a bar along the bottom for 15 s.

**Sketches** are ordinary Sonic Pi files in `~/sonicpi-sketches/`, played in filename order. The ones in `sketches/` are copied
in the first time (later additions: `cp -n sketches/*.rb ~/sonicpi-sketches/`):

Each sketch has a `# category: Name` line near the top. Change it to move the sketch to another category; a new name
makes a new category, and a sketch without the line goes under **Other**. **All 60 sketches are described below, under
[The sketches](#the-sketches).**

**Your Keys sound follows you into the Grooves.** Grooves with `# keys: last` add whichever Keys sketch you played last
(it's remembered across restarts; Pluck until you choose), so pick an instrument, then a groove, and play over it. The
summary on the pi-top shows the pair, for example "Beat and keys + Piano".

**Volume is matched across sketches.** Each has a `# gain:` line, which the station applies as a level effect around it.
`tools/level_check.py` sets the gains by measuring each sketch at the USB card against Keys (01), with Grooves 2 dB
lower to leave room for the Keys sound on top. `--verify` re-measures with the gains in place.

**Writing your own:** keep the first comment line as `# Title - summary` and the lines after it as the
description, because `tools/gen_readme.py` builds the guide below from them. Put `sleep 0.05` after the `set`s at the top, before any `live_loop` that reads them with `get`.
Without it, a loop can start before the values are set and read `nil`, but only sometimes (1 run in 6 for Airport loops).
Values saved with `set` come back **frozen**. Copy one with `get(:x).to_a.dup` before changing it in place
(sketches 16, 18 and 19 do this). Use local variables rather than Ruby constants.

`python3 tools/sketch_check.py [--seconds N] sketches/*.rb` runs every sketch on the real Sonic Pi, playing a chromatic MIDI phrase through
ALSA's Midi Through port so that code triggered by keys runs too, and reports any errors. Write or edit sketches on the Mac and copy them over.
Before each sketch runs, the station sets `get(:wx_temp)`, `:wx_rain` (mm now), `:wx_wind` (mph), `:wx_code` and `:wx_day`,
with `:wx_known` false when there's no forecast yet.

**Why a chroot:** Sonic Pi 5's arm64 AppImage needs glibc 2.38, and the pi-top's Bookworm has 2.36. So the Sonic Pi daemon
runs inside a minimal Debian 13 at `/srv/trixie` (`tools/trixie-run.sh`), sharing PipeWire, MIDI, `/home` and localhost.
The app stays on Bookworm and drives it over OSC. It keeps the daemon alive with a message every second, so if the app
dies, Sonic Pi shuts itself down within 3 s. Idle, Sonic Pi uses about 5 % of one core and 120 MB.

The audio buffer is 128 samples (about 2.7 ms). At 128 and 256, glitches only happen in the first 2 s after start-up, never while
playing, even with chords and drums together.

## KeebDeck: a QWERTY keyboard as a MIDI controller

A [Solder Party KeebDeck Basic](https://www.solder.party/docs/keebdeck/basic/) (an ordinary USB keyboard running QMK) plugged
into the pi-top becomes a MIDI controller. The app grabs it exclusively, so keys don't also type, and plays it on a virtual
MIDI port, "KeebDeck", that Sonic Pi picks up like any other controller. The keyboard's firmware is untouched.
(`pitop_weather/keeb.py`; needs `python3-evdev` and `python3-rtmidi`.)

| Keys | Do |
|---|---|
| **A S D F G H J K L ; '** | white keys, from middle C up |
| **W E T Y U O P** | black keys |
| **Z X C V B N M , . /** | white keys an octave lower |
| **1–8** | jump to that octave (4 = middle C) |
| **← →** | octave down / up |
| **↑ ↓** | transpose a semitone up / down |
| **□** (F1) | stop the music |
| **△ / ×** (F2 / F3) | previous / next sketch in the category playing (Keys if nothing is), and show it |
| **○** (F4) | switch headphones / speaker |
| **☘** (F5) | sustain: notes hold while it's down |
| **◇** (F6) | panic: all notes off |
| **Esc** | let go of the keyboard so it types normally / take it back |

The six shape keys send F1–F6 from the keyboard's firmware; Fn plus the number row also sends F-keys. All notes play at
velocity 100. Settings are in `[keebdeck]` in `~/.config/pitop-weather.ini`: `enabled`, `match` (the name in
`/dev/input/by-id/`), `octave`, `channel`, `velocity`. Tested on the Pi: 288 notes, every note-on matched by its note-off.

## Bluetooth MIDI controllers

Any controller that advertises Bluetooth MIDI connects by itself: no pairing, no cable. It shows on the Sonic Pi
page as, for example, "MIDI: Lydian7 (BT)". `btmidi-autoconnect.service` (`pitop_weather/btmidi.py`):

- scans only for devices advertising the Bluetooth MIDI service, and only while no controller is connected
  (scanning alongside a connection can add latency on the Pi's shared Wi-Fi/Bluetooth chip);
- reconnects when a controller comes back (switched on, back in range);
- backs off from a controller that keeps failing: 5 s, then 10, 20... up to 2 minutes;
- keeps the Bluetooth adapter powered on.

To skip a device, add `[bluetooth_midi]` with `ignore = Name, Other name` to `~/.config/pitop-weather.ini`.
The log is `~/.cache/pitop-weather/btmidi.log`.

**This needs bluetoothd's MIDI plugin.** On the pi-top, a leftover drop-in from pi-top's Further Link
(`/usr/lib/systemd/system/bluetooth.service.d/10-experimental-mode.conf`) starts bluetoothd with only the `gatt`
and `hostname` plugins, so controllers connected but no MIDI port appeared. `install.sh` adds
`/etc/systemd/system/bluetooth.service.d/20-midi.conf` (`bluetooth-midi.conf` here), with the same command line
plus `midi`. Delete it to undo.

It is also the **pairing agent**. It approves "Just Works" pairing for devices that advertise MIDI and refuses
everything else. Some controllers (anything using Adafruit's `adafruit_ble_midi`, for example) only let an encrypted,
paired link read the MIDI characteristic. BlueZ then starts pairing, and with no agent it asks nobody, so the pairing
fails and the link drops. After the first pairing they are bonded and reconnect encrypted straight away.

Tested: an ESP32 box with Arduino BLE MIDI connected first time and reconnected by itself. A CircuitPython ESP32
controller (`adafruit_ble_midi`) needed three fixes, all found with `btmon`:

1. **"Connection Timeout" about 1 s in.** BlueZ's LE supervision timeout is 420 ms, so a slow peripheral that
   missed about 8 connection events was dropped. Raised to 4 s (see below).
2. **Scanning during the connection.** The service now stops scanning *before* connecting, not afterwards.
3. **"Insufficient Authentication" on the MIDI read.** Pairing was needed and nobody approved it; the agent now does.

**Supervision timeout:** `/etc/bluetooth/main.conf`, `[LE]`, `ConnectionSupervisionTimeout = 400` (in 10 ms units,
so 4 s). For a one-off test until reboot: `echo 400 | sudo tee /sys/kernel/debug/bluetooth/hci0/supervision_timeout`.

If a controller is also paired with a Mac, the Mac reconnects to it whenever it can, and the two take turns
grabbing it. Disconnect it in Audio MIDI Setup's Bluetooth window when you want the pi-top to have it.

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

<!-- sketches:start -->

## The sketches

[Keys (15)](#keys) · [Sequencers (15)](#sequencers) · [Grooves (15)](#grooves) · [Ambient (15)](#ambient)

### Keys

Playable instruments: every note you play sounds straight away. The Grooves use whichever of these you played last.

#### Keys
*`01-keys.rb`*: Prophet synth on your keyboard.

Every note you play, straight through a warm analogue-style synth.

#### Chords
*`02-chords.rb`*: Each key plays a soft minor-7th pad.

One finger, whole chords. Long release, lots of reverb.

#### Echo keys
*`06-echo-keys.rb`*: Every note repeats and fades.

A bright synth through a dotted-eighth echo. Play slowly and let it ring.

#### Harmony
*`09-harmony.rb`*: Each key plays a three-note chord in C major.

Every note gets the chord built on it from the white-key scale. Black keys snap to the nearest white key.

#### Strummer
*`12-strummer.rb`*: Each key strums a guitar-like chord.

Plucked strings, low to high, with a little gap between each. The chord is major on white keys and minor on black keys.

#### Bells
*`15-bells.rb`*: Keys ring slow, shimmering bells.

Each note also rings an octave up, softer, with a long cathedral tail.

#### Piano
*`26-piano.rb`*: A grand piano in a warm room.

#### Electric piano
*`27-electric-piano.rb`*: A mellow Rhodes with gentle tremolo.

#### Organ
*`28-organ.rb`*: A tonewheel organ through a slow swirl.

Each note holds for a moment, like a drawbar organ with a slow rotary speaker.

#### Supersaw
*`29-supersaw.rb`*: A huge detuned trance lead.

#### Hoover
*`30-hoover.rb`*: The old-school rave sound.

Low notes are the classic; try the bottom octave.

#### Deep bass
*`31-deep-bass.rb`*: A fat synth bass, an octave below what you play.

Two layers: a round foundation and a growly top.

#### Tech saws
*`32-tech-saws.rb`*: A wide, glossy synth pad.

#### Pluck
*`38-pluck.rb`*: A bright plucked string.

The sound from Beat and keys, on its own. Short and percussive; good for fast lines.

#### Marimba
*`39-marimba.rb`*: Warm wooden mallets.

A soft FM mallet with a short, round decay. Lower notes ring longer.

### Sequencers

They play by themselves, and your notes steer them: change the key, rewrite the pattern, teach them a phrase.

#### Arpeggio
*`03-arpeggio.rb`*: The last key you press sets the root.

It starts on C straight away; play a key to move it.

#### Acid bass
*`07-acid-bass.rb`*: Keys set the root of a squelchy bassline.

A TB-303 pattern with a slowly opening filter, over a four-on-the-floor kick.

#### Loop what you play
*`08-loop-what-you-play.rb`*: Play a phrase, pause, and it loops.

Play a few notes (two or more), then stop for a second: your phrase loops on a kalimba, in your own rhythm. Play a new phrase and pause again to replace it; the old one finishes its pass first.

#### Evolving sequencer
*`16-evolving-sequencer.rb`*: A pattern that keeps changing, and you steer it.

A 16-step melody mutates a little every bar. Your notes push it:

- **below middle C**: changes the key (the bass follows)
- **middle C and up**: your note is written into the pattern, and the interval above the key picks the mode (minor 3rd: minor, major 3rd: major...)
- **playing a lot**: more notes, faster changes, brighter filter, then hats and kick. Leave it alone and it calms back down.

#### Copycat
*`17-copycat.rb`*: Improvises from what you've played.

It learns which note tends to follow which, and wanders through your own ideas. Play a phrase, stop, and listen to it come back rearranged.

#### Euclid garden
*`18-euclid-garden.rb`*: Three rhythms drifting in and out of phase.

Each voice spreads its hits evenly over 16 steps; every two bars one of them gains or loses a hit, or shifts round. Each key you play gives the next voice that pitch and a new number of hits.

#### Cellular
*`19-cellular.rb`*: A melody grown by a cellular automaton.

A row of 16 cells evolves every bar by a simple rule; live cells play notes. White keys flip a cell on or off; black keys change the rule. If the row ever dies out, a single cell is planted to start again.

#### Phase
*`24-phase.rb`*: Two players, one tune, slowly drifting apart.

The same eight notes on left and right, one a touch faster, so the pattern slides against itself (after Steve Reich's Piano Phase). Play eight notes to give them a new tune.

#### Turing machine
*`40-turing-machine.rb`*: A looping pattern that slowly rewrites itself.

After the Music Thinking Machines module: a 16-step loop where, as each step comes round, it may flip. Locked, it repeats exactly; unlocked, it drifts. Keys below middle C lock the loop. Middle C and above unlock it: the higher the key, the faster it changes.

#### Bouncing balls
*`41-bouncing-balls.rb`*: Every key drops a ball that bounces.

Each note repeats faster and quieter, like a ball settling on the floor. Drop several and they bounce against each other. With no keys, a ball drops by itself every few seconds.

#### Random walk
*`42-random-walk.rb`*: A melody that wanders one step at a time.

Each note moves a step or two up or down the scale. The walk leans towards the last note you played, so a key pulls the tune towards it.

#### Polymeter
*`43-polymeter.rb`*: Loops of 3, 4, 5 and 7 steps playing together.

Four short patterns at the same speed but different lengths, so they only line up again every 420 steps. Each key replaces one note, working through the four patterns in turn.

#### Chord wanderer
*`44-chord-wanderer.rb`*: An endless chord progression that finds its own way.

Every two bars the chord moves somewhere related (up a fourth or fifth, to a relative minor...). Play a key and the next chord is built on it.

#### Ratchets
*`45-ratchets.rb`*: A techno sequence with bursts of quick repeats.

A 16-step bassline where some steps "ratchet" into 2-4 fast repeats. Keys set the root; the higher the key, the more ratchets.

#### Your arp
*`46-your-arp.rb`*: The last four notes you play become the arpeggio.

Played up, down, up-and-down, then at random, changing every four bars. Play four new notes to change the chord.

### Grooves

Backing tracks to play over. Most add **your last Keys sound** on top, so pick an instrument under Keys first (Pluck until you do).

#### Beat and keys
*`04-beat-and-keys.rb` · plays your last Keys sound*: A steady groove to play over.

Kick, hats and snare at 100 bpm. Your keys play whichever sound you last chose under Keys (Pluck until you pick one).

#### Chiptune
*`11-chiptune.rb`*: 8-bit arpeggios under your fingers.

Each key fires a fast home-computer arpeggio over a chip bass and noise drums.

#### Finger drums
*`13-finger-drums.rb`*: The keys play a drum kit.

C kick, D snare, E closed hat, F open hat, G clap, A low tom, B high tom. Sharps are percussion. Every octave repeats the kit.

#### Dub stabs
*`21-dub-stabs.rb`*: Chords that echo away over a slow dub groove.

Each key fires a short minor-chord stab into a long echo. Keys below A3 move the bassline to that note.

#### Late night jazz
*`23-late-night-jazz.rb`*: A walking bass trio you can play over.

ii-V-I-vi on electric piano, walking bass and a swung ride. Keys below G3 change the key; higher keys play electric piano.

#### House
*`47-house.rb` · plays your last Keys sound*: Four-on-the-floor at 122 bpm.

Kick on every beat, open hats on the off-beats, claps on 2 and 4, and an off-beat bass in A minor. Your keys play your last Keys sound.

#### Boom bap
*`48-boom-bap.rb` · plays your last Keys sound*: A dusty, swung hip-hop beat at 90 bpm.

Heavy kick, crisp snare on 2 and 4, lazy swung hats and a little vinyl hiss. Your keys play your last Keys sound.

#### Drum and bass
*`49-drum-and-bass.rb` · plays your last Keys sound*: The Amen break at 174 bpm.

The classic breakbeat, stretched to tempo, over a deep sub bass that walks between E and G. Your keys play your last Keys sound.

#### Bossa nova
*`50-bossa-nova.rb` · plays your last Keys sound*: Soft rim clicks, shaker and a gentle bass.

The bossa clave on a rim click, a steady shaker, and a root-and-fifth bass moving between two chords. Your keys play your last Keys sound; Electric piano and Marimba suit it well.

#### One drop
*`51-one-drop.rb` · plays your last Keys sound*: A laid-back reggae rhythm at 76 bpm.

Kick and rim shot together on beat three only, skipping hats, and a round bass line. Play off-beat chords on your keys for the skank.

#### Techno
*`52-techno.rb` · plays your last Keys sound*: A driving 130 bpm groove.

Punchy kick, off-beat hats, a clap that moves around, and a rumbling low bass under the kick. Your keys play your last Keys sound; Supersaw and Hoover suit it.

#### Lo-fi
*`53-lo-fi.rb` · plays your last Keys sound*: A sleepy, muffled beat with crackle.

Soft swung drums through a low-pass filter, vinyl hiss and a warm bass. Your keys play your last Keys sound; Electric piano is the classic.

#### Funk
*`54-funk.rb` · plays your last Keys sound*: Syncopated drums and a slap bass at 104 bpm.

Sixteenth-note hats, a kick that dances round the beat, ghost notes on the snare and a popping bass line. Your keys play your last Keys sound; Organ and Electric piano suit it.

#### Waltz
*`55-waltz.rb` · plays your last Keys sound*: A gentle oom-pah-pah in three.

Bass on the first beat and soft chords on the second and third, moving round C, A minor, F and G. Play a melody over it with your last Keys sound.

#### Breakbeat
*`56-breakbeat.rb` · plays your last Keys sound*: A chopped funk break with a rolling bass.

A classic breakbeat loop, now and then chopped up by starting it from a different point, over a bass that bounces between two notes. Your keys play your last Keys sound.

### Ambient

Slow, evolving soundscapes that need no keys at all; playing adds something gentle. Some follow the real weather.

#### Weather drift
*`05-weather-drift.rb`*: Ambient that follows today's weather.

No keys needed. Colder is lower, rain adds drops, wind speeds it up. The station sets these before every sketch runs.

#### Night and day
*`10-night-and-day.rb`*: Changes with the sun.

No keys needed. Daytime is a bright kalimba melody; after sunset, a slow dark pad with distant sounds. Cloud and rain soften it.

#### Rain on the roof
*`14-rain-on-the-roof.rb`*: The sound of today's rain.

No keys needed. Real rain makes it heavier; on a dry day it's a light shower. Play keys for a soft piano over the top.

#### Drone choir
*`20-drone-choir.rb`*: Build a slowly breathing chord, one key at a time.

Press a note to add it to the drone; press it again to take it out. Up to six voices; the oldest drops out when you add a seventh.

#### Space station
*`22-space-station.rb`*: Hums, telemetry and distant signals.

No keys needed. Keys fire laser pings that swoop down an octave.

#### Music box
*`25-music-box.rb`*: A tune that slowly winds down.

It plays by itself, getting slower and quieter as the spring runs out. Every key you press winds it back up and adds your note to the tune.

#### Aurora
*`33-aurora.rb`*: Slow shifting chords under a breathing filter.

No keys needed. Keys add soft high notes that hang in the air.

#### Tidal
*`34-tidal.rb`*: Waves on a shore, and the odd gull.

No keys needed. Keys ring soft bells over the water.

#### Forest dawn
*`35-forest-dawn.rb`*: Birdsong over a soft morning pad.

No keys needed. Keys play a gentle kalimba among the birds.

#### Snowfall
*`36-snowfall.rb`*: Sparse glassy bells, slowly falling.

No keys needed; twice as many flakes when it's really snowing. Keys add your own flakes, an octave up.

#### Airport loops
*`37-airport-loops.rb`*: Long loops of different lengths drifting in and out of line.

After Brian Eno's Music for Airports: each voice sings one note on its own cycle, so the combination never quite repeats. Each key gives the next voice your note instead.

#### Wind chimes
*`57-wind-chimes.rb`*: Chimes that ring with today's wind.

No keys needed. The windier it is outside, the more often the chimes are caught by a gust, and the louder the breeze. Keys strike a chime yourself.

#### Underwater
*`58-underwater.rb`*: Bubbles, a deep hum and distant whale song.

No keys needed. Everything is muffled as if heard below the surface. Keys ring soft, muted bells.

#### Night crickets
*`59-night-crickets.rb`*: A summer night outside.

No keys needed. Crickets chirping at their own rates, a frog now and then, the odd owl, and a low night pad. Keys play a quiet kalimba.

#### Glacier
*`60-glacier.rb`*: Vast, very slow chords that barely move.

No keys needed. Each chord swells in over ten seconds and changes every twenty, over a deep sub and a distant choir. Keys hold long, soft notes.

<!-- sketches:end -->
