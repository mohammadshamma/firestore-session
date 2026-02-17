# Firestore Session for Google ADK

A specialized implementation of the `BaseSessionService` that uses Google Cloud Firestore for persisting application sessions, user states, and event logs.

## Overview

This package provides the `FirestoreSessionService` class, which handles the lifecycle of sessions within the Google ADK (Agent Development Kit) framework. It organizes data in a hierarchical Firestore structure:

- `apps/{app_name}`: Global application state.
- `apps/{app_name}/users/{user_id}`: Persistent user-specific state.
- `apps/{app_name}/users/{user_id}/sessions/{session_id}`: Individual session data and state.
- `apps/{app_name}/users/{user_id}/sessions/{session_id}/events/{event_id}`: Historical event logs for the session.

## Installation

You can include this package in your project's dependencies using the Git URL.

### Using `pip`
```bash
pip install git+https://github.com/mohammadshamma/firestore-session.git
```

### Using `uv` (pyproject.toml)
```toml
dependencies = [
    "firestore-session @ git+https://github.com/mohammadshamma/firestore-session.git"
]
```

## Usage with Google ADK

To use the `FirestoreSessionService` with Google ADK, you must register it with the ADK `ServiceRegistry` before creating your application. This allows ADK to instantiate and use the Firestore service based on a URI.

### 1. Register the Service

In your main serving file (e.g., `serving.py`), register a factory function for the Firestore session service:

```python
from google.adk.cli.service_registry import get_service_registry
from firestore_session import FirestoreSessionService

# Define a factory function that returns the service instance
def firestore_session_factory(uri: str, **kwargs):
    # You can initialize the Firestore client here or use default credentials
    return FirestoreSessionService()

# Register it under a specific scheme (e.g., "firestore")
get_service_registry().register_session_service("firestore", firestore_session_factory)
```

### 2. Configure the ADK App

When initializing your FastAPI application using ADK, specify the URI scheme you registered:

```python
from google.adk.cli.fast_api import get_fast_api_app

app = get_fast_api_app(
    agents_dir="path/to/agents",
    session_service_uri="firestore://default", # Uses the registered "firestore" service
    web=True
)
```

## Standalone Usage

You can also use the service directly without the full ADK registry:

```python
from google.cloud import firestore
from firestore_session import FirestoreSessionService

# Initialize with an existing client
client = firestore.AsyncClient()
session_service = FirestoreSessionService(client=client)

# Create a new session
session = await session_service.create_session(
    app_name="my-app",
    user_id="user-123",
    metadata={"source": "telegram"}
)
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
