# Beat and keys - a steady groove to play over
# category: Grooves
# Kick, hats and snare at 100 bpm, with the keys on a plucky synth.

live_loop :drums do
  use_bpm 100
  sample :bd_haus, amp: 1.2
  sleep 0.5
  sample :drum_cymbal_closed, amp: 0.5
  sleep 0.5
  sample :drum_snare_hard, amp: 0.6
  sleep 0.5
  sample :drum_cymbal_closed, amp: 0.5
  sleep 0.5
end

live_loop :keys do
  use_real_time
  note, vel = sync "/midi*/note_on"
  synth :pluck, note: note, amp: vel / 70.0 if vel > 0
end
