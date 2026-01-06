#!/usr/bin/env python3
"""Quick test to validate parser fixes"""

import sys
sys.path.insert(0, '.')

from core.parser import Parser

parser = Parser()

# Test cases: raw responses from server (with prefixes) and expected parsing
test_cases = [
    # (raw_response, expected_code, expected_type)
    ("227 Entering Passive Mode (172,25,0,12,156,189)", "227", "success"),
    ("> 227 Entering Passive Mode (172,25,0,12,156,189)", "227", "success"),  # With prefix (should be cleaned in connection layer)
    ("200 OK", "200", "success"),
    ("500 Syntax error", "500", "error"),
    ("150 Opening data connection", "150", "preliminary"),
    ("331 Password required", "331", "missing_info"),
    ("425 Can't open data connection", "425", "error"),
]

print("Testing Parser.parse_data()...")
print()

all_passed = True
for raw, expected_code, expected_type in test_cases:
    # Simulate what connection.receive_response() returns (cleaned)
    # Remove prefix if present
    cleaned = raw
    while cleaned.startswith('>') or cleaned.startswith('*'):
        cleaned = cleaned[1:].strip()
    
    result = parser.parse_data(cleaned)
    
    passed = result.code == expected_code and result.type == expected_type
    status = "✓" if passed else "✗"
    
    print(f"{status} Input: '{raw}'")
    print(f"   Cleaned: '{cleaned}'")
    print(f"   Got: code={result.code}, type={result.type}")
    print(f"   Expected: code={expected_code}, type={expected_type}")
    
    if not passed:
        all_passed = False
    print()

if all_passed:
    print("✓ All tests passed!")
    sys.exit(0)
else:
    print("✗ Some tests failed")
    sys.exit(1)
