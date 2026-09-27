# Hoover - the old-school rave sound
# category: Keys
# Low notes are the classic; try the bottom octave.

with_fx :reverb, room: 0.5, mix: 0.2 do
  live_loop :hoover do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :hoover, note: note, amp: vel / 1000.0, attack: 0.05, sustain: 0.4, release: 0.6, cutoff: 120 if vel > 0
  end
end
