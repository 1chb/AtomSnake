# Program Transfer Guide

This document explains how to transfer Snake.atom from your computer to the 6502 board via USB.

## Prerequisites

### Hardware
- USB-to-RS232 adapter (DB9 connector)
- Cable to connect adapter to your 6502 board

### Software (Linux)
- `stty` command (usually pre-installed)
- Optional: `screen` or `minicom` for manual interaction

## Quick Start

1. **Connect the hardware:**
   ```bash
   # Disconnect VT100 from board
   # Connect USB-to-RS232 adapter to board
   # Connect USB end to computer
   ```

2. **Identify the device:**
   ```bash
   ls -l /dev/ttyUSB*
   # Usually /dev/ttyUSB0
   ```

3. **Upload the program:**
   ```bash
   chmod +x upload-to-board.sh
   ./upload-to-board.sh /dev/ttyUSB0 9600 Snake.atom
   ```

4. **Verify (optional):**
   ```bash
   chmod +x verify-upload.sh
   ./verify-upload.sh /dev/ttyUSB0 9600 Snake.atom
   # Press Ctrl+C when listing completes
   # Compare /tmp/board-listing.txt with Snake.atom
   ```

5. **Reconnect VT100:**
   ```bash
   # Disconnect USB cable
   # Reconnect VT100 terminal
   # Type: RUN
   ```

## Manual Transfer (Alternative)

If the script doesn't work, transfer manually:

```bash
# Configure serial port
stty -F /dev/ttyUSB0 9600 cs8 -cstopb -parenb raw -echo

# Clear existing program
echo "NEW" > /dev/ttyUSB0
sleep 1

# Send program (adjust delay if lines are dropped)
while IFS= read -r line; do
    echo "$line" > /dev/ttyUSB0
    sleep 0.05  # 50ms delay between lines
done < Snake.atom
```

## Manual Verification

```bash
# Send LIST command
echo "LIST" > /dev/ttyUSB0

# Read output
cat /dev/ttyUSB0
# Press Ctrl+C to stop
```

## Troubleshooting

### Device not found
```bash
# Check USB connection
lsusb

# Check for serial devices
ls -l /dev/tty*

# Check dmesg for USB events
dmesg | tail -20
```

### Permission denied
```bash
# Add yourself to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect

# Or use sudo
sudo ./upload-to-board.sh
```

### Lines being dropped

If lines are missing after upload:
1. Increase LINE_DELAY in upload-to-board.sh (try 0.1 or 0.2)
2. Check baud rate matches board (should be 9600)
3. Verify cable connections

### Garbled output

- Wrong baud rate: Try different values (300, 1200, 9600, 19200)
- Cable issue: Check connections, try different cable
- Wrong port settings: Script uses 8N1 (8 data bits, no parity, 1 stop bit)

## Interactive Terminal (For Testing)

Use `screen` for interactive access:

```bash
# Install if needed
sudo apt-get install screen

# Connect
screen /dev/ttyUSB0 9600

# Exit screen: Ctrl+A then K then Y
```

Or use `minicom`:

```bash
# Install if needed
sudo apt-get install minicom

# Configure
minicom -s
# Set serial device to /dev/ttyUSB0
# Set baud to 9600
# Save setup as default

# Connect
minicom
```

## Workflow Summary

```
Computer               6502 Board          VT100
   |                      |                  |
   |                      |<---serial--------|
   |                   [Normal use]          |
   |                      |                  |
   |                      X  Disconnect      |
   |                      |                  |
   |---USB-to-serial----->|                  |
   |   (NEW command)      |                  |
   |   (upload program)   |                  |
   |   (verify with LIST) |                  |
   |                      |                  |
   X  Disconnect          |                  |
   |                      |                  |
   |                      |<---serial--------|
   |                   [Run program]         |
```

## File Transfer Speed Estimate

- Snake.atom: ~129 lines
- At 50ms/line: ~6.5 seconds
- At 100ms/line: ~13 seconds
- Much faster than manual typing!

## Notes

- The board echoes characters back, so you may see doubled output
- BBC BASIC accepts programs line-by-line as if typed
- Line numbers don't need to be sequential
- NEW command clears program memory
- RUN command starts execution
- LIST command displays the program
