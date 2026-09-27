# Vibraphone - soft mallets on metal bars, with the motor on
# category: Keys
# gain: 0.33
# A mellow bell tone through a slow tremolo, like a vibraphone's spinning
# fans. Lovely for slow chords and jazz lines.

with_fx :reverb, room: 0.5, mix: 0.3 do
  with_fx :tremolo, phase: 0.25, depth: 0.4, mix: 0.7 do
    live_loop :vibes do
      use_real_time
      note, vel = sync "/midi*/note_on"
      synth :dull_bell, note: note, amp: vel / 90.0, attack: 0.005, release: 2.2 if vel > 0
    end
  end
end
