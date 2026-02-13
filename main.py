import os
import sys
import time
import threading
from mido import MidiFile
import keyboard

# --- CONFIGURATION ---
# Base keys per row from the screenshot
ROW_KEYS = [
    ['z', 'x', 'c', 'v', 'b', 'n', 'm'], # Low Row
    ['a', 's', 'd', 'f', 'g', 'h', 'j'], # Medium Row
    ['q', 'w', 'e', 'r', 't', 'y', 'u']  # High Row
]

C3_PITCH = 48
play_state = 'idle'
stop_signal = False
manual_octave_offset = -12 # Default to -1 octave

def get_key_and_modifier(pitch):
    relative_pitch = pitch % 12
    semitone_map = {
        0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (2, -1),
        4: (2, 0), 5: (3, 0), 6: (3, 1), 7: (4, 0),
        8: (4, 1), 9: (5, 0), 10: (6, -1), 11: (6, 0)
    }

    # Calculate octave relative to C3 (48)
    octave = (pitch - C3_PITCH) // 12
    octave = max(0, min(2, octave)) # Squeeze into the 3 rows

    key_idx, mod = semitone_map[relative_pitch]
    return ROW_KEYS[octave][key_idx], mod

def find_best_shift(midi_file):
    notes = [n.note for n in midi_file if not n.is_meta and n.type == 'note_on']
    if not notes: return 0
    avg_note = sum(notes) / len(notes)
    return round((60 - avg_note) / 12) * 12

def play_midi(midi, auto_shifting, speed):
    global play_state, stop_signal, manual_octave_offset

    for i in range(3, 0, -1):
        if stop_signal: return
        print(f"Switch to Game! Starting in {i}...   ", end='\r')
        time.sleep(1)

    print("\n[PLAYING] F5: Stop | +/-: Octave Shift")
    play_state = 'playing'

    for event in midi:
        if stop_signal or play_state != 'playing': break

        time.sleep(max(0, event.time / speed))
        if event.is_meta or event.type != 'note_on' or event.velocity == 0:
            continue

        # Real-time calculation using the latest manual_octave_offset
        pitch = event.note + auto_shifting + manual_octave_offset
        pitch = max(C3_PITCH, min(C3_PITCH + 35, pitch))

        key, mod = get_key_and_modifier(pitch)

        if mod == 1:
            keyboard.press('shift')
            keyboard.press_and_release(key)
            keyboard.release('shift')
        elif mod == -1:
            keyboard.press('ctrl')
            keyboard.press_and_release(key)
            keyboard.release('ctrl')
        else:
            keyboard.press_and_release(key)

    play_state = 'idle'
    print("\n[FINISHED] Ready. Press F5 to play again.")

def change_octave(amount):
    global manual_octave_offset
    manual_octave_offset += (amount * 12)
    current = manual_octave_offset // 12
    print(f"Current Octave Offset: {current} ({manual_octave_offset} semitones)      ", end='\r')

def toggle_control(midi, shifting, speed):
    global play_state, stop_signal
    if play_state == 'playing':
        stop_signal = True
        play_state = 'idle'
    else:
        stop_signal = False
        threading.Thread(target=play_midi, args=(midi, shifting, speed), daemon=True).start()

if __name__ == '__main__':
    midi_path = sys.argv[1] if len(sys.argv) > 1 else 'asd.midi'

    if not os.path.exists(midi_path):
        print(f"Error: {midi_path} not found.")
        sys.exit(1)

    try:
        midi = MidiFile(midi_path)
        auto_shift = find_best_shift(midi)

        print(f"File: {midi_path}")
        print(f"Default Octave: -1")
        print("---------------------------------")
        print("F5            : Start / Stop")
        print("+ (or Numpad+): Octave Up")
        print("- (or Numpad-): Octave Down")
        print("Esc           : Exit Script")

        keyboard.add_hotkey('f5', lambda: toggle_control(midi, auto_shift, 1.0), suppress=True)

        # Multiple hotkeys for compatibility
        keyboard.add_hotkey('+', lambda: change_octave(1), suppress=True)
        keyboard.add_hotkey('=', lambda: change_octave(1), suppress=True) # Common for main keyboard '+'
        keyboard.add_hotkey('plus', lambda: change_octave(1), suppress=True)

        keyboard.add_hotkey('-', lambda: change_octave(-1), suppress=True)
        keyboard.add_hotkey('minus', lambda: change_octave(-1), suppress=True)

        keyboard.wait('esc')
    except Exception as e:
        print(f"Error: {e}")
