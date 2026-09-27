# Loop what you play - your last 8 notes become a looping phrase
# Play a few notes; they repeat in order until you play more.

set :phrase, [:c4, :e4, :g4, :b4]

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    synth :pluck, note: note, amp: 0.8
    set :phrase, ((get(:phrase) || []).to_a + [note]).last(8)
  end
end

live_loop :phrase do
  use_bpm 96
  use_synth :kalimba
  notes = (get(:phrase) || []).to_a
  sleep 0.5 if notes.empty?     # the phrase may not be set yet on the very first pass
  notes.each do |n|
    play n, amp: 0.7
    sleep 0.5
  end
end
