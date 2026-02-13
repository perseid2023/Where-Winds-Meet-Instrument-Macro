import os
import sys
import types
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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

# --- CONFIGURATION ---
keytable = "z?x?cv?b?n?m" + "a?s?df?g?h?j" + "q?w?er?t?y?u"
octave_interval = 12
c3_pitch = 48
c5_pitch = 72
b5_pitch = 83

class MidiMacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Where Winds Meet - MIDI Playlist")
        self.root.geometry("500x550")

        self.playlist_data = []
        self.current_midi = None
        self.play_state = 'idle'
        self.stop_signal = False
        self.shifting = 0

        # UI Layout
        tk.Label(root, text="MIDI Playlist Manager", font=("Arial", 12, "bold")).pack(pady=10)

        self.frame = tk.Frame(root)
        self.frame.pack(pady=5, padx=10, fill="both", expand=True)

        self.scrollbar = tk.Scrollbar(self.frame, orient="vertical")
        self.listbox = tk.Listbox(self.frame, yscrollcommand=self.scrollbar.set, selectmode="single", font=("Consolas", 10))
        self.scrollbar.config(command=self.listbox.yview)

        self.scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        # Progress Bar & Timer
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)
        self.time_label = tk.Label(root, text="00:00 / 00:00", font=("Arial", 10))
        self.time_label.pack()

        btn_frame1 = tk.Frame(root)
        btn_frame1.pack(pady=5)
        tk.Button(btn_frame1, text="Add Files", command=self.add_files, width=15).pack(side="left", padx=2)
        tk.Button(btn_frame1, text="Clear Playlist", command=self.clear_playlist, width=15).pack(side="left", padx=2)

        speed_frame = tk.Frame(root)
        speed_frame.pack(pady=5)
        tk.Label(speed_frame, text="Speed:").pack(side="left")
        self.speed_entry = tk.Entry(speed_frame, width=5, justify='center')
        self.speed_entry.insert(0, "1.0")
        self.speed_entry.pack(side="left", padx=5)

        btn_frame2 = tk.Frame(root)
        btn_frame2.pack(pady=10)
        tk.Button(btn_frame2, text="▶ Play", command=self.start_play, width=10, bg="#d4edda").pack(side="left", padx=5)
        tk.Button(btn_frame2, text="⏸ Pause", command=self.pause_play, width=10).pack(side="left", padx=5)
        tk.Button(btn_frame2, text="⏹ Stop", command=self.stop_play, width=10, bg="#f8d7da").pack(side="left", padx=5)

        self.status = tk.StringVar(value="Status: Idle")
        tk.Label(root, textvariable=self.status, font=("Arial", 10, "italic")).pack(pady=5)
        tk.Label(root, text="Hotkeys: F5 (Play/Pause) | ESC (Stop Script)", fg="gray", font=("Arial", 8)).pack()

        keyboard.add_hotkey('f5', self.toggle_play_macro, suppress=True, trigger_on_release=True)

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("MIDI files", "*.mid *.midi")])
        if files:
            for f in files:
                try:
                    # Calculate duration for the playlist display
                    temp_mid = MidiFile(f)
                    duration = time.strftime('%M:%S', time.gmtime(temp_mid.length))
                    display_name = f"{os.path.basename(f)} [{duration}]"

                    self.playlist_data.append(f)
                    self.listbox.insert("end", display_name)
                except Exception:
                    # Fallback if file is corrupted
                    self.playlist_data.append(f)
                    self.listbox.insert("end", os.path.basename(f))

            self.status.set(f"Added {len(files)} files.")

    def clear_playlist(self):
        self.stop_play()
        self.playlist_data = []
        self.listbox.delete(0, "end")
        self.status.set("Playlist cleared.")

    def find_best_shift(self, midi_data):
        note_counter = [0] * octave_interval
        octave_list = [0] * 11
        for event in midi_data:
            if not self.midi_playable(event): continue
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

    def midi_playable(self, event):
        return not event.is_meta and event.type == 'note_on'

    def play_logic(self):
        try:
            speed = float(self.speed_entry.get())
        except ValueError:
            speed = 1.0

        total_len = self.current_midi.length
        current_time = 0

        for event in self.current_midi:
            if self.stop_signal:
                break

            while self.play_state == 'paused':
                if self.stop_signal: break
                time.sleep(0.1)

            time.sleep(event.time / speed)
            current_time += event.time

            # Update Progress Bar and Timer Label
            progress_val = (current_time / total_len) * 100
            cur_fmt = time.strftime('%M:%S', time.gmtime(current_time))
            tot_fmt = time.strftime('%M:%S', time.gmtime(total_len))
            self.root.after(0, lambda p=progress_val, t=f"{cur_fmt} / {tot_fmt}": self.update_progress(p, t))

            if not self.midi_playable(event): continue

            pitch = event.note + self.shifting
            if pitch < c3_pitch:
                pitch = pitch % octave_interval + c3_pitch
            elif pitch > b5_pitch:
                pitch = pitch % octave_interval + c5_pitch

            if c3_pitch <= pitch <= b5_pitch:
                key_idx = pitch - c3_pitch
                key_press = keytable[key_idx]
                if key_press != '?':
                    keyboard.send(key_press)

        if not self.stop_signal:
            self.status.set("Status: Finished")
        self.play_state = 'idle'
        self.root.after(0, lambda: self.update_progress(0, "00:00 / 00:00"))

    def update_progress(self, val, txt):
        self.progress['value'] = val
        self.time_label.config(text=txt)

    def start_play(self):
        if self.play_state == 'paused':
            self.play_state = 'playing'
            self.status.set("Status: Resumed")
            return

        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a MIDI from the playlist first!")
            return

        file_path = self.playlist_data[selection[0]]
        try:
            self.current_midi = MidiFile(file_path)
            self.shifting = self.find_best_shift(self.current_midi)
            self.stop_signal = False
            self.play_state = 'playing'
            self.status.set(f"Playing: {os.path.basename(file_path)}")
            threading.Thread(target=self.play_logic, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Could not play: {e}")

    def pause_play(self):
        if self.play_state == 'playing':
            self.play_state = 'paused'
            self.status.set("Status: Paused")

    def stop_play(self):
        self.stop_signal = True
        self.play_state = 'idle'
        self.status.set("Status: Stopped")
        self.update_progress(0, "00:00 / 00:00")

    def toggle_play_macro(self):
        if self.play_state == 'playing':
            self.pause_play()
        else:
            self.start_play()

if __name__ == '__main__':
    root = tk.Tk()
    app = MidiMacroGUI(root)
    root.bind('<Escape>', lambda e: root.destroy())
    root.mainloop()
