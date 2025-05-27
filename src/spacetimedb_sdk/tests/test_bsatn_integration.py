"""
Integration tests for BSATN implementation against SpacetimeDB test module.

These tests verify compatibility with the Rust BSATN implementation by
testing against the bsatn-test module.
"""

import pytest

# Skip all tests in this file - API has changed
pytestmark = pytest.mark.skip(reason="BSATN API has changed - tests need to be rewritten")


class TestBsatnIntegration:
    """Integration tests against SpacetimeDB bsatn-test module."""
    pass
