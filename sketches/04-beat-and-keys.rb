# Beat and keys - a steady groove to play over
# category: Grooves
# keys: last
# gain: 1.27
# Kick, hats and snare at 100 bpm. Your keys play whichever sound you last
# chose under Keys (Pluck until you pick one).

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
