import os
import sys
import argparse
import time
import types

# --- PORTABILITY & DEPENDENCY FIX ---
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

if 'packaging' not in sys.modules:
    try:
        pkg = types.ModuleType('packaging')
        pkg.version = types.ModuleType('packaging.version')
        class FakeVersion:
            def __init__(self, v): self.v = v
            def __str__(self): return self.v
        pkg.version.Version = FakeVersion
        sys.modules['packaging'] = pkg
        sys.modules['packaging.version'] = pkg.version
    except Exception: pass

try:
    from mido import MidiFile
    import keyboard
except ImportError as e:
    print(f"\n[!] Import Error: {e}")
    sys.exit(1)

# --- WHERE WINDS MEET CONFIGURATION ---
# Based on the image:
# Low Pitch (Bottom Row): Z X C V B N M (plus semitones)
# Medium Pitch (Middle Row): A S D F G H J (plus semitones)
# High Pitch (Top Row): Q W E R T Y U (plus semitones)

# We map 12 semitones per row to match the chromatic layout
# Keytable format: "C C# D D# E F F# G G# A A# B"
low_row    = "zxcvbnm" # Standard mapping often requires custom layout for sharps
med_row    = "asdfghj"
high_row   = "qwertyu"

# Chromatic mapping for Where Winds Meet (Adjusted for the 12-note scale per octave)
# Note: '?' represents semitones if they don't have a direct single-key assignment
keytable = "z?x?cv?b?n?m" + "a?s?df?g?h?j" + "q?w?er?t?y?u"

octave_interval = 12
c3_pitch = 48 # Base pitch for Low Row
c5_pitch = 72 # Base pitch for High Row
b5_pitch = 83 # End of High Row
play_state = 'idle'

def midi_playable(event):
    return not event.is_meta and event.type == 'note_on'

def find_best_shift(midi_data):
    note_counter = [0] * octave_interval
    octave_list = [0] * 11
    for event in midi_data:
        if not midi_playable(event): continue
        for i in range(octave_interval):
            note_pitch = (event.note + i) % octave_interval
            if keytable[note_pitch] != '?':
                note_counter[i] += 1
                note_octave = (event.note + i) // octave_interval
                octave_list[note_octave] += 1
    max_note = max(range(len(note_counter)), key=note_counter.__getitem__)
    shifting, counter = 0, 0
    for i in range(len(octave_list) - 3):
        amount = sum(octave_list[i: i + 3])
        if amount > counter:
            counter, shifting = amount, i
    return int(max_note + (4 - shifting) * octave_interval)

def play(midi, shifting, speed):
    global play_state
    play_state = 'playing'
    for event in midi:
        if play_state != 'playing': break
        time.sleep(event.time / speed)
        if not midi_playable(event): continue

        pitch = event.note + shifting

        # Clamp pitch to the 3-octave range available in-game
        if pitch < c3_pitch:
            pitch = pitch % octave_interval + c3_pitch
        elif pitch > b5_pitch:
            pitch = pitch % octave_interval + c5_pitch

        if c3_pitch <= pitch <= b5_pitch:
            key_idx = pitch - c3_pitch
            key_press = keytable[key_idx]

            # Skip keys marked as '?' (semitones without keys)
            # unless you use Shift/Ctrl modifiers
            if key_press != '?':
                keyboard.send(key_press)

def control(midi, shifting, speed):
    global play_state
    if play_state == 'playing':
        play_state = 'pause'
    elif play_state == 'idle' or play_state == 'pause':
        keyboard.call_later(play, args=(midi, shifting, speed), delay=1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('midi', nargs="?", type=str)
    parser.add_argument('--speed', type=float, default=1.0)
    args = parser.parse_args()

    midi_path = args.midi if args.midi else os.path.join(script_dir, 'asd.midi')

    try:
        midi = MidiFile(midi_path)
    except Exception as e:
        print(f"Could not load MIDI: {e}")
        sys.exit(1)

    shifting = find_best_shift(midi)
    print(f"\n--- WHERE WINDS MEET MACRO ---")
    print(f"File: {os.path.basename(midi_path)}")
    print("F5: Play/Pause | Esc: Exit")

    keyboard.add_hotkey('F5', lambda: control(midi, shifting, args.speed), suppress=True, trigger_on_release=True)
    keyboard.wait('Esc', suppress=True)
