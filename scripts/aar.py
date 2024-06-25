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

from pathlib import Path
from zipfile import ZipFile
import argparse
import textwrap


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group-id", help="The group ID of the AAR that will be published"
    )
    parser.add_argument(
        "--artifact-id", help="The artifact ID of the AAR that will be published"
    )
    parser.add_argument(
        "--min-sdk-version",
        type=int,
        default=26,
        help="The minSdkVersion of the built artifacts",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output file name")
    parser.add_argument(
        "library_directory",
        type=Path,
        help="Directory containing the built libraries, separated into ABI-named subdirectories",
    )
    args = parser.parse_args()

    generate_aar(
        args.output,
        args.library_directory,
        args.group_id,
        args.artifact_id,
        args.min_sdk_version,
    )


if __name__ == "__main__":
    main()
