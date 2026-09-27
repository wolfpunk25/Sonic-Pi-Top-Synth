# Marimba - warm wooden mallets
# category: Keys
# gain: 0.54
# A soft FM mallet with a short, round decay. Lower notes ring longer.

with_fx :reverb, room: 0.35, mix: 0.2 do
  live_loop :marimba do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      synth :fm, note: note, amp: vel / 110.0, attack: 0.002, release: 0.25 + [[84 - note, 0].max, 40].min / 60.0,
        depth: 1.2, divisor: 4
      synth :sine, note: note, amp: vel / 250.0, attack: 0.002, release: 0.3
    end
  end
end
