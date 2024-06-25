#!/usr/bin/env python3
#
# Copyright (c) 2024 LunarG, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Entry point for jitpack.yml.

This implements the custom build command used by the jitpack.yml in the top level of
this repo. See the documentation in that file for more information.
"""
import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from zipfile import ZipFile

import android
import common_ci


def artifact_info_from_env() -> tuple[str, str, str]:
    """Returns a tuple of [group ID, artifact ID, version]."""
    # Jitpack puts this information in the environment:
    # https://jitpack.io/docs/BUILDING/#build-environment
    try:
        return os.environ["GROUP"], os.environ["ARTIFACT"], os.environ["VERSION"]
    except KeyError as ex:
        sys.exit(f"{ex.args[0]} must be set in the environment")


def ndk_default_abis() -> Iterator[str]:
    """Yields each default NDK ABI.

    The NDK includes a meta/abis.json file that enumerates each ABI the NDK is capable
    of building for, and includes some descriptive data for each ABI. One of those
    fields is "default", which will be true if the ABI is one that the NDK maintainers
    recommend including support for by default. Most of the time all ABIs are
    recommended to be built by default, but in the rare case where an ABI is under
    development, or an old one is deprecated, we can key off that field to avoid them.

    At the time of writing (July 2024), the only non-default ABI is riscv64. The NDK r27
    changelog says that it's only there for bringup and shouldn't be used for release
    artifacts yet.
    """
    try:
        ndk = Path(os.environ["ANDROID_NDK_HOME"])
    except KeyError:
        sys.exit("ANDROID_NDK_HOME must be set in the environment")

    abis_meta_path = ndk / "meta/abis.json"
    if not abis_meta_path.exists():
        sys.exit(
            f"{abis_meta_path} does not exist. Does ANDROID_NDK_HOME ({ndk}) point to "
            "a valid NDK?"
        )

    with abis_meta_path.open("r", encoding="utf-8") as abis_meta_file:
        abis_meta = json.load(abis_meta_file)

    for name, data in abis_meta.items():
        if data["default"]:
            yield name


def generate_aar(
    output_path: Path,
    library_dir: Path,
    group_id: str,
    artifact_id: str,
    min_sdk_version: int,
) -> None:
    """Creates an AAR from the CMake binaries."""
    with ZipFile(output_path, mode="w") as zip_file:
        zip_file.writestr(
            "AndroidManifest.xml",
            textwrap.dedent(
                f"""\
                <?xml version="1.0" encoding="utf-8"?>
                <manifest xmlns:android="http://schemas.android.com/apk/res/android"
                    package="{group_id}.{artifact_id}" >
                    <uses-sdk android:minSdkVersion="{min_sdk_version}" />
                </manifest>
                """
            ),
        )

        for abi_dir in library_dir.iterdir():
            libs = list(abi_dir.glob("*.so"))
            if not libs:
                raise RuntimeError(f"No libraries found matching {abi_dir}/*.so")
            for lib in libs:
                zip_file.write(lib, arcname=f"jni/{abi_dir.name}/{lib.name}")


def install(aar: Path, group_id: str, artifact_id: str, version: str) -> None:
    """Installs the AAR to the local maven repository."""
    # A custom jitpack build must install the artifact to the local maven repository.
    # https://jitpack.io/docs/BUILDING/#custom-commands
    #
    # The jitpack host has mvn installed, so the easiest way to do this is to follow
    # https://maven.apache.org/guides/mini/guide-3rd-party-jars-local.html
    subprocess.run(
        [
            "mvn",
            "install:install-file",
            f"-Dfile={aar}",
            f"-DgroupId={group_id}",
            f"-DartifactId={artifact_id}",
            f"-Dversion={version}",
            "-Dpackaging=aar",
        ],
        check=True,
    )


def main() -> None:
    """Entry point called by jitpack.yml."""
    group_id, artifact_id, version = artifact_info_from_env()
    build_dir = android.build("Release", list(ndk_default_abis()), "c++_static")

    aar_dir = Path(common_ci.RepoRelative("build-android/aar"))
    aar_dir.mkdir(parents=True, exist_ok=True)
    aar = aar_dir / f"{artifact_id}-{version}.aar"
    generate_aar(aar, build_dir / "lib", group_id, artifact_id, android.MIN_SDK_VERSION)
    install(aar, group_id, artifact_id, version)


if __name__ == "__main__":
    main()
