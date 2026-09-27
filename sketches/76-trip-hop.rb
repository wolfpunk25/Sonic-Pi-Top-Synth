# Trip hop - slow, heavy and smoky at 82 bpm
# category: Grooves
# keys: last
# gain: 0.49
# A heavy half-time beat, a deep sub, crackle and a dark wash, after the
# Bristol sound. Your keys play your last Keys sound; Strings, Electric
# piano and Glass suit it.

with_fx :lpf, cutoff: 100 do                 # made once, not every bar
  live_loop :gr_drums do
    use_bpm 82
    16.times do |i|
      sample :bd_boom, amp: 1.4 if [0, 3, 10].include?(i)
      sample :sn_dub, amp: 0.8 if [4, 12].include?(i)
      sample :hat_tap, amp: 0.2 if i.even?
      sleep i.even? ? 0.27 : 0.23
    end
  end
end

live_loop :gr_hiss do
  sample :vinyl_hiss, amp: 0.3
  sleep sample_duration(:vinyl_hiss)
end

live_loop :gr_sub, sync: :gr_drums do
  use_bpm 82
  [:c2, :c2, :ab1, :bb1].each do |n|
    synth :sine, note: n, attack: 0.05, sustain: 3, release: 0.9, amp: 0.7
    sleep 4
  end
end

live_loop :gr_wash, sync: :gr_drums do
  use_bpm 82
  c = chord(:c3, :m7)
  c.each do |n|                              # voices 30 ms apart; they share the level as notes: did
    synth :dark_ambience, note: n, attack: 4, sustain: 4, release: 6, amp: 0.3 / c.length
    sleep 0.03
  end
  sleep 16 - c.length * 0.03
end
