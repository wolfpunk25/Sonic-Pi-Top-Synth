# Techno - a driving 130 bpm groove
# category: Grooves
# keys: last
# gain: 0.70
# Punchy kick, off-beat hats, a clap that moves around, and a rumbling low
# bass under the kick. Your keys play your last Keys sound;
# Supersaw and Hoover suit it.

live_loop :gr_drums do
  use_bpm 130
  16.times do |i|
    sample :bd_tek, amp: 1.3 if i % 4 == 0
    sample :hat_zild, amp: 0.35 if i % 4 == 2
    sample :hat_tap, amp: 0.15 if one_in(4)
    sample :perc_snap, amp: 0.5 if i == 12 || (i == 6 && one_in(3))
    sleep 0.25
  end
end

live_loop :gr_rumble, sync: :gr_drums do
  use_bpm 130
  with_fx :lpf, cutoff: 70 do
    4.times do
      sleep 0.25
      synth :fm, note: :a1, release: 0.5, amp: 0.5, depth: 2, divisor: 1
      sleep 0.75
    end
  end
end
