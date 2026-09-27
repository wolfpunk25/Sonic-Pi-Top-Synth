# Night crickets - a summer night outside
# category: Ambient
# No keys needed. Crickets chirping at their own rates, a frog now and then,
# the odd owl, and a low night pad. Keys play a quiet kalimba.

define :cricket do |pan, pitch|
  rrand_i(3, 5).times do
    synth :sine, note: pitch, attack: 0.003, sustain: 0.012, release: 0.01, amp: 0.15, pan: pan
    sleep 0.035
  end
end

with_fx :reverb, room: 0.7, mix: 0.35 do
  live_loop :cricket_a do
    cricket -0.6, 99
    sleep rrand(0.45, 0.6)
  end

  live_loop :cricket_b, delay: 0.3 do
    cricket 0.5, 101
    sleep rrand(0.6, 0.9)
  end

  live_loop :cricket_c, delay: 1.1 do
    sleep rrand(1, 3)
    3.times { cricket 0.1, 97; sleep 0.2 }
  end

  live_loop :frog do
    sleep rrand(5, 12)
    2.times do
      synth :fm, note: rrand(43, 48), attack: 0.01, release: 0.12, amp: 0.75, depth: 3, divisor: 0.5, pan: -0.3
      sleep 0.18
    end
  end

  live_loop :owl do
    sleep rrand(15, 30)
    [67, 64, 64].each do |n|
      synth :sine, note: n, attack: 0.1, sustain: 0.3, release: 0.3, amp: 0.24, pan: 0.6
      sleep 0.7
    end
  end

  live_loop :night do
    synth :hollow, notes: chord([:a2, :d3, :e3].choose, :m7), attack: 5, sustain: 4, release: 6, amp: 1.35
    sleep 12
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :kalimba, note: note, amp: vel / 12.0 if vel > 0
  end
end
