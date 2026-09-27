# Wobble bass - a growling bass that wobbles in time
# category: Keys
# gain: 0.83
# Each note is an octave down with a filter wobbling four times a beat at
# 140 bpm. Best in the lower octaves; try it over Techno or Drum and bass.

live_loop :wobble do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    use_bpm 140
    synth :mod_saw, note: note - 12, amp: vel / 150.0, mod_phase: 0.25, mod_range: 5, mod_wave: 3,
      cutoff: 85, attack: 0.01, sustain: 0.8, release: 0.3
  end
end
