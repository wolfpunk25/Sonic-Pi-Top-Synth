# Finger drums - the keys play a drum kit
# category: Grooves
# gain: 0.76
# C kick, D snare, E closed hat, F open hat, G clap, A low tom,
# B high tom. Sharps are percussion. Every octave repeats the kit.

kit = {
  0 => :bd_haus,  2 => :drum_snare_hard, 4 => :drum_cymbal_closed,
  5 => :drum_cymbal_open, 7 => :perc_snap, 9 => :drum_tom_lo_hard,
  11 => :drum_tom_hi_hard, 1 => :perc_bell, 3 => :elec_blip2,
  6 => :drum_cowbell, 8 => :elec_tick, 10 => :perc_till
}

live_loop :pads do
  use_real_time
  note, vel = sync "/midi*/note_on"
  sample kit[note % 12], amp: vel / 90.0 if vel > 0
end
