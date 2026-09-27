# Chord wanderer - an endless chord progression that finds its own way
# category: Sequencers
# gain: 1.63
# Every two bars the chord moves somewhere related (up a fourth or fifth,
# to a relative minor...). Play a key and the next chord is built on it.

set :cw_root, 48
set :cw_force, -1
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :cw_force, note if vel > 0
end

with_fx :reverb, room: 0.7, mix: 0.4 do
  live_loop :progression do
    use_bpm 80
    forced = get(:cw_force)
    if forced >= 0
      root = 48 + forced % 12
      set :cw_force, -1
    else
      root = 48 + (get(:cw_root) + [5, 7, 9, 3, 2, 10].choose) % 12
    end
    set :cw_root, root
    quality = [:major, :minor, :major7, :m7, :sus4, :add9].choose
    notes = chord(root, quality)
    synth :hollow, notes: notes, attack: 0.5, sustain: 6, release: 2, amp: 0.8
    synth :fm, note: root - 12, release: 7, amp: 0.4, depth: 0.5, divisor: 1
    8.times do
      synth :pluck, note: (notes + notes.map { |n| n + 12 }).choose, amp: 0.35
      sleep 1
    end
  end
end
