# Euclid garden - three rhythms drifting in and out of phase
# category: Sequencers
# Each voice spreads its hits evenly over 16 steps; every two bars one of
# them gains or loses a hit, or shifts round. Each key you play gives the
# next voice that pitch and a new number of hits.

set :v_notes, [45, 64, 76]
set :v_hits, [3, 5, 7]
set :v_rot, [0, 0, 0]
set :v_next, 0
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    k = get(:v_next)
    notes = get(:v_notes).to_a.dup     # stored values are frozen; copy before changing
    hits = get(:v_hits).to_a.dup     # stored values are frozen; copy before changing
    notes[k] = note
    hits[k] = 2 + (note % 11)          # the key decides how busy that voice gets
    set :v_notes, notes
    set :v_hits, hits
    set :v_next, (k + 1) % 3
  end
end

with_fx :reverb, room: 0.5, mix: 0.25 do
  live_loop :garden do
    use_bpm 112
    16.times do |i|
      notes, hits, rot = get(:v_notes), get(:v_hits), get(:v_rot)
      synth :fm, note: notes[0], release: 0.3, amp: 0.55, depth: 1 if spread(hits[0], 16).rotate(rot[0])[i]
      synth :pretty_bell, note: notes[1], release: 0.4, amp: 0.25 if spread(hits[1], 16).rotate(rot[1])[i]
      synth :pluck, note: notes[2], amp: 0.35 if spread(hits[2], 16).rotate(rot[2])[i]
      sample :drum_cymbal_closed, amp: 0.15 if i % 4 == 2
      sleep 0.25
    end
  end
end

live_loop :drift, sync: :garden do
  use_bpm 112
  sleep 8
  k = rand_i(3)
  if one_in(2)
    hits = get(:v_hits).to_a.dup     # stored values are frozen; copy before changing
    hits[k] = [[hits[k] + [-1, 1].choose, 1].max, 13].min
    set :v_hits, hits
  else
    rot = get(:v_rot).to_a.dup     # stored values are frozen; copy before changing
    rot[k] = (rot[k] + 1) % 16
    set :v_rot, rot
  end
end
