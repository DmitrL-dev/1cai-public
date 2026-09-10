"""Keep sdist inputs independent of ambient Git/Mercurial ignore files."""

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        # Hatchling 1.32.0 force-includes discovered VCS files even with
        # ignore-vcs=true. Discovery can climb outside the project root.
        # The explicit sdist whitelist owns our source selection; remove only
        # these automatic additions, keeping README/license/backend metadata.
        for files in self.build_config.vcs_exclusion_files.values():
            for path in files:
                build_data["force_include"].pop(path, None)
