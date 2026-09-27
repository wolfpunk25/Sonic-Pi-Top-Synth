# Shepard staircase - a scale that rises forever and never gets higher
# category: Sequencers
# gain: 2.36
# An auditory illusion: every note is played in eight octaves at once, the
# middle ones loud and the outer ones faint, so each step sounds higher yet
# the whole thing never climbs out of range. Keys below middle C make it
# fall, middle C and above make it rise.

set :sh_dir, 1
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  set :sh_dir, note < 60 ? -1 : 1 if vel > 0
end

live_loop :stairs do
  use_bpm 100
  step = (get(:sh_step) || 0) + get(:sh_dir)
  set :sh_step, step
  pc = step % 12
  8.times do |oct|
    n = 24 + oct * 12 + pc
    x = (n - 24) / 96.0                              # 0..1 across the eight octaves
    level = Math.exp(-((x - 0.5) ** 2) / 0.045)      # a bell curve: loud in the middle
    synth :sine, note: n, attack: 0.02, release: 0.45, amp: level * 0.25 if level > 0.01
  end
  sleep 0.5
end
