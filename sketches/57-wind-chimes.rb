# Wind chimes - chimes that ring with today's wind
# category: Ambient
# gain: 3.37
# No keys needed. The windier it is outside, the more often the chimes are
# caught by a gust, and the louder the breeze. Keys strike a chime yourself.

wind = get(:wx_known) ? get(:wx_wind) : 8
gap = [8.0 / [wind, 1].max, 0.4].max
chimes = [:c6, :d6, :e6, :g6, :a6, :c7]

with_fx :reverb, room: 0.8, mix: 0.45 do
  live_loop :gusts do
    rrand_i(1, 2 + (wind / 6).to_i).times do
      synth :pretty_bell, note: chimes.choose, amp: rrand(0.1, 0.3), release: rrand(2, 4), pan: rrand(-0.7, 0.7)
      sleep rrand(0.06, 0.18)
    end
    sleep rrand(gap, gap * 3)
  end

  live_loop :breeze do
    synth :bnoise, attack: 3, sustain: 2, release: 3, cutoff: 60 + [wind, 30].min,
      amp: 0.04 + [wind / 300.0, 0.1].min, pan: rrand(-0.5, 0.5)
    sleep 7
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :pretty_bell, note: note + 12, amp: vel / 400.0, release: 3 if vel > 0
  end
end
