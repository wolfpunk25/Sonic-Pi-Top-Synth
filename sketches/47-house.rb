# House - four-on-the-floor at 122 bpm
# category: Grooves
# keys: last
# gain: 0.80
# Kick on every beat, open hats on the off-beats, claps on 2 and 4, and an
# off-beat bass in A minor. Your keys play your last Keys sound.

live_loop :gr_drums do
  use_bpm 122
  4.times do |b|
    sample :bd_haus, amp: 1.3
    sample :perc_snap, amp: 0.6 if b.odd?
    sleep 0.5
    sample :drum_cymbal_open, amp: 0.3, sustain: 0, release: 0.2
    sleep 0.5
  end
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 122
  [:a1, :a1, :c2, :g1].each do |n|
    sleep 0.5
    synth :fm, note: n, release: 0.3, amp: 0.7, depth: 0.8, divisor: 2
    sleep 0.5
  end
end
