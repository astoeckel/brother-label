from brother_label.reader import chunker, match_opcode


def test_match_opcode() -> None:
    opcode = match_opcode(b"\x1b\x69\x58\x47\x00\x23\x56")

    assert opcode == b"\x1b\x69\x58\x47"

def test_chunker() -> None:
    instructions = [
        b"\x00",
        b"\x1b\x69\x7A\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09",
        # TODO: the next opcode is likely not correctly constructed
        b"\x47\x02\x01" + b"\x00" * 256 + b"\x00\x00",
        b"\x67\x00\x03\xaa\xbb\xcc",
    ]

    chunks = list(chunker(b"".join(instructions)))

    assert instructions == chunks
