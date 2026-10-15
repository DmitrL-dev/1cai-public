"""The installed GUI bootstrap stays bounded, loopback-only and session-private."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location(
    'portable_gui_delivery',
    Path(__file__).resolve().parents[2] / 'scripts/verification/verify_portable_delivery.py',
)
delivery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delivery)

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX installed GUI bootstrap uses selectable pipes')


def start(url):
    code = 'import sys;sys.stdout.write(' + repr('Private startup\n' + url + '\n') + ');sys.stdout.flush()'
    return subprocess.Popen([sys.executable, '-I', '-c', code], stdout=subprocess.PIPE)


def test_installed_bootstrap_accepts_only_private_loopback_url():
    token = 'a' * 43
    child = start('http://127.0.0.1:12345/#' + token)
    try:
        assert delivery.bootstrap(child) == ('http://127.0.0.1:12345', token)
    finally:
        child.communicate(timeout=5)


@pytest.mark.parametrize('url', [
    'https://127.0.0.1:12345/#{token}', 'http://localhost:12345/#{token}',
    'http://0.0.0.0:12345/#{token}', 'http://127.0.0.1/#{token}',
    'http://user@127.0.0.1:12345/#{token}', 'http://127.0.0.1:12345/path#{token}',
    'http://127.0.0.1:12345/?session=private#{token}', 'http://127.0.0.1:12345/#short',
])
def test_invalid_bootstrap_is_rejected_without_printing_session(url):
    token = 'private_token_' + 'x' * 29
    child = start(url.format(token=token))
    try:
        with pytest.raises(AssertionError) as error:
            delivery.bootstrap(child)
        assert token not in str(error.value)
        assert 'http' not in str(error.value)
    finally:
        child.communicate(timeout=5)


def test_bootstrap_readiness_has_a_deadline():
    child = subprocess.Popen([sys.executable, '-I', '-c', 'import time;time.sleep(10)'], stdout=subprocess.PIPE)
    try:
        with pytest.raises(AssertionError, match='readiness timed out'):
            delivery.bootstrap(child, timeout=.05)
    finally:
        child.kill()
        child.communicate(timeout=5)


def test_bootstrap_is_bounded_even_when_child_prints_unterminated_output():
    child = subprocess.Popen([sys.executable, '-I', '-c', 'print("x" * 9000, end="", flush=True)'], stdout=subprocess.PIPE)
    try:
        with pytest.raises(AssertionError, match='invalid startup'):
            delivery.bootstrap(child)
    finally:
        child.communicate(timeout=5)
