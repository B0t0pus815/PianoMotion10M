"""Pytest configuration — register custom markers, suppress warnings."""


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'slow: integration tests that load Ramoneda checkpoints and '
        'run inference (~12 min total). Skip with -m "not slow".',
    )
