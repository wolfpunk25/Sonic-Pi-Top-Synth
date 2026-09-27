# Harmony - each key plays a three-note chord in C major
# Every note gets the chord built on it from the white-key scale.
# Black keys snap to the nearest white key.

steps = scale(:c0, :major, num_octaves: 9).to_a

with_fx :reverb, room: 0.7, mix: 0.35 do
  live_loop :harmony do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      i = steps.index(steps.min_by { |s| (s - note).abs })
      synth :saw, notes: [steps[i], steps[i + 2], steps[i + 4]], amp: vel / 250.0,
        attack: 0.02, release: 1.4, cutoff: 90
    end
  end
end
