# Random walk - a melody that wanders one step at a time
# category: Sequencers
# gain: 1.73
# Each note moves a step or two up or down the scale. The walk leans
# towards the last note you played, so a key pulls the tune towards it.

set :target, 67
set :pos, 14
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :target, note if vel > 0
end

live_loop :walk do
  use_bpm 96
  steps = scale(:c3, :dorian, num_octaves: 4).to_a
  cur = get(:pos)
  t = get(:target)
  aim = steps.index(steps.min_by { |s| (s - t).abs })
  step = [-2, -1, -1, 1, 1, 2].choose
  step += (aim <=> cur) if one_in(2)          # lean towards your note
  cur = [[cur + step, 0].max, steps.length - 1].min
  set :pos, cur
  synth :prophet, note: steps[cur], release: 0.3, cutoff: 90, amp: 0.5
  sleep [0.25, 0.25, 0.5].choose
end

live_loop :root, sync: :walk do
  use_bpm 96
  synth :sine, note: :c2, attack: 0.5, release: 3.5, amp: 0.4
  sleep 4
end
