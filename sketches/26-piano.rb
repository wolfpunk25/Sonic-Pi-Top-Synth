# Piano - a grand piano in a warm room
# category: Keys
# gain: 0.63

with_fx :reverb, room: 0.55, mix: 0.3 do
  live_loop :piano do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :piano, note: note, amp: vel / 90.0, hard: 0.45, sustain: 0.5, release: 1.5 if vel > 0   # no vel: opt - it clips
  end
end
