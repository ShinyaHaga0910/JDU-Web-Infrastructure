"""Render only the two fixed classroom SQL profiles; never execute SQL or accept passwords."""
import argparse
from pathlib import Path

from configuration import PROFILES

FILES = ('01_create_roles.sql', '02_prepare_schema.sql', '03_runtime_grants.sql', '04_disable_setup.sql')


def render(profile, filename):
    if profile not in PROFILES or filename not in FILES:
        raise ValueError('Choose a fixed profile and reviewed SQL operation')
    text = (Path(__file__).resolve().parent / 'sql' / filename).read_text()
    if profile == 'practice':
        for original, replacement in zip(PROFILES['mission'][:3], PROFILES['practice'][:3]):
            text = text.replace(original, replacement)
    return text


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', choices=tuple(PROFILES), required=True)
    p.add_argument('filename', choices=FILES)
    a = p.parse_args(); print(render(a.profile, a.filename), end='')
