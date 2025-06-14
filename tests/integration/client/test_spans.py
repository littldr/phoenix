from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import random
from secrets import token_hex
from typing import cast

import pandas as pd
import pytest
from phoenix.client.__generated__ import v1
from typing_extensions import TypeAlias

from .._helpers import (
    _ADMIN,
    _MEMBER,
    _await_or_return,
    _GetUser,
    _RoleOrUser,
)

# Type aliases for better readability
SpanId: TypeAlias = str
SpanGlobalId: TypeAlias = str


class TestClientForSpanAnnotationsRetrieval:
    @pytest.mark.parametrize("is_async", [True, False])
    @pytest.mark.parametrize("role_or_user", [_MEMBER, _ADMIN])
    async def test_get_span_annotations_dataframe_and_list(
        self,
        is_async: bool,
        role_or_user: _RoleOrUser,
        _span_ids: tuple[tuple[SpanId, SpanGlobalId], tuple[SpanId, SpanGlobalId]],
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (span_id1, _), (span_id2, _) = _span_ids

        user = _get_user(role_or_user).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        annotation_name_1 = f"test_anno_{token_hex(4)}"
        annotation_name_2 = f"test_anno_{token_hex(4)}"

        score1 = random()
        score2 = random()
        label1 = token_hex(4)
        label2 = token_hex(4)
        explanation1 = token_hex(8)
        explanation2 = token_hex(8)

        await _await_or_return(
            Client().annotations.add_span_annotation(
                annotation_name=annotation_name_1,
                span_id=span_id1,
                annotator_kind="LLM",
                label=label1,
                score=score1,
                explanation=explanation1,
                sync=True,
            )
        )

        await _await_or_return(
            Client().annotations.add_span_annotation(
                annotation_name=annotation_name_2,
                span_id=span_id2,
                annotator_kind="CODE",
                label=label2,
                score=score2,
                explanation=explanation2,
                sync=True,
            )
        )

        df = await _await_or_return(
            Client().spans.get_span_annotations_dataframe(
                span_ids=[span_id1, span_id2],
                project_identifier="default",
            )
        )

        assert isinstance(df, pd.DataFrame)
        assert {
            span_id1,
            span_id2,
        }.issubset(set(df.index.astype(str))), "Expected span IDs missing from dataframe"  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]

        annotations = await _await_or_return(
            Client().spans.get_span_annotations(
                span_ids=[span_id1, span_id1, span_id2],  # include duplicate on purpose
                project_identifier="default",
            )
        )

        assert isinstance(annotations, list)
        assert all(isinstance(a, dict) for a in annotations)

        by_key: dict[tuple[str, str], v1.SpanAnnotation] = {
            (a["span_id"], a["name"]): a for a in annotations
        }

        key1, key2 = (span_id1, annotation_name_1), (span_id2, annotation_name_2)
        assert key1 in by_key, "Annotation for span 1 missing from list response"
        assert key2 in by_key, "Annotation for span 2 missing from list response"

        anno1, anno2 = by_key[key1], by_key[key2]
        for anno, expected_label, expected_score, expected_explanation in (
            (anno1, label1, score1, explanation1),
            (anno2, label2, score2, explanation2),
        ):
            assert "result" in anno, "Expected 'result' key in span annotation response"
            res = anno["result"]
            assert isinstance(res, dict)
            assert res.get("label") == expected_label
            assert abs(float(res.get("score", 0.0)) - expected_score) < 1e-6
            assert res.get("explanation") == expected_explanation

        spans_input_df = pd.DataFrame({"context.span_id": [span_id1, span_id2]})
        df_from_df = await _await_or_return(
            Client().spans.get_span_annotations_dataframe(
                spans_dataframe=spans_input_df,
                project_identifier="default",
            )
        )

        assert isinstance(df_from_df, pd.DataFrame)
        for sid, aname, label, scr, expl in (
            (span_id1, annotation_name_1, label1, score1, explanation1),
            (span_id2, annotation_name_2, label2, score2, explanation2),
        ):
            subset = df_from_df[df_from_df.index.astype(str) == sid]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
            subset = subset[subset["annotation_name"] == aname]  # pyright: ignore[reportUnknownVariableType]
            assert not subset.empty  # pyright: ignore[reportUnknownMemberType]
            row = subset.iloc[0]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
            assert "result.label" in row
            assert row["result.label"] == label
            assert abs(float(row["result.score"]) - scr) < 1e-6  # pyright: ignore[reportUnknownArgumentType]
            assert row["result.explanation"] == expl

    @pytest.mark.parametrize("is_async", [True, False])
    @pytest.mark.parametrize("role_or_user", [_MEMBER, _ADMIN])
    async def test_note_annotations_filtering_behavior(
        self,
        is_async: bool,
        role_or_user: _RoleOrUser,
        _span_ids: tuple[tuple[SpanId, SpanGlobalId], tuple[SpanId, SpanGlobalId]],
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (span_id1, _), (span_id2, _) = _span_ids

        user = _get_user(role_or_user).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        regular_annotation_name = f"test_anno_{token_hex(4)}"

        score1 = random()
        label1 = token_hex(4)
        explanation1 = token_hex(8)

        await _await_or_return(
            Client().annotations.add_span_annotation(
                annotation_name=regular_annotation_name,
                span_id=span_id1,
                annotator_kind="LLM",
                label=label1,
                score=score1,
                explanation=explanation1,
                sync=True,
            )
        )

        df_default = await _await_or_return(
            Client().spans.get_span_annotations_dataframe(
                span_ids=[span_id1, span_id2],
                project_identifier="default",
            )
        )

        assert isinstance(df_default, pd.DataFrame)
        if not df_default.empty:
            annotation_names_default = set(df_default["annotation_name"].tolist())  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
            assert regular_annotation_name in annotation_names_default

        df_with_notes = await _await_or_return(
            Client().spans.get_span_annotations_dataframe(
                span_ids=[span_id1, span_id2],
                project_identifier="default",
                include_annotation_names=[regular_annotation_name, "note"],
            )
        )

        assert isinstance(df_with_notes, pd.DataFrame)
        if not df_with_notes.empty:
            annotation_names_with_notes = set(df_with_notes["annotation_name"].tolist())  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
            assert regular_annotation_name in annotation_names_with_notes

        df_excluded = await _await_or_return(
            Client().spans.get_span_annotations_dataframe(
                span_ids=[span_id1, span_id2],
                project_identifier="default",
                exclude_annotation_names=[regular_annotation_name],
            )
        )

        assert isinstance(df_excluded, pd.DataFrame)
        if not df_excluded.empty:
            annotation_names_excluded = set(df_excluded["annotation_name"].tolist())  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
            assert regular_annotation_name not in annotation_names_excluded

        annotations_default = await _await_or_return(
            Client().spans.get_span_annotations(
                span_ids=[span_id1, span_id2],
                project_identifier="default",
            )
        )

        assert isinstance(annotations_default, list)
        if annotations_default:
            default_names = {a["name"] for a in annotations_default}
            assert regular_annotation_name in default_names

        annotations_with_notes = await _await_or_return(
            Client().spans.get_span_annotations(
                span_ids=[span_id1, span_id2],
                project_identifier="default",
                include_annotation_names=[regular_annotation_name, "note"],
            )
        )

        assert isinstance(annotations_with_notes, list)
        if annotations_with_notes:
            with_notes_names = {a["name"] for a in annotations_with_notes}
            assert regular_annotation_name in with_notes_names

    def test_invalid_arguments_validation(self) -> None:
        """Supplying multiple or no parameters should error."""
        from phoenix.client import Client

        spans_client = Client().spans

        # Test get_span_annotations_dataframe
        with pytest.raises(ValueError):
            spans_client.get_span_annotations_dataframe(project_identifier="default")

        dummy_df = pd.DataFrame()

        with pytest.raises(ValueError):
            spans_client.get_span_annotations_dataframe(
                spans_dataframe=dummy_df,
                span_ids=["abc"],
                project_identifier="default",
            )

        # Create complete v1.Span objects for testing
        test_span_1 = cast(
            v1.Span,
            {
                "id": "test_1",
                "name": "test_span_no_id",
                "context": {"trace_id": "trace123", "span_id": "abc"},
                "span_kind": "INTERNAL",
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-01-01T00:01:00Z",
                "status_code": "OK",
            },
        )

        test_span_2 = cast(
            v1.Span,
            {
                "id": "test_2",
                "name": "valid_span",
                "context": {"trace_id": "trace456", "span_id": "def"},
                "span_kind": "INTERNAL",
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-01-01T00:01:00Z",
                "status_code": "OK",
            },
        )

        with pytest.raises(ValueError):
            spans_client.get_span_annotations_dataframe(
                spans_dataframe=dummy_df,
                spans=[test_span_1],
                project_identifier="default",
            )

        with pytest.raises(ValueError):
            spans_client.get_span_annotations_dataframe(
                span_ids=["abc"],
                spans=[test_span_2],
                project_identifier="default",
            )

        # Test get_span_annotations
        with pytest.raises(ValueError):
            spans_client.get_span_annotations(project_identifier="default")

        with pytest.raises(ValueError):
            spans_client.get_span_annotations(
                span_ids=["abc"],
                spans=[test_span_2],
                project_identifier="default",
            )

    @pytest.mark.parametrize("is_async", [True, False])
    @pytest.mark.parametrize("role_or_user", [_MEMBER, _ADMIN])
    async def test_get_span_annotations_with_spans_objects(
        self,
        is_async: bool,
        role_or_user: _RoleOrUser,
        _span_ids: tuple[tuple[SpanId, SpanGlobalId], tuple[SpanId, SpanGlobalId]],
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test getting span annotations using Span objects from get_spans."""
        (span_id1, _), (span_id2, _) = _span_ids

        user = _get_user(role_or_user).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        annotation_name_1 = f"test_spans_obj_{token_hex(4)}"
        annotation_name_2 = f"test_spans_obj_{token_hex(4)}"

        score1 = 0.8
        score2 = 0.6
        label1 = "positive"
        label2 = "negative"

        # Add annotations to specific spans
        await _await_or_return(
            Client().annotations.add_span_annotation(
                annotation_name=annotation_name_1,
                span_id=span_id1,
                annotator_kind="LLM",
                label=label1,
                score=score1,
                sync=True,
            )
        )

        await _await_or_return(
            Client().annotations.add_span_annotation(
                annotation_name=annotation_name_2,
                span_id=span_id2,
                annotator_kind="CODE",
                label=label2,
                score=score2,
                sync=True,
            )
        )

        # Get spans using the new get_spans method
        spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=50,
            )
        )

        # Filter to only the spans we're interested in
        target_spans = [s for s in spans if s["context"]["span_id"] in [span_id1, span_id2]]
        assert len(target_spans) >= 2, "Should find at least the two test spans"

        # Test get_span_annotations_dataframe with spans objects
        df = await _await_or_return(
            Client().spans.get_span_annotations_dataframe(
                spans=target_spans,
                project_identifier="default",
            )
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 2, "Should have annotations for both spans"

        # Test get_span_annotations with spans objects
        annotations = await _await_or_return(
            Client().spans.get_span_annotations(
                spans=target_spans,
                project_identifier="default",
            )
        )

        assert isinstance(annotations, list)
        assert len(annotations) >= 2, "Should have annotations for both spans"

        # Verify the annotations contain our test data
        by_span_name = {(a["span_id"], a["name"]): a for a in annotations}

        key1 = (span_id1, annotation_name_1)
        key2 = (span_id2, annotation_name_2)

        assert key1 in by_span_name, f"Annotation {key1} not found"
        assert key2 in by_span_name, f"Annotation {key2} not found"

        # Test with spans that have missing span_ids (should not cause errors)
        spans_with_missing_ids: list[v1.Span] = [
            cast(
                v1.Span,
                {
                    "id": "test_missing_1",
                    "name": "test_span_no_id",
                    "context": {"trace_id": "trace789", "span_id": ""},  # Empty span_id
                    "span_kind": "INTERNAL",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2023-01-01T00:01:00Z",
                    "status_code": "OK",
                },
            ),
            cast(
                v1.Span,
                {
                    "id": "test_valid_1",
                    "name": "valid_span",
                    "context": {"trace_id": "trace999", "span_id": span_id1},
                    "span_kind": "INTERNAL",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2023-01-01T00:01:00Z",
                    "status_code": "OK",
                },
            ),
        ]

        annotations_filtered = await _await_or_return(
            Client().spans.get_span_annotations(
                spans=spans_with_missing_ids,
                project_identifier="default",
            )
        )

        # Should only get annotations for the span with valid span_id
        span_ids_found = {a["span_id"] for a in annotations_filtered}
        assert span_id1 in span_ids_found
        assert len([a for a in annotations_filtered if a["span_id"] == span_id1]) >= 1


class TestClientForSpansRetrieval:
    """Test the get_spans method with various filtering and pagination options."""

    @pytest.mark.parametrize("is_async", [True, False])
    @pytest.mark.parametrize("role_or_user", [_MEMBER, _ADMIN])
    async def test_basic_span_retrieval(
        self,
        is_async: bool,
        role_or_user: _RoleOrUser,
        _span_ids: tuple[tuple[SpanId, SpanGlobalId], tuple[SpanId, SpanGlobalId]],
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test basic span retrieval returns ergonomic span format."""
        user = _get_user(role_or_user).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=10,
            )
        )

        assert isinstance(spans, list)
        # Should have at least the test spans
        assert len(spans) >= 2

        # Each span should be a dict with the expected structure
        for span in spans:
            assert isinstance(span, dict)
            # Check required fields exist according to v1.Span
            assert "id" in span
            assert "name" in span
            assert "context" in span
            assert "span_kind" in span
            assert "start_time" in span
            assert "end_time" in span
            assert "status_code" in span

            # Check context structure
            context = span["context"]
            assert isinstance(context, dict)
            assert "trace_id" in context
            assert "span_id" in context
            assert isinstance(context["trace_id"], str)
            assert isinstance(context["span_id"], str)

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_time_filtering(
        self,
        is_async: bool,
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that start_time and end_time filters work correctly."""
        user = _get_user(_MEMBER).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        # Get all spans first
        all_spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=50,
            )
        )

        if len(all_spans) < 2:
            pytest.skip("Not enough spans for time filtering test")

        # Parse timestamps and sort spans
        spans_with_time: list[tuple[v1.Span, datetime]] = []
        for span in all_spans:
            try:
                start_time = datetime.fromisoformat(span["start_time"].replace("Z", "+00:00"))
                spans_with_time.append((span, start_time))
            except (ValueError, KeyError):
                continue

        if len(spans_with_time) < 2:
            pytest.skip("Not enough spans with valid timestamps")

        sorted_spans: list[tuple[v1.Span, datetime]] = sorted(spans_with_time, key=lambda x: x[1])
        earliest_time: datetime = sorted_spans[0][1]
        latest_time: datetime = sorted_spans[-1][1]

        # Test with start_time filter
        spans_after = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                start_time=earliest_time + timedelta(microseconds=1),
                limit=50,
            )
        )

        # Should have fewer spans
        assert len(spans_after) < len(sorted_spans)

        # All returned spans should be after the start_time
        for span in spans_after:
            try:
                span_start_time = datetime.fromisoformat(span["start_time"].replace("Z", "+00:00"))
                assert span_start_time >= earliest_time
            except (ValueError, KeyError):
                continue

        # Test with end_time filter
        spans_before = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                end_time=latest_time,
                limit=50,
            )
        )

        # All returned spans should be before the end_time
        for span in spans_before:
            try:
                span_start_time = datetime.fromisoformat(span["start_time"].replace("Z", "+00:00"))
                assert span_start_time < latest_time
            except (ValueError, KeyError):
                continue

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_automatic_pagination(
        self,
        is_async: bool,
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the method automatically handles pagination to fetch up to the limit."""
        user = _get_user(_MEMBER).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        # The method uses page_size = min(100, limit), so test with limit > 100
        # to ensure pagination happens (if there are enough spans)
        limit = 150
        spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=limit,
            )
        )

        # We should get up to the limit, or all available spans
        assert len(spans) <= limit

        # Test with small limit
        small_limit = 5
        small_spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=small_limit,
            )
        )

        assert len(small_spans) <= small_limit

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_project_identifier_types(
        self,
        is_async: bool,
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that project identifier works with both project names and IDs."""
        user = _get_user(_ADMIN).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        # First get the project to find its ID
        projects = await _await_or_return(Client().projects.list())
        default_project = next((p for p in projects if p["name"] == "default"), None)

        if not default_project:
            pytest.skip("Default project not found")

        project_id = default_project["id"]

        # Get spans by project name
        spans_by_name = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=5,
            )
        )

        # Get spans by project ID
        spans_by_id = await _await_or_return(
            Client().spans.get_spans(
                project_identifier=project_id,
                limit=5,
            )
        )

        # Both should return spans
        assert len(spans_by_name) > 0
        assert len(spans_by_id) > 0

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_span_structure(
        self,
        is_async: bool,
        _span_ids: tuple[tuple[SpanId, SpanGlobalId], tuple[SpanId, SpanGlobalId]],
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user = _get_user(_MEMBER).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                limit=10,
            )
        )

        assert len(spans) > 0

        for span in spans:
            # Check required fields from v1.Span
            assert "id" in span
            assert "name" in span
            assert "context" in span
            assert "span_kind" in span
            assert "start_time" in span
            assert "end_time" in span
            assert "status_code" in span

            # Check datetime fields are strings (ISO format)
            assert isinstance(span["start_time"], str)
            assert isinstance(span["end_time"], str)

            # Check context structure
            context = span["context"]
            assert isinstance(context, dict)
            assert "trace_id" in context
            assert "span_id" in context
            assert isinstance(context["trace_id"], str)
            assert isinstance(context["span_id"], str)

            # Check optional attributes
            if "attributes" in span:
                assert isinstance(span["attributes"], dict)

            # Check events if present
            if "events" in span:
                assert isinstance(span["events"], list)
                for event in span["events"]:
                    assert isinstance(event, dict)
                    assert "name" in event
                    assert "timestamp" in event
                    assert isinstance(event["timestamp"], str)
                    if "attributes" in event:
                        assert isinstance(event["attributes"], dict)

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_empty_results(
        self,
        is_async: bool,
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test behavior when no spans match the filter criteria."""
        user = _get_user(_MEMBER).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        # Use a far future date that shouldn't have any spans
        far_future = datetime.now(timezone.utc) + timedelta(days=365 * 10)

        spans = await _await_or_return(
            Client().spans.get_spans(
                project_identifier="default",
                start_time=far_future,
                limit=10,
            )
        )

        # Should return empty list, not error
        assert isinstance(spans, list)
        assert len(spans) == 0

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_invalid_project_identifier(
        self,
        is_async: bool,
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test error handling for invalid project identifier."""
        user = _get_user(_MEMBER).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        import httpx
        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        # Test with non-existent project
        with pytest.raises(httpx.HTTPStatusError):
            await _await_or_return(
                Client().spans.get_spans(
                    project_identifier="non_existent_project_xyz_123",
                    limit=10,
                )
            )

    @pytest.mark.parametrize("is_async", [True, False])
    async def test_client_get_spans(
        self,
        is_async: bool,
        _span_ids: tuple[tuple[SpanId, SpanGlobalId], tuple[SpanId, SpanGlobalId]],
        _get_user: _GetUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test the get_spans method returns spans correctly."""
        user = _get_user(_MEMBER).log_in()
        monkeypatch.setenv("PHOENIX_API_KEY", user.create_api_key())

        from phoenix.client import AsyncClient
        from phoenix.client import Client as SyncClient

        Client = AsyncClient if is_async else SyncClient  # type: ignore[unused-ignore]

        # Extract the span IDs from the fixture
        (span_id1, _), (span_id2, _) = _span_ids

        all_spans = await _await_or_return(
            Client().spans.get_spans(project_identifier="default", limit=50)
        )

        span_ids_found = {span["context"]["span_id"] for span in all_spans}
        assert span_id1 in span_ids_found, f"Expected span {span_id1} not found in {span_ids_found}"
        assert span_id2 in span_ids_found, f"Expected span {span_id2} not found in {span_ids_found}"

        limited_spans = await _await_or_return(
            Client().spans.get_spans(project_identifier="default", limit=1)
        )
        assert len(limited_spans) <= 1, "Limit parameter should be respected"

        # Each span should have required fields
        for span in all_spans:
            assert "id" in span
            assert "name" in span
            assert "context" in span
            assert "span_id" in span["context"]
            assert "trace_id" in span["context"]
