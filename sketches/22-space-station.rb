# Space station - hums, telemetry and distant signals
# category: Ambient
# gain: 1.68
# No keys needed. Keys fire laser pings that swoop down an octave.

with_fx :reverb, room: 0.9, mix: 0.5 do
  live_loop :hum do
    sample :ambi_haunted_hum, rate: 0.5, amp: 0.5
    sleep 8
  end

  live_loop :telemetry do
    use_bpm 120
    8.times do
      synth :beep, note: scale(:c6, :minor_pentatonic).choose, release: 0.05, amp: 0.12 if one_in(2)
      sleep 0.25
    end
    sleep [0, 2, 4].choose
  end

  live_loop :signal do
    sleep rrand(5, 12)
    synth :zawa, note: [:e2, :a2, :b2].choose, attack: 1, sustain: 2, release: 3, amp: 0.4,
      phase: rrand(0.5, 3), cutoff: rrand(70, 100)
  end

  live_loop :swoosh do
    sleep rrand(10, 20)
    sample [:ambi_swoosh, :misc_cineboom].choose, amp: 0.4, rate: [0.5, 1].choose
  end

  live_loop :lasers do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      s = synth :tri, note: note + 12, sustain: 0.25, release: 0.3, amp: 0.4, note_slide: 0.4
      control s, note: note
    end
  end
end
