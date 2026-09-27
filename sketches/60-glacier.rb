# Glacier - vast, very slow chords that barely move
# category: Ambient
# gain: 2.61
# No keys needed. Each chord swells in over ten seconds and changes every
# twenty, over a deep sub and a distant choir. Keys hold long, soft notes.

with_fx :reverb, room: 1, mix: 0.7, damp: 0.6 do
  live_loop :ice do
    c = [chord(:c3, :major7), chord(:a2, :m9), chord(:f2, :major7), chord(:g2, :sus4)].ring.tick
    synth :dark_ambience, notes: c, attack: 10, sustain: 6, release: 10, amp: 0.7
    synth :hollow, notes: c, attack: 10, sustain: 6, release: 10, amp: 0.5
    synth :sine, note: c[0] - 12, attack: 8, sustain: 8, release: 8, amp: 0.25
    sleep 20
  end

  live_loop :choir do
    sleep rrand(12, 25)
    sample :ambi_choir, rate: [0.5, 0.75].choose, amp: 0.3, pan: rrand(-0.5, 0.5)
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :hollow, note: note, attack: 1.5, sustain: 2, release: 6, amp: vel / 70.0 if vel > 0
  end
end
