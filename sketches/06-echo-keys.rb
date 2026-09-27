# Echo keys - every note repeats and fades
# category: Keys
# gain: 0.73
# A bright synth through a dotted-eighth echo. Play slowly and let it ring.

with_fx :echo, phase: 0.375, decay: 6, mix: 0.45 do
  with_fx :reverb, room: 0.6, mix: 0.3 do
    live_loop :keys do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :blade, note: note, amp: vel / 110.0, attack: 0.01, release: 0.8, cutoff: 105 if vel > 0
    end
  end
end
