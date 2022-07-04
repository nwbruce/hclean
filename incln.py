#!/usr/bin/python3

import argparse
import multiprocessing
import logging
import asyncio
import re
import os

LOGGER = logging.getLogger(__file__)

INCLUDE_RE = re.compile(r'#\s*include\s*(["\<])([^"\>]*)')
        


class IncludeDirs:
    dirs = []

    def __init__(self, user, sys):
        self.dirs = [user, sys]

    def locate(self, target: str):
        for i, dirtype in enumerate(self.dirs):
            for dir in dirtype:
                full = os.path.join(dir, target)
                if os.path.exists(full):
                    return (i>0, full)
        raise Exception(f'Failed to locate header [{target}] in provided include directories')

    def shorten(self, fullpath: str):
        for dirtype in self.dirs:
            for dir in dirtype:
                if fullpath.startswith(dir):
                    return fullpath[len(dir):]
        return fullpath


class IncludeRef:
    lineno = 0
    raw = ''
    is_local = False
    target = ''
    is_sys = False
    fullpath = ''

    def __init__(self, lineno: int, raw: str, inc_dirs: IncludeDirs):
        self.lineno = lineno
        self.raw = raw
        m = INCLUDE_RE.match(raw)
        if m:
            self.target = m.group(2)
            self.is_local = m.group(1) == '"'
            self.is_sys, self.fullpath = inc_dirs.locate(self.target)
    
    def __repr__(self):
        lstyle = '"' if self.is_local else '<'
        rstyle = '"' if self.is_local else '>'
        return f'L#{self.lineno}{lstyle}{self.target}{rstyle}->{self.fullpath}'


class HCFile:
    full_path = ''
    includes = []
    modifiable = False
    removed_includes = []

    def __repr__(self):
        return 'F=' + self.full_path + \
            ' I=' + str(self.includes) + \
            ' M=' + str(self.modifiable) + \
            ' R=' + str(self.removed_includes)



"""
- scan all headers in -I directories and all cpp's listed and create a graph of includes (with full file paths based on -I). note which headers can be modified (e.g. not std lib)
- topological sort
- for each file, starting with top level header in topological order
    - for each include in this file, add all the lines in file.h.rem for that include here. shorten the path based on -I
    - remove each include and try to compile each time
    - store successfully removed files in file.h.rem
"""

async def main():
    parser = argparse.ArgumentParser(description="Cleanup unused includes", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-j', '--jobs', default=multiprocessing.cpu_count(), type=int, help='Max number of parallel jobs to run')
    parser.add_argument('-I', action='append', help='Additional include directory')
    parser.add_argument('-isystem', action='append', help='Additional system include directory')
    parser.add_argument('cppfile', nargs='+', help='C++ files to modify')
    args = parser.parse_args()

    logging.basicConfig(filename='./log.txt', level=logging.DEBUG)
    LOGGER.info('Invoked with arguments: %s', str(args))

    inc_dirs = IncludeDirs(args.I, args.isystem)

    to_scan = set([os.path.abspath(f) for f in args.cppfile])
    scanned = set()
    while len(to_scan):
        results = await scan_for_includes(to_scan, inc_dirs, args.jobs)
        print(results)


        scanned.update(to_scan)
        to_scan = set()


def flatten_list_of_dicts(lod: list):
    results = {}
    for partial in lod:
        if len(partial):
            results.update(partial)
    return results


async def scan_for_includes(cppfiles: list, inc_dirs: IncludeDirs, jobs: int):
    async def _worker(q: asyncio.Queue):
        try:
            results = {}
            while not q.empty():
                fpath = await q.get()
                result = HCFile()
                result.full_path = fpath
                result.modifiable = True
                with open(fpath, 'r') as fd:
                    for i, line in enumerate(fd):
                        if line.startswith('#include'):
                            incref = IncludeRef(i+1, line, inc_dirs)
                            LOGGER.debug(f'Include found in {fpath}: {incref}')
                            result.includes.append(incref)
                LOGGER.info(f'Found {len(result.includes)} includes in {fpath}')
                results[fpath] = result
            return results
        except Exception as e:
            LOGGER.exception(e)
            raise
    ### end worker
    q = asyncio.Queue()
    for file in cppfiles:
        q.put_nowait(file)
    tasks = [asyncio.create_task(_worker(q)) for _ in range(jobs)]
    worker_results = await asyncio.gather(*tasks, return_exceptions=True)
    return flatten_list_of_dicts(worker_results)



if __name__ == "__main__":
    asyncio.run(main())
