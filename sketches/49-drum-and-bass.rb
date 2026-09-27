# Drum and bass - the Amen break at 174 bpm
# category: Grooves
# keys: last
# gain: 0.75
# The classic breakbeat, stretched to tempo, over a deep sub bass that walks
# between E and G. Your keys play your last Keys sound.

live_loop :gr_break do
  use_bpm 174
  sample :loop_amen, beat_stretch: 4, amp: 1.1
  sleep 4
end

live_loop :gr_sub, sync: :gr_break do
  use_bpm 174
  [:e1, :e1, :g1, :d1].each do |n|
    synth :sine, note: n, attack: 0.02, sustain: 3, release: 0.8, amp: 0.8
    sleep 4
  end
end
