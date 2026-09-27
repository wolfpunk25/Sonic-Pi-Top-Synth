# Glass - bright, detuned glassy tones
# category: Keys
# gain: 0.79
# Two slightly detuned triangle waves ringing out in a big room. Sparkly in
# the upper octaves.

with_fx :reverb, room: 0.8, mix: 0.4 do
  live_loop :glass do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :dtri, note: note, amp: vel / 330.0, detune: 0.12, attack: 0.005, release: 1.6 if vel > 0
  end
end
