# Ratchets - a techno sequence with bursts of quick repeats
# category: Sequencers
# gain: 1.01
# A 16-step bassline where some steps "ratchet" into 2-4 fast repeats.
# Keys set the root; the higher the key, the more ratchets.

set :rat_root, 45
set :rat_amount, 0.2
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    r = note
    r -= 12 while r > 51
    r += 12 while r < 40
    set :rat_root, r
    set :rat_amount, [[note - 36, 0].max, 48].min / 60.0
  end
end

live_loop :ratchets do
  use_bpm 128
  root, amount = get(:rat_root), get(:rat_amount)
  [0, 0, 12, 0, 3, 0, 7, 10, 0, 0, 12, 0, 3, 5, 7, 0].each do |off|
    n = rand < amount ? [2, 3, 4].choose : 1
    n.times do
      synth :tb303, note: root + off, release: 0.1, cutoff: rrand(70, 105), res: 0.8, amp: 0.55, wave: 0
      sleep 0.25 / n
    end
  end
end

live_loop :kick, sync: :ratchets do
  use_bpm 128
  sample :bd_tek, amp: 1.1
  sleep 1
end
