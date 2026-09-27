# Deep bass - a fat synth bass, an octave below what you play
# category: Keys
# Two layers: a round foundation and a growly top.

live_loop :bass do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    synth :bass_foundation, note: note - 12, amp: vel / 110.0, release: 0.7
    synth :bass_highend, note: note - 12, amp: vel / 260.0, release: 0.4, res: 0.3
  end
end
