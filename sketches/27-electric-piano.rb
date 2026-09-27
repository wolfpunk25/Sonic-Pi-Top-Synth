# Electric piano - a mellow Rhodes with gentle tremolo
# category: Keys
# gain: 0.34

with_fx :reverb, room: 0.45, mix: 0.25 do
  with_fx :tremolo, phase: 0.3, depth: 0.25, mix: 0.6 do
    live_loop :rhodes do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :rhodey, note: note, amp: vel / 90.0, release: 1.4 if vel > 0
    end
  end
end
