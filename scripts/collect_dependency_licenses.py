"""Collect exact-version runtime notices from the Windows build environment.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
from packaging.requirements import Requirement


def collect(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    supplements = Path(__file__).resolve().parent.parent / 'third_party_notices'
    shutil.copytree(supplements, output / 'supplemental', dirs_exist_ok=True)
    pending = ['aiohttp', 'grpcio', 'protobuf', 'tzdata', 'TikTokLive', 'pywebview', 'pyinstaller']
    seen, inventory = set(), []
    while pending:
        name = pending.pop()
        dist = metadata.distribution(name)
        name = dist.metadata['Name']
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        destination = output / name
        destination.mkdir(exist_ok=True)
        notices = []
        for file in dist.files or []:
            parts = Path(str(file)).parts
            if '..' in parts or Path(str(file)).is_absolute():
                continue
            if not any(word in Path(str(file)).name.lower() for word in ('license', 'licence', 'copying', 'notice')):
                continue
            source = Path(dist.locate_file(file))
            if source.is_file():
                target = destination.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                notices.append(str(file))
        (destination / 'METADATA.txt').write_text(dist.read_text('METADATA') or json.dumps(dict(dist.metadata.items()), indent=2), encoding='utf-8')
        inventory.append(dict(name=name, version=dist.version,
            license=dist.metadata.get('License-Expression') or dist.metadata.get('License', ''),
            project_urls=dist.metadata.get_all('Project-URL', []),
            homepage=dist.metadata.get('Home-page', ''), notices=notices))
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                pending.append(requirement.name)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Python runtime LICENSE.txt missing from build environment')
    shutil.copyfile(python_license, output / 'Python-LICENSE.txt')
    (output / 'inventory.json').write_text(json.dumps(sorted(inventory,key=lambda row:row['name'].lower()), indent=2), encoding='utf-8')
    print(f'Collected runtime notices for {len(inventory)} distributions and Python.')


if __name__ == '__main__':
    collect(sys.argv[1] if len(sys.argv)>1 else 'third-party-licenses')
