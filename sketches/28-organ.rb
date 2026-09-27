# Organ - a tonewheel organ through a slow swirl
# category: Keys
# gain: 0.76
# Each note holds for a moment, like a drawbar organ with a slow rotary speaker.

with_fx :reverb, room: 0.4, mix: 0.2 do
  with_fx :flanger, phase: 3, depth: 3, mix: 0.3, feedback: 0.1 do
    live_loop :organ do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :organ_tonewheel, note: note, amp: vel / 120.0, attack: 0.01, sustain: 0.6, release: 0.3 if vel > 0
    end
  end
end
