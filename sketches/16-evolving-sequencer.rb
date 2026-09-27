# Evolving sequencer - a pattern that keeps changing, and you steer it
# category: Sequencers
# gain: 1.05
# A 16-step melody mutates a little every bar. Your notes push it:
#   below middle C   - changes the key (the bass follows)
#   middle C and up  - your note is written into the pattern, and the interval
#                      above the key picks the mode (minor 3rd: minor, major 3rd: major...)
#   playing a lot    - more notes, faster changes, brighter filter, then hats and kick.
#                      Leave it alone and it calms back down.

set :root, 50                     # D3
set :mode, :dorian
set :energy, 0.3
set :step, 0
set :pattern, [0, -1, 2, -1, 4, 3, -1, 2, 0, -1, 5, 4, -1, 2, 1, -1]   # scale degrees, -1 = rest
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

modes = { 1 => :phrygian, 3 => :minor, 4 => :major, 6 => :lydian,
          8 => :minor, 9 => :dorian, 10 => :mixolydian, 11 => :major }

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    set :energy, [get(:energy) + 0.12, 1.0].min
    if note < 60
      set :root, note
    else
      mode = modes[(note - get(:root)) % 12]
      set :mode, mode if mode
      notes = scale(get(:root) + 12, get(:mode), num_octaves: 3).to_a
      degree = notes.index(notes.min_by { |s| (s - note).abs })
      p = get(:pattern).to_a.dup     # stored values are frozen; copy before changing
      p[(get(:step) + 1) % 16] = degree
      set :pattern, p
    end
  end
end

live_loop :seq do
  use_bpm 108
  16.times do |i|
    set :step, i
    e = get(:energy)
    d = get(:pattern)[i]
    if d >= 0 && rand < 0.55 + e * 0.45
      notes = scale(get(:root) + 12, get(:mode), num_octaves: 3)
      synth :tb303, note: notes[d], release: 0.18, cutoff: 62 + e * 50, res: 0.7,
        amp: (i % 4 == 0 ? 0.65 : 0.45), wave: 1
    end
    sleep 0.25
  end
end

live_loop :evolve, sync: :seq do
  use_bpm 108
  sleep 4
  e = get(:energy)
  p = get(:pattern).to_a.dup     # stored values are frozen; copy before changing
  (1 + (e * 4).to_i).times do
    i = rand_i(16)
    r = rand
    if r < 0.4                                        # nudge a note up or down
      p[i] = p[i] < 0 ? rand_i(8) : [[p[i] + [-2, -1, 1, 2].choose, 0].max, 13].min
    elsif r < 0.6                                     # rests are likelier when it's calm
      p[i] = -1 if one_in(2 + (e * 4).to_i)
    elsif r < 0.8                                     # swap two steps
      j = rand_i(16)
      p[i], p[j] = p[j], p[i]
    else                                              # repeat a motif from a beat earlier
      p[i] = p[(i + 12) % 16]
    end
  end
  set :pattern, p
  set :energy, e * 0.85                               # calms down when left alone
end

live_loop :bass, sync: :seq do
  use_bpm 108
  b = get(:root)
  b -= 12 while b > 47
  b += 12 while b < 36
  synth :fm, note: b, release: 1.6, amp: 0.5, depth: 1.2, divisor: 2
  sleep 2
end

live_loop :drums, sync: :seq do
  use_bpm 108
  e = get(:energy)
  sample :bd_tek, amp: 0.9 if e > 0.7
  sleep 0.5
  sample :drum_cymbal_closed, amp: 0.3 if e > 0.45
  sleep 0.5
end
