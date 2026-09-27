# Lo-fi - a sleepy, muffled beat with crackle
# category: Grooves
# keys: last
# gain: 0.60
# Soft swung drums through a low-pass filter, vinyl hiss and a warm bass.
# Your keys play your last Keys sound; Electric piano is the classic.

with_fx :lpf, cutoff: 95 do
  live_loop :gr_drums do
    use_bpm 78
    16.times do |i|
      sample :bd_boom, amp: 1.2 if [0, 7, 10].include?(i)
      sample :sn_dolf, amp: 0.6 if [4, 12].include?(i)
      sample :hat_tap, amp: 0.25 if i.even?
      sleep i.even? ? 0.28 : 0.22
    end
  end
end

live_loop :gr_hiss do
  sample :vinyl_hiss, amp: 0.3
  sleep sample_duration(:vinyl_hiss)
end

live_loop :gr_bass, sync: :gr_drums do
  use_bpm 78
  [:f1, :f1, :a1, :e1].each do |n|
    synth :sine, note: n, attack: 0.05, release: 3.5, amp: 0.6
    sleep 4
  end
end
