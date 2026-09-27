# Late night jazz - a walking bass trio you can play over
# category: Grooves
# ii-V-I-vi on electric piano, walking bass and a swung ride.
# Keys below G3 change the key; higher keys play electric piano.

set :jazz_key, 48      # C
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    if note < 55
      set :jazz_key, note
    else
      synth :rhodey, note: note, amp: vel / 110.0
    end
  end
end

define :fold_bass do |n|
  n -= 12 while n > 47
  n += 12 while n < 33
  n
end

live_loop :band do
  use_bpm 116
  k = get(:jazz_key)
  prog = [[k + 2, :m7], [k + 7, "7"], [k, :major7], [k + 9, :m7]]
  prog.each_with_index do |(root, quality), i|
    r = fold_bass(root)
    nxt = fold_bass(prog[(i + 1) % 4][0])
    third = quality == :m7 ? 3 : 4
    walk = [r, r + third, r + 7, nxt + [-1, 1].choose]
    synth :rhodey, notes: chord(root + 12, quality), amp: 0.35, release: 1.5
    4.times do |b|
      synth :fm, note: walk[b], release: 0.5, amp: 0.6, depth: 0.4, divisor: 1
      sample :drum_cymbal_soft, amp: 0.25, rate: 1.2
      sleep 0.66
      sample :drum_cymbal_soft, amp: 0.15, rate: 1.2 if b.odd?          # the swung skip beat
      synth :rhodey, notes: chord(root + 12, quality), amp: 0.2, release: 0.3 if b == 1 && one_in(2)
      sleep 0.34
    end
  end
end
