# Your arp - the last four notes you play become the arpeggio
# category: Sequencers
# Played up, down, up-and-down, then at random, changing every four bars.
# Play four new notes to change the chord.

set :arp_notes, [60, 64, 67, 71]
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :arp_notes, (get(:arp_notes).to_a + [note]).last(4) if vel > 0
end

live_loop :arp do
  use_bpm 124
  up = get(:arp_notes).to_a.sort
  up += up.map { |n| n + 12 }
  mode = [:up, :down, :updown, :random][(tick(:bar) / 4) % 4]
  seq = case mode
        when :up then up
        when :down then up.reverse
        when :updown then up + up.reverse[1..-2]
        else up.shuffle
        end
  16.times do |i|
    synth :blade, note: seq[i % seq.length], release: 0.15, cutoff: 95, amp: 3.4
    sleep 0.25
  end
end
