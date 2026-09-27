# Underwater - bubbles, a deep hum and distant whale song
# category: Ambient
# gain: 1.17
# No keys needed. Everything is muffled as if heard below the surface.
# Keys ring soft, muted bells.

with_fx :reverb, room: 0.9, mix: 0.5 do
  with_fx :lpf, cutoff: 75 do
    live_loop :hum do
      synth :sine, note: :e1, attack: 4, sustain: 4, release: 4, amp: 0.5
      sleep 10
    end

    live_loop :bubbles do
      rrand_i(2, 6).times do
        s = synth :sine, note: rrand(72, 90), attack: 0.005, sustain: 0.02, release: 0.04,
          amp: 0.2, note_slide: 0.05, pan: rrand(-0.8, 0.8)
        control s, note: rrand(90, 100)
        sleep rrand(0.05, 0.2)
      end
      sleep rrand(1, 4)
    end

    live_loop :whale do
      sleep rrand(8, 18)
      s = synth :hollow, note: rrand(42, 50), attack: 1.5, sustain: 3, release: 3, amp: 1.2, note_slide: 3
      control s, note: rrand(50, 58)
    end

    live_loop :keys do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :pretty_bell, note: note, amp: vel / 200.0, release: 3 if vel > 0
    end
  end
end
