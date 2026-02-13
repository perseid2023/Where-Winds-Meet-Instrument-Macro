import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- DEPENDENCY CHECK ---
try:
    from mido import MidiFile
    import keyboard
except ImportError:
    print("\n[!] Missing dependencies. Run: pip install mido keyboard")
    sys.exit(1)

# --- CONFIGURATION ---
row_keys = [
    ['z', 'x', 'c', 'v', 'b', 'n', 'm'], # Low Pitch Row
    ['a', 's', 'd', 'f', 'g', 'h', 'j'], # Medium Pitch Row
    ['q', 'w', 'e', 'r', 't', 'y', 'u']  # High Pitch Row
]

C3_MIDI_PITCH = 48

class MidiMacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Where Winds Meet Instrument Macro")
        self.root.geometry("500x550")

        self.playlist_data = []
        self.current_midi = None
        self.play_state = 'idle'
        self.stop_signal = False
        self.auto_shift = 0

        tk.Label(root, text="WWM MIDI Player 32-Keys", font=("Arial", 11, "bold")).pack(pady=10)

        self.frame = tk.Frame(root)
        self.frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.listbox = tk.Listbox(self.frame, font=("Consolas", 10))
        self.listbox.pack(side="left", fill="both", expand=True)

        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)

        speed_frame = tk.Frame(root)
        speed_frame.pack(pady=5)
        tk.Label(speed_frame, text="Speed:").pack(side="left")
        self.speed_entry = tk.Entry(speed_frame, width=5)
        self.speed_entry.insert(0, "1.0")
        self.speed_entry.pack(side="left", padx=5)

        tk.Label(speed_frame, text="Octave Offset:").pack(side="left")
        # Spinbox for manual octave control
        self.octave_shift = tk.Spinbox(speed_frame, from_=-3, to=3, width=5)
        self.octave_shift.delete(0, "end")
        self.octave_shift.insert(0, "-1")
        self.octave_shift.pack(side="left", padx=5)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Add MIDI", command=self.add_files, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="▶ Play (F5)", command=self.start_play, bg="#d4edda", width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="⏹ Stop", command=self.stop_play, bg="#f8d7da", width=12).pack(side="left", padx=5)

        self.status = tk.StringVar(value="Status: Ready")
        tk.Label(root, textvariable=self.status, font=("Arial", 10, "italic")).pack(pady=5)

        # Register Hotkeys
        keyboard.add_hotkey('f5', self.toggle_play_macro, suppress=True)

        # Octave Up Hotkeys
        keyboard.add_hotkey('+', lambda: self.adjust_octave_gui(1), suppress=True)
        keyboard.add_hotkey('=', lambda: self.adjust_octave_gui(1), suppress=True)
        keyboard.add_hotkey('plus', lambda: self.adjust_octave_gui(1), suppress=True)

        # Octave Down Hotkeys
        keyboard.add_hotkey('-', lambda: self.adjust_octave_gui(-1), suppress=True)
        keyboard.add_hotkey('minus', lambda: self.adjust_octave_gui(-1), suppress=True)

    def adjust_octave_gui(self, amount):
        """Adjusts the Spinbox value safely from a hotkey thread."""
        try:
            current = int(self.octave_shift.get())
            new_val = max(-3, min(3, current + amount))
            self.root.after(0, lambda: self.set_spinbox_val(new_val))
        except:
            pass

    def set_spinbox_val(self, val):
        self.octave_shift.delete(0, "end")
        self.octave_shift.insert(0, str(val))

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("MIDI files", "*.mid *.midi")])
        for f in files:
            self.playlist_data.append(f)
            self.listbox.insert("end", os.path.basename(f))

    def find_best_shift(self, midi_data):
        notes = [n.note for n in midi_data if not n.is_meta and n.type == 'note_on']
        if not notes: return 0
        avg_note = sum(notes) / len(notes)
        return round((60 - avg_note) / 12) * 12

    def play_logic(self):
        for i in range(3, 0, -1):
            if self.stop_signal: return
            self.status.set(f"Switch to Game! Starting in {i}...")
            time.sleep(1)

        self.status.set("Playing...")

        semitone_map = {
            0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (2, -1),
            4: (2, 0), 5: (3, 0), 6: (3, 1), 7: (4, 0),
            8: (4, 1), 9: (5, 0), 10: (6, -1), 11: (6, 0)
        }

        for event in self.current_midi:
            if self.stop_signal: break

            # Re-read UI values for every note to allow real-time changes
            try:
                speed = float(self.speed_entry.get())
                manual_trans = int(self.octave_shift.get()) * 12
            except:
                speed, manual_trans = 1.0, -12

            time.sleep(max(0, event.time / speed))

            if event.is_meta or event.type != 'note_on' or event.velocity == 0:
                continue

            # Calculate pitch with real-time manual_trans
            pitch = event.note + self.auto_shift + manual_trans
            pitch = max(C3_MIDI_PITCH, min(C3_MIDI_PITCH + 35, pitch))

            relative_pitch = pitch % 12
            octave = (pitch - C3_MIDI_PITCH) // 12
            octave = max(0, min(2, octave))

            key_idx, modifier = semitone_map[relative_pitch]
            target_key = row_keys[octave][key_idx]

            if modifier == 1:
                keyboard.press('shift')
                keyboard.press_and_release(target_key)
                keyboard.release('shift')
            elif modifier == -1:
                keyboard.press('ctrl')
                keyboard.press_and_release(target_key)
                keyboard.release('ctrl')
            else:
                keyboard.press_and_release(target_key)

        if not self.stop_signal:
            self.status.set("Status: Finished")
        self.play_state = 'idle'

    def start_play(self):
        if self.play_state == 'playing': return
        selection = self.listbox.curselection()
        if not selection: return
        self.stop_signal = False
        self.play_state = 'playing'
        self.current_midi = MidiFile(self.playlist_data[selection[0]])
        self.auto_shift = self.find_best_shift(self.current_midi)
        threading.Thread(target=self.play_logic, daemon=True).start()

    def stop_play(self):
        self.stop_signal = True
        self.play_state = 'idle'
        self.status.set("Status: Stopped")

    def toggle_play_macro(self):
        if self.play_state == 'playing': self.stop_play()
        else: self.root.after(0, self.start_play)

if __name__ == '__main__':
    root = tk.Tk()
    app = MidiMacroGUI(root)
    root.mainloop()
