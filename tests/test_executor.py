from jarvis_antigravity_agent.executor import _deduplicate_final, _describe_tool


class TestDescribeTool:
    def test_run_command_formats_correctly(self):
        result = _describe_tool("run_command", {"CommandLine": "ls -la"})
        assert "ls -la" in result
        assert result.startswith("+")

    def test_run_command_truncates_at_65_chars(self):
        long_cmd = "echo " + "x" * 100
        result = _describe_tool("run_command", {"CommandLine": long_cmd})
        assert len(result) < 100

    def test_run_command_uses_first_line_only(self):
        result = _describe_tool(
            "run_command", {"CommandLine": "first line\nsecond line"}
        )
        assert "second line" not in result
        assert "first line" in result

    def test_write_to_file_shows_basename(self):
        result = _describe_tool("write_to_file", {"TargetFile": "/some/path/myfile.py"})
        assert "myfile.py" in result
        assert "/some/path" not in result

    def test_replace_file_content_shows_basename(self):
        result = _describe_tool(
            "replace_file_content", {"TargetFile": "/deep/dir/config.toml"}
        )
        assert "config.toml" in result

    def test_view_file_shows_basename(self):
        result = _describe_tool("view_file", {"AbsolutePath": "/home/user/main.py"})
        assert "main.py" in result

    def test_grep_search_includes_query(self):
        result = _describe_tool("grep_search", {"Query": "def my_function"})
        assert "def my_function" in result

    def test_grep_search_truncates_at_45_chars(self):
        result = _describe_tool("grep_search", {"Query": "q" * 100})
        assert len(result) < 100

    def test_search_web_includes_query(self):
        result = _describe_tool("search_web", {"query": "python asyncio"})
        assert "python asyncio" in result

    def test_invoke_subagent_label(self):
        result = _describe_tool("invoke_subagent", {})
        assert "subagent" in result.lower()

    def test_unknown_tool_returns_generic_label(self):
        result = _describe_tool("some_unknown_tool", {})
        assert "some_unknown_tool" in result

    def test_missing_params_use_defaults(self):
        result = _describe_tool("run_command", {})
        assert isinstance(result, str)

    def test_returns_string_for_all_known_tools(self):
        known_tools = [
            ("run_command", {"CommandLine": "pwd"}),
            ("write_to_file", {"TargetFile": "x.py"}),
            ("replace_file_content", {"TargetFile": "y.py"}),
            ("view_file", {"AbsolutePath": "z.py"}),
            ("grep_search", {"Query": "foo"}),
            ("search_web", {"query": "bar"}),
            ("invoke_subagent", {}),
        ]
        for name, params in known_tools:
            assert isinstance(_describe_tool(name, params), str)


class TestDeduplicateFinal:
    def test_no_dispatched_texts_returns_unchanged(self):
        result = _deduplicate_final("Final answer.", [])
        assert result == "Final answer."

    def test_removes_prefix_that_was_dispatched(self):
        dispatched = ["Here is what I found:"]
        final = "Here is what I found:\n\nAnd here is more."
        result = _deduplicate_final(final, dispatched)
        assert not result.startswith("Here is what I found:")

    def test_leaves_text_when_no_overlap(self):
        dispatched = ["Something completely different."]
        final = "The actual final answer."
        result = _deduplicate_final(final, dispatched)
        assert "actual final answer" in result

    def test_strips_whitespace_from_result(self):
        result = _deduplicate_final("  answer  ", [])
        assert result == "answer"

    def test_empty_dispatched_entry_skipped(self):
        result = _deduplicate_final("hello", ["", "  "])
        assert result == "hello"

    def test_empty_final_returns_empty(self):
        result = _deduplicate_final("", ["something"])
        assert result == ""
