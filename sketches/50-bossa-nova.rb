# Bossa nova - soft rim clicks, shaker and a gentle bass
# category: Grooves
# keys: last
# gain: 1.91
# The bossa clave on a rim click, a steady shaker, and a root-and-fifth bass
# moving between two chords. Your keys play your last Keys sound;
# Electric piano and Marimba suit it well.

live_loop :gr_percussion do
  use_bpm 130
  clave = [1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0]
  16.times do |i|
    sample :elec_wood, amp: 0.5, rate: 1.2 if clave[i] == 1
    sample :hat_cab, amp: (i % 4 == 0 ? 0.3 : 0.15)
    sleep 0.25
  end
end

live_loop :gr_bass, sync: :gr_percussion do
  use_bpm 130
  [[:d2, :a1], [:g1, :d2]].each do |root, fifth|
    2.times do
      synth :fm, note: root, release: 0.9, amp: 0.55, depth: 0.4, divisor: 1
      sleep 1.5
      synth :fm, note: fifth, release: 0.5, amp: 0.45, depth: 0.4, divisor: 1
      sleep 0.5
    end
  end
end
