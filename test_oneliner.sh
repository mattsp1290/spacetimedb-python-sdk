#!/bin/bash
# One-liner to test connection (from SDK directory)
python -c "import asyncio; from src.spacetimedb_sdk import SpacetimeDBClient; \
client = SpacetimeDBClient(protocol='v1.json.spacetimedb'); \
asyncio.run(client.connect('localhost:3000', 'blackholio', None, False)); \
print('Success!')"
