"""SpectrePass - Desktop UI."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# Allow running both as script and as frozen exe
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrubber import process_image

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff")


class ScrubberUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SpectrePass")
        self.geometry("560x520")
        self.resizable(False, False)
        self.input_files: list[str] = []

        # --- Dark theme colors ---
        bg, fg, accent = "#1e1e1e", "#e8e8e8", "#4caf50"
        self.configure(bg=bg)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("Horizontal.TProgressbar", troughcolor="#333", background=accent)

        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="SpectrePass", style="Title.TLabel").pack(pady=(0, 4))
        ttk.Label(main, text="Strip AI fingerprints while preserving visual quality.").pack(pady=(0, 12))

        # File list
        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True)
        self.file_list = tk.Listbox(list_frame, height=7, bg="#2d2d2d", fg=fg,
                                    selectmode=tk.EXTENDED, relief="flat",
                                    highlightthickness=1, highlightbackground="#444")
        self.file_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        sb.pack(side="right", fill="y")
        self.file_list.configure(yscrollcommand=sb.set)

        btn_row = ttk.Frame(main)
        btn_row.pack(fill="x", pady=8)
        ttk.Button(btn_row, text="Add Images", command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Add Folder", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Remove", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Clear", command=self.clear_all).pack(side="left", padx=6)

        # Output dir + quality
        opt = ttk.Frame(main)
        opt.pack(fill="x", pady=4)
        ttk.Label(opt, text="Output folder:").grid(row=0, column=0, sticky="w")
        self.out_var = tk.StringVar(value=str(Path.home() / "Pictures" / "Scrubbed"))
        ttk.Entry(opt, textvariable=self.out_var, width=38).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(opt, text="Browse", command=self.browse_out).grid(row=1, column=1)
        opt.columnconfigure(0, weight=1)

        q_frame = ttk.Frame(main)
        q_frame.pack(fill="x", pady=8)
        ttk.Label(q_frame, text="JPEG Quality:").pack(side="left")
        self.quality_var = tk.IntVar(value=92)
        self.q_label = ttk.Label(q_frame, text="92")
        self.q_label.pack(side="right")
        q_scale = ttk.Scale(q_frame, from_=70, to=100, variable=self.quality_var,
                            orient="horizontal", command=lambda v: self.q_label.config(text=str(int(float(v)))))
        q_scale.pack(side="right", fill="x", expand=True, padx=10)

        self.progress = ttk.Progressbar(main, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=8)
        self.status_var = tk.StringVar(value="Ready. Add images to begin.")
        ttk.Label(main, textvariable=self.status_var, wraplength=500).pack(pady=(0, 8))

        run_row = ttk.Frame(main)
        run_row.pack(fill="x")
        self.run_btn = ttk.Button(run_row, text="SCRUB IMAGES", command=self.start_scrub)
        self.run_btn.pack(fill="x")

    # --- file handling ---
    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff"), ("All files", "*.*")])
        for f in files:
            if f not in self.input_files:
                self.input_files.append(f)
                self.file_list.insert("end", f)
        self.update_status()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return
        for p in sorted(Path(folder).iterdir()):
            if p.suffix.lower() in SUPPORTED_EXTS:
                s = str(p)
                if s not in self.input_files:
                    self.input_files.append(s)
                    self.file_list.insert("end", s)
        self.update_status()

    def remove_selected(self):
        for i in reversed(self.file_list.curselection()):
            del self.input_files[i]
            self.file_list.delete(i)
        self.update_status()

    def clear_all(self):
        self.input_files.clear()
        self.file_list.delete(0, "end")
        self.update_status()

    def browse_out(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.out_var.set(d)

    def update_status(self):
        n = len(self.input_files)
        self.status_var.set(f"Ready. {n} image(s) queued." if n else "Ready. Add images to begin.")

    # --- processing ---
    def start_scrub(self):
        if not self.input_files:
            messagebox.showwarning("No images", "Add at least one image first.")
            return
        out_dir = self.out_var.get().strip() or os.getcwd()
        os.makedirs(out_dir, exist_ok=True)
        self.run_btn.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.input_files)
        threading.Thread(target=self._worker, args=(list(self.input_files), out_dir, self.quality_var.get()),
                         daemon=True).start()

    def _worker(self, files, out_dir, quality):
        ok, fail = 0, 0
        for f in files:
            name = os.path.basename(f)
            try:
                self.after(0, self.status_var.set, f"Processing {name}...")
                stem, ext = os.path.splitext(name)
                if ext.lower() not in SUPPORTED_EXTS:
                    ext = ".jpg"
                out = os.path.join(out_dir, f"{stem}_scrubbed{ext}")
                process_image(f, out, quality=quality)
                ok += 1
            except Exception as e:  # noqa: BLE001
                fail += 1
                self.after(0, self.status_var.set, f"Failed {name}: {e}")
            self.after(0, self._step)
        msg = f"Done! {ok} scrubbed, {fail} failed.\nSaved to: {out_dir}"
        self.after(0, self._finished, msg, fail == 0)

    def _step(self):
        self.progress["value"] += 1

    def _finished(self, msg, success):
        self.run_btn.config(state="normal")
        self.status_var.set(msg.split("\n")[0])
        if success:
            if messagebox.askyesno("Complete", msg + "\n\nOpen output folder?"):
                os.startfile(self.out_var.get())
        else:
            messagebox.showinfo("Complete", msg)


if __name__ == "__main__":
    ScrubberUI().mainloop()
