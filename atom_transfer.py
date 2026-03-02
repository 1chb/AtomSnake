import serial
import re
import argparse
import sys

def process_line(line, strip_remarks):
    """
    Process a BASIC program line, optionally stripping REM remarks.
    """
    line = line.strip()  # Strip outer whitespace, but preserve internal
    if not line:
        return None
    
    # Match line number and optional single lowercase letter label
    match = re.match(r'^(\d+)([a-z]?)', line)
    if not match:
        return None
    
    num = match.group(1)
    label = match.group(2)
    rest = line[match.end():]  # Preserve original whitespace in rest
    
    if not strip_remarks:
        return num + label + rest
    
    # For stripping: split by ; (assuming no ; inside strings)
    # Stop at first REM statement
    parts = re.split(r';\s*', rest.lstrip())  # lstrip to remove leading spaces after label
    new_parts = []
    for part in parts:
        p = part.strip()
        if p.upper().startswith('REM'):
            break
        new_parts.append(part.strip())  # Strip individual parts for cleanliness
    
    new_rest = '; '.join(new_parts)
    
    full_line = num + label
    if new_rest:
        full_line += ' ' + new_rest  # Add space only if needed
    return full_line if full_line.strip() else None

def send_and_get_response(ser, cmd, is_line_entry=False):
    """
    Send a command character by character, verify echoes, send CR,
    verify LF then CR (as per board behavior), then collect output until '>' at the start of a line.
    """
    output = b""
    
    cmd_bytes = cmd.encode('ascii')
    
    # Send each byte and verify echo
    for b in cmd_bytes:
        ser.write(bytes([b]))
        echo = ser.read(1)
        if not echo:
            raise ValueError(f"Timeout on echo for {b}")
        if echo != bytes([b]):
            raise ValueError(f"Echo mismatch: sent {b}, got {echo}")
    
    # Send CR
    ser.write(b'\r')
    
    # Expect LF first
    echo_lf = ser.read(1)
    if not echo_lf:
        raise ValueError("Timeout on LF after CR")
    if echo_lf != b'\n':
        raise ValueError(f"No LF after CR, got {echo_lf}")
    
    # Expect CR next
    echo_cr = ser.read(1)
    if not echo_cr:
        raise ValueError("Timeout on CR after LF")
    if echo_cr != b'\r':
        raise ValueError(f"No CR after LF, got {echo_cr}")
    
    # Now collect output until '>' at the start of a line
    last_was_newline = True  # After LF CR, we are at start of line
    newline_chars = {b'\r', b'\n'}
    
    while True:
        byte = ser.read(1)
        if not byte:
            raise ValueError("Timeout waiting for prompt")
        
        if last_was_newline and byte == b'>':
            # Found '>' at start of line, stop without including it
            break
        
        output += byte
        last_was_newline = byte in newline_chars
    
    # Decode output with ascii, ignoring errors
    output_str = output.decode('ascii', errors='ignore')
    
    # For line entry, expect no output
    if is_line_entry and output_str.strip():
        print("Warning: Unexpected output during line entry:", output_str, file=sys.stderr)
    
    return output_str

def main():
    parser = argparse.ArgumentParser(description="Utility for uploading/downloading BASIC programs to Acorn Atom via serial.")
    parser.add_argument('--port', required=True, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--upload', help='File to upload (BASIC program)')
    parser.add_argument('--download', help='File to save downloaded program to')
    parser.add_argument('--strip', action='store_true', help='Strip REM remarks during upload')
    
    args = parser.parse_args()
    
    if not args.upload and not args.download:
        parser.error("Specify --upload or --download (or both)")
    
    ser = serial.Serial(args.port, 9600, timeout=2, xonxoff=True)
    ser.reset_input_buffer()
    
    # Optional: Sync by reading until '>' at start of line or timeout
    sync_data = b""
    last_was_newline = True  # Assume potential start
    newline_chars = {b'\r', b'\n'}
    while True:
        byte = ser.read(1)
        if not byte:
            break  # Exit on timeout, no hang
        if last_was_newline and byte == b'>':
            break
        sync_data += byte
        last_was_newline = byte in newline_chars
    if sync_data:
        print("Synced, discarded:", sync_data.decode('ascii', errors='ignore'), file=sys.stderr)
    
    try:
        if args.upload:
            # Clear memory with NEW
            send_and_get_response(ser, "NEW", is_line_entry=True)
            
            with open(args.upload, 'r') as f:
                for line_num, file_line in enumerate(f, 1):
                    processed = process_line(file_line, args.strip)
                    if processed:
                        try:
                            send_and_get_response(ser, processed, is_line_entry=True)
                        except ValueError as e:
                            print(f"Error on line {line_num}: {e}", file=sys.stderr)
                            break
        
        if args.download:
            listing = send_and_get_response(ser, "LIST")
            # Normalize line endings to single \n, remove extra newlines
            listing = re.sub(r'[\r\n]+', '\n', listing).strip()
            with open(args.download, 'w') as f:
                f.write(listing + '\n')  # Ensure trailing newline
    
    finally:
        ser.close()

if __name__ == "__main__":
    main()
