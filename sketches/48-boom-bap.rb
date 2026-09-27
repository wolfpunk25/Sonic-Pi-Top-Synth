# Boom bap - a dusty, swung hip-hop beat at 90 bpm
# category: Grooves
# keys: last
# gain: 0.54
# Heavy kick, crisp snare on 2 and 4, lazy swung hats and a little vinyl
# hiss. Your keys play your last Keys sound.

live_loop :gr_drums do
  use_bpm 90
  kick = [1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0]
  snare = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]
  16.times do |i|
    sample :bd_boom, amp: 1.4 if kick[i] == 1
    sample :sn_dolf, amp: 0.9 if snare[i] == 1
    sample :hat_tap, amp: (i.even? ? 0.5 : 0.25) if i.even? || one_in(3)
    sleep i.even? ? 0.29 : 0.21            # swing
  end
end

live_loop :gr_hiss do
  sample :vinyl_hiss, amp: 0.25
  sleep sample_duration(:vinyl_hiss)
end
