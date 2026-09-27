# Disco - four on the floor with an octave-jumping bass
# category: Grooves
# keys: last
# gain: 0.87
# A steady kick, open hats on the off-beats, handclaps on 2 and 4 and the
# classic bass that leaps between octaves. Your keys play your last Keys
# sound; Strings and Electric piano suit it.

live_loop :gr_drums do
  use_bpm 118
  4.times do |b|
    sample :bd_haus, amp: 1.2
    sample :perc_snap, amp: 0.5 if b.odd?
    sleep 0.5
    sample :drum_cymbal_open, amp: 0.3, sustain: 0, release: 0.25
    sleep 0.5
  end
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 118
  [:a1, :a1, :d2, :e2].each do |root|
    4.times do
      synth :fm, note: root, release: 0.18, amp: 0.55, depth: 0.7, divisor: 2
      sleep 0.5
      synth :fm, note: root + 12, release: 0.18, amp: 0.45, depth: 0.7, divisor: 2
      sleep 0.5
    end
  end
end
