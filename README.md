# Firestore Session for Google ADK

A specialized implementation of the `BaseSessionService` that uses Google Cloud Firestore for persisting application sessions, user states, and event logs.

## Overview

This package provides the `FirestoreSessionService` class, which handles the lifecycle of sessions within the Google ADK (Agent Development Kit) framework. It organizes data in a hierarchical Firestore structure:

- `apps/{app_name}`: Global application state.
- `apps/{app_name}/users/{user_id}`: Persistent user-specific state.
- `apps/{app_name}/users/{user_id}/sessions/{session_id}`: Individual session data and state.
- `apps/{app_name}/users/{user_id}/sessions/{session_id}/events/{event_id}`: Historical event logs for the session.

## Installation

Since this is a private repository, you can include it in your project's dependencies using the Git URL.

### Using `pip`
```bash
pip install git+https://github.com/mohammadshamma/firestore-session.git
```

### Using `uv` (pyproject.toml)
```toml
dependencies = [
    "wisal-firestore-session @ git+https://github.com/mohammadshamma/firestore-session.git"
]
```

## Usage

To use the service, initialize it with a Firestore `AsyncClient`.

```python
from google.cloud import firestore
from firestore_session import FirestoreSessionService

# Initialize the Firestore client
client = firestore.AsyncClient()

# Create the session service
session_service = FirestoreSessionService(client=client)

# Create a new session
session = await session_service.create_session(
    app_name="my-app",
    user_id="user-123",
    metadata={"source": "telegram"}
)

print(f"Created session: {session.id}")
```

## Dependencies

- `google-adk`: Core agent framework.
- `google-cloud-firestore`: Official Firestore client.
- `google-cloud-storage`: Used for extended state persistence.

## Development

### Running Tests
Tests use `pytest`. Ensure you have a Firestore emulator or a project configured for testing.

```bash
pytest tests/
```
