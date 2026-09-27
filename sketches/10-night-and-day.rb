# Night and day - changes with the sun
# category: Ambient
# gain: 2.01
# No keys needed. Daytime is a bright kalimba melody; after sunset,
# a slow dark pad with distant sounds. Cloud and rain soften it.

day = get(:wx_known) ? get(:wx_day) : true
code = get(:wx_known) ? get(:wx_code) : 1
grey = code >= 3        # overcast, fog, rain, snow...

if day
  notes = scale(:c4, grey ? :minor_pentatonic : :major_pentatonic, num_octaves: 2)
  with_fx :reverb, room: 0.7, mix: 0.4 do
    live_loop :melody do
      use_bpm grey ? 70 : 95
      use_synth :kalimba
      play notes.choose, amp: 3 unless grey && one_in(2)   # sparser when it's grey
      sleep [0.5, 0.5, 1].choose
    end
    live_loop :bass do
      use_bpm grey ? 70 : 95
      synth :fm, note: notes[0] - 24, amp: 0.4, release: 2, depth: 1
      sleep 4
    end
  end
else
  notes = scale(:a2, :minor, num_octaves: 2)
  with_fx :reverb, room: 0.95, mix: 0.7 do
    live_loop :pad do
      synth :hollow, note: notes.choose, attack: 3, release: 7, amp: 1.2
      sleep 5
    end
    live_loop :distant do
      sleep rrand(6, 14)
      sample [:ambi_lunar_land, :ambi_dark_woosh, :ambi_glass_rub].choose, amp: 0.35, rate: [0.5, 0.75].choose
    end
  end
end
