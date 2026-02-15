import os
import sys
import time
import threading
import random
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
    ['z', 'x', 'c', 'v', 'b', 'n', 'm'], # Low Pitch Row (Octave 0)
    ['a', 's', 'd', 'f', 'g', 'h', 'j'], # Medium Pitch Row (Octave 1)
    ['q', 'w', 'e', 'r', 't', 'y', 'u']  # High Pitch Row (Octave 2)
]

C3_MIDI_PITCH = 48

class MidiMacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WWM Instrument Macro")
        self.root.geometry("600x680")

        self.playlist_data = []
        self.play_state = 'idle'
        self.stop_signal = False
        self.current_time_sec = 0
        self.total_time_sec = 0
        self.current_index = -1

        # Toggle Variables
        self.clamp_enabled = tk.BooleanVar(value=True)
        self.loop_enabled = tk.BooleanVar(value=False)
        self.shuffle_enabled = tk.BooleanVar(value=False)
        self.auto_next_enabled = tk.BooleanVar(value=True) # New Toggle

        self.last_hotkey_time = 0
        self.debounce_sec = 0.15

        # --- UI HEADER ---
        tk.Label(root, text="WWM MIDI Player 32-Keys", font=("Arial", 12, "bold")).pack(pady=10)

        # --- PLAYLIST SECTION ---
        list_frame = tk.Frame(root)
        list_frame.pack(pady=5, padx=10, fill="both", expand=True)

        v_scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        h_scrollbar = tk.Scrollbar(list_frame, orient="horizontal")

        self.listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 10),
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set,
            selectmode="browse"
        )

        v_scrollbar.config(command=self.listbox.yview)
        h_scrollbar.config(command=self.listbox.xview)

        self.listbox.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # --- PROGRESS & TIMESTAMP ---
        progress_frame = tk.Frame(root)
        progress_frame.pack(fill="x", padx=20, pady=5)

        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x")

        self.time_label = tk.Label(progress_frame, text="00:00 / 00:00", font=("Consolas", 10))
        self.time_label.pack(pady=2)

        # --- SETTINGS ---
        settings_frame = tk.Frame(root)
        settings_frame.pack(pady=5)

        tk.Label(settings_frame, text="Speed:").pack(side="left")
        self.speed_entry = tk.Entry(settings_frame, width=5)
        self.speed_entry.insert(0, "1.0")
        self.speed_entry.pack(side="left", padx=5)

        tk.Label(settings_frame, text="Octave:").pack(side="left")
        self.octave_shift = tk.Spinbox(settings_frame, from_=-3, to=3, width=3)
        self.octave_shift.delete(0, "end")
        self.octave_shift.insert(0, "0")
        self.octave_shift.pack(side="left", padx=5)

        # Toggles Row
        toggles_frame = tk.Frame(root)
        toggles_frame.pack(pady=5)
        tk.Checkbutton(toggles_frame, text="Clamp", variable=self.clamp_enabled).pack(side="left", padx=5)
        tk.Checkbutton(toggles_frame, text="Loop", variable=self.loop_enabled).pack(side="left", padx=5)
        tk.Checkbutton(toggles_frame, text="Shuffle", variable=self.shuffle_enabled).pack(side="left", padx=5)
        tk.Checkbutton(toggles_frame, text="Auto-Next", variable=self.auto_next_enabled).pack(side="left", padx=5)

        # --- BUTTONS ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Add MIDI", command=self.add_files, width=11).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Clear List", command=self.clear_playlist, width=11, fg="red").pack(side="left", padx=3)
        tk.Button(btn_frame, text="▶ Play (F5)", command=self.start_play, bg="#d4edda", width=11).pack(side="left", padx=3)
        tk.Button(btn_frame, text="⏹ Stop", command=self.stop_play, bg="#f8d7da", width=11).pack(side="left", padx=3)

        self.status = tk.StringVar(value="Status: Ready")
        tk.Label(root, textvariable=self.status, font=("Arial", 10, "italic")).pack(pady=5)

        self.setup_hotkeys()

    def setup_hotkeys(self):
        try:
            keyboard.add_hotkey('f5', self.toggle_play_macro, suppress=True)
            for k in ['=', '+', 'equal', 'plus']:
                keyboard.add_hotkey(k, self.hotkey_inc, suppress=True)
            for k in ['-', '_', 'minus', 'dash']:
                keyboard.add_hotkey(k, self.hotkey_dec, suppress=True)
        except: pass

    def hotkey_inc(self):
        now = time.time()
        if now - self.last_hotkey_time > self.debounce_sec:
            self.last_hotkey_time = now
            self.root.after(0, self.change_octave, 1)

    def hotkey_dec(self):
        now = time.time()
        if now - self.last_hotkey_time > self.debounce_sec:
            self.last_hotkey_time = now
            self.root.after(0, self.change_octave, -1)

    def change_octave(self, delta):
        try:
            current = int(self.octave_shift.get())
            new_val = max(-3, min(3, current + delta))
            self.octave_shift.delete(0, "end")
            self.octave_shift.insert(0, str(new_val))
            self.status.set(f"Status: Octave Shifted to {new_val}")
        except:
            self.octave_shift.delete(0, "end")
            self.octave_shift.insert(0, "0")

    def format_time(self, seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def clear_playlist(self):
        self.stop_play()
        self.playlist_data = []
        self.listbox.delete(0, tk.END)
        self.progress['value'] = 0
        self.time_label.config(text="00:00 / 00:00")
        self.status.set("Status: Playlist Cleared")

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("MIDI files", "*.mid *.midi")])
        for f in files:
            self.playlist_data.append(f)
            self.listbox.insert("end", os.path.basename(f))

    def play_logic(self):
        # 3 Second Countdown before starting the session
        for i in range(3, 0, -1):
            if self.stop_signal: return
            self.status.set(f"Switch to Game! Starting in {i}...")
            time.sleep(1)

        while self.play_state == 'playing' and not self.stop_signal:
            try:
                mid = MidiFile(self.playlist_data[self.current_index])
                self.total_time_sec = mid.length
                self.current_time_sec = 0

                # Update UI
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(self.current_index)
                self.listbox.see(self.current_index)
                self.status.set(f"Playing: {os.path.basename(self.playlist_data[self.current_index])}")
            except:
                break

            semitone_map = {0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (2, -1), 4: (2, 0), 5: (3, 0), 6: (3, 1), 7: (4, 0), 8: (4, 1), 9: (5, 0), 10: (6, -1), 11: (6, 0)}

            for event in mid:
                if self.stop_signal: break

                try:
                    speed = float(self.speed_entry.get())
                    manual_trans = int(self.octave_shift.get()) * 12
                except: speed, manual_trans = 1.0, 0

                time.sleep(max(0, event.time / speed))
                self.current_time_sec += event.time

                if self.total_time_sec > 0:
                    self.progress['value'] = (self.current_time_sec / self.total_time_sec) * 100
                self.time_label.config(text=f"{self.format_time(self.current_time_sec)} / {self.format_time(self.total_time_sec)}")

                if event.is_meta or event.type != 'note_on' or event.velocity == 0:
                    continue

                pitch = event.note + manual_trans
                if self.clamp_enabled.get():
                    pitch = max(C3_MIDI_PITCH, min(C3_MIDI_PITCH + 35, pitch))

                relative_pitch = pitch % 12
                octave = (pitch - C3_MIDI_PITCH) // 12

                if 0 <= octave < len(row_keys):
                    key_idx, modifier = semitone_map[relative_pitch]
                    target_key = row_keys[octave][key_idx]
                    if modifier == 1:
                        keyboard.press('shift'); keyboard.press_and_release(target_key); keyboard.release('shift')
                    elif modifier == -1:
                        keyboard.press('ctrl'); keyboard.press_and_release(target_key); keyboard.release('ctrl')
                    else:
                        keyboard.press_and_release(target_key)

            if self.stop_signal: break

            # If Auto-Next is disabled, stop here
            if not self.auto_next_enabled.get():
                break

            # Playlist Navigation
            if self.shuffle_enabled.get():
                self.current_index = random.randint(0, len(self.playlist_data) - 1)
            else:
                self.current_index += 1
                if self.current_index >= len(self.playlist_data):
                    if self.loop_enabled.get():
                        self.current_index = 0
                    else:
                        break

        self.play_state = 'idle'
        self.status.set("Status: Finished/Stopped")

    def start_play(self):
        if not self.playlist_data: return
        if self.play_state == 'playing': return
        selection = self.listbox.curselection()
        self.current_index = selection[0] if selection else 0
        self.stop_signal = False
        self.play_state = 'playing'
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
