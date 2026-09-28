"""Execute the exact PowerShell projection with fake WMI objects, without native privileges."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


PRELUDE = r"""$script:itemCalls=0
class ProjectionProperties {
    [hashtable] $Values
    [bool] $Fault
    ProjectionProperties([hashtable] $values, [bool] $fault) {
        $this.Values=$values; $this.Fault=$fault
    }
    [object] Item([string] $name) {
        if($this.Fault){throw 'Injected property failure'}
        return @{Value=$this.Values[$name]}
    }
}
class ProjectionProcess {
    [ProjectionProperties] $Properties_
    ProjectionProcess([hashtable] $values, [bool] $fault) {
        $this.Properties_=[ProjectionProperties]::new($values,$fault)
    }
}
class ProjectionObjectSet {
    [object[]] $Items
    [int] $Count
    [bool] $Fault
    ProjectionObjectSet([object[]] $items, [bool] $fault) {
        $this.Items=$items; $this.Count=$items.Length; $this.Fault=$fault
    }
    [object] ItemIndex([int] $index) {
        $script:itemCalls++
        if($this.Fault){throw 'Injected index failure'}
        return $this.Items[$index]
    }
}
class ProjectionPrivileges {
    [void] AddAsString([string] $name, [bool] $enabled) {
        if($name -ne 'SeDebugPrivilege' -or !$enabled){throw 'Privilege request differs'}
    }
}
class ProjectionSecurity {
    [int] $ImpersonationLevel
    [ProjectionPrivileges] $Privileges=[ProjectionPrivileges]::new()
}
class ProjectionService {
    [ProjectionSecurity] $Security_=[ProjectionSecurity]::new()
    [object] $Collection
    [string] $ExpectedQuery
    [bool] $Fault
    [object] ExecQuery([string] $query, [string] $language, [int] $flags) {
        if($query -cne $this.ExpectedQuery -or $language -cne 'WQL' -or
           $flags -notin @(16,48) -or $this.Security_.ImpersonationLevel -ne 3){
            throw 'Local fixed query request differs'
        }
        $script:queryFlags=$flags
        if($this.Fault){throw 'Injected query failure'}
        return $this.Collection
    }
}
class ProjectionLocator {
    [ProjectionService] $Service
    [object] ConnectServer([string] $computer, [string] $namespace) {
        if($computer -cne '.' -or $namespace -cne 'root\cimv2'){throw 'Local namespace differs'}
        return $this.Service
    }
}
function New-Object {
    param([string] $ComObject)
    if($ComObject -cne 'WbemScripting.SWbemLocator'){throw 'COM request differs'}
    return $script:locator
}
"""


def source_script():
    path = Path(__file__).resolve().parents[2] / "scripts/verification/scm_stock_git_lifecycle.py"
    tree = ast.parse(path.read_bytes())
    methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_processes"]
    assert len(methods) == 1
    values = [ast.literal_eval(node.value) for node in methods[0].body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "script" for target in node.targets)]
    assert len(values) == 1 and isinstance(values[0], str)
    return values[0]


@pytest.fixture(scope="module")
def pwsh():
    executable = os.environ.get("RENTGEN_TEST_PWSH") or shutil.which("pwsh.exe") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 required for executable process projection regression")
    return executable


def project(pwsh, tmp_path, count, *, fault="", missing=""):
    expected = [{"ProcessId": 1000 + i, "ParentProcessId": 700 + i,
                 "ExecutablePath": rf"C:\Runtime {i}\python.exe", "CommandLine": f"python --fixture {i}"}
                for i in range(count)]
    if missing:
        expected[0][missing] = None
    rows_path, calls_path = tmp_path / "rows.json", tmp_path / "calls.json"
    rows_path.write_text(json.dumps(expected), "utf-8")
    script = source_script()
    query = "SELECT ProcessId,ParentProcessId,ExecutablePath,CommandLine FROM Win32_Process WHERE " \
            "Name='java.exe' OR Name='git.exe' OR Name='bsl-scan.exe' OR Name='python.exe'"
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    setup = f"""        $inputRows=@(Get-Content -LiteralPath {quote(rows_path)} -Raw | ConvertFrom-Json -AsHashtable)
        $items=@(foreach($row in $inputRows){{[ProjectionProcess]::new($row,${str(fault == 'property').lower()})}})
        $collection=[ProjectionObjectSet]::new($items,${str(fault == 'index').lower()})
        $service=[ProjectionService]::new(); $service.Collection=$collection
        if({quote(fault)} -eq 'count'){{$service.Collection=[pscustomobject]@{{}}}}
        if({quote(fault)} -eq 'count'){{Add-Member -InputObject $service.Collection -MemberType ScriptProperty -Name Count -Value {{throw 'Injected count failure'}}}}
        $service.ExpectedQuery={quote(query)}; $service.Fault=${str(fault == 'query').lower()}
        $script:locator=[ProjectionLocator]::new(); $script:locator.Service=$service
        $projection=[scriptblock]::Create({quote(script)})
        try{{ & $projection }}
        finally{{ @{{item_calls=$script:itemCalls;flags=$script:queryFlags}} | ConvertTo-Json -Compress | Set-Content -LiteralPath {quote(calls_path)} -Encoding utf8 }}
    """
    result = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", PRELUDE + setup],
                            capture_output=True, timeout=10)
    assert len(result.stdout) <= 32768 and len(result.stderr) <= 32768
    assert calls_path.exists(), result.stderr.decode("utf-8", errors="replace")
    calls = json.loads(calls_path.read_text("utf-8-sig"))
    return result, calls, expected


@pytest.mark.parametrize("count", [0, 1, 2, 100])
def test_exact_source_projects_non_enumerable_object_set_by_index(pwsh, tmp_path, count):
    result, calls, expected = project(pwsh, tmp_path, count)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert json.loads(result.stdout.decode("utf-8-sig")) == expected
    assert calls == {"item_calls": count, "flags": 16}


def test_exact_source_refuses_collection_over_row_bound_before_index_read(pwsh, tmp_path):
    result, calls, _ = project(pwsh, tmp_path, 101)
    assert result.returncode != 0 and result.stdout == b""
    assert b"Native process inventory row limit" in result.stderr
    assert calls == {"item_calls": 0, "flags": 16}


@pytest.mark.parametrize("missing", ["ExecutablePath", "CommandLine"])
def test_exact_source_preserves_null_fields_for_strict_downstream_validation(pwsh, tmp_path, missing):
    result, calls, expected = project(pwsh, tmp_path, 1, missing=missing)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert json.loads(result.stdout.decode("utf-8-sig")) == expected
    assert calls == {"item_calls": 1, "flags": 16}


@pytest.mark.parametrize("fault", ["query", "count", "index", "property"])
def test_exact_source_projection_failure_has_no_partial_success_json(pwsh, tmp_path, fault):
    result, calls, _ = project(pwsh, tmp_path, 2, fault=fault)
    assert result.returncode != 0 and result.stdout == b""
    message = "Native process inventory count unavailable" if fault == "count" else "Injected " + fault + " failure"
    assert message.encode() in result.stderr
    assert calls["item_calls"] == (1 if fault in {"index", "property"} else 0)
