"""
Updated SpacetimeDB Python SDK Quickstart Client for v1.1.2
Demonstrates proper usage with database identity parameter
"""

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
from multiprocessing import Queue
import threading
import os

from spacetimedb_sdk.spacetimedb_async_client import SpacetimeDBAsyncClient
import spacetimedb_sdk.local_config as local_config

import module_bindings
from module_bindings.user import User
from module_bindings.message import Message
import module_bindings.send_message_reducer as send_message_reducer
import module_bindings.set_name_reducer as set_name_reducer

# Configuration for v1.1.2
SPACETIMEDB_HOST = os.environ.get("SPACETIMEDB_HOST", "localhost:3000")
DATABASE_NAME = os.environ.get("SPACETIMEDB_DB", "chat")
DATABASE_IDENTITY = os.environ.get("SPACETIMEDB_IDENTITY", None)
PROTOCOL = os.environ.get("SPACETIMEDB_PROTOCOL", "v1.json.spacetimedb")

input_queue = Queue()
local_identity = None
saved_db_identity = None


def run_client(spacetime_client):
    """Run the async client with v1.1.2 compatible connection"""
    # Note: The async client uses the synchronous client internally
    # The db_identity parameter needs to be set on the underlying client
    if DATABASE_IDENTITY or local_config.get_string("db_identity"):
        # Set db_identity on the underlying sync client if available
        db_id = DATABASE_IDENTITY or local_config.get_string("db_identity")
        # This is a workaround - ideally async client should handle this
        spacetime_client.client._db_identity = db_id
    
    asyncio.run(
        spacetime_client.run(
            auth_token=local_config.get_string("auth_token"),
            host=SPACETIMEDB_HOST,
            address_or_name=DATABASE_NAME,
            ssl_enabled=False,
            on_connect=on_connect,
            subscription_queries=["SELECT * FROM User", "SELECT * FROM Message"]
        )
    )


def input_loop():
    global input_queue

    print("\nSpacetimeDB Chat Client (v1.1.2)")
    print("Commands:")
    print("  /name <new_name> - Change your name")
    print("  /quit - Exit the chat")
    print("  <message> - Send a message")
    print("")

    while True:
        user_input = input()
        if user_input == "/quit" or len(user_input) == 0:
            return
        elif user_input.startswith("/name "):
            input_queue.put(("name", user_input[6:]))
        else:
            input_queue.put(("message", user_input))


def on_connect(auth_token, identity, db_identity=None):
    """Handle connection and save identity for reconnection"""
    global local_identity, saved_db_identity
    local_identity = identity
    saved_db_identity = db_identity

    # Save for future connections
    local_config.set_string("auth_token", auth_token)
    if db_identity:
        local_config.set_string("db_identity", db_identity)
        print(f"SYSTEM: Connected with database identity: {db_identity}")
    else:
        print(f"SYSTEM: Connected (legacy mode - no db_identity)")


def check_commands():
    global input_queue

    if not input_queue.empty():
        choice = input_queue.get()
        if choice[0] == "name":
            set_name_reducer.set_name(choice[1])
        else:
            send_message_reducer.send_message(choice[1])

    spacetime_client.schedule_event(0.1, check_commands)


def print_messages_in_order():
    all_messages = sorted(Message.iter(), key=lambda x: x.sent)
    for entry in all_messages:
        print(
            f"{user_name_or_identity(User.filter_by_identity(entry.sender))}: {entry.text}"
        )


def on_subscription_applied():
    print(f"\nSYSTEM: Connected to {SPACETIMEDB_HOST}")
    print(f"SYSTEM: Database: {DATABASE_NAME}")
    print(f"SYSTEM: Protocol: {PROTOCOL}")
    if saved_db_identity:
        print(f"SYSTEM: Using saved database identity")
    print_messages_in_order()


def on_send_message_reducer(sender_id, sender_address, status, message, msg):
    if sender_id == local_identity:
        if status == "failed":
            print(f"Failed to send message: {message}")


def on_set_name_reducer(sender_id, sender_address, status, message, name):
    if sender_id == local_identity:
        if status == "failed":
            print(f"Failed to set name: {message}")


def on_message_row_update(row_op, message_old, message, reducer_event):
    if reducer_event is not None and row_op == "insert":
        print_message(message)


def print_message(message):
    user = User.filter_by_identity(message.sender)
    user_name = "unknown"
    if user is not None:
        user_name = user_name_or_identity(user)

    print(f"{user_name}: {message.text}")


def user_name_or_identity(user):
    if user.name:
        return user.name
    else:
        return (str(user.identity))[:8]


def on_user_row_update(row_op, user_old, user, reducer_event):
    if row_op == "insert":
        if user.online:
            print(f"User {user_name_or_identity(user)} connected.")
    elif row_op == "update":
        if user_old.online and not user.online:
            print(f"User {user_name_or_identity(user)} disconnected.")
        elif not user_old.online and user.online:
            print(f"User {user_name_or_identity(user)} connected.")

        if user_old.name != user.name:
            print(
                f"User {user_name_or_identity(user_old)} renamed to {user_name_or_identity(user)}."
            )


def register_callbacks(spacetime_client):
    spacetime_client.register_on_subscription_applied(on_subscription_applied)

    User.register_row_update(on_user_row_update)
    Message.register_row_update(on_message_row_update)

    set_name_reducer.register_on_set_name(on_set_name_reducer)
    send_message_reducer.register_on_send_message(on_send_message_reducer)

    spacetime_client.schedule_event(0.1, check_commands)


def main():
    """Main entry point with v1.1.2 setup"""
    global spacetime_client
    
    local_config.init(".spacetimedb-python-quickstart")

    # Check if we need database identity
    if not DATABASE_IDENTITY and not local_config.get_string("db_identity"):
        print("\n" + "="*60)
        print("SpacetimeDB v1.1.2 Setup Required")
        print("="*60)
        print("For v1.1.2 compatibility, you need to provide a database identity.")
        print("\nOptions:")
        print("1. Set SPACETIMEDB_IDENTITY environment variable")
        print("2. Run the chat server and copy the identity from the output")
        print("3. For testing, the SDK will try to use the database name as identity")
        print("="*60)
        print(f"\nAttempting to connect to: {SPACETIMEDB_HOST}/{DATABASE_NAME}")
        print("If this fails, please provide the database identity.")
        print("")

    # Create client with protocol selection
    # Note: Protocol must be set on the underlying sync client
    spacetime_client = SpacetimeDBAsyncClient(module_bindings)
    spacetime_client.client.protocol = PROTOCOL

    register_callbacks(spacetime_client)

    # Run client in thread
    thread = threading.Thread(target=run_client, args=(spacetime_client,))
    thread.start()

    try:
        input_loop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        spacetime_client.force_close()
        thread.join()
        print("Goodbye!")


if __name__ == "__main__":
    main()
