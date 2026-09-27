# Lead - a singing synth lead with a little echo
# category: Keys
# gain: 0.62
# A warm, vocal lead sound for melodies over the grooves.

with_fx :echo, phase: 0.375, decay: 1.5, mix: 0.2 do
  with_fx :reverb, room: 0.5, mix: 0.25 do
    live_loop :lead do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :winwood_lead, note: note, amp: vel / 120.0, attack: 0.02, sustain: 0.3, release: 0.5 if vel > 0
    end
  end
end
