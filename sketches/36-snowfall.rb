# Snowfall - sparse glassy bells, slowly falling
# category: Ambient
# No keys needed; twice as many flakes when it's really snowing.
# Keys add your own flakes, an octave up.

code = get(:wx_known) ? get(:wx_code) : 0
snowing = [71, 73, 75, 77, 85, 86].include?(code)
notes = scale(:e5, :major_pentatonic, num_octaves: 2)

with_fx :reverb, room: 1, mix: 0.7 do
  live_loop :flakes do
    synth [:pretty_bell, :dull_bell].choose, note: notes.choose, amp: rrand(0.08, 0.2),
      release: rrand(1, 3), pan: rrand(-0.8, 0.8)
    sleep [0.5, 1, 1.5, 2, 3].choose / (snowing ? 2.0 : 1.0)
  end

  live_loop :hush do
    synth :bnoise, cutoff: 60, attack: 4, sustain: 4, release: 4, amp: 0.05
    sleep 10
  end

  live_loop :pad do
    synth :hollow, notes: chord([:e3, :a2, :b2].choose, :major7), attack: 5, sustain: 4, release: 7, amp: 0.5
    sleep 12
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :pretty_bell, note: note + 12, amp: vel / 450.0, release: 3 if vel > 0
  end
end
