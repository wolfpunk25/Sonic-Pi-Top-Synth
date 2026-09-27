# Canon - whatever you play comes back as a round
# category: Sequencers
# gain: 2.09
# A second voice answers a fifth higher two beats later, and a third an
# octave up two beats after that, like a round sung by three people. Play
# slow phrases and let them tangle.

with_fx :reverb, room: 0.6, mix: 0.3 do
  live_loop :canon do
    use_real_time
    note, vel = sync "/midi*/note_on"
    if vel > 0
      synth :pluck, note: note, amp: 0.8
      in_thread do
        use_bpm 84
        sleep 2
        synth :kalimba, note: note + 7, amp: 3, pan: -0.5
        sleep 2
        synth :pretty_bell, note: note + 12, amp: 0.25, release: 1, pan: 0.5
      end
    end
  end
end
