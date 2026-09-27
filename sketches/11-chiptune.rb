# Chiptune - 8-bit arpeggios under your fingers
# Each key fires a fast home-computer arpeggio over a chip bass and noise drums.

live_loop :keys do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    in_thread do
      use_synth :chiplead
      chord(note, :major).take(3).each do |n|   # a quick up-arpeggio, 30 ms per step
        play n, amp: 0.5, release: 0.06
        sleep 0.03
      end
      play note + 12, amp: 0.5, release: 0.25
    end
  end
end

live_loop :chipbass do
  use_bpm 140
  use_synth :chipbass
  play (ring :c2, :c2, :g2, :a2).tick, release: 0.2, amp: 0.6
  sleep 1
end

live_loop :chipdrums, sync: :chipbass do
  use_bpm 140
  synth :chipnoise, freq_band: 2, release: 0.05, amp: 0.5
  sleep 0.5
  synth :chipnoise, freq_band: 14, release: 0.12, amp: 0.4
  sleep 0.5
end
