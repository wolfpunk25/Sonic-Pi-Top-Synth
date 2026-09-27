# Polymeter - loops of 3, 4, 5 and 7 steps playing together
# category: Sequencers
# gain: 1.57
# Four short patterns at the same speed but different lengths, so they only
# line up again every 420 steps. Each key replaces one note, working through
# the four patterns in turn.

set :pm_0, [45, 52, 48]
set :pm_1, [64, 67, 69, 67]
set :pm_2, [72, 76, 79, 74, 76]
set :pm_3, [84, 88, 86, 91, 84, 79, 81]
set :pm_turn, 0
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    k = get(:pm_turn)
    key = "pm_#{k % 4}".to_sym
    pat = get(key).to_a.dup     # stored values are frozen; copy before changing
    pat[(k / 4) % pat.length] = note
    set key, pat
    set :pm_turn, k + 1
  end
end

live_loop :three do
  use_bpm 110
  synth :fm, note: get(:pm_0).to_a.ring.tick, release: 0.3, amp: 0.6, depth: 0.6, divisor: 1
  sleep 0.5
end

live_loop :four, sync: :three do
  use_bpm 110
  synth :pluck, note: get(:pm_1).to_a.ring.tick, amp: 0.6
  sleep 0.5
end

live_loop :five, sync: :three do
  use_bpm 110
  synth :kalimba, note: get(:pm_2).to_a.ring.tick, amp: 3
  sleep 0.5
end

live_loop :seven, sync: :three do
  use_bpm 110
  synth :pretty_bell, note: get(:pm_3).to_a.ring.tick, amp: 0.15, release: 0.4
  sleep 0.5
end
