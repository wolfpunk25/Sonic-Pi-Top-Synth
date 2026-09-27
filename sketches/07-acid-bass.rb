# Acid bass - keys set the root of a squelchy bassline
# A TB-303 pattern with a slowly opening filter, over a four-on-the-floor kick.

set :bass_root, 40            # E2, as a MIDI number so the pattern can add to it

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :bass_root, note - 12 * ((note - 40) / 12) if vel > 0   # fold into the bass octave
end

live_loop :kick do
  use_bpm 124
  sample :bd_tek, amp: 1.3
  sleep 1
end

live_loop :hats, sync: :kick do
  use_bpm 124
  sleep 0.5
  sample :drum_cymbal_pedal, amp: 0.4
  sleep 0.5
end

live_loop :bass, sync: :kick do
  use_bpm 124
  use_synth :tb303
  pattern = [0, 0, 12, 0, 7, 0, 10, 12]
  cut = range(60, 115, 1.5).mirror.tick(:cut)
  8.times do |i|
    play get(:bass_root) + pattern[i], release: 0.18, cutoff: cut, res: 0.85, wave: 0, amp: 0.7
    sleep 0.25
  end
end
