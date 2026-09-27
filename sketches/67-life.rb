# Life - Conway's Game of Life, played column by column
# category: Sequencers
# gain: 1.69
# An 8x8 grid evolves every bar. The music reads it left to right: each live
# cell in a column plays its row's note. If the grid dies out or gets stuck
# it reseeds itself. Each key you play brings a cell to life in the column
# being played, in the row matching your note.

cells = []
64.times { cells << (one_in(3) ? 1 : 0) }
set :life, cells
set :life_col, 0
set :life_same, 0
sleep 0.05     # let these settle before any loop reads them (they can race on start-up)

live_loop :listen do
  use_real_time
  note, vel = sync "/midi*/note_on"
  if vel > 0
    g = get(:life).to_a.dup     # stored values are frozen; copy before changing
    g[(note % 8) * 8 + get(:life_col)] = 1
    set :life, g
  end
end

with_fx :echo, phase: 0.75, decay: 2, mix: 0.2 do
  live_loop :read do
    use_bpm 112
    rows = scale(:d4, :minor_pentatonic, num_octaves: 2).take(8).reverse
    8.times do |x|
      set :life_col, x
      g = get(:life)
      8.times { |y| synth :kalimba, note: rows[y], amp: 2.2 if g[y * 8 + x] == 1 }
      synth :sine, note: rows[7] - 24, amp: 0.2, release: 0.4 if x % 4 == 0
      sleep 0.5
    end
    # the next generation
    g = get(:life).to_a
    nxt = (0...64).map do |i|
      y, x = i / 8, i % 8
      around = 0
      [-1, 0, 1].each { |dy| [-1, 0, 1].each { |dx| around += g[((y + dy) % 8) * 8 + (x + dx) % 8] unless dx == 0 && dy == 0 } }
      (around == 3 || (g[i] == 1 && around == 2)) ? 1 : 0
    end
    same = nxt == g ? get(:life_same) + 1 : 0
    if nxt.sum < 3 || same >= 4                      # dead or frozen: sow new seeds
      nxt = (0...64).map { one_in(3) ? 1 : 0 }
      same = 0
    end
    set :life_same, same
    set :life, nxt
  end
end
