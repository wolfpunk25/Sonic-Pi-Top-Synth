# Two-step - shuffling UK garage at 132 bpm
# category: Grooves
# keys: last
# gain: 0.69
# The skippy two-step kick that avoids the downbeats, crisp snares on 2 and
# 4, swung hats and a rubbery bass. Your keys play your last Keys sound.

live_loop :gr_drums do
  use_bpm 132
  kick = [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0]
  16.times do |i|
    sample :bd_tek, amp: 1.2 if kick[i] == 1
    sample :perc_snap, amp: 0.6 if [4, 12].include?(i)
    sample :hat_zild, amp: 0.3 if i.odd? || one_in(4)
    sleep i.even? ? 0.29 : 0.21                       # the swing is the whole style
  end
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 132
  [[:f2, 0.75], [:f2, 0.5], [:ab2, 0.75], [:c3, 0.5], [:bb2, 1], [:f2, 0.5]].each do |n, d|
    synth :tb303, note: n, release: d * 0.8, cutoff: 75, res: 0.4, amp: 0.45, wave: 1
    sleep d
  end
end
