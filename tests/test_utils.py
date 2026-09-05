from jarvis_antigravity_agent.utils import split_message


class TestSplitMessage:
    def test_short_message_returned_as_single_chunk(self):
        result = split_message("Hello, world!")
        assert result == ["Hello, world!"]

    def test_empty_string_returned_as_single_chunk(self):
        result = split_message("")
        assert result == [""]

    def test_exact_max_length_is_not_split(self):
        text = "a" * 4000
        result = split_message(text)
        assert len(result) == 1
        assert result[0] == text

    def test_text_longer_than_max_is_split(self):
        text = "a" * 4001
        result = split_message(text)
        assert len(result) > 1

    def test_all_chunks_within_max_length(self):
        text = "\n".join(["word " * 50] * 100)
        result = split_message(text)
        for chunk in result:
            assert len(chunk) <= 4000

    def test_full_text_is_preserved_across_chunks(self):
        lines = [f"Line {i}: " + "x" * 80 for i in range(200)]
        text = "\n".join(lines)
        result = split_message(text)
        reassembled = "\n".join(result)
        assert reassembled == text

    def test_single_line_longer_than_max_is_split_at_boundary(self):
        text = "z" * 9000
        result = split_message(text)
        assert all(len(chunk) <= 4000 for chunk in result)
        assert "".join(result) == text

    def test_custom_max_length_is_respected(self):
        text = "a" * 50
        result = split_message(text, max_length=20)
        assert all(len(chunk) <= 20 for chunk in result)
        assert "".join(result) == text

    def test_multiline_text_split_preserves_line_integrity(self):
        lines = ["short line"] * 5
        text = "\n".join(lines)
        result = split_message(text, max_length=30)
        for chunk in result:
            assert len(chunk) <= 30
