# Dembow - the reggaeton rhythm at 94 bpm
# category: Grooves
# keys: last
# gain: 1.08
# Boom, ch-boom-chick: the kick on every beat with the snare's famous
# syncopation, plus a simple bass. Your keys play your last Keys sound.

live_loop :gr_drums do
  use_bpm 94
  4.times do
    sample :bd_808, amp: 1.5
    sleep 0.75
    sample :sn_generic, amp: 0.6, rate: 1.2
    sleep 0.25
    sample :bd_808, amp: 1.2
    sleep 0.5
    sample :sn_generic, amp: 0.6, rate: 1.2
    sleep 0.5
  end
end

live_loop :gr_hats, sync: :gr_drums do
  use_bpm 94
  sample :hat_tap, amp: 0.2
  sleep 0.5
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 94
  [:a1, :a1, :f1, :g1].each do |n|
    synth :sine, note: n, release: 1.8, amp: 0.7
    sleep 2
  end
end
