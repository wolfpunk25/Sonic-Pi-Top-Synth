# Wave melody - a tune traced by two slow waves
# category: Sequencers
# gain: 2.02
# Two sine waves at unrelated speeds are added together and read off a
# scale, so the melody rises and falls in long, never-quite-repeating arcs.
# A key sets the key of the scale.

set :wm_root, :d3
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    r = note
    r -= 12 while r > 55
    r += 12 while r < 43
    set :wm_root, r
  end
end

with_fx :reverb, room: 0.6, mix: 0.3 do
  live_loop :waves do
    use_bpm 96
    t = tick * 0.25
    notes = scale(get(:wm_root), :dorian, num_octaves: 3)
    v = (Math.sin(t * 0.37) + Math.sin(t * 0.37 * 1.618) * 0.6) / 1.6   # -1..1
    i = ((v + 1) / 2 * (notes.length - 1)).round
    synth :blade, note: notes[i], release: 0.35, cutoff: 95, amp: 0.8 unless one_in(6)
    synth :sine, note: notes[0], release: 1.8, amp: 0.25 if tick(:bar) % 8 == 0
    sleep 0.25
  end
end
