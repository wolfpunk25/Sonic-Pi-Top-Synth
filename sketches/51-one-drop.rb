# One drop - a laid-back reggae rhythm at 76 bpm
# category: Grooves
# keys: last
# gain: 0.91
# Kick and rim shot together on beat three only, skipping hats, and a round
# bass line. Play off-beat chords on your keys for the skank.

live_loop :gr_drums do
  use_bpm 76
  8.times do |i|
    sample :hat_tap, amp: 0.3 if i.odd?
    if i == 4
      sample :bd_fat, amp: 1.3
      sample :sn_generic, amp: 0.5, rate: 1.4
    end
    sleep 0.5
  end
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 76
  [[:a1, 1], [:c2, 0.5], [:e2, 0.5], [:d2, 1], [:c2, 1]].each do |n, d|
    synth :sine, note: n, release: d * 0.9, amp: 0.8
    synth :fm, note: n, release: d * 0.5, amp: 0.2, depth: 0.5, divisor: 1
    sleep d
  end
end
