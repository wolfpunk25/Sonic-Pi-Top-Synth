# Chords - each key plays a soft minor-7th pad
# category: Keys
# gain: 2.24
# One finger, whole chords. Long release, lots of reverb.

with_fx :reverb, room: 0.85, mix: 0.5 do
  live_loop :chords do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :hollow, notes: chord(note, :m7), attack: 0.05, release: 3, amp: 1.4 if vel > 0
  end
end
