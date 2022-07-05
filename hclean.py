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
                    return (i>0, os.path.abspath(full))
        raise Exception(f'Failed to locate header <{target}> in provided include directories')

    def shorten(self, fullpath: str):
        for dirtype in self.dirs:
            for dir in dirtype:
                if fullpath.startswith(dir):
                    return fullpath[len(dir):]
        return fullpath


class IncludeRef:
    lineno = 0
    raw = ''
    is_quotes = False
    target = ''
    is_sys = False
    fullpath = ''

    def __init__(self, lineno: int, raw: str, inc_dirs: IncludeDirs):
        self.lineno = lineno
        self.raw = raw
        m = INCLUDE_RE.match(raw)
        if m:
            self.target = m.group(2)
            self.is_quotes = m.group(1) == '"'
            self.is_sys, self.fullpath = inc_dirs.locate(self.target)
    
    def __repr__(self):
        lstyle = '"' if self.is_quotes else '<'
        rstyle = '"' if self.is_quotes else '>'
        return f'L#{self.lineno} {lstyle}{self.target}{rstyle} -> {self.fullpath} Sys={self.is_sys}'


class HCFile:
    fullpath = ''
    includes = []
    modifiable = False
    removed_includes = []

    def __repr__(self):
        return 'F=' + self.fullpath + \
            ' I=' + str(self.includes) + \
            ' M=' + str(self.modifiable) + \
            ' R=' + str(self.removed_includes)



"""
- scan all headers in -I directories and all cpp's listed and create a graph of includes (with full file paths based on -I). note which headers can be modified (e.g. not std lib)
- topological sort
- for each file, starting with top level header in topological order
    - do a test compile
    - for each include in this file, add all the lines in file.h.rem for that include here. shorten the path based on -I
    - remove each include and try to compile each time
    - store successfully removed files in file.h.rem
"""

async def main():
    parser = argparse.ArgumentParser(description="Cleanup unused includes", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--log', default="./log.txt", help='Path to write log file')
    parser.add_argument('-j', '--jobs', default=multiprocessing.cpu_count(), type=int, help='Max number of parallel jobs to run')
    parser.add_argument('-I', action='append', default=[], help='Additional include directory')
    parser.add_argument('-isystem', action='append', default=[], help='Additional system include directory')
    parser.add_argument('cppfile', nargs='+', help='C++ files to modify')
    args = parser.parse_args()

    logging.basicConfig(filename=args.log, level=logging.DEBUG)
    LOGGER.info('dir=%s args=%s', os.getcwd(), str(args))

    try:
        inc_dirs = IncludeDirs(args.I, args.isystem)

        LOGGER.info('Scanning files to build include graph')
        graph = await build_file_graph(inc_dirs, args.cppfile, args.jobs)

        LOGGER.info('Determining visitation order')
        ordered_file_list = topological_sort(graph)
        LOGGER.info('Visitation order: %s', str([f for f in ordered_file_list]))

    except Exception as e:
        LOGGER.exception(e)
        print('ERROR:', e)
        exit(1)

def topological_sort(graph):
    visited = set()
    result = []
    for vertex in graph:
        topo_visit(graph, vertex, visited, result)
    return reversed(result)

def topo_visit(graph: dict, vertex: str, visited: set, result: list):
    if vertex in visited:
        return
    visited.add(vertex)
    for inc in topo_iter_incoming(graph, vertex):
        topo_visit(graph, inc, visited, result)
    if graph[vertex].modifiable:
        result.append(vertex)

def topo_iter_incoming(graph: dict, vertex: str):
    for f in graph:
        for inc in graph[f].includes:
            if inc.fullpath == vertex:
                yield f


async def build_file_graph(inc_dirs, seed_cpp, num_jobs):
    to_scan = set(seed_cpp)
    graph = {}
    while len(to_scan):
        local_results = await scan_for_includes(to_scan, inc_dirs, num_jobs)
        graph.update(local_results)
        to_scan = update_results(graph, local_results)
    return graph


def update_results(results: dict, local_results: dict):
    to_scan = set()
    for _, hcfile in local_results.items():
        for inc in hcfile.includes:
            if not inc.fullpath in results:
                if inc.is_sys:
                    hcf = HCFile()
                    hcf.fullpath = inc.fullpath
                    results[inc.fullpath] = hcf
                else:
                    to_scan.add(inc.fullpath)
    return to_scan


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
                fpath = os.path.abspath(fpath)
                result = HCFile()
                result.fullpath = fpath
                result.modifiable = True
                LOGGER.debug(f'Scanning {fpath}')
                with open(fpath, 'r') as fd:
                    for i, line in enumerate(fd):
                        if line.startswith('#include'):
                            incref = IncludeRef(i+1, line, inc_dirs)
                            LOGGER.debug(f'Include found in {fpath}: {incref}')
                            result.includes.append(incref)
                LOGGER.info(f'Found {len(result.includes)} include(s) in {fpath}')
                results[fpath] = result
            return results
        except Exception as e:
            LOGGER.exception(e)
            print('ERROR:', e)
            exit(1)
    ### end worker
    q = asyncio.Queue()
    for file in cppfiles:
        q.put_nowait(file)
    tasks = [asyncio.create_task(_worker(q)) for _ in range(jobs)]
    worker_results = await asyncio.gather(*tasks, return_exceptions=True)
    return flatten_list_of_dicts(worker_results)



if __name__ == "__main__":
    asyncio.run(main())
