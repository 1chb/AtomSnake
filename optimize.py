#!/usr/bin/env python3
"""Optimizer for Acorn Atom BASIC PROD output.

Reads a .atom file (PROD preprocessed) and applies size optimizations:
1. Strip cpp warnings from output
2. Remove trailing semicolons
3. Remove spaces after labels (letter suffixes on line numbers)
4. Remove spaces after abbreviated commands (I. F. G. P. N. etc.)
5. Remove spaces after THEN (which is empty in PROD)
6. Merge consecutive short lines (respecting 63-char limit), except:
   - Lines that are GOTO/GOSUB targets (by line number)
   - Don't append to a line whose last statement is IF (THEN gates rest of line)
7. Remove empty lines

Usage: python3 optimize.py < input.atom > output.atom
       python3 optimize.py input.atom [output.atom]
"""

import re
import sys


MAX_LINE = 63


def find_jump_targets(lines):
    """Find all line numbers that are GOTO or GOSUB targets."""
    targets = set()
    for line in lines:
        # G. 1280 or G.1280 or GOS. 1140 or GOS.1140
        for m in re.finditer(r'(?:G\.|GOS\.)\s*(\d+)', line):
            targets.add(m.group(1))
    return targets


def parse_line(line):
    """Parse a line into (line_number, label, body).
    
    Line format: <number>[<label>] [<body>]
    Examples:
        '10 W=40'        -> ('10', '', 'W=40')
        '1000p'          -> ('1000', 'p', '')
        '1000pGOS.h'     -> ('1000', 'p', 'GOS.h')
        '1100q I.B=0 R.' -> ('1100', 'q', ' I.B=0 R.')
        '60'             -> ('60', '', '')
    """
    m = re.match(r'^(\d+)([a-z]?)(.*)', line)
    if not m:
        return None, None, None
    num, label, body = m.group(1), m.group(2), m.group(3)
    return num, label, body


def contains_if(line):
    """Check if the line contains any IF statement (outside strings).
    
    In Atom BASIC, IF condition is false skips the ENTIRE rest of the line.
    So we can never safely append to a line that contains any IF — the
    appended code would be gated by that IF's condition.
    """
    in_string = False
    for i, c in enumerate(line):
        if c == '"':
            in_string = not in_string
        elif not in_string and c == 'I' and i + 1 < len(line) and line[i + 1] == '.':
            # Exclude DIM etc: only reject if preceded by uppercase alpha
            if i == 0 or not line[i - 1].isupper():
                return True
    return False


def remove_trailing_semicolons(line):
    """Remove trailing semicolons (and whitespace after them)."""
    return re.sub(r';\s*$', '', line)


def remove_unnecessary_spaces(line):
    """Remove unnecessary spaces in PROD BASIC code.
    
    - Space after label: '1100q I.' -> '1100qI.'
    - Space after abbreviated commands: 'I. ', 'G. ', 'GOS. ', 'F. ', 'P. ',
      'N. ', 'R. ', 'T. ', 'S. ', 'U. ', 'E. ', 'DIM '
    - But NOT inside strings or after commands where the space is meaningful
    """
    result = []
    i = 0
    in_string = False
    
    while i < len(line):
        c = line[i]
        
        if c == '"':
            in_string = not in_string
            result.append(c)
            i += 1
            continue
        
        if in_string:
            result.append(c)
            i += 1
            continue
        
        # After line number + label, remove space before first statement
        # This is handled by the merge logic, but also catch standalone:
        # e.g., '1100q I.B=0' -> '1100qI.B=0'
        
        # Remove space after abbreviated commands ending in '.'
        # Pattern: letter(s) + '.' + space -> letter(s) + '.'
        # But only for known commands
        if (c == ' ' and i > 0 and line[i-1] == '.' and i >= 2):
            # Check if this is after an abbreviated command
            # Look back to find the command
            j = i - 2
            while j >= 0 and line[j].isalpha():
                j -= 1
            cmd = line[j+1:i-1]  # the letters before the dot
            if cmd in ('I', 'G', 'GOS', 'F', 'P', 'N', 'R', 'T', 'S', 'U', 'E'):
                # Skip the space
                i += 1
                continue
        
        result.append(c)
        i += 1
    
    return ''.join(result)


def remove_label_space(line):
    """Remove space or semicolon between label and first statement.
    
    '1100q I.B=0 R.' -> '1100qI.B=0 R.'
    '2200l;P=P*8'    -> '2200lP=P*8'
    """
    m = re.match(r'^(\d+[a-z])[ ;](.*)', line)
    if m:
        return m.group(1) + m.group(2)
    return line


def optimize(text):
    """Apply all optimizations to the input text."""
    # Split into lines
    lines = text.rstrip('\n').split('\n')
    
    # Step 1: Strip cpp warnings (lines not starting with a digit)
    lines = [l for l in lines if re.match(r'^\d', l)]
    
    # Find jump targets before any modifications
    targets = find_jump_targets(lines)
    
    # Step 2: Per-line optimizations
    optimized = []
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        
        # Remove trailing semicolons
        line = remove_trailing_semicolons(line)
        
        # Remove space after label
        line = remove_label_space(line)
        
        # Remove unnecessary spaces
        line = remove_unnecessary_spaces(line)
        
        # Skip empty lines (just a line number)
        num, label, body = parse_line(line)
        if num and not label and not body.strip():
            continue
        
        optimized.append(line)
    
    # Step 3: Merge consecutive lines
    merged = []
    for line in optimized:
        num, label, body = parse_line(line)
        if num is None or body is None:
            merged.append(line)
            continue
        
        if not merged:
            merged.append(line)
            continue
        
        # Don't merge if this line is a jump target
        if num in targets:
            merged.append(line)
            continue
        
        # Don't merge if this line has a label (it's a GOSUB target)
        if label:
            merged.append(line)
            continue
        
        # Don't merge into previous line if it contains any IF
        if contains_if(merged[-1]):
            merged.append(line)
            continue
        
        # Try to merge: previous line + ';' + this line's body
        prev = merged[-1]
        prev_num, prev_label, prev_body = parse_line(prev)
        if prev_label and not prev_body:
            # Label-only line: no semicolon needed
            append_text = body.lstrip()
        else:
            append_text = ';' + body.lstrip()
        
        if len(prev) + len(append_text) <= MAX_LINE:
            merged[-1] = prev + append_text
        else:
            merged.append(line)
    
    return '\n'.join(merged) + '\n'


def main():
    text = sys.stdin.read()
    result = optimize(text)
    sys.stdout.write(result)
    print(f"Optimized: {len(text)} -> {len(result)} bytes "
          f"(saved {len(text) - len(result)})", file=sys.stderr)


if __name__ == '__main__':
    main()
