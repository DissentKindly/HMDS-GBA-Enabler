# Enabling GBA Connectivity in Harvest Moon DS / DS Cute Saves

*A reverse-engineering write-up: the save format, the connectivity flags, and the checksum system of Harvest Moon DS (USA, Rev 1) and Harvest Moon DS Cute (USA), with a working patcher. Both games verified in-game — flag-patched saves load cleanly and spawn Mineral Town visitors. July 2026.*

## Background

Harvest Moon DS and DS Cute have a dual-slot feature: if Harvest Moon: Friends of Mineral Town (or More Friends of Mineral Town) is inserted in the DS's Slot-2 (GBA) port when the game runs, a set of Mineral Town features unlocks — Mineral Town villagers visit Forget-Me-Not Valley, additional courtship options open up, and related content becomes reachable. The RetroAchievements set for DS Cute gates over 30 achievements behind this content.

The important mechanical detail, confirmed by the RA community and verified here: the game performs the cartridge check and then **persists the result into the save file**. Once a save has been created or loaded with the cart present, connectivity stays enabled in that save forever, no cartridge required. This means the entire feature reduces to one question: *which bytes in the save encode "cart was detected"?* Answer that, and connectivity can be granted to any save with a hex editor — no DS, no cartridges, no emulator gymnastics. Nobody had published the answer; the RA set developer publicly noted attempting a patch for exactly this and abandoning it. This document is, to our knowledge, the first public documentation of the flag and of the save's integrity system.

## Save containers

The same 256 KiB flash image travels in three wrappers, and the patcher handles all of them transparently:

- **Raw `.sav`** — the flash image as-is. Used by melonDS, DraStic, most flashcarts and Android emulators.
- **DeSmuME `.dsv`** — the image followed by a text-marked binary footer (`|<--Snip above here …|-DESMUME SAVE-|`) recording DeSmuME's autodetected backup-device type and geometry. Note that DeSmuME can misdetect this game as EEPROM 512 kbit; the real hardware is **FLASH 2 Mbit**, and a `.dsv` created under misdetection will replay the wrong device type when reloaded. When importing into DeSmuME, use *Import Backup Memory* with MANUAL → FLASH 2 Mbit.
- **Action Replay `.duc`/`.dss`** — a 500-byte header beginning `ARDS0001`, containing the game title and metadata strings (UTF-16), followed by the raw image.

A DeSmuME-created image may be only 64 KiB if the emulator sized the backup device down; the game only needs block A to exist, and the image grows naturally. When converting to a 2 Mbit raw image, pad with `0xFF` (erased-flash state), not zeros.

## Flash image layout

```
0x00000  +--------------------------------------------------+
         | Global header (16 bytes)                         |
         |   +0x0  u16 counterA   — save count, block A     |
         |   +0x2  u16 counterB   — save count, block B     |
         |   +0x4  u16 chkA       — CRC of block A          |
         |   +0x6  u16 chkB       — CRC of block B (0 if    |
         |                          block B never written)  |
         |   +0x8  u16 magic      — 0x424B, ASCII "KB"      |
         |   +0xA  u16 hdrcrc     — CRC of bytes 0x0..0x7   |
0x00010  | 0xFF filler                                      |
0x00200  | Save block A  (0x8C00 bytes)                     |
0x08E00  | Save block B  (0x8C00 bytes)                     |
0x119FF  | (0xFF to end of flash)                           |
0x40000  +--------------------------------------------------+
```

Blocks A and B correspond to the game's two **diary save slots** — Slot 1 writes block A, Slot 2 writes block B, confirmed by the save's owner recalling the Slot 2 save date matching block B's contents. The counters at header +0x0/+0x2 are **slot-occupancy flags**, not save counts: re-saving to an already-used slot leaves its counter at 1. A brand-new save file has only block A (`counterB = 0`, `chkB = 0`). Because the player may load either slot, a patcher must modify **every present block**.

### Block internals

Each 0x8C00-byte block is close to a serialized dump of the game's save-data struct in RAM (around `0x023B96xx–0x023C1xxx` in the USA DS Cute build), piecewise-linear with small serialization gaps. Verified anchor points (offsets are block-relative):

| Offset      | Contents                                            |
|-------------|-----------------------------------------------------|
| +0x000      | u32, purpose unclear (stable across generations)    |
| +0x004      | Name table, ASCII, 16-byte fields: farm name, farmer name (+0x014), dog (+0x054), cat (+0x064), and further display strings including a birthday string (+0x264). In the male game every field starts one byte later, after a 0x01 marker at +0x004 — one of several small layout shifts between the two games. |
| +0x2F0      | u32 in-game clock                                   |
| +0x2F4      | u8 weather                                          |
| +0x2F8      | u8 fatigue, +0x2F9 fullness, +0x2FA stamina         |
| +0x2FC      | u32 gold                                            |
| +0x300      | u32 casino medals                                   |
| +0x304      | Rucksack/tool slots, 4 bytes each ([u16 id][u16]), `0xFFFF` = empty |
| +0xE18      | Clothing box entries                                |
| ~+0x58xx    | NPC records, 0x28 bytes per character               |
| ~+0x73C0–0x74A1 | Calendar / elapsed-time counters; +0x742C is the day-of-month, 0-indexed (Spring 1 stores 0) |
| **+0x73ED** | **Cute: GBA connectivity flag byte — bit 0x20 set by an MFoMT cart** |

In the male Harvest Moon DS the layout shifts: the connectivity flag sits at **+0x7361, bit 0x10**. The offsets are genuinely game-specific — Cute's mature saves carry unrelated data at +0x7361, and the male saves are zero at +0x73ED — so a patcher must know which game it is patching.

The full game x cartridge matrix was tested empirically, and every cell is verified:

| DS game              | + FoMT cart    | + MFoMT cart   |
|----------------------|----------------|----------------|
| Harvest Moon DS      | bit 0x10 set ✔ | bit 0x10 set ✔ |
| Harvest Moon DS Cute | bit 0x20 set ✔ | bit 0x20 set ✔ |

An early hypothesis that the bit encodes the cart type (0x10 = FoMT, 0x20 = MFoMT) was disproven: **either cartridge sets the same bit in either game**. The bit means simply "a Mineral Town cart was detected"; the differing values between the two games are incidental.

Closing the matrix surfaced a second finding about **detection timing**. An intermediate test — loading an existing Cute save with FoMT inserted and saving immediately — set nothing: no flag, and none of the transient session markers that accompany cart detection. Repeating Cute+FoMT as a fresh new game set bit 0x20 with the full transient signature, byte-identical to the MFoMT run. Conclusion: the Slot-2 probe runs during day-start initialization (new game, or presumably each new morning), not at save-load. Practical corollary for real-cartridge users that the community guides don't spell out: after inserting the cart, play into a new in-game day before saving, or the connectivity flag will not be persisted.

## Finding the flag: methodology

With only a connected save available, the flag can't be isolated — its two internal generations both carry it. The decisive method was a **minimal-pair experiment**: two fresh runs in DeSmuME with identical inputs (same character, names, birthday, saved at the first diary opportunity), differing in exactly one variable — More Friends of Mineral Town present in Slot-2 or not.

The resulting diff contained ~2,100 differing bytes, nearly all noise: the randomized farm-debris layout (branch/stone/weed object codes differ per run because the RNG seeds from the real-time clock) and RTC timestamps. Three structural candidates remained:

1. `blk+0x1430`: a table entry `80FF 80FF …02` present only with the cart
2. `blk+0x5880`: a serialized RAM pointer (`0x0215A138`) plus a `01` byte
3. `blk+0x73ED`: bit `0x20` set

Cross-checking against a mature connected save (in-game day 26, two save generations) eliminated candidates 1 and 2 — both were transient runtime state, absent from the older save. Candidate 3 was set in the fresh with-cart save **and** in both generations of the mature save, and absent from the no-cart save. Persistent, minimal, consistent: that's the flag.

**GBA connectivity flag: block offset +0x73ED, bit 0x20.**
File-absolute: `0x75ED` (block A), `0x101ED` (block B); add 500 for `.duc` files.

## The checksum system

Setting the bit alone produces a save the game silently treats as nonexistent — proven by a three-file isolation test (known-good save loads; unmodified fresh save loads; bit-flipped fresh save does not). The game therefore validates integrity. Locating the check: a content checksum must differ whenever content differs, so it must lie in the intersection of the diff-sets of two independent save pairs. That intersection contained **no bytes inside the block** — pinning the checksums to the global header words, which differ in every pair.

Standard algorithms (CRC-16 presets, CRC-32 variants, Adler, Fletcher, BSD rotate-add, ones'-complement sums, plain sums in 8/16/32-bit units, all over every candidate range) all failed. The breakthrough was an exhaustive search over all 65,536 CRC-16 polynomials in both bit orders, made init- and xorout-independent by a linearity trick: for any CRC, `crc(a) ⊕ crc(b) = crc₀(a ⊕ b)`, so XORing each sample pair cancels the unknown seed, leaving a pure polynomial test. Across every polynomial × every prefix length × two independent sample pairs, exactly **one** candidate satisfied both pairs:

> **CRC-16, reflected, polynomial 0xA001** (the classic IBM/ARC polynomial), over the **full 0x8C00 block**, with a constant offset.

Deriving the constant from four known-good blocks gave the same value every time:

```
chk  = crc16_A001(block, init=0) XOR 0x4FC3        (per block)
hdrcrc = crc16_A001(header[0x0..0x7], init=0) XOR 0x0E65
```

The XOR constants fold in whatever init/final-xor convention the game's implementation uses; the formulas above reproduce all three sample saves' headers byte-exactly. Note the two-tier design: each block is checked, and then the header — containing the counters and both block checksums — is checked again by `hdrcrc`. A patcher that fixes only the block CRC still fails validation; both tiers must be recomputed. This is very likely why previous patch attempts by others failed: an edited save doesn't crash or warn, it just vanishes from the load menu, giving no hint that a second-order checksum exists.

## The patcher

`hmds_gba_enabler_gui.py` (Tkinter GUI, no dependencies beyond stock Python 3) and `hmds_savetool.py` (CLI with `info` / `diff` / `set` / `convert` / `enable-gba`) implement the complete procedure:

1. Unwrap the container (`.duc` header / `.dsv` footer / raw), preserving the wrapper bytes for re-assembly.
2. Sanity-check: size, `"KB"` header magic, and block-A CRC validation — a corrupt or foreign file is rejected before anything is touched.
3. Set bit `0x20` at `+0x73ED` in every present block (block B only if `counterB > 0`).
4. Recompute `chkA`, `chkB`, then `hdrcrc`, in that order.
5. Rename the original to `<name>.backup-<timestamp>` and write the patched file under the original name (the GUI restores the backup automatically if the write fails).

The net change to a save is five bytes: one flag bit and four checksum bytes.

## Using the tools

Two implementations ship with this document, both dependency-free Python 3:

**`hmds_gba_enabler_gui.py`** — for end users. Run it, pick the save, click *Enable GBA Connectivity*. It auto-detects the game and container, validates checksums before touching anything, renames the original to a timestamped `.backup-*`, patches every used diary slot, and rewrites both checksum tiers.

**`hmds_savetool.py`** — command-line toolkit. `enable-gba SAVE [OUT] [--game auto|cute|boy]` is the equivalent one-shot patcher (no automatic backup — pass an output path for precious saves). `info` summarizes a save (game, slots, names, flag state); `diff` aligns two saves and lists differing bytes — the exact instrument used for every discovery in this document; `set` writes arbitrary bytes with checksum fixup for further research; `convert` rewraps between `.sav`/`.dsv`/`.duc`. All commands accept any of the three containers and answer `-h` with details.

## Caveats and open questions

Verification status: both games (Harvest Moon DS USA Rev 1, Harvest Moon DS Cute USA), all four game x cartridge combinations, and both patched-save load paths have been tested — the container, the two-tier CRC (same constants 0x4FC3 / 0x0E65 in both games), the per-game flag bits, and in-game activation of Mineral Town content from flag-only patched saves are all confirmed. What remains is a short list of loose ends, none of which affect the patcher.

A u16 stored twice at blk+0x5E83/0x5E9B in the male game initially looked flag-correlated (1736 without a cart, 1749 with FoMT), but a third sample (1564 with MFoMT) shows it simply varies per session. The transient structures written alongside cart detection have a partially characterized lifecycle: the `+0x5880` pointer is cleared by the next morning (a true per-session artifact), while the `+0x1430` entry and the byte at `+0x5885` persist at least one day but are gone from mature saves weeks later — consistent with visitor-scheduling records that get consumed over time. The meaning of the stable u32 at block offset 0 is unidentified. One prediction of the detection-timing model remains untested directly: that inserting a cart, loading an unflagged save, sleeping one night, and saving would set the flag (twenty years of real-cartridge community practice strongly implies it, but it hasn't been demonstrated at the byte level here).

Region caveats: all findings are from USA releases. European DS releases had the GBA-connection feature removed entirely, and Japanese releases only link with Japanese GBA carts and carry additional newspaper content — neither has been examined at the save level, and the flag offsets documented here should not be assumed to transfer.
