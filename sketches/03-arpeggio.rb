# Arpeggio - the last key you press sets the root
# It starts on C straight away; play a key to move it.

set :root, :c3

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :root, note if vel > 0
end

live_loop :arp do
  use_bpm 120
  use_synth :tb303
  play chord(get(:root), :minor7, num_octaves: 2).tick, release: 0.2, cutoff: rrand(70, 110), amp: 0.6
  sleep 0.25
end
