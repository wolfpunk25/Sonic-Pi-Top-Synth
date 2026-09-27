# Phase - two players, one tune, slowly drifting apart
# The same eight notes on left and right, one a touch faster, so the
# pattern slides against itself (after Steve Reich's Piano Phase).
# Play eight notes to give them a new tune.

set :tune, [64, 66, 71, 73, 74, 66, 64, 73]

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :tune, (get(:tune).to_a + [note]).last(8) if vel > 0
end

with_fx :reverb, room: 0.4, mix: 0.25 do
  live_loop :left do
    use_bpm 100
    get(:tune).to_a.each do |n|
      synth :kalimba, note: n, amp: 0.8, pan: -0.7
      sleep 0.25
    end
  end

  live_loop :right do
    use_bpm 101.5
    get(:tune).to_a.each do |n|
      synth :kalimba, note: n, amp: 0.8, pan: 0.7
      sleep 0.25
    end
  end
end
