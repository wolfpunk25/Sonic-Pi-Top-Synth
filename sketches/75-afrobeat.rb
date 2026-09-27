# Afrobeat - interlocking drums, shaker, cowbell and a busy bass
# category: Grooves
# keys: last
# gain: 0.60
# A loping 110 bpm groove after Tony Allen: the kick and snare dance
# around a steady shaker and a cowbell pattern, with a looping bass. Your
# keys play your last Keys sound; Organ and Electric piano suit it.

live_loop :gr_drums do
  use_bpm 110
  kick = [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0]
  snare = [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1]
  bell = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0]
  16.times do |i|
    sample :bd_klub, amp: 1.1 if kick[i] == 1
    sample :drum_snare_soft, amp: 0.55 if snare[i] == 1
    sample :drum_cowbell, amp: 0.25, rate: 1.1 if bell[i] == 1
    sample :hat_cab, amp: (i.even? ? 0.35 : 0.2)
    sleep 0.25
  end
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 110
  [:d2, nil, :d2, :f2, nil, :g2, :a2, nil, :d2, nil, :c3, :a2, nil, :g2, :f2, nil].each do |n|
    synth :fm, note: n, release: 0.2, amp: 0.6, depth: 1, divisor: 2 if n
    sleep 0.25
  end
end
