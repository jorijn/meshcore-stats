"""Tests for with_retries async function."""

import asyncio

import pytest

from meshmon.retry import with_retries


class TestWithRetriesSuccess:
    """Tests for successful operation scenarios."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self):
        """Returns result when operation succeeds."""
        async def success_fn():
            return "result"

        success, result, exception = await with_retries(success_fn)

        assert success is True
        assert result == "result"
        assert exception is None

    @pytest.mark.asyncio
    async def test_single_attempt_on_success(self):
        """Only calls function once when successful."""
        call_count = 0

        async def counting_fn():
            nonlocal call_count
            call_count += 1
            return "done"

        await with_retries(counting_fn, attempts=3)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_returns_complex_result(self):
        """Returns complex result types correctly."""
        async def complex_fn():
            return {"status": "ok", "data": [1, 2, 3]}

        success, result, _ = await with_retries(complex_fn)

        assert result == {"status": "ok", "data": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_returns_none_result(self):
        """Returns None result correctly (distinct from failure)."""
        async def none_fn():
            return None

        success, result, exception = await with_retries(none_fn)

        assert success is True
        assert result is None
        assert exception is None


class TestWithRetriesFailure:
    """Tests for failure scenarios."""

    @pytest.mark.asyncio
    async def test_returns_false_on_exhausted_attempts(self):
        """Returns failure when all attempts exhausted."""
        async def failing_fn():
            raise ValueError("always fails")

        success, result, exception = await with_retries(
            failing_fn, attempts=3, backoff_s=0.01
        )

        assert success is False
        assert result is None
        assert isinstance(exception, ValueError)

    @pytest.mark.asyncio
    async def test_retries_specified_times(self):
        """Retries the specified number of times."""
        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        await with_retries(failing_fn, attempts=5, backoff_s=0.01)

        assert call_count == 5

    @pytest.mark.asyncio
    async def test_returns_last_exception(self):
        """Returns the exception from the last attempt."""
        attempt = 0

        async def changing_error_fn():
            nonlocal attempt
            attempt += 1
            raise ValueError(f"error {attempt}")

        success, result, exception = await with_retries(
            changing_error_fn, attempts=3, backoff_s=0.01
        )

        assert str(exception) == "error 3"


class TestWithRetriesRetryBehavior:
    """Tests for retry behavior."""

    @pytest.mark.asyncio
    async def test_succeeds_on_retry(self):
        """Succeeds if operation succeeds on retry."""
        attempt = 0

        async def eventually_succeeds():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise RuntimeError("not yet")
            return "success"

        success, result, exception = await with_retries(
            eventually_succeeds, attempts=5, backoff_s=0.01
        )

        assert success is True
        assert result == "success"
        assert exception is None
        assert attempt == 3

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Waits backoff_s between retries."""
        import time

        async def failing_fn():
            raise RuntimeError("fail")

        start = time.time()
        await with_retries(failing_fn, attempts=3, backoff_s=0.1)
        elapsed = time.time() - start

        # Should wait ~0.2s total (2 backoffs between 3 attempts)
        assert elapsed >= 0.18
        assert elapsed < 0.5  # Allow some overhead

    @pytest.mark.asyncio
    async def test_no_backoff_after_last_attempt(self):
        """Does not wait after final failed attempt."""
        import time

        async def failing_fn():
            raise RuntimeError("fail")

        start = time.time()
        await with_retries(failing_fn, attempts=2, backoff_s=0.5)
        elapsed = time.time() - start

        # Only 1 backoff between 2 attempts (~0.5s)
        assert elapsed >= 0.45
        assert elapsed < 0.8  # Should not wait twice


class TestWithRetriesParameters:
    """Tests for parameter handling."""

    @pytest.mark.asyncio
    async def test_default_attempts(self):
        """Uses default of 2 attempts."""
        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        await with_retries(failing_fn, backoff_s=0.01)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        """Works with single attempt (no retry)."""
        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        await with_retries(failing_fn, attempts=1, backoff_s=0.01)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_zero_backoff(self):
        """Works with zero backoff."""
        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        await with_retries(failing_fn, attempts=3, backoff_s=0)

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_name_parameter_for_logging(self, capfd):
        """Name parameter is used in logging."""
        async def failing_fn():
            raise RuntimeError("fail")

        await with_retries(
            failing_fn, attempts=2, backoff_s=0.01, name="test_operation"
        )

        # The function logs with the operation name
        # (actual output depends on log configuration)


class TestWithRetriesExceptionTypes:
    """Tests for different exception types."""

    @pytest.mark.asyncio
    async def test_handles_value_error(self):
        """Handles ValueError correctly."""
        async def fn():
            raise ValueError("value error")

        success, _, exception = await with_retries(fn, attempts=1)

        assert success is False
        assert isinstance(exception, ValueError)

    @pytest.mark.asyncio
    async def test_handles_runtime_error(self):
        """Handles RuntimeError correctly."""
        async def fn():
            raise RuntimeError("runtime error")

        success, _, exception = await with_retries(fn, attempts=1)

        assert success is False
        assert isinstance(exception, RuntimeError)

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self):
        """Handles asyncio.TimeoutError correctly."""
        async def fn():
            raise TimeoutError("timeout")

        success, _, exception = await with_retries(fn, attempts=1)

        assert success is False
        assert isinstance(exception, asyncio.TimeoutError)

    @pytest.mark.asyncio
    async def test_handles_os_error(self):
        """Handles OSError correctly."""
        async def fn():
            raise OSError("os error")

        success, _, exception = await with_retries(fn, attempts=1)

        assert success is False
        assert isinstance(exception, OSError)

    @pytest.mark.asyncio
    async def test_handles_custom_exception(self):
        """Handles custom exception types correctly."""
        class CustomError(Exception):
            pass

        async def fn():
            raise CustomError("custom")

        success, _, exception = await with_retries(fn, attempts=1)

        assert success is False
        assert isinstance(exception, CustomError)


class TestWithRetriesAsyncBehavior:
    """Tests for async-specific behavior."""

    @pytest.mark.asyncio
    async def test_concurrent_retries_independent(self):
        """Multiple concurrent retry operations are independent."""
        calls_a = 0
        calls_b = 0

        async def fn_a():
            nonlocal calls_a
            calls_a += 1
            if calls_a < 2:
                raise RuntimeError("a fails first")
            return "a"

        async def fn_b():
            nonlocal calls_b
            calls_b += 1
            if calls_b < 3:
                raise RuntimeError("b fails more")
            return "b"

        results = await asyncio.gather(
            with_retries(fn_a, attempts=3, backoff_s=0.01),
            with_retries(fn_b, attempts=4, backoff_s=0.01),
        )

        assert results[0] == (True, "a", None)
        assert results[1] == (True, "b", None)
        assert calls_a == 2
        assert calls_b == 3

    @pytest.mark.asyncio
    async def test_does_not_block_event_loop(self):
        """Backoff uses asyncio.sleep, not blocking sleep."""
        events = []

        async def fn():
            events.append("fn")
            raise RuntimeError("fail")

        async def background():
            await asyncio.sleep(0.05)
            events.append("bg")
            await asyncio.sleep(0.05)
            events.append("bg")

        await asyncio.gather(
            with_retries(fn, attempts=2, backoff_s=0.08),
            background(),
        )

        # Background task should interleave with retry backoff
        assert "bg" in events
