# Tidal - waves on a shore, and the odd gull
# category: Ambient
# gain: 1.26
# No keys needed. Keys ring soft bells over the water.

with_fx :reverb, room: 0.8, mix: 0.4 do
  live_loop :waves do
    s = synth :bnoise, attack: rrand(2, 4), sustain: rrand(0.5, 2), release: rrand(3, 6),
      cutoff: 60, cutoff_slide: 3, amp: rrand(0.3, 0.55), pan: rrand(-0.6, 0.6), pan_slide: 5
    control s, cutoff: rrand(95, 110), pan: rrand(-0.6, 0.6)
    sleep rrand(5, 8)
  end

  live_loop :backwash, delay: 3 do
    synth :pnoise, attack: 1, sustain: 1, release: 3, cutoff: 75, amp: 0.12, pan: rrand(-0.8, 0.8)
    sleep rrand(6, 9)
  end

  live_loop :deep do
    synth :sine, note: :e2, attack: 6, sustain: 4, release: 6, amp: 0.25
    synth :hollow, note: [:b2, :e3, :gs3].choose, attack: 6, sustain: 4, release: 6, amp: 0.4
    sleep 12
  end

  live_loop :gulls do
    sleep rrand(12, 25)
    rrand_i(1, 3).times do
      s = synth :sine, note: 88, sustain: 0.25, release: 0.15, amp: 0.05, note_slide: 0.3, pan: rrand(-0.9, 0.9)
      control s, note: 81
      sleep 0.5
    end
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :pretty_bell, note: note, amp: vel / 300.0, release: 3 if vel > 0
  end
end
