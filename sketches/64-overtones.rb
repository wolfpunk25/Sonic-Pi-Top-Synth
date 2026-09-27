# Overtones - a drone made of one note's natural harmonics
# category: Ambient
# gain: 0.90
# The first sixteen harmonics of a low C fade in and out one at a time, so
# the chord hiding inside a single note slowly reveals itself. Keys move
# the low note; the harmonics follow over the next few seconds.

set :ot_root, 36
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    r = note
    r -= 12 while r > 43
    r += 12 while r < 31
    set :ot_root, r
  end
end

with_fx :reverb, room: 0.9, mix: 0.55 do
  live_loop :fundamental do
    synth :sine, note: get(:ot_root), attack: 3, sustain: 4, release: 3, amp: 0.35
    sleep 8
  end

  live_loop :harmonics do
    k = rrand_i(2, 16)
    f = midi_to_hz(get(:ot_root)) * k
    synth :sine, note: hz_to_midi(f), attack: rrand(1.5, 3), sustain: rrand(1, 3), release: rrand(3, 5),
      amp: 0.5 / k ** 0.6, pan: rrand(-0.7, 0.7)
    sleep rrand(0.6, 1.4)
  end
end
