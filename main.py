import os
import sys
import time
import threading
from mido import MidiFile
import keyboard

# --- CONFIGURATION ---
ROW_KEYS = [
    ['z', 'x', 'c', 'v', 'b', 'n', 'm'], # Low Row (Octave 0)
    ['a', 's', 'd', 'f', 'g', 'h', 'j'], # Medium Row (Octave 1)
    ['q', 'w', 'e', 'r', 't', 'y', 'u']  # High Row (Octave 2)
]

C3_PITCH = 48
MAX_PITCH = C3_PITCH + 35 # Highest note in the 3-row layout
play_state = 'idle'
stop_signal = False
manual_octave_offset = 0

# Debounce settings
last_hotkey_time = 0
debounce_sec = 0.2

def get_key_and_modifier(pitch):
    relative_pitch = pitch % 12
    semitone_map = {
        0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (2, -1),
        4: (2, 0), 5: (3, 0), 6: (3, 1), 7: (4, 0),
        8: (4, 1), 9: (5, 0), 10: (6, -1), 11: (6, 0)
    }

    octave = (pitch - C3_PITCH) // 12
    # Ensure octave is valid for our ROW_KEYS list
    if octave < 0 or octave >= len(ROW_KEYS):
        return None, None

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

        pitch = event.note + auto_shifting + manual_octave_offset

        # --- FOLDING LOGIC ---
        # Fold high notes down until they fit
        while pitch > MAX_PITCH:
            pitch -= 12

        # Ignore low notes (let them be missing without clamping)
        if pitch < C3_PITCH:
            continue

        key, mod = get_key_and_modifier(pitch)

        if key is None: # Safety check
            continue

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
    global manual_octave_offset, last_hotkey_time
    current_time = time.time()
    if current_time - last_hotkey_time < debounce_sec:
        return
    last_hotkey_time = current_time

    manual_octave_offset += (amount * 12)
    manual_octave_offset = max(-36, min(36, manual_octave_offset))

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
        print(f"Auto-Shifting: {auto_shift // 12} octaves")
        print("---------------------------------")
        print("F5            : Start / Stop")
        print("+ / =         : Octave Up")
        print("-             : Octave Down")
        print("Esc           : Exit Script")

        keyboard.add_hotkey('f5', lambda: toggle_control(midi, auto_shift, 1.0), suppress=True)

        for k in ['+', '=', 'plus']:
            try: keyboard.add_hotkey(k, lambda: change_octave(1), suppress=True)
            except: pass

        for k in ['-', '_', 'minus']:
            try: keyboard.add_hotkey(k, lambda: change_octave(-1), suppress=True)
            except: pass

        keyboard.wait('esc')
    except Exception as e:
        print(f"Error: {e}")
