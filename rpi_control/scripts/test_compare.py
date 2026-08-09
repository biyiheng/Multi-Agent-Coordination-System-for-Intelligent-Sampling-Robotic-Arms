"""Test the bytes comparison bug in read_response"""
# Simulate what read_response does
byte = b'!'
terminator_byte = "!".encode("ascii")[0]  # This is an integer 33

print(f"byte = {byte!r}, type = {type(byte)}")
print(f"terminator_byte = {terminator_byte!r}, type = {type(terminator_byte)}")
print(f"byte == terminator_byte: {byte == terminator_byte}")
print(f"byte[0] == terminator_byte: {byte[0] == terminator_byte}")
print(f"byte == b'!': {byte == b'!'}")

# This is the bug: serial.read(1) returns bytes, comparing with int is always False
print("\nCONCLUSION: byte == terminator_byte (int) is ALWAYS False in Python 3!")
print("This means the '!' terminator is NEVER detected!")