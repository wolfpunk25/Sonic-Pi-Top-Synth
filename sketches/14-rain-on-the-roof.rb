# Rain on the roof - the sound of today's rain
# No keys needed. Real rain makes it heavier; on a dry day it's a light shower.
# Play keys for a soft piano over the top.

rain = get(:wx_known) ? get(:wx_rain) : 0
heavy = [rain, 0.3].max          # never completely dry, or there'd be nothing to hear
gap = [0.35 / heavy, 0.04].max   # heavier rain, more drops

with_fx :reverb, room: 0.6, mix: 0.4 do
  live_loop :hiss do
    synth :bnoise, attack: 2, sustain: 4, release: 2, cutoff: 70 + [heavy * 10, 25].min,
      amp: 0.15 + [heavy / 10.0, 0.25].min
    sleep 6
  end

  live_loop :drops do
    sample :elec_tick, rate: rrand(0.6, 1.6), amp: rrand(0.05, 0.25), pan: rrand(-0.8, 0.8)
    sleep rrand(gap * 0.5, gap * 1.5)
  end

  live_loop :gutter do
    sleep rrand(2, 5)
    sample :elec_plip, rate: rrand(0.5, 0.8), amp: 0.2, pan: rrand(-0.5, 0.5)
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :piano, note: note, amp: vel / 120.0, hard: 0.3 if vel > 0
  end
end
