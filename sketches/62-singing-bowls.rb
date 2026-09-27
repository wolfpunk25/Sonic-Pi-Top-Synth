# Singing bowls - struck bowls with long, shimmering tails
# category: Ambient
# gain: 0.76
# Each bowl rings with its own out-of-tune overtones, and each overtone is
# doubled a hair sharp, so it slowly beats and swirls. No keys needed; keys
# strike a bowl at your note.

define :bowl do |pitch, level|
  f = midi_to_hz(pitch)
  in_thread do
    [[1.0, 1.0], [2.76, 0.45], [5.4, 0.2], [8.93, 0.08]].each do |ratio, a|
      synth :sine, note: hz_to_midi(f * ratio), attack: 0.005, release: 12 / ratio ** 0.3, amp: a * level
      synth :sine, note: hz_to_midi(f * ratio * 1.003), attack: 0.005, release: 11 / ratio ** 0.3, amp: a * level * 0.7
      sleep 0.01                                     # stagger the voices: easier on the Pi
    end
  end
end

with_fx :reverb, room: 0.9, mix: 0.5 do
  live_loop :strike do
    bowl [:a3, :c4, :d4, :e4, :g4, :a4].choose, rrand(0.3, 0.5)
    sleep rrand(4, 9)
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    bowl note, vel / 220.0 if vel > 0
  end
end
