# Copycat - improvises from what you've played
# It learns which note tends to follow which, and wanders through your own ideas.
# Play a phrase, stop, and listen to it come back rearranged.

set :heard, [60, 62, 64, 67, 64, 62, 60]
set :cur, 60

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    set :heard, (get(:heard).to_a + [note]).last(48)
    set :cur, note                     # jump to where you are
  end
end

with_fx :reverb, room: 0.6, mix: 0.35 do
  live_loop :improvise do
    use_bpm 100
    heard = get(:heard).to_a
    cur = get(:cur)
    followers = []
    heard.each_with_index { |n, i| followers << heard[i + 1] if n == cur && i + 1 < heard.length }
    n = followers.empty? ? heard.choose : followers.choose
    set :cur, n
    synth :pluck, note: n, amp: 0.7, coef: 0.25
    synth :sine, note: n - 12, amp: 0.15, release: 0.4 if one_in(3)
    sleep [0.25, 0.5, 0.5, 0.75, 1].choose
  end
end
