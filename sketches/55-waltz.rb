# Waltz - a gentle oom-pah-pah in three
# category: Grooves
# keys: last
# gain: 2.08
# Bass on the first beat and soft chords on the second and third, moving
# round C, A minor, F and G. Play a melody over it with your last Keys sound.

live_loop :gr_waltz do
  use_bpm 96
  [[:c2, :c4], [:a1, :a3], [:f1, :f3], [:g1, :g3]].each do |bass, root|
    q = [:a1, :a3].include?(bass) ? :minor : :major
    2.times do
      synth :fm, note: bass, release: 0.8, amp: 0.55, depth: 0.5, divisor: 1
      sleep 1
      2.times do
        synth :hollow, notes: chord(root, q), release: 0.5, amp: 0.4
        sample :drum_cymbal_soft, amp: 0.08, rate: 1.5
        sleep 1
      end
    end
  end
end
