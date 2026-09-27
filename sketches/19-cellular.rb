# Cellular - a melody grown by a cellular automaton
# category: Sequencers
# A row of 16 cells evolves every bar by a simple rule; live cells play
# notes. White keys flip a cell on or off; black keys change the rule.
# If the row ever dies out, a single cell is planted to start again.

rules = [30, 90, 110, 150, 45, 73, 105, 22]
set :rule, 90
set :row, [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    if [1, 3, 6, 8, 10].include?(note % 12)
      set :rule, rules[(note / 12 + note % 12) % rules.length]
    else
      r = get(:row).to_a.dup     # stored values are frozen; copy before changing
      r[note % 16] = 1 - r[note % 16]
      set :row, r
    end
  end
end

with_fx :echo, phase: 0.375, decay: 3, mix: 0.25 do
  live_loop :cells do
    use_bpm 104
    notes = scale(:a3, :minor_pentatonic, num_octaves: 3)
    row = get(:row)
    16.times do |i|
      synth :kalimba, note: notes[i], amp: 0.7 if row[i] == 1
      synth :sine, note: notes[i] - 24, amp: 0.2, release: 0.5 if row[i] == 1 && i % 4 == 0
      sleep 0.25
    end
    # grow the next generation: each cell looks at itself and its two neighbours
    rule = get(:rule)
    nxt = (0...16).map do |i|
      l, c, r = row[(i - 1) % 16], row[i], row[(i + 1) % 16]
      (rule >> (l * 4 + c * 2 + r)) & 1
    end
    nxt[rand_i(16)] = 1 if nxt.sum == 0
    set :row, nxt
  end
end
