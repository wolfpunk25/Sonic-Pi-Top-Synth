# Airport loops - long loops of different lengths drifting in and out of line
# category: Ambient
# After Brian Eno's Music for Airports: each voice sings one note on its own
# cycle, so the combination never quite repeats. Each key gives the next
# voice your note instead.

set :loop_notes, [:f4, :ab4, :c5, :db5, :eb5, :f5, :ab3].map { |n| note(n) }
set :loop_next, 0
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)
lengths = [17.8, 20.1, 23.6, 25.2, 29.4, 31.1, 19.3]

live_loop :listen do
  use_real_time
  n, vel = sync "/midi*/note_on"
  if vel > 0
    k = get(:loop_next)
    notes = get(:loop_notes).to_a.dup     # stored values are frozen; copy before changing
    notes[k] = n
    set :loop_notes, notes
    set :loop_next, (k + 1) % notes.length
  end
end

with_fx :reverb, room: 1, mix: 0.65 do
  lengths.each_with_index do |len, i|
    live_loop "voice_#{i}".to_sym, delay: i * 1.3 do
      n = get(:loop_notes)[i]
      synth :hollow, note: n, attack: 2, sustain: 1.5, release: 4, amp: 0.7, pan: (i - 3) / 4.0
      synth :sine, note: n, attack: 2.5, sustain: 1, release: 4, amp: 0.12, pan: (i - 3) / 4.0
      sleep len
    end
  end
end
