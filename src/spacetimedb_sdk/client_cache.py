import importlib
import pkgutil
from typing import Dict, Any, Optional, Type, TypeVar, ValuesView
from types import ModuleType

T = TypeVar('T')

def snake_to_camel(snake_case_string: str) -> str:
    """Convert snake_case to CamelCase."""
    return snake_case_string.replace("_", " ").title().replace(" ", "")


class TableCache:
    def __init__(self, table_class: Type[T]) -> None:
        self.entries: Dict[Any, T] = {}
        self.table_class = table_class

    def decode(self, value: Any) -> T:
        """Decode a raw value into a table entry."""
        return self.table_class(value)

    def set_entry(self, key: Any, value: Any) -> None:
        """Set an entry by decoding the raw value."""
        self.entries[key] = self.decode(value)

    def set_entry_decoded(self, key: Any, decoded_value: T) -> None:
        """Set an entry with an already decoded value."""
        self.entries[key] = decoded_value

    def delete_entry(self, key: Any) -> None:
        """Delete an entry by key."""
        if key in self.entries:
            del self.entries[key]
        else:
            print(f"[delete_entry] Error, key not found. ({key})")

    def get_entry(self, key: Any) -> Optional[T]:
        """Get an entry by key, returning None if not found."""
        if key in self.entries:
            return self.entries[key]
        return None

    def values(self) -> ValuesView[T]:
        """Get all cached values."""
        return self.entries.values()


class ClientCache:
    def __init__(self, autogen_package: ModuleType) -> None:
        self.tables: Dict[str, TableCache] = {}
        self.reducer_cache: Dict[str, Any] = {}

        for importer, module_name, is_package in pkgutil.iter_modules(
            autogen_package.__path__
        ):
            if not is_package:
                module = importlib.import_module(
                    f"{autogen_package.__name__}.{module_name}"
                )

                # check if its a reducer
                if module_name.endswith("_reducer"):
                    reducer_name = getattr(module, "reducer_name")
                    args_class = getattr(module, "_decode_args")
                    self.reducer_cache[reducer_name] = args_class
                else:
                    # Assuming table class name is the same as the module name
                    table_class_name = snake_to_camel(module_name)

                    if hasattr(module, table_class_name):
                        table_class = getattr(module, table_class_name)

                        # Check for a special property, e.g. 'is_table_class'
                        if getattr(table_class, "is_table_class", False):
                            self.tables[table_class_name] = TableCache(table_class)

    def get_table_cache(self, table_name):
        return self.tables[table_name]

    def decode(self, table_name, value):
        if not table_name in self.tables:
            print(f"[decode] Error, table not found. ({table_name})")
            return

        return self.tables[table_name].decode(value)

    def set_entry(self, table_name, key, value):
        if not table_name in self.tables:
            print(f"[set_entry] Error, table not found. ({table_name})")
            return

        self.tables[table_name].set_entry(key, value)

    def set_entry_decoded(self, table_name, key, value):
        if not table_name in self.tables:
            print(f"[set_entry_decoded] Error, table not found. ({table_name})")
            return

        self.tables[table_name].set_entry_decoded(key, value)

    def delete_entry(self, table_name, key):
        if not table_name in self.tables:
            print(f"[delete_entry] Error, table not found. ({table_name})")
            return

        self.tables[table_name].delete_entry(key)

    def get_entry(self, table_name, key):
        if not table_name in self.tables:
            print(f"[get_entry] Error, table not found. ({table_name})")
            return

        return self.tables[table_name].get_entry(key)
