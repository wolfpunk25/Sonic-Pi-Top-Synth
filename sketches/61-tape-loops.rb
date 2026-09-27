# Tape loops - a phrase that wears away a little more each time round
# category: Ambient
# gain: 1.25
# After William Basinski's Disintegration Loops: the same short phrase
# repeats, and on every pass it gets duller, dustier and more broken, until
# a fresh copy takes over. No keys needed; keys play electric piano on top.

phrase = [[:e4, 1.5], [:g4, 1], [:b4, 1.5], [:a4, 2], [:e4, 1], [:d4, 3]]
passes = 20

with_fx :reverb, room: 0.8, mix: 0.45 do
  with_fx :lpf, cutoff: 125 do |tone|
    with_fx :bitcrusher, sample_rate: 11000, bits: 8, mix: 0 do |dust|
      live_loop :tape do
        wear = (tick % passes) / (passes - 1.0)       # 0 fresh .. 1 almost gone
        control tone, cutoff: 125 - wear * 55
        control dust, mix: wear * 0.7
        phrase.each do |n, len|
          synth :rhodey, note: n, amp: 0.7, release: len * 0.9 unless rand < wear * 0.45   # gaps as it wears
          sleep len * (1 + wear * 0.04)                                                   # and it drags
        end
      end

      live_loop :bed do
        synth :hollow, notes: chord(:e3, :m7), attack: 3, sustain: 3, release: 4, amp: 0.4
        sleep 10
      end
    end
  end

  live_loop :keys do
    use_real_time
    note, vel = sync "/midi*/note_on"
    synth :rhodey, note: note, amp: vel / 130.0, release: 1.5 if vel > 0
  end
end
