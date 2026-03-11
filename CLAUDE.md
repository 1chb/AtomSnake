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

### Best Practices for This Project
1. Commit changes regularly with descriptive messages
2. The user must manually type any changes into the 6502 board, so minimize code size when possible
3. Test changes thoroughly before the user invests time typing them in
4. Use feature branches for experimental changes
5. Snake.atom is generated from Snake.abp - regenerate after editing .abp files

### Source Files

**Source → Generated relationship:**
- `AcornAtom.abp` - **COMMON MACROS** for Acorn Atom platform (VT100, BASIC language, OS keyboard)
- `Snake.abp` - **SOURCE FILE** with game-specific code, includes AcornAtom.abp
- `Snake.atom` - **GENERATED FILE** created by running `cpp -P Snake.abp`

The `.abp` extension stands for "Atom BASIC Preprocessed" — indicating the file requires the C preprocessor.

**Build Command:**
```bash
cpp -P Snake.abp > Snake.atom
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
- `[` - Up
- `;` - Left
- `,` - Right
- `/` - Down
- `+/-` - Adjust speed
- `W/Q` - Adjust width
- `H/G` - Adjust height
- `1/2/3` - Number of players
- `Esc/Q` - Quit

### Variables

Global state is stored in single-letter variables (A-Z). See `Snake.abp` for the complete variable list and their `#define` macro names. Key variables include `AA` (area array / binary indexed tree), `W` (width), `H` (height), `Z` (grid size W×H), `S` (snake head), `T` (snake tail), `D` (direction). Variables `I,J,K,L,M,N,P,Q` are temporaries reused across functions.

## Key Implementation Details

### Acorn Atom BASIC: IF Semantics
**CRITICAL**: When an `IF` condition is **false**, the **entire rest of the line** is skipped — all statements after `THEN` to the end of the line, including those separated by `;`. There is no way to escape the THEN scope on the same line. A second `IF` on the same line creates a nested condition — its THEN scope also extends to end of line.

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
1. Edit the **SOURCE** file: `Snake.abp` (or `AcornAtom.abp` for platform macros)
2. Generate the target file: `cpp -P Snake.abp > Snake.atom`
3. Review the generated `Snake.atom` for correctness
4. Upload to the board and test on actual hardware

**Deploy from a separate computer connected to the board via USB-to-serial:**
```bash
scp work:Documents/snake/{Snake,AcornAtom}.abp . && \
  (cpp -DPROD=1 Snake.abp > Snake.atom || true) && \
  python3 atom_transfer.py --port /dev/ttyUSB0 --upload Snake.atom && \
  picocom /dev/ttyUSB0 -b 9600
```

This command:
1. Copies the source files from the development machine (`work:` via SSH)
2. Builds the production `.atom` file with PROD mode (abbreviated keywords, no comments)
3. Uploads the program to the Acorn Atom board via USB-to-serial
4. Opens an interactive terminal session to the board with `picocom`

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
- **Program**: ~3442 bytes in memory (optimized PROD)
- **`DIM AA(Z-1)`**: Z × 4 bytes (integer array; double-letter DIM = 4-byte integers)
- **`DIM F(18)`**: 19 bytes (string buffer; single-letter DIM = 1-byte ASCII characters)
- **For 40×21 board**: 840 × 4 + 19 = 3379 bytes for arrays, leaving ~89 bytes free
- **For 40×22 board**: 880 × 4 + 19 = 3539 bytes — does NOT fit (exceeds available memory)

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
