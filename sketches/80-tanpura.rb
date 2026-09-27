# Tanpura - the shimmering drone behind Indian classical music
# category: Ambient
# gain: 2.51
# Four strings plucked in an endless cycle (fifth, two high tonics, low
# tonic), each ringing long enough to blur into a living, buzzing hum. No
# keys needed; keys play a soft voice-like tone over it.

with_fx :reverb, room: 0.8, mix: 0.4 do
  live_loop :strings do
    [:g2, :c3, :c3, :c2].each do |n|
      synth :pluck, note: n, amp: 0.9, coef: 0.02, pluck_decay: 60
      synth :sine, note: n + 12, attack: 0.3, release: 4, amp: 0.08       # the jivari shimmer
      sleep 1.3
    end
    sleep 0.6
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :hollow, note: note, attack: 0.3, sustain: 0.6, release: 2.5, amp: vel / 60.0 if vel > 0
  end
end
