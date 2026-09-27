# Tech saws - a wide, glossy synth pad
# category: Keys
# gain: 1.10

with_fx :reverb, room: 0.8, mix: 0.4 do
  live_loop :saws do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :tech_saws, note: note, amp: vel / 160.0, attack: 0.08, release: 1.8, cutoff: 105 if vel > 0
  end
end
