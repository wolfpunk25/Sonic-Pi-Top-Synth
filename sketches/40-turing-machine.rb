# Turing machine - a looping pattern that slowly rewrites itself
# category: Sequencers
# gain: 1.24
# After the Music Thinking Machines module: a 16-step loop where, as each
# step comes round, it may flip. Locked, it repeats exactly; unlocked, it drifts.
# Keys below middle C lock the loop. Middle C and above unlock it: the higher
# the key, the faster it changes.

set :bits, [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 1]
set :chance, 0.12
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    set :chance, note < 60 ? 0.0 : [[(note - 60) / 24.0, 0.03].max, 0.9].min   # (Sonic Pi's clamp takes one argument)
  end
end

live_loop :turing do
  use_bpm 115
  notes = scale(:e3, :minor_pentatonic, num_octaves: 2).to_a
  bits = get(:bits).to_a.dup     # stored values are frozen; copy before changing
  chance = get(:chance)
  16.times do
    b = bits.shift
    b = 1 - b if rand < chance
    bits << b
    value = bits.first(5).each_with_index.sum { |bit, k| bit << k }   # 0..31
    if value > 5
      synth :fm, note: notes[value * notes.length / 32], amp: 0.6, release: 0.2, depth: 0.8, divisor: 2
    end
    sleep 0.25
  end
  set :bits, bits
end

live_loop :pulse, sync: :turing do
  use_bpm 115
  sample :bd_tek, amp: 0.8
  sleep 1
end
