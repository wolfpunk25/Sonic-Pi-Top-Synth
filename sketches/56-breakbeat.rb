# Breakbeat - a chopped funk break with a rolling bass
# category: Grooves
# keys: last
# gain: 1.04
# A classic breakbeat loop, now and then chopped up by starting it from a
# different point, over a bass that bounces between two notes. Your keys
# play your last Keys sound.

live_loop :gr_break do
  use_bpm 110
  if one_in(4)
    4.times do                                      # four random quarter-bar slices
      s = [0, 0.25, 0.5, 0.75].choose
      sample :loop_breakbeat, beat_stretch: 4, start: s, finish: s + 0.25, amp: 1.1
      sleep 1
    end
  else
    sample :loop_breakbeat, beat_stretch: 4, amp: 1.1
    sleep 4
  end
end

live_loop :gr_bass, sync: :gr_break do
  use_bpm 110
  [:d2, :d2, :f2, :d2, :c2, :d2, :a1, :c2].each do |n|
    synth :tb303, note: n, release: 0.3, cutoff: 70, res: 0.5, amp: 0.45
    sleep 0.5
  end
end
