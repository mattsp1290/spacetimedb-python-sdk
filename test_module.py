"""Simple test module for SpacetimeDB v1.1.2"""

from spacetimedb import spacetimedb

@spacetimedb(table_name="test_table")
class TestTable:
    id: int
    name: str

@spacetimedb(reducer=True)
def add_test(name: str):
    TestTable.insert(TestTable(id=1, name=name))
