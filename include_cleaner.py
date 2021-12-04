#!/usr/bin/env python3

from argparse import ArgumentParser
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

def compile(cmd):
    rc = subprocess.call(cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    return rc

def write_and_compile(cmd, cppfile, lines, exclude_index):
    write_file(cppfile, lines, [exclude_index])
    return compile(cmd)
    

def do_clean(cppfile, cmd):
    with open(cppfile, 'r') as fd:
        lines = fd.readlines()

    rc = write_and_compile(cmd, cppfile, lines, None)
    if rc != 0:
        print('Failed to do basic compile')
        exit(1)

    removable_locs = []
    header_locations = find_headers(lines)
    for loc in header_locations:
        print('without:', lines[loc].rstrip())
        rc = write_and_compile(cmd, cppfile, lines, loc)
        if rc != 0:
            removable_locs.append(loc)

    write_file(cppfile, lines, removable_locs)


def main():
    parser = ArgumentParser()
    parser.add_argument('cppfile', help='C++ file to clean')
    parser.add_argument('cmd', help='exact compilation command')
    args = parser.parse_args()
    do_clean(args.cppfile, args.cmd)

if __name__ == "__main__":
    main()