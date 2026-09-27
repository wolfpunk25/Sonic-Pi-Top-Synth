# Drone choir - build a slowly breathing chord, one key at a time
# category: Ambient
# gain: 1.06
# Press a note to add it to the drone; press it again to take it out.
# Up to six voices; the oldest drops out when you add a seventh.

set :drone, [45, 52]
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    d = get(:drone).to_a.dup
    if d.include?(note)
      d.delete(note)
    else
      d = (d + [note]).last(6)
    end
    set :drone, d
  end
end

with_fx :reverb, room: 0.95, mix: 0.55 do
  live_loop :choir do
    d = get(:drone)
    level = [2.0 / [d.length, 1].max, 1.1].min
    d.each do |n|
      # 8-second notes restarted every 4 seconds overlap into one long sound;
      # voices start 30 ms apart so the Pi isn't asked to start them all at once
      synth :hollow, note: n, attack: 2, sustain: 2, release: 4, amp: level
      sleep 0.03
      synth :dark_ambience, note: n - 12, attack: 2, sustain: 2, release: 4, amp: level * 0.5
      sleep 0.03
    end
    sleep 4 - d.length * 0.06
  end

  live_loop :shimmer do
    d = get(:drone)
    synth :sine, note: d.to_a.choose + 24, amp: 0.07, attack: 1, release: 2 unless d.to_a.empty?
    sleep 2
  end
end
