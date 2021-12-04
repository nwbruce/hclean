#!/usr/bin/env python3

from argparse import ArgumentParser
from shutil import copy2
import re
import subprocess

def find_headers(lines):
    include_pattern = re.compile(r'^#\s*include\s*[\<"][^\>"]*[^\>"]')
    header_locations = []
    for i, l in enumerate(lines):
        m = include_pattern.match(l)
        if m:
            header_locations.append(i)
    return header_locations


def write_file(cppfile, lines, exclude_list):
    with open(cppfile, 'w') as fd:
        for i, l in enumerate(lines):
            if not i in exclude_list:
                fd.write(l)

def compile(cppfile):
    cmd = ['g++', '-c', cppfile]
    rc = subprocess.call(cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT)
    return rc == 0

def try_compile(cppfile, lines, exclude_index):
    write_file(cppfile, lines, [exclude_index])
    return compile(cppfile)
    

def do_clean(cppfile):
    copy2(cppfile, cppfile + '.bak')
    with open(cppfile, 'r') as fd:
        lines = fd.readlines()

    works = try_compile(cppfile, lines, None)
    if not works:
        print('Failed to do basic compile')
        exit(1)

    removable_locs = []
    header_locations = find_headers(lines)
    for loc in header_locations:
        print('without:', lines[loc].rstrip())
        works = try_compile(cppfile, lines, loc)
        if works:
            removable_locs.append(loc)

    write_file(cppfile, lines, removable_locs)


def main():
    parser = ArgumentParser()
    parser.add_argument('cppfile', help='C++ file to clean')
    args = parser.parse_args()
    do_clean(args.cppfile)

if __name__ == "__main__":
    main()