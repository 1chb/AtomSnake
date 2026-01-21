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
- **No Automatic Transfer**: Programs must be manually typed into the VT100 terminal character-by-character.
- **Development Cycle**: Extremely slow due to manual entry requirement.
- **Future Plan**: USB-to-serial connection for automatic transfer (separate project).

### Source Control
Files are under Git source control. Standard git workflow applies.

### Best Practices for This Project
1. Commit changes regularly with descriptive messages
2. The user must manually type any changes into the 6502 board, so minimize code size when possible
3. Test changes thoroughly before the user invests time typing them in
4. Use feature branches for experimental changes
5. Snake.atom is generated from Snake.ab - regenerate after editing Snake.ab

### Source Files

**Source → Generated relationship:**
- `Snake.ab` - **SOURCE FILE** with C preprocessor macros for readability
- `Snake.atom` - **GENERATED FILE** created by running `cpp -P Snake.ab`
- `Snake.atom~` and `Snake.ab~` - Backup files (tilde suffix)

**Build Command:**
```bash
cpp -P Snake.ab > Snake.atom
```

The `.ab` file uses `#define` macros for:
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

Global state is stored in single-letter variables:
- `AA` - Area array (binary indexed tree)
- `C` - Turn (-1=Left, 0=Ahead, 1=Right)
- `D` - Direction (0=West, 1=North, 2=East, 3=South)
- `H` - Height (3-22, default 22)
- `S` - Snake head position
- `T` - Snake tail position
- `U` - Score
- `V` - String buffer for drawing
- `W` - Width (5-40, default 40)
- `Z` - Grid size (H×W)
- `I,J,K,L,M,N,P,Q` - Temporary variables (reused across functions)

## Key Implementation Details

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
1. Edit the **SOURCE** file: `Snake.ab`
2. Generate the target file: `cpp -P Snake.ab > Snake.atom`
3. Review the generated `Snake.atom` for correctness
4. User manually types the program into the 6502 board via VT100 terminal
5. Test on actual hardware

**Remember**: Because of the manual typing requirement, favor smaller, cleaner code. Every character counts!

### Testing Considerations
When modifying the code:
- The binary indexed tree logic (Init, Adjust, Locate) is critical and fragile
- Test boundary conditions: minimum grid (5×3), maximum grid (40×22)
- Verify snake collision detection at borders and self-collision
- Check that food placement never overlaps snake or borders
- Ensure terminal escape sequences render correctly on target system

### Performance Characteristics
- Tree operations: O(log n) for both Adjust and Locate
- Memory usage: 2×(W×H) words for tree array
- Display updates: Direct cursor positioning (no full redraws)

## Common Modifications

When adding features or fixing bugs:
- Be cautious with temporary variables I,J,K,L,M,N - they're reused across function calls
- Preserve the tree invariant: parent count = sum of children counts
- Remember that `AA` indices use 0-based indexing but positions use grid coordinates
- VT100 sequences may need adjustment for different terminals
- The `@` variable controls some BASIC interpreter behavior (see line 4020, 9810)
