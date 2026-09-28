"""Fixed stock SCM binding; injected controls never confer native acceptance."""
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.unit.test_git_scm_diagnostic import control_api, prepared_control, row


def api():
    script = Path(__file__).resolve().parents[2] / 'scripts/verification/scm_stock_git_control.py'
    assert script.is_file(), 'Stock SCM control adapter missing'
    spec = importlib.util.spec_from_file_location('stock_scm_control_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepared(tmp_path, monkeypatch, **authority):
    module = api()
    control, old, native, probe, commands, _ = prepared_control(tmp_path, monkeypatch, **authority)
    config = old.workdir / 'fixture/localservice/stock-git-service.json'
    manifest = old.workdir / 'fixture/localservice/stock-source-manifest.json'
    entry = old.workdir / 'runtime/Lib/site-packages/rentgen_core/service_entry.py'
    entry.parent.mkdir()
    config.write_bytes(b'{"schema":3}')
    manifest.write_bytes(b'{"schema":1}')
    entry.write_bytes(b'# fixed stock entry metadata; never executed by unit tests\n')
    expected = {path:hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (old.workdir/'runtime/python.exe', config, manifest, entry)}
    stock = module.create_installer(control, probe, native, old.workdir, old.authority, old.output, expected)
    capture = probe.capture
    def invoke(command, *args, **kwargs):
        result = capture(command, *args, **kwargs)
        if command[1] != 'delete':
            native.query.return_value = row(stock.spec, 4 if command[1]=='start' else 1)
        return result
    monkeypatch.setattr(probe,'capture',invoke)
    return module, stock, native, probe, commands, expected


def test_actual_public_stock_spec_fixed_owned_localservice_control_sequence(tmp_path, monkeypatch):
    from rentgen_core.service_installer import ServiceInstallSpec
    _, stock, native, _, commands, expected = prepared(tmp_path, monkeypatch)
    assert type(stock.spec) is ServiceInstallSpec
    assert stock.spec.arguments == ('-I','-m','rentgen_core.service_entry','--service','--config',
        str(stock.workdir/'fixture/localservice/stock-git-service.json'))
    assert stock.spec.display_name == 'Rentgen Isolated Stock Git CI'
    assert stock.spec.service_name == 'Rentgen.CI.' + 'a'*12
    stock.install(stock.spec)
    assert stock.created and commands[0][-2:] == ('obj=', r'NT AUTHORITY\LocalService')
    assert commands[0][4] == stock.spec.binary_path
    stock.start(stock.spec)
    stock.stop(stock.spec)
    stock.uninstall(stock.spec)
    assert [command[1] for command in commands] == ['create','start','stop','delete']
    assert native.query.return_value == {'exists':False}
    assert len(list(stock.output.glob('control-*.json'))) == 4
    assert {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in expected} == expected


@pytest.mark.parametrize('missing',['elevated','create_access','backup_privilege','restore_privilege'])
def test_stock_control_refuses_missing_authority_before_query_or_child(tmp_path, monkeypatch, missing):
    _, stock, native, _, commands, _ = prepared(tmp_path, monkeypatch, **{missing:False})
    with pytest.raises(RuntimeError):
        stock.install(stock.spec)
    native.query.assert_not_called()
    assert not commands and not stock.created


@pytest.mark.parametrize('index',range(4))
def test_changed_interpreter_config_manifest_or_stock_entry_never_created(tmp_path, monkeypatch, index):
    _, stock, native, _, commands, expected = prepared(tmp_path, monkeypatch)
    list(expected)[index].write_bytes(b'changed input')
    with pytest.raises(ValueError):
        stock.install(stock.spec)
    native.query.assert_not_called()
    assert not commands and not stock.created


@pytest.mark.parametrize('key',['binary_path','account','service_type','start_type','display_name'])
def test_stock_refuses_foreign_binding_after_acknowledged_create(tmp_path, monkeypatch, key):
    _, stock, native, _, commands, _ = prepared(tmp_path, monkeypatch)
    stock.install(stock.spec)
    changed = row(stock.spec)
    changed['config'][key] = 'foreign'
    native.query.return_value = changed
    with pytest.raises(RuntimeError):
        stock.start(stock.spec)
    with pytest.raises(RuntimeError):
        stock.uninstall(stock.spec)
    assert len(commands)==1


def test_existing_service_is_not_adopted(tmp_path, monkeypatch):
    _, stock, native, _, commands, _ = prepared(tmp_path, monkeypatch)
    native.query.return_value = row(stock.spec)
    with pytest.raises(RuntimeError):
        stock.install(stock.spec)
    with pytest.raises(RuntimeError):
        stock.uninstall(stock.spec)
    assert not commands and not stock.created


def test_foreign_spec_and_implicit_start_refused(tmp_path, monkeypatch):
    _, stock, _, _, commands, _ = prepared(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        stock.install(Mock())
    with pytest.raises(ValueError):
        stock.install(stock.spec,start=True)
    assert not commands


def test_timeout_cannot_authorize_deletion(tmp_path, monkeypatch):
    _, stock, native, probe, commands, _ = prepared(tmp_path, monkeypatch)
    original = probe.capture
    monkeypatch.setattr(probe,'capture',lambda *args,**kwargs:original(*args,**kwargs)|{'timed_out':True})
    with pytest.raises(RuntimeError):
        stock.install(stock.spec)
    assert native.query.return_value['exists'] and not stock.created
    with pytest.raises(RuntimeError):
        stock.uninstall(stock.spec)
    assert len(commands)==1


@pytest.mark.parametrize('change',['extra','missing','outside_output','outside_workdir'])
def test_constructor_binds_only_owned_fixed_inputs_before_control(tmp_path, monkeypatch, change):
    module, stock, native, probe, commands, expected = prepared(tmp_path, monkeypatch)
    output, work = stock.output, stock.workdir
    if change=='extra':
        expected = expected | {work/'runtime/Lib/site-packages/scm_git_probe_service.py':'a'*64}
    elif change=='missing':
        expected.pop(work/'fixture/localservice/stock-source-manifest.json')
    elif change=='outside_output':
        output = tmp_path
    else:
        work = tmp_path
    with pytest.raises(ValueError):
        module.create_installer(control_api(),probe,native,work,stock.authority,output,expected)
    assert not commands
