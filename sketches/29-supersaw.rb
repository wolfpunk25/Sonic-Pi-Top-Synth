# Supersaw - a huge detuned trance lead
# category: Keys

with_fx :reverb, room: 0.6, mix: 0.3 do
  with_fx :echo, phase: 0.375, decay: 2, mix: 0.2 do
    live_loop :supersaw do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :supersaw, note: note, amp: vel / 250.0, release: 0.6, cutoff: 110, detune: 0.2 if vel > 0
    end
  end
end
