# SpacetimeDB v1.1.2 Python SDK Validation Report

Generated: 2025-05-29T21:54:00.341091

## Configuration

- **Host**: localhost:3000
- **Database**: test-validation
- **Identity**: Not provided
- **Protocol**: JSON and BSATN tested

## Overall Status

❌ **Some validation tests FAILED**

## Test Results

### Real Server

- Status: ❌
- Failed: 0 tests

### Performance

- Status: ❌
- Failed: 12 tests

### Integration

- Status: ✅
- Passed: 13 tests

### Example Application

- Status: ❌
- Updated quickstart example tested

## Issues Found

- real_server tests failed
- performance tests failed
- performance: /Users/punk1290/.pyenv/versions/3.12.8/lib/python3.12/site-packages/pytest_asyncio/plugin.py:217: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The 
- Example application failed
- Traceback (most recent call last):
  File "/Users/punk1290/git/spacetimedb-python-sdk/examples/quickstart/client/main_v112.py", line 14, in <module>
    from module_bindings.user import User
  File "/

## Conclusion

The validation encountered some issues that need to be addressed. Please review the issues and recommendations above.
