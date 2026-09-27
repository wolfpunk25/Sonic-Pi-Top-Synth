# Funk - syncopated drums and a slap bass at 104 bpm
# category: Grooves
# keys: last
# gain: 0.55
# Sixteenth-note hats, a kick that dances round the beat, ghost notes on the
# snare and a popping bass line. Your keys play your last Keys sound; Organ
# and Electric piano suit it.

live_loop :gr_drums do
  use_bpm 104
  kick = [1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0]
  snare = [0, 0, 0, 0, 2, 0, 0, 1, 0, 1, 0, 0, 2, 0, 0, 1]   # 2 = backbeat, 1 = ghost
  16.times do |i|
    sample :bd_klub, amp: 1.3 if kick[i] == 1
    sample :drum_snare_hard, amp: 0.8 if snare[i] == 2
    sample :drum_snare_soft, amp: 0.2 if snare[i] == 1
    sample :drum_cymbal_closed, amp: (i.even? ? 0.35 : 0.18)
    sleep 0.25
  end
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 104
  bassline = [:e2, nil, :e3, nil, :e2, :g2, nil, :a2, nil, :e2, :e3, nil, :d3, nil, :b2, :g2]   # not "line": that's a built-in
  bassline.each do |n|
    synth :fm, note: n, release: 0.15, amp: 0.6, depth: 1.5, divisor: 2 if n
    sleep 0.25
  end
end
