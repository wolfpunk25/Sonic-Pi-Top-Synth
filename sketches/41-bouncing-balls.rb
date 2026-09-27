# Bouncing balls - every key drops a ball that bounces
# category: Sequencers
# gain: 1.79
# Each note repeats faster and quieter, like a ball settling on the floor.
# Drop several and they bounce against each other. With no keys, a ball
# drops by itself every few seconds.

define :bounce do |note, pan|
  in_thread do
    gap, amp = 0.6, 1.0
    while gap > 0.03
      synth :pluck, note: note, amp: amp * 0.9, pan: pan
      synth :sine, note: note + 12, amp: amp * 0.08, release: 0.1, pan: pan
      sleep gap
      gap *= 0.78
      amp *= 0.86
    end
  end
end

live_loop :drop do
  use_real_time
  note, vel = sync "/midi*/note_on"
  bounce note, rrand(-0.6, 0.6) if vel > 0
end

live_loop :by_itself do
  sleep rrand(3, 7)
  bounce scale(:c4, :major_pentatonic, num_octaves: 2).choose, rrand(-0.8, 0.8)
end
