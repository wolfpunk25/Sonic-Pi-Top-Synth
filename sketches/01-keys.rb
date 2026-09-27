# Keys - Prophet synth on your keyboard
# category: Keys
# gain: 1.01
# Every note you play, straight through a warm analogue-style synth.

live_loop :keys do
  use_real_time
  note, vel = sync "/midi*/note_on"
  synth :prophet, note: note, amp: vel / 100.0, release: 1.2, cutoff: 100 if vel > 0
end
