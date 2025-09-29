#!/usr/bin/env python3

import pytest

from json_schema_to_code.cli_utils import reconstruct_command_line


def get_click_command():
    """Helper to get Click command for testing"""
    try:
        from json_schema_to_code.json_schema_to_code import json_schema_to_code

        return json_schema_to_code
    except ImportError:
        return None


class TestCliUtils:
    """Test cases for CLI utilities"""

    def test_reconstruct_command_line_without_context(self):
        """Test command reconstruction without active Click context (fallback)"""
        click_cmd = get_click_command()
        if not click_cmd:
            pytest.skip("Click command not available")

        # Since there's no active Click context in tests, this should return fallback
        result = reconstruct_command_line(click_cmd)
        assert result == "json_schema_to_code"

    def test_reconstruct_command_line_function_exists(self):
        """Test that the function exists and is callable"""
        click_cmd = get_click_command()
        if not click_cmd:
            pytest.skip("Click command not available")

        # Should not raise an exception
        result = reconstruct_command_line(click_cmd)
        assert isinstance(result, str)
        assert "json_schema_to_code" in result


if __name__ == "__main__":
    pytest.main([__file__])
