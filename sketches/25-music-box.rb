# Music box - a tune that slowly winds down
# category: Ambient
# gain: 2.04
# It plays by itself, getting slower and quieter as the spring runs out.
# Every key you press winds it back up and adds your note to the tune.

set :wind, 1.0
set :box_tune, [72, 76, 79, 76, 74, 77, 81, 77, 72, 79, 76, 74]
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    synth :pretty_bell, note: note + 12, amp: 0.5, release: 0.8
    set :wind, 1.0
    set :box_tune, (get(:box_tune).to_a + [note + 12]).last(16)
  end
end

with_fx :reverb, room: 0.5, mix: 0.3 do
  live_loop :box do
    w = get(:wind)
    n = get(:box_tune).to_a.ring.tick
    synth :pretty_bell, note: n, amp: 0.05 + 0.4 * w, release: 0.7
    sample :elec_tick, amp: 0.03, rate: 3 if one_in(4)          # the mechanism
    sleep 0.25 / [w, 0.12].max                                  # slower as it unwinds
    set :wind, w * 0.994
  end
end
