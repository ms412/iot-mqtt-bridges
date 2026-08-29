#!/usr/bin/env python3
"""Tests for common.logging.app_logger.AppLogger.setup()."""

import logging

import pytest

from common.logging.app_logger import AppLogger


def _stdout_handler_level():
    """Return the level of the root's stdout StreamHandler, or None."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            return handler.level
    return None


def test_setup_returns_logger_with_requested_name():
    log = AppLogger().setup(name='mybridge', loggingmode='CONSOLE', level='INFO')
    assert log.name == 'mybridge'


def test_console_mode_configures_stdout_handler():
    AppLogger().setup(name='mybridge', loggingmode='CONSOLE', level='INFO')
    assert _stdout_handler_level() == logging.INFO


def test_console_mode_is_case_insensitive():
    AppLogger().setup(name='mybridge', loggingmode='console', level='WARNING')
    assert _stdout_handler_level() == logging.WARNING


def test_unknown_mode_falls_back_to_console():
    AppLogger().setup(name='mybridge', loggingmode='NONSENSE', level='INFO')
    assert _stdout_handler_level() == logging.INFO


def test_child_logger_emits_at_configured_level(capsys):
    AppLogger().setup(name='mybridge', loggingmode='CONSOLE', level='INFO')
    child = logging.getLogger('mybridge.reader.Reader')
    child.info('hello-info')
    child.debug('hidden-debug')
    captured = capsys.readouterr()
    assert 'hello-info' in captured.out
    assert 'hidden-debug' not in captured.out


def test_file_mode_uses_given_filename(tmp_path):
    logfile = tmp_path / 'bridge.log'
    AppLogger().setup(name='mybridge', loggingmode='FILE', level='INFO', filename=str(logfile))
    file_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, logging.FileHandler)
    ]
    assert file_handlers, 'FILE mode should install a file handler'
    assert file_handlers[0].baseFilename == str(logfile)


@pytest.fixture(autouse=True)
def _reset_root_handlers():
    """Keep tests isolated: restore root handlers after each test."""
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    yield
    # Close any file handlers opened during the test to release the temp file.
    for handler in list(root.handlers):
        if handler not in saved and isinstance(handler, logging.FileHandler):
            handler.close()
    root.handlers = saved
    root.setLevel(saved_level)
