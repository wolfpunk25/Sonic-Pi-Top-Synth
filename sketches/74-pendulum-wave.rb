# Pendulum wave - twelve pendulums drifting in and out of step
# category: Sequencers
# gain: 2.77
# Each pendulum is a little shorter than the last, so it swings a little
# faster; each chimes as it passes the middle. They start together, spread
# into patterns and waves, and every 60 seconds line up again. A key sets
# the key of the chimes.

set :pw_root, :c4
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :pw_root, note if vel > 0
end

# every 60 s all twelve chime at once; the compressor keeps that from clipping
with_fx :compressor, threshold: 0.35, slope_above: 0.4, clamp_time: 0.005, relax_time: 0.15 do
with_fx :reverb, room: 0.6, mix: 0.3 do
  12.times do |k|
    live_loop "pendulum_#{k}".to_sym do
      notes = scale(get(:pw_root), :major_pentatonic, num_octaves: 3)
      synth :kalimba, note: notes[k], amp: 2.5, pan: (k - 5.5) / 7.0
      sleep 30.0 / (20 + k)          # swings 20, 21 ... 31 times a minute; all meet again at 60 s
    end
  end
end
end
