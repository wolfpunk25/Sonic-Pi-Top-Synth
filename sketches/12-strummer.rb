# Strummer - each key strums a guitar-like chord
# category: Keys
# Plucked strings, low to high, with a little gap between each.
# The chord is major on white keys and minor on black keys.

black = [1, 3, 6, 8, 10]

with_fx :reverb, room: 0.5, mix: 0.25 do
  live_loop :strum do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      kind = black.include?(note % 12) ? :minor : :major
      notes = chord(note - 12, kind, num_octaves: 2).take(6)
      in_thread do
        notes.each do |n|
          synth :pluck, note: n, amp: 0.6, coef: 0.3
          sleep 0.025
        end
      end
    end
  end
end
