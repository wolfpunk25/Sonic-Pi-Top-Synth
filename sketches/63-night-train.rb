# Night train - a distant train rolling through the dark
# category: Ambient
# gain: 1.79
# A low rumble, wheels clacking over the rail joints, a horn far off and
# now and then a station chime. No keys needed; keys ring soft bells.

with_fx :reverb, room: 0.7, mix: 0.35 do
  live_loop :rumble do
    synth :bnoise, cutoff: 55, attack: 2, sustain: 4, release: 2, amp: 0.35
    synth :sine, note: :a1, attack: 2, sustain: 4, release: 2, amp: 0.12
    sleep 7
  end

  live_loop :wheels do
    with_fx :lpf, cutoff: 80 do
      2.times do
        sample :drum_cymbal_pedal, amp: 0.25, rate: 0.6
        sleep 0.16
        sample :drum_cymbal_pedal, amp: 0.2, rate: 0.55
        sleep 0.54
      end
    end
    sleep rrand(0.4, 0.5)
  end

  live_loop :horn do
    sleep rrand(20, 40)
    with_fx :lpf, cutoff: 70 do
      synth :saw, notes: [:bb2, :d3], attack: 0.3, sustain: 1.4, release: 1.5, amp: 0.2
    end
  end

  live_loop :station do
    sleep rrand(30, 60)
    [:e5, :c5, :g4].each do |n|
      synth :pretty_bell, note: n, amp: 0.15, release: 2
      sleep 0.6
    end
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :pretty_bell, note: note, amp: vel / 400.0, release: 2 if vel > 0
  end
end
