# Pluck - a bright plucked string
# category: Keys
# gain: 1.77
# The sound from Beat and keys, on its own. Short and percussive; good for
# fast lines.

live_loop :keys do
  use_real_time
  note, vel = sync "/midi*/note_on"
  synth :pluck, note: note, amp: vel / 70.0 if vel > 0
end
