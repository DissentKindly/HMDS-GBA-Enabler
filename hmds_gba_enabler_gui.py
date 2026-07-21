#!/usr/bin/env python3
"""
Harvest Moon DS / DS Cute — GBA Connectivity Enabler (GUI)
==========================================================
Sets the persistent "Friends of Mineral Town cartridge detected" flag in a
Harvest Moon DS or DS Cute save, so Mineral Town features (visitors,
GBA-linked content, and the RetroAchievements [GBA] achievements) work
without real hardware. Both games verified in-game (July 2026): patched
saves load cleanly and spawn Mineral Town visitors at the Inn.

Supports Action Replay (.duc/.dss), DeSmuME (.dsv), and raw (.sav) saves.
The original file is renamed to a timestamped .backup before anything is
written. Requires only Python 3 with tkinter (bundled on Windows/macOS;
on Linux: sudo apt install python3-tk).

Technical write-up of the save format and how this works:
see hmds_gba_connectivity_writeup.md
"""

import os
import struct
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# ---------------------------------------------------------------------------
# Save format constants (see the write-up for how these were derived)
# ---------------------------------------------------------------------------
BLOCK_A = 0x200
BLOCK_B = 0x8E00
BLOCK_LEN = 0x8C00

# Per-game flag locations (block-relative offset, bit), each verified via a
# with/without minimal-pair experiment:
#   DS Cute (USA):        +0x73ED bit 0x20
#   DS male (USA, Rev 1): +0x7361 bit 0x10
# Either FoMT or MFoMT sets the same bit; all four combinations verified.
GAMES = {
    "cute": ("Harvest Moon DS Cute", 0x73ED, 0x20),
    "boy":  ("Harvest Moon DS",      0x7361, 0x10),
}

K_BLOCK = 0x4FC3           # XOR constant for block CRCs
K_HDR = 0x0E65             # XOR constant for the header CRC
HDR_MAGIC = 0x424B         # "KB"

ARDS_MAGIC = b"ARDS"
ARDS_HEADER_LEN = 500
DSV_SNIP = b"|<--Snip above here"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def crc16(data, init=0):
    c = init
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


def unwrap(data):
    """-> (raw_image, kind, wrapper_blob)"""
    if data[:4] == ARDS_MAGIC:
        return data[ARDS_HEADER_LEN:], "Action Replay (.duc)", (data[:ARDS_HEADER_LEN], b"")
    snip = data.find(DSV_SNIP)
    if snip != -1:
        return data[:snip], "DeSmuME (.dsv)", (b"", data[snip:])
    return data, "raw (.sav)", (b"", b"")


def rewrap(raw, blob):
    head, tail = blob
    return head + raw + tail


def validate(raw):
    if len(raw) < BLOCK_A + BLOCK_LEN:
        return "File too small to be a Harvest Moon DS save."
    cnt_a, cnt_b = struct.unpack_from("<HH", raw, 0)
    if struct.unpack_from("<H", raw, 8)[0] != HDR_MAGIC:
        return "Header magic 'KB' not found — not a Harvest Moon DS (Cute) save?"
    chk_a = crc16(raw[BLOCK_A:BLOCK_A + BLOCK_LEN]) ^ K_BLOCK
    if chk_a != struct.unpack_from("<H", raw, 4)[0]:
        return ("Block A checksum mismatch — save appears corrupt "
                "(or an unknown format variant).")
    return None


def blocks_present(raw):
    bases = [BLOCK_A]
    cnt_b = struct.unpack_from("<H", raw, 2)[0]
    if cnt_b > 0 and len(raw) >= BLOCK_B + BLOCK_LEN:
        bases.append(BLOCK_B)
    return bases


def detect_game(raw):
    """Both games share the container; layouts diverge at the name table:
    the male game has a 0x01 marker at blk+0x004 before the farm name,
    Cute starts the farm-name string there directly."""
    return "boy" if raw[BLOCK_A + 4] < 0x20 else "cute"


def flag_state(raw, game):
    off, bit = GAMES[game][1], GAMES[game][2]
    return all(raw[b + off] & bit for b in blocks_present(raw))


def fix_checksums(raw):
    cnt_b = struct.unpack_from("<H", raw, 2)[0]
    chk_a = crc16(raw[BLOCK_A:BLOCK_A + BLOCK_LEN]) ^ K_BLOCK
    chk_b = 0
    if cnt_b > 0 and len(raw) >= BLOCK_B + BLOCK_LEN:
        chk_b = crc16(raw[BLOCK_B:BLOCK_B + BLOCK_LEN]) ^ K_BLOCK
    struct.pack_into("<HH", raw, 4, chk_a, chk_b)
    struct.pack_into("<H", raw, 10, crc16(raw[0:8]) ^ K_HDR)


def patch(path, game):
    """Returns a human-readable result string. Raises on I/O errors."""
    with open(path, "rb") as f:
        data = f.read()
    raw, kind, blob = unwrap(data)
    err = validate(raw)
    if err:
        raise ValueError(err)
    if flag_state(raw, game):
        return ("GBA connectivity is already enabled in this save.\n"
                "No changes were made and no backup was created.")

    raw = bytearray(raw)
    flag_off, flag_bit = GAMES[game][1], GAMES[game][2]
    touched = []
    for base in blocks_present(raw):
        off = base + flag_off
        if not raw[off] & flag_bit:
            raw[off] |= flag_bit
            touched.append(f"0x{off:05X}")
    fix_checksums(raw)

    backup = f"{path}.backup-{time.strftime('%Y%m%d-%H%M%S')}"
    os.rename(path, backup)
    try:
        with open(path, "wb") as f:
            f.write(rewrap(bytes(raw), blob))
    except Exception:
        # restore the original on any write failure
        if not os.path.exists(path):
            os.rename(backup, path)
        raise

    return (f"Success! GBA connectivity enabled.\n\n"
            f"Game: {GAMES[game][0]}\n"
            f"Save type: {kind}\n"
            f"Flag set at file offset(s): {', '.join(touched)}\n"
            f"Checksums recomputed.\n\n"
            f"Original backed up as:\n{os.path.basename(backup)}")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.path = None
        root.title("HM DS / DS Cute — GBA Connectivity Enabler")
        root.resizable(False, False)

        frame = tk.Frame(root, padx=16, pady=14)
        frame.pack()

        tk.Label(frame, text="Harvest Moon DS / DS Cute\nGBA · Mineral Town Connectivity Enabler",
                 font=("TkDefaultFont", 12, "bold"), justify="center").pack(pady=(0, 4))
        tk.Label(frame, text="Enables Friends of Mineral Town link features\n"
                             "without a real GBA cartridge.",
                 justify="center").pack(pady=(0, 10))

        self.game_var = tk.StringVar(value="cute")
        gframe = tk.Frame(frame)
        gframe.pack(pady=(0, 8))
        tk.Radiobutton(gframe, text="HM DS Cute", variable=self.game_var,
                       value="cute").pack(side="left", padx=4)
        tk.Radiobutton(gframe, text="HM DS (boy)", variable=self.game_var,
                       value="boy").pack(side="left", padx=4)

        self.file_label = tk.Label(frame, text="No save file selected",
                                   fg="gray", wraplength=340, justify="center")
        self.file_label.pack(pady=(0, 10))

        self.select_btn = tk.Button(frame, text="Select Save File…",
                                    width=28, command=self.select_file)
        self.select_btn.pack(pady=2)

        self.patch_btn = tk.Button(frame, text="Enable GBA Connectivity",
                                   width=28, state="disabled", command=self.do_patch)
        self.patch_btn.pack(pady=2)

        tk.Button(frame, text="Quit", width=28, command=root.destroy).pack(pady=(2, 6))

        self.status = tk.Label(frame, text="Supported: .sav  .dsv  .duc",
                               fg="gray", wraplength=340, justify="center")
        self.status.pack()

    def select_file(self):
        path = filedialog.askopenfilename(
            title="Select Harvest Moon DS Cute save file",
            filetypes=[("DS save files", "*.sav *.dsv *.duc *.dss"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            raw, kind, _ = unwrap(data)
            err = validate(raw)
            if err:
                messagebox.showerror("Invalid save", err)
                return
            game = detect_game(raw)
            self.game_var.set(game)
            enabled = flag_state(raw, game)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return

        self.path = path
        state = "already ENABLED" if enabled else "not enabled"
        self.file_label.config(text=os.path.basename(path), fg="black")
        self.status.config(
            text=f"Detected: {GAMES[game][0]}, {kind}\nGBA connectivity {state}",
            fg="green" if enabled else "black")
        self.patch_btn.config(state="disabled" if enabled else "normal")

    def do_patch(self):
        if not self.path:
            return
        try:
            result = patch(self.path, self.game_var.get())
        except Exception as e:
            messagebox.showerror("Patch failed", str(e))
            return
        messagebox.showinfo("Done", result)
        self.status.config(text="GBA connectivity enabled ✔", fg="green")
        self.patch_btn.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
