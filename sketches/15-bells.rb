# Bells - keys ring slow, shimmering bells
# category: Keys
# Each note also rings an octave up, softer, with a long cathedral tail.

with_fx :reverb, room: 1, mix: 0.6, damp: 0.3 do
  live_loop :bells do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      synth :pretty_bell, note: note, amp: vel / 100.0, release: 4
      synth :pretty_bell, note: note + 12, amp: vel / 300.0, release: 3
      synth :dark_ambience, note: note - 12, amp: 0.4, attack: 0.5, release: 5
    end
  end
end
