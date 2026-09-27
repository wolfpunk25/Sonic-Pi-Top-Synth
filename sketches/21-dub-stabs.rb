# Dub stabs - chords that echo away over a slow dub groove
# category: Grooves
# Each key fires a short minor-chord stab into a long echo.
# Keys below A3 move the bassline to that note.

set :dub_root, 45
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :drums do
  use_bpm 72
  sample :bd_fat, amp: 1.6
  sleep 1
  sample :drum_cymbal_closed, amp: 0.25
  sleep 0.5
  sample :drum_cymbal_closed, amp: 0.2
  sleep 0.5
  sample :sn_dub, amp: 0.9
  sleep 1
  sample :drum_cymbal_closed, amp: 0.25
  sleep 1
end

live_loop :bass, sync: :drums do
  use_bpm 72
  r = get(:dub_root)
  [0, 0, 7, 10, 12, 10, 7, 3].each do |i|
    synth :fm, note: r - 12 + i, release: 0.45, amp: 0.7, depth: 0.6, divisor: 1
    sleep 0.5
  end
end

with_fx :echo, phase: 0.625, decay: 7, mix: 0.5 do
  with_fx :lpf, cutoff: 95 do
    live_loop :stabs do
      use_real_time
      note, vel = sync "/midi*/note_on"
      if vel > 0
        if note < 57
          set :dub_root, note
        else
          synth :dsaw, notes: chord(note, :minor), release: 0.12, amp: 0.5, detune: 0.2
        end
      end
    end
  end
end
