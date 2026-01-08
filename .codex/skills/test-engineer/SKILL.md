---
name: test-engineer
description: Test planning, writing, and review across unit/integration/e2e, primarily with pytest. Use when adding tests, improving coverage, diagnosing flaky tests, or designing a testing strategy.
---

# Test Engineer

## Overview
Create fast, reliable tests that validate behavior and improve coverage without brittleness.

## Testing Principles
- Follow F.I.R.S.T. (fast, isolated, repeatable, self-validating, timely)
- Use Arrange-Act-Assert structure
- Favor unit tests, add integration tests as needed, minimize e2e
- Test behavior, not implementation details
- Keep one behavior per test

## Python Testing Focus
- pytest fixtures, parametrization, markers, conftest organization
- unittest + mock for legacy patterns
- hypothesis for property-based tests
- coverage.py for measurement
- pytest-asyncio for async code

## Test Categories
- Unit tests
- Integration tests
- End-to-end tests
- Property-based tests
- Regression tests
- Performance tests (when relevant)

## Writing Tests
- Identify contract: inputs, outputs, side effects, exceptions
- Enumerate cases: happy path, boundaries, invalid input, failure modes
- Use descriptive names and keep tests independent
- Use fixtures for shared setup; parametrize for variations

## Reviewing Tests
- Look for missing edge cases and error scenarios
- Identify flakiness (time/order/external dependencies)
- Avoid over-mocking; mock only boundaries
- Ensure assertions are specific and meaningful
- Verify cleanup and resource management

## Naming Convention
Use `test_<function>_<scenario>_<expected_result>`.

## Test Structure
```python
def test_function_name_describes_behavior():
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value
```

## Fixture Best Practices
- Prefer function-scoped fixtures
- Use `yield` for cleanup
- Document fixture purpose

## Mocking Guidelines
- Mock at the boundary (DB, filesystem, network)
- Do not mock the unit under test
- Verify interactions when they are the behavior
- Use `autospec=True` to catch interface mismatches

## Edge Cases to Consider
- Numeric: zero, negative, large, precision
- Strings: empty, whitespace, unicode, long, special chars
- Collections: empty, single, large, duplicates, None elements
- Time: DST, leap years, month boundaries, epoch edges
- I/O: not found, permission denied, timeouts, partial writes, concurrency

## Output Expectations
- Provide runnable tests with brief explanations
- Call out missing coverage or risky gaps
- Follow project conventions in `AGENTS.md`
