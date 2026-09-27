# Strings - a soft string section that swells in
# category: Keys
# gain: 0.72
# A slow bow-like attack and a long release, so held notes and chords bloom.
# Play slowly and let each note arrive.

with_fx :reverb, room: 0.85, mix: 0.45 do
  live_loop :strings do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      synth :blade, note: note, amp: vel / 130.0, attack: 0.4, sustain: 0.8, release: 2, cutoff: 90
      synth :blade, note: note - 12, amp: vel / 400.0, attack: 0.5, sustain: 0.6, release: 2, cutoff: 80
    end
  end
end
