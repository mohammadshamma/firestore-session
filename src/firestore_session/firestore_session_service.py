# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any, Optional, AsyncGenerator
import uuid
import time
import copy
from google.cloud import firestore
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.sessions.base_session_service import GetSessionConfig
from google.adk.sessions.base_session_service import ListSessionsResponse
from google.adk.sessions.session import Session
from google.adk.events.event import Event
from google.adk.sessions.state import State

class FirestoreSessionService(BaseSessionService):
    """
    A Firestore-based implementation of the SessionService.
    
    Persists sessions, events, and state to Google Cloud Firestore.
    structure:
    apps/{app_name} (App State)
    apps/{app_name}/users/{user_id} (User State)
    apps/{app_name}/users/{user_id}/sessions/{session_id} (Session Data + Session State)
    apps/{app_name}/users/{user_id}/sessions/{session_id}/events/{event_id} (Events)
    """

    def __init__(self, client: Optional[firestore.AsyncClient] = None):
        """
        Args:
            client: Optional Firestore AsyncClient. If not provided, one will be created.
        """
        self._client = client or firestore.AsyncClient()

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = (
            session_id.strip() if session_id and session_id.strip() else str(uuid.uuid4())
        )
        
        session_ref = self._client.collection("apps").document(app_name)\
            .collection("users").document(user_id)\
            .collection("sessions").document(session_id)

        current_time = time.time()
        initial_session_state = state or {}
        
        # We don't store events in the session document, they go to a subcollection
        session_data = {
            "id": session_id,
            "app_name": app_name,
            "user_id": user_id,
            "state": initial_session_state,
            "last_update_time": current_time,
            # We don't persist 'events' list in the document, it's reconstructed
        }

        # Create the session document
        await session_ref.set(session_data)

        # Create the local Session object to return
        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=initial_session_state,
            last_update_time=current_time,
            events=[]
        )

        return await self._merge_state(app_name, user_id, session)

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        session_ref = self._client.collection("apps").document(app_name)\
            .collection("users").document(user_id)\
            .collection("sessions").document(session_id)

        doc_snapshot = await session_ref.get()
        if not doc_snapshot.exists:
            return None

        session_data = doc_snapshot.to_dict()
        # Events are not stored in the main doc
        session_data["events"] = [] 
        
        # Reconstruct base Session object
        try:
            # We explicitly handle 'events' being empty list here
            session = Session.model_validate(session_data)
        except Exception as e:
            # Fallback if validation fails (e.g. data structure evolution)
            # Log error? 
            # For now, minimal reconstruction
            session = Session(
                id=session_data.get("id"),
                app_name=session_data.get("app_name"),
                user_id=session_data.get("user_id"),
                state=session_data.get("state", {}),
                last_update_time=session_data.get("last_update_time", 0.0),
                events=[]
            )

        # Fetch events
        events_ref = session_ref.collection("events")
        query = events_ref.order_by("timestamp")

        if config:
            if config.after_timestamp:
                query = query.where(filter=firestore.FieldFilter("timestamp", ">", config.after_timestamp))
            # limit needs to be applied at the end ideally, checking if we need to reverse order to get "recent"
            if config.num_recent_events:
                 # If we want RECENT events, we might want to order by timestamp DESC, limit, then reverse back
                 # But ADK interface usually implies chronological order
                 # If we use orderBy timestamp ASC (default), limit will get the OLDEST events
                 # So we need to sort DESC, limit, then sort ASC
                 query = events_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(config.num_recent_events)
        
        # Execute query
        # Note: If we used DESCENDING optimization above, we receive them in reverse order
        events_snapshots = await query.get()
        
        loaded_events = []
        for snap in events_snapshots:
            event_data = snap.to_dict()
            try:
                event = Event.model_validate(event_data)
                loaded_events.append(event)
            except Exception:
                continue

        if config and config.num_recent_events:
             # If we queried with DESCENDING, we need to reverse to get back to chronological
            loaded_events.sort(key=lambda e: e.timestamp)

        session.events = loaded_events
        
        return await self._merge_state(app_name, user_id, session)

    async def list_sessions(
        self, *, app_name: str, user_id: str
    ) -> ListSessionsResponse:
        sessions_ref = self._client.collection("apps").document(app_name)\
            .collection("users").document(user_id)\
            .collection("sessions")
        
        # Simple list, maybe order by last_update_time desc?
        # The interface doesn't specify order, but users usually want recent
        query = sessions_ref.order_by("last_update_time", direction=firestore.Query.DESCENDING)
        
        snapshots = await query.get()
        sessions_list = []
        
        for snap in snapshots:
            data = snap.to_dict()
            data["events"] = [] # Don't load events for listing
            try:
                session = Session.model_validate(data)
                # Merge state? Interface doc says "The events and states are not set within each Session object."
                # But Base implementation implementation does merge app/user state?
                # The docstring in BaseSessionService says:
                # "The events and states are not set within each Session object."
                # But InMemorySessionService.list_sessions DOES merge state but copies session and sets events to empty.
                # Let's match InMemorySessionService behavior: merge state.
                merged_session = await self._merge_state(app_name, user_id, session)
                sessions_list.append(merged_session)
            except Exception:
                continue
                
        return ListSessionsResponse(sessions=sessions_list)

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        # Delete session document
        session_ref = self._client.collection("apps").document(app_name)\
            .collection("users").document(user_id)\
            .collection("sessions").document(session_id)
            
        # Delete subcollection 'events'
        # Firestore does not automatically delete subcollections. 
        # We need to manually delete documents in 'events'.
        # For efficiency, we can batch delete.
        events_ref = session_ref.collection("events")
        await self._delete_collection(events_ref, batch_size=50)
        
        # Delete the session doc itself
        await session_ref.delete()

    async def append_event(self, session: Session, event: Event) -> Event:
        # 1. Append event to in-memory session object (super behavior)
        if event.partial:
            return event

        # We manually update session state locally first as super().append_event does
        self._update_session_state_local(session, event)
        session.events.append(event)
        session.last_update_time = event.timestamp

        # 2. Persist to Firestore
        batch = self._client.batch()
        
        app_name = session.app_name
        user_id = session.user_id
        session_id = session.id
        
        # Refs
        app_ref = self._client.collection("apps").document(app_name)
        user_ref = app_ref.collection("users").document(user_id)
        session_ref = user_ref.collection("sessions").document(session_id)
        event_ref = session_ref.collection("events").document(event.id) # Use event.id as doc id

        # Prepare Event Write
        event_dict = event.model_dump(mode='json', exclude_none=True)
        batch.set(event_ref, event_dict)

        # Prepare State Updates
        # We separate state deltas into App, User, and Session scope
        if event.actions and event.actions.state_delta:
            for key, value in event.actions.state_delta.items():
                if key.startswith(State.TEMP_PREFIX):
                    continue
                
                if key.startswith(State.APP_PREFIX):
                    # App State
                    clean_key = key.removeprefix(State.APP_PREFIX)
                    batch.set(app_ref, {clean_key: value}, merge=True)
                elif key.startswith(State.USER_PREFIX):
                    # User State
                    clean_key = key.removeprefix(State.USER_PREFIX)
                    batch.set(user_ref, {clean_key: value}, merge=True)
                else:
                    # Session State
                    # Update session document 'state' field
                    # Firestore 'merge=True' works on top level. 
                    # To update nested 'state.key', we need dot notation
                    batch.update(session_ref, {f"state.{key}": value})

        # Also update last_update_time on session
        batch.update(session_ref, {"last_update_time": session.last_update_time})

        await batch.commit()
        return event

    async def _merge_state(self, app_name: str, user_id: str, session: Session) -> Session:
        """Helper to merge App and User state into the Session object."""
        # 1. Fetch App State
        app_ref = self._client.collection("apps").document(app_name)
        app_snap = await app_ref.get()
        if app_snap.exists:
            app_data = app_snap.to_dict()
            for k, v in app_data.items():
                session.state[State.APP_PREFIX + k] = v

        # 2. Fetch User State
        user_ref = app_ref.collection("users").document(user_id)
        user_snap = await user_ref.get()
        if user_snap.exists:
            user_data = user_snap.to_dict()
            for k, v in user_data.items():
                session.state[State.USER_PREFIX + k] = v
                
        return session

    async def _delete_collection(self, coll_ref, batch_size):
        """Recursively delete a collection."""
        # Note: This is a simplified deletion useful for small-ish collections (events in a session)
        docs = await coll_ref.limit(batch_size).get()
        deleted = 0

        for doc in docs:
            # We don't recursively check subcollections of events (events usually don't have them)
            await doc.reference.delete()
            deleted += 1

        if deleted >= batch_size:
            return await self._delete_collection(coll_ref, batch_size)

    def _update_session_state_local(self, session: Session, event: Event) -> None:
        """Updates the session state based on the event (logic from BaseSessionService)."""
        if not event.actions or not event.actions.state_delta:
            return
        for key, value in event.actions.state_delta.items():
            if key.startswith(State.TEMP_PREFIX):
                continue
            session.state.update({key: value})
