# Loop what you play - play a phrase, pause, and it loops
# category: Sequencers
# Play a few notes (two or more), then stop for a second: your phrase
# loops on a kalimba, in your own rhythm. Play a new phrase and pause
# again to replace it; the old one finishes its pass first.

set :take, []          # the phrase you're playing now: note, time, note, time...
set :loop_notes, []
set :loop_gaps, []
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    synth :pluck, note: note, amp: 0.8
    take = get(:take).to_a
    take = [] if take.any? && vt - take[-1] > 1.5     # a long gap starts a new phrase
    set :take, take + [note, vt]
  end
end

live_loop :commit do          # once you pause, what you played becomes the loop
  use_real_time
  sleep 0.2
  take = get(:take).to_a
  if take.length >= 4 && vt - take[-1] > 1.0
    notes = take.each_slice(2).map(&:first)
    times = take.each_slice(2).map(&:last)
    gaps = times.each_cons(2).map { |a, b| [b - a, 0.04].max }
    gaps << [gaps.sum / gaps.length, 0.25].max           # close the loop with a typical gap
    set :loop_notes, notes
    set :loop_gaps, gaps
    set :take, []
  end
end

live_loop :looper do
  notes = get(:loop_notes).to_a
  gaps = get(:loop_gaps).to_a
  if notes.empty? || gaps.length != notes.length
    sleep 0.25                # nothing recorded yet
  else
    notes.each_with_index do |n, i|
      synth :kalimba, note: n, amp: 4     # kalimba is ~15 dB quieter than other synths
      sleep gaps[i]           # seconds: the default 60 bpm makes a beat one second
    end
  end
end
