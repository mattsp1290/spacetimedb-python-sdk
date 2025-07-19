# SpacetimeDB Server Issue Report

This folder contains documentation about a critical server issue discovered by the Python SDK team on May 31, 2025.

## Contents

1. **SPACETIMEDB_SERVER_UNRESPONSIVE_ISSUE.md**
   - Comprehensive technical report of the server unresponsive issue
   - Evidence from multiple test approaches
   - Root cause analysis
   - Impact assessment
   - Recommendations for immediate and long-term fixes

2. **fix-server-unresponsive-task.yaml**
   - Structured task definition for tracking the fix
   - Acceptance criteria
   - Step-by-step action items
   - Testing and verification requirements

## Quick Summary

**Issue**: SpacetimeDB server at `localhost:3000` is running but completely unresponsive to all HTTP and WebSocket requests.

**Impact**: Complete service outage - no clients can connect, blocking all development including ML agent teams.

**Root Cause**: Unknown - likely deadlock or blocked event loop in server code.

**Immediate Action**: Restart the server with debug logging enabled.

## For Platform Team

Please review the detailed report and follow the immediate actions in the task YAML to restore service. The Python SDK is verified to be working correctly - this is entirely a server-side issue.

## Test Scripts

Test scripts referenced in this report are located in the parent directory:
- `/Users/punk1290/git/spacetimedb-python-sdk/test_blackholio_connection.py`
- `/Users/punk1290/git/spacetimedb-python-sdk/test_websocket_raw.py`

---
Report prepared by: Python SDK Team  
Date: May 31, 2025
