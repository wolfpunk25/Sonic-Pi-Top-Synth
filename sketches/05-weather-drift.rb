# Weather drift - ambient that follows today's weather
# No keys needed. Colder is lower, rain adds drops, wind speeds it up.
# The station sets these before every sketch runs.

temp = get(:wx_known) ? get(:wx_temp) : 12
rain = get(:wx_known) ? get(:wx_rain) : 0
wind = get(:wx_known) ? get(:wx_wind) : 5

root = temp < 5 ? :d3 : (temp < 15 ? :a2 : :c3)
notes = scale(root, rain > 0 ? :minor_pentatonic : :major_pentatonic, num_octaves: 2)
bpm = [40 + wind, 90].min

with_fx :reverb, room: 0.9, mix: 0.6 do
  live_loop :pad do
    use_bpm bpm
    synth :dark_ambience, note: notes.choose, attack: 2, release: 6, amp: 1.2
    sleep 4
  end

  live_loop :drops do
    use_bpm bpm
    if rain > 0
      synth :pretty_bell, note: notes.choose + 12, amp: 0.25, release: 0.3
      sleep [0.25, 0.5, 1].choose
    else
      synth :sine, note: notes.choose + 12, amp: 0.15, attack: 0.5, release: 1.5
      sleep 3
    end
  end
end
