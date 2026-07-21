<img width="313" height="313" alt="MadeByAI" src="https://github.com/user-attachments/assets/1e78aa61-895e-4026-a510-4e9de784dca6" />


# HMDS GBA Connectivity Enabler

Enable the GBA / Mineral Town connectivity bonus in **Harvest Moon DS** and
**Harvest Moon DS Cute** save files — no Nintendo DS, no GBA cartridge, no
Slot-2 hardware required.

When either DS game detects a *Friends of Mineral Town* or *More Friends of
Mineral Town* cartridge in the DS's GBA slot, it permanently unlocks bonus
content in that save: Mineral Town villagers visit Forget-Me-Not Valley, five
extra marriage candidates become available, exclusive music records appear in
shops — and some RetroAchievements are gated behind it. The detection
result is stored as a single flag bit in the save file, protected by a
two-tier CRC integrity system. This tool sets the flag and fixes the
checksums, which is all the games ever check.

## Features

- **One-click GUI** (`hmds_gba_enabler_gui.py`) — select save, click patch,
  done. Automatic timestamped backup of the original file.
- **CLI toolkit** (`hmds_savetool.py`) — scriptable patching plus research
  commands: save inspection, byte-level diffing, raw patching with checksum
  fixup, and container conversion.
- Supports all common save containers: raw **`.sav`** (melonDS, DraStic,
  flashcarts), DeSmuME **`.dsv`**, and Action Replay **`.duc`**.
- Auto-detects which game a save belongs to (manual override available).
- Patches both diary save slots and recomputes both checksum tiers, so the
  game accepts the file without complaint.
- Zero dependencies — stock Python 3 only.

## Requirements

- Python 3.8+ (any OS). The GUI additionally needs tkinter, which is bundled
  with Python on Windows and macOS; on Debian/Ubuntu:
  `sudo apt install python3-tk`.

## Usage

### GUI

```
python3 hmds_gba_enabler_gui.py
```

Click **Select Save File…**, pick your `.sav` / `.dsv` / `.duc`, confirm the
detected game, and click **Enable GBA Connectivity**. Your original file is
renamed to `<name>.backup-<timestamp>` before anything is written.

### Command line

```
# patch in place
python3 hmds_savetool.py enable-gba mysave.sav

# patch to a new file, forcing the game selection
python3 hmds_savetool.py enable-gba mysave.duc patched.duc --game cute

# inspect a save
python3 hmds_savetool.py info mysave.dsv

# see all commands
python3 hmds_savetool.py --help
```

Note: unlike the GUI, the CLI does not create backups.

## How it works

Short version: the save image contains two diary-slot blocks. Each game
stores a persistent "Mineral Town cartridge detected" bit inside the block —
**+0x73ED bit 0x20** in DS Cute, **+0x7361 bit 0x10** in the male game —
and validates each block with a CRC-16 (polynomial 0xA001) XOR 0x4FC3,
then validates the checksum table itself with a second CRC XOR 0x0E65.
Editing the flag without recomputing both tiers makes the save silently
vanish from the load menu, which is why earlier patch attempts by others
failed. Either GBA cartridge sets the same bit; all four game × cartridge
combinations were verified empirically.

The full reverse-engineering story — container formats, block layout, the
minimal-pair methodology, the checksum brute-force, detection timing, and
remaining open questions — is in
[`hmds_gba_connectivity_writeup.md`](hmds_gba_connectivity_writeup.md).

## Verification status

Tested on USA releases: Harvest Moon DS (Rev 1) and Harvest Moon DS Cute.
All four game × cartridge combinations confirmed at the byte level, and
flag-patched saves verified in-game on melonDS, DeSmuME, and Android
handheld emulation (Mineral Town visitors appear, achievements unlock).

**Not covered:** European releases (Natsume/Rising Star removed the GBA
feature entirely) and Japanese releases (region-locked linking, different
content) — the documented offsets should not be assumed to transfer.

## Repository contents

| File | Purpose |
|------|---------|
| `hmds_gba_enabler_gui.py` | End-user GUI patcher |
| `hmds_savetool.py` | CLI patcher and research toolkit |
| `hmds_gba_connectivity_writeup.md` | Full technical write-up |

## Contributing / further research

The `diff` command is the instrument that produced every finding here: make
two saves that differ in exactly one variable and compare them. Open
questions that a contributor with the right setup could close are listed at
the end of the write-up — Japanese-release offsets are the most interesting
gap.

## Acknowledgements

Thanks to the RetroAchievements community — particularly **Brylefi**,
developer of the Harvest Moon DS achievement sets, whose forum notes
confirmed the flag-persistence behavior and the need for exactly this tool —
and to fogu.com (Ushi No Tane), whose two decades of Harvest Moon
documentation anchored the gameplay side of this work.

## License

CC0 — see [`LICENSE`](LICENSE).

## Disclaimer

This project modifies game save files. It does not contain, require, or
distribute any ROMs or copyrighted game data. Always keep backups of saves
you care about (the GUI makes one for you). Not affiliated with Natsume,
Marvelous, or Nintendo.
