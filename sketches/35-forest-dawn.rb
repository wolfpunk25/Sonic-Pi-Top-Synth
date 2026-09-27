# Forest dawn - birdsong over a soft morning pad
# category: Ambient
# No keys needed. Keys play a gentle kalimba among the birds.

define :warble do |base, pan|
  rrand_i(3, 7).times do
    s = synth :sine, note: base + rrand(-2, 3), attack: 0.01, sustain: 0.04, release: 0.05,
      amp: 0.12, note_slide: 0.05, pan: pan
    control s, note: base + rrand(3, 9)
    sleep rrand(0.08, 0.16)
  end
end

with_fx :reverb, room: 0.85, mix: 0.45 do
  live_loop :robin do
    sleep rrand(1.5, 5)
    warble rrand(86, 94), rrand(-0.8, 0.8)
  end

  live_loop :wren, delay: 2 do
    sleep rrand(3, 8)
    warble rrand(92, 99), rrand(-0.8, 0.8)
    warble rrand(92, 99), rrand(-0.8, 0.8) if one_in(2)
  end

  live_loop :dove, delay: 5 do
    sleep rrand(8, 16)
    [76, 72, 72].each do |n|
      synth :sine, note: n, attack: 0.08, sustain: 0.25, release: 0.2, amp: 0.1, pan: -0.4
      sleep 0.5
    end
  end

  live_loop :pad do
    synth :hollow, notes: chord([:g3, :c4, :d4].choose, :add9), attack: 5, sustain: 3, release: 6, amp: 0.6
    sleep 10
  end

  live_loop :breeze do
    synth :bnoise, attack: 4, sustain: 2, release: 4, cutoff: 70, amp: 0.05, pan: rrand(-0.5, 0.5)
    sleep 9
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :kalimba, note: note, amp: vel / 28.0 if vel > 0
  end
end
