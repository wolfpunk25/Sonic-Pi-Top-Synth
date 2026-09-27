# Aurora - slow shifting chords under a breathing filter
# category: Ambient
# No keys needed. Keys add soft high notes that hang in the air.

progression = [chord(:d3, :m9), chord(:bb2, :major7), chord(:f3, :add9), chord(:c3, :sus2)]

with_fx :reverb, room: 1, mix: 0.6 do
  with_fx :lpf, cutoff: 80 do |filter|
    live_loop :breath do
      control filter, cutoff: rrand(65, 105), cutoff_slide: 8
      sleep 8
    end

    live_loop :chords do
      c = progression.ring.tick
      synth :hollow, notes: c, attack: 4, sustain: 4, release: 6, amp: 0.8
      synth :dark_ambience, notes: c, attack: 4, sustain: 4, release: 6, amp: 0.45
      sleep 10
    end
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :sine, note: note + 12, attack: 0.5, release: 4, amp: 0.25 if vel > 0
  end
end
