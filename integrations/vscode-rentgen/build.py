"""Reproducible VSIX from this dependency-free extension; no network or npm."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZipInfo, ZIP_STORED


ROOT = Path(__file__).resolve().parent


def build_bytes():
    paths = ["package.json", "extension.cjs", "README.md", "LICENSE.txt", "build.py"]
    paths += sorted(
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in (ROOT / "lib").glob("*.cjs")
    )
    paths += sorted(
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in (ROOT / "test").glob("*.cjs")
    )
    # Text-only package: normalize checkout line endings for identical bytes.
    files = {
        "extension/" + p: (ROOT / p).read_text("utf-8").encode("utf-8") for p in paths
    }
    # A distributed extension rebuilds from its own bundled adapter sources.
    adapter = (
        ROOT / "repair" if (ROOT / "repair").is_dir() else ROOT.parent / "open-editor"
    )
    for name in ("run_repair.py", "repair_workflow.py", "repair_model.py"):
        files["extension/repair/" + name] = (
            (adapter / name).read_text("utf-8").encode("utf-8")
        )
    package = json.loads(files["extension/package.json"])
    if package.get("dependencies") or package.get("devDependencies"):
        raise ValueError("This packager supports only the dependency-free companion")
    manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
<Metadata>
<Identity Language="ru-RU" Id={quoteattr(package['name'])} Version={quoteattr(package['version'])} Publisher={quoteattr(package['publisher'])}/>
<DisplayName>{escape(package['displayName'])}</DisplayName>
<Description xml:space="preserve">{escape(package['description'])}</Description>
<Tags>1C,BSL,Rentgen</Tags><Categories>Other</Categories><GalleryFlags>Public</GalleryFlags>
<Properties>
<Property Id="Microsoft.VisualStudio.Code.Engine" Value={quoteattr(package['engines']['vscode'])}/>
<Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace"/>
<Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true"/>
</Properties><License>extension/LICENSE.txt</License>
</Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/>
<Assets>
<Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
<Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true"/>
<Asset Type="Microsoft.VisualStudio.Services.Content.License" Path="extension/LICENSE.txt" Addressable="true"/>
</Assets></PackageManifest>
"""
    files["extension.vsixmanifest"] = manifest.encode("utf-8")
    types = {
        "cjs": "application/javascript",
        "json": "application/json",
        "md": "text/markdown",
        "txt": "text/plain",
        "py": "text/plain",
        "vsixmanifest": "text/xml",
    }
    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + "".join(
            f'<Default Extension=".{ext}" ContentType="{mime}"/>'
            for ext, mime in types.items()
        )
        + "</Types>\n"
    ).encode("utf-8")
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(name, (2026, 9, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = build_bytes()
    with args.output.open("xb") as stream:
        stream.write(content)
    print(
        json.dumps(
            {
                "path": str(args.output.absolute()),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        )
    )


if __name__ == "__main__":
    main()
