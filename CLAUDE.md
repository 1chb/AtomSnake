# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Snake game implementation written in BBC BASIC for a custom 6502 board computer (modified Acorn Atom). The game features:
- Classic snake gameplay with configurable grid size and speed
- Multiple player modes (1-3 players) including auto-play
- VT100 terminal graphics with double-width characters
- Efficient space management using a binary indexed tree

**Project Status**: Unfinished, last worked on ~3 years ago (2023).

## CRITICAL: Development Environment & Workflow

### Hardware Setup
- **Target System**: Custom 6502 board computer (modified Acorn Atom from 1980)
- **Key Difference from Original**: Original Acorn Atom had built-in keyboard and TV output. This variant connects to a VT100 terminal via RS232 serial port.
- **Transfer**: Programs are uploaded to the board via USB-to-serial using `atom_transfer.py`.

### Source Control
Files are under Git source control. Standard git workflow applies.

### CRITICAL: Git Commit Workflow

**NEVER commit without explicit user approval.**

When working on changes:
1. **Always include "Commit changes" as a TODO item** at the start of work
2. **Complete all implementation and testing** first
3. **Show the user a summary/diff** of all changes made
4. **Wait for explicit "Commit" or "Go" command** from the user
5. **Only then run git commit**

The user ALWAYS wants to review changes before they are committed. No exceptions.

### Best Practices for This Project
1. **Bugs are not allowed.** Test changes thoroughly before the user invests time typing them in
2. Minimize code size when possible so the program fits into the 8KB RAM
3. Use feature branches for experimental changes
4. Snake.atom is generated from Snake.abp - regenerate after editing .abp files

### Source Files

**Source → Generated relationship:**
- `AcornAtom.abp` - **COMMON MACROS** for Acorn Atom platform (VT100, BASIC language, OS keyboard)
- `Snake.abp` - **SOURCE FILE** with game-specific code, includes AcornAtom.abp
- `optimize.py` - **BUILD TOOL** that optimizes the preprocessed output (strips warnings, removes spaces, merges lines, etc.)
- `Snake.atom` - **GENERATED FILE** created by the build pipeline: `cpp -P Snake.abp | python3 optimize.py > Snake.atom`

The `.abp` extension stands for "Atom BASIC Preprocessed" — indicating the file requires the C preprocessor.

**Build Command:**
```bash
cpp -P Snake.abp | python3 optimize.py > Snake.atom
```

Or use the Makefile (recommended):
```bash
make Snake.atom          # Build only
make transfer            # Build and upload to board
make play                # Build, upload, and open terminal
```

The `.abp` files use `#define` macros for:
- Variable names (e.g., `#define width W`, `#define height H`)
- Constants (e.g., `#define West 0`, `#define East 2`)
- Control flow readability (e.g., `#define If(expr) IF expr`)
- Label management (e.g., `#define Subroutine(line, label)`)

The generated `.atom` file contains expanded BASIC code with inline documentation, state machine diagrams, bit field specifications, and algorithm explanations.

## Architecture

### State Machine
The game operates as a state machine with these states:
- `START` → `WELCOME` - Initialization and help screen
- `WELCOME` - Main menu (options: Play, Auto, configure, quit)
- `PLAY` - Active gameplay with player control
- `AUTO` - Automatic/AI gameplay
- `PAUSE` - Game paused
- `RESULT` - Game over screen
- `CONFIRM` - Quit confirmation
- `STOP` - Exit

### Data Structure: Binary Indexed Tree (Fenwick Tree)

The game uses a clever space-efficient data structure stored in the `AA` array. Each cell stores information in bit fields:

**Bits 0-1**: Content type
- `00` (Empty=0) - Empty space
- `01` (Mouse=1) - Food/cake
- Direction for snake segments: `00`=West, `01`=North, `10`=East, `11`=South

**Bit 2**: Border/snake flag
- `1` if the cell contains a snake segment or wall
- `0` otherwise

**Bits 3-30**: Empty cell count in the tree structure (multiples of 8)

**Bit 31**: Unused

The array implements a binary indexed tree that efficiently tracks empty cells for random food placement. The tree is structured so that:
- `AA(0)` contains the total count of empty cells (×8)
- Child nodes at indices `2*i+1` and `2*i+2` split the range
- This enables O(log n) updates and O(log n) random empty cell lookup

### Core Subroutines

**Line 1000: Adjust(P, Q)** - Updates the binary tree when cells change state
- P = cell index
- Q = quantity to adjust (±8)
- Traverses tree from root to leaf, updating counts

**Line 2000: Locate(P)** - Finds the Nth empty cell using binary tree
- P = count (0 ≤ P*8 < AA(0))
- Returns position in J
- Uses binary search down tree, then linear search at leaf level

**Line 4000-4400: Page, MoveTo, HomePage, Border** - VT100 terminal rendering
- Page: Clears screen and draws UI with double-width title
- MoveTo: Positions cursor at game grid coordinates
- HomePage: Draws initial border using reverse video
- Border: Draws and marks border cells, updating tree

**Line 4500: InitSnake** - Places initial snake in center of grid
- Calculates center position: `(H+1)/2*W-W/2`
- Creates 3-segment snake facing East
- Snake represented as `+` characters

**Line 5000: ChangeDirection(D)** - Updates snake head direction
- Only updates if direction actually changed
- Stores new direction in bits 0-1 of head cell

**Line 6000: Step** - Calculates next position given current position and direction
- Formula: `P + (D&2-1) * ((D&1)*(W-1)+1)`
- Handles all four cardinal directions with single expression

**Line 6500: EatTail** - Removes tail segment when snake moves without eating
- Releases space back to tree via Adjust
- Clears display with space character
- Advances tail pointer using Step

**Line 6700: AdvanceHead** - Moves snake forward
- Gets current direction from head
- Calculates new head position
- Checks for collision (bit 2 set)
- Allocates new head cell from tree
- Eats tail if no food consumed
- Updates score based on what was eaten

**Line 7000: Draw(P, V)** - Renders a character at game grid position

**Line 9000: Clash** - Handles game over condition

### Control Scheme

- `P` - Play/Pause
- `A` - Auto mode
- `8` - Up (keyboard mode) / Down (phone mode)
- `4` - Left
- `6` - Right
- `2` - Down (keyboard mode) / Up (phone mode)
- `/` - Toggle between keyboard and phone numpad layouts (only in pause mode)
- `+/-` - Adjust speed
- `W/Q` - Adjust width
- `H/G` - Adjust height
- `1/2/3` - Number of players
- `Esc/Q` - Quit

### Numpad Layout Toggle

The game supports both keyboard numpad and phone numpad layouts, since these have opposite vertical orientations. **The toggle can only be changed while paused** - press `P` to pause, then `/` to toggle.

**Keyboard mode (default):**
- `8` (top of numpad) = Up
- `2` (bottom of numpad) = Down
- `4` = Left, `6` = Right

**Phone mode (press `P` to pause, then `/` to toggle):**
- `2` (top of phone keypad) = Up
- `8` (bottom of phone keypad) = Down
- `4` = Left, `6` = Right

The selected mode persists across games until toggled again.

### Variables

Global state is stored in single-letter variables (A-Z). See `Snake.abp` for the complete variable list and their `#define` macro names. Key variables include `AA` (area array / binary indexed tree), `W` (width), `H` (height), `Z` (grid size W×H), `S` (snake head), `T` (snake tail), `D` (direction). Variables `I,J,K,L,M,N,P,Q` are temporaries reused across functions.

### Variable Usage Annotations (`vu(...)`)

Each code line in `Snake.abp` has a `vu(G-IJKLMN)` annotation that tracks the **liveness of temporary variables** at that line. The purpose is to answer: "which temp variables hold live values that must not be overwritten?"

The 8 positions track: `G` (player2), `-` (separator), then `I`, `J`, `K`, `L`, `M`, `N`. Variables `P` and `Q` (pos, quantity) are not tracked as they are transient parameters to subroutines.

**Annotation symbols:**

| Symbol | Meaning | Details |
|--------|---------|---------|
| `.` | Free | Variable does not hold a live value. Safe to overwrite. |
| **Uppercase** (`I`) | **Write** | Variable is assigned a new value on this line. The previous value is irrelevant — it does NOT depend on the current value. Introduces a new live value. |
| **Lowercase** (`i`) | **Read** (and maybe write) | Variable's current value is **read/depended upon** on this line. The value from a prior assignment matters. It may also be modified, but the key point is the read dependency. |
| **Pipe** (`\|`) | **Holds value** | Variable has a live value that will be needed on a future line, but is NOT accessed on this line. Used inside loops where a variable set before the loop is still needed after. |
| `*` | **Clash (BUG)** | Variable was live (pipe or lowercase) but is destroyed on this line. Indicates a potential bug — the live value will be lost. |

The lifecycle of a value is: **Uppercase** (written), then zero or more **Pipe** lines (holding), then **Lowercase** (used). This pattern repeats each time the value is needed on a subsequent line. A subroutine call is no different from inline code — if it destroys a variable, that's an Uppercase; if it reads one, that's a Lowercase. The subroutine's signature tells you which variables are affected.

**Example:**
```
3520 vu(.-......) For(time=1) To(3)          // time written (not tracked), no temps
3525 vu(.-.J....)   J=head; ...              // J written (uppercase)
3530 vu(.-IjKLMN)  If(AA(J)&7) Gosub(...)   // J read; I,K,L,M,N destroyed by callee
3540 vu(.-.j....)   pos=J; ...               // J read (lowercase, value survived)
3550 vu(.-I...MN)   ...; Gosub(Adjust)       // I,M,N destroyed by Adjust
3560 vu(.-......) Next(time)                  // no tracked temps live
```

### Subroutine Signatures

Subroutines are documented with input/output/destroyed annotations:
```
Subroutine(line, label, inputs => outputs : destroyed)
```
Or for line-number-referenced subroutines:
```
#define Name line // inputs => outputs : destroyed
```

- **Inputs**: variables read by the subroutine (or its callees, transitively).
- **Outputs**: variables whose values are meaningful to the caller after return. This includes variables modified as side effects, even if the caller doesn't always use them.
- **Destroyed**: variables whose values are overwritten and unpredictable after return. The caller must not rely on their pre-call values surviving.

**Signatures must reflect worst-case behavior**: if a conditional branch destroys a variable, it must be listed as destroyed. If a callee destroys a variable, the caller's signature must propagate that destruction upward.

**Transitive closure**: a subroutine's inputs/outputs/destroyed must account for all callees recursively. If `A` calls `B` which destroys `I`, then `A` also destroys `I`.

## Key Implementation Details

### Acorn Atom BASIC: IF Semantics
**CRITICAL**: When an `IF` condition is **false**, the **entire rest of the line** is skipped — all statements after `THEN` to the end of the line, including those separated by `;`. There is no way to escape the THEN scope on the same line. A second `IF` on the same line creates a nested condition — its THEN scope also extends to end of line.

### Operator Precedence
Acorn Atom BASIC operator precedence (highest to lowest):
1. `*`, `/`, `%`, `&` — Multiplicative and bitwise AND (same level, left-to-right)
2. `+`, `-`, `|`, `:` — Additive and bitwise OR/XOR (same level, left-to-right)
3. `=`, `<`, `>` — Comparison (return 1 for true, 0 for false)
4. `AND`, `OR` - Also bitwise like `&` and `|` but lower precedence

**Key implications:**
- `flags&3=3` is parsed as `(flags&3)=3` — AND before comparison. Safe for flag testing.
- `flags&1=0` is parsed as `(flags&1)=0` — works correctly for negative flag checks.
- `5&2*2` is parsed as `(5&2)*2` = `0` — AND has same precedence as multiply, left-to-right.
- `2*2&5` is parsed as `(2*2)&5` = `4` — multiply before AND, left-to-right.
- `A+B&C` is parsed as `(A+B)&C` — wrong level! AND is level 1, addition is level 2. Use parentheses: `A+(B&C)`.
- `A|B:C` is parsed as `(A|B):C` — OR and XOR are same level, left-to-right.

### Labels vs Variables
Labels (lowercase a-z) and variables (uppercase A-Z) are **completely separate namespaces** in Acorn Atom BASIC. There is no relationship between `i` (a label) and `I` (a variable). Labels are assigned at program load time: a line like `1000p` sets `p=1000` when the program is loaded into memory, not when the line executes. `GOSUB p` then jumps to line 1000.

### Direction Encoding
Directions use 2 bits with a clever encoding that simplifies calculations:
- West=0, North=1, East=2, South=3
- Turning: `D = (D + Turn) & 3` where Turn ∈ {-1, 0, 1}
- Opposite check: `(D1 ^ D2) = 2` means directions are opposite

### Movement Calculation
The Step subroutine uses bitwise operations to avoid branching:
```
NewPos = P + (D&2-1) * ((D&1)*(W-1)+1)
```
This single expression handles all four directions.

### VT100 Sequences
The game uses ANSI/VT100 escape codes:
- `$12` - Clear screen
- `$27"[2J"` - Alternative clear
- `$27"[{row};{col}H"` - Position cursor
- `$27"#6"` - Double-width characters
- `$27"#3"` or `$27"#4"` - Double-height (top/bottom)
- `$27"[7m"` - Reverse video
- `$27"[m"` - Normal video

## Development Notes

### Development Workflow

**Recommended workflow using the Makefile:**

1. Edit the **SOURCE** files on the development machine: `Snake.abp` or `AcornAtom.abp`
2. From the deployment computer (connected to the board via USB-to-serial), run:
   ```bash
   make play
   ```
   This automatically:
   - Fetches source files from the dev machine via `scp` (configured in `SRC_DIR` variable)
   - Runs the build pipeline: `cpp -P -DPROD Snake.abp | python3 optimize.py > Snake.atom`
   - Uploads `Snake.atom` to the board via `atom_transfer.py` (with `--optimize-esc` in PROD mode)
   - Opens an interactive terminal session with `picocom`

**Manual workflow (if not using Makefile):**

1. Edit the **SOURCE** file: `Snake.abp` (or `AcornAtom.abp` for platform macros)
2. Generate the target file: `cpp -P Snake.abp | python3 optimize.py > Snake.atom`
3. Review the generated `Snake.atom` for correctness
4. Upload to the board and test on actual hardware

**Build pipeline details:**

The build process runs through two stages:
1. **C Preprocessor (`cpp`)**: Expands macros, processes `#define`/`#include` directives
   - In PROD mode (`-DPROD`): Keywords are abbreviated (IF→I., GOTO→G., etc.), comments stripped
   - Non-PROD mode: Full keywords and comments preserved for readability
2. **Optimizer (`optimize.py`)**: Post-processes the output to minimize size
   - Strips cpp warnings
   - Removes trailing semicolons and unnecessary spaces
   - Converts hex literals to decimal (`#38` → `56`)
   - Evaluates constant expressions (`(-1-2)` → `-3`)
   - Merges adjacent string literals (`"A" "B"` → `"AB"`)
   - Merges consecutive short lines (respecting 63-character limit and jump targets)
   - Truncates REM comments if lines exceed 63 characters
   - In PROD mode with `--optimize-esc`: Further optimizes VT100 escape sequences

**Remember**: The `.atom` file has a 63-character line length limit. Favor smaller, cleaner code.

**CRITICAL**: Never use `GOTO` or `GOSUB` to jump to a line that only contains `Remark(...)`. In PROD mode, `Remark` expands to nothing, so the line is deleted entirely and the jump target becomes invalid. Always ensure jump targets have at least one executable statement. If needed, move the remark to the end of the next executable line.

**Code size tips**: Use `//` cpp comments instead of `Remark(...)` for documentation that doesn't need to appear in the `.atom` output — cpp strips them entirely (zero bytes). `Remark(...)` costs vary by context: `...; Remark(text)` appended to a line costs 6+len(text) bytes in non-PROD (expands to `; REM text`) and 1 byte in PROD (just the `;`). A standalone `Remark(text)` line costs 8+len(text) bytes in non-PROD (line number, space, `REM `, text, newline) but zero bytes in PROD (the line is deleted entirely).

### Testing Considerations
When modifying the code:
- The binary indexed tree logic (Init, Adjust, Locate) is critical and fragile
- Test boundary conditions: minimum grid (5×3), maximum grid (40×21)
- Verify snake collision detection at borders and self-collision
- Check that food placement never overlaps snake or borders
- Ensure terminal escape sequences render correctly on target system

### Memory Layout
- **Total RAM**: 8192 bytes (8KB)
- **System/BASIC workspace**: ~1282 bytes (from address 0)
- **Program**: ~4558 bytes in memory (optimized PROD)
- **`DIM AA(Z-1)`**: Z × 4 bytes (integer array; double-letter DIM = 4-byte integers)
- **`DIM F(31)`**: 32 bytes (string buffer; single-letter DIM = 1-byte ASCII characters)
- **For 38×17 board**: 38 x (17-2) × 4 + 32 = 2312 bytes for arrays, leaving ~8 bytes free
- **For 40×22 board**: 40 x (22-2) × 4 + 32 = 3232 bytes — does NOT fit (exceeds available memory with ~1 KB)

Note: `DIM` with single-letter variable names allocates byte strings (1 byte per element).
`DIM` with double-letter variable names allocates integer arrays (4 bytes per element).

### Performance Characteristics
- Tree operations: O(log n) for both Adjust and Locate
- Display updates: Direct cursor positioning (no full redraws)

## Common Modifications

When adding features or fixing bugs:
- Be cautious with temporary variables I,J,K,L,M,N - they're reused across function calls
- Preserve the tree invariant: parent count = sum of children counts
- Remember that `AA` indices use 0-based indexing but positions use grid coordinates
- VT100 sequences may need adjustment for different terminals
- The `@` variable controls some BASIC interpreter behavior (see line 4020, 9810)
