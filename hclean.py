#!/usr/bin/python3

import argparse
import multiprocessing
import logging
import asyncio
import re
import os
import shutil

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

    def __init__(self, lineno: int, raw: str, inc_dirs: IncludeDirs):
        self.lineno = lineno
        self.raw = raw
        m = INCLUDE_RE.match(raw)
        if m:
            self.target = m.group(2)
            self.is_quotes = m.group(1) == '"'
            self.is_sys, self.fullpath = inc_dirs.locate(self.target)
        else:
            raise Exception('Failed to match regex for include on |%s|' % str(raw))
    
    def __repr__(self):
        lstyle = '"' if self.is_quotes else '<'
        rstyle = '"' if self.is_quotes else '>'
        return f'L#{self.lineno} {lstyle}{self.target}{rstyle} -> {self.fullpath} Sys={self.is_sys}'


class HCFile:
    def __init__(self):
        self.fullpath = ''
        self.includes = []
        self.modifiable = False
        self.removed_includes = []

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
    parser.add_argument('-c', dest='command', required=True, help='Compile command to run with {0} interpolated with target file')
    parser.add_argument('-l', dest='logpath', help='Path to write log file')
    parser.add_argument('-j', dest='jobs', default=multiprocessing.cpu_count(), type=int, help='Max number of parallel jobs to run')
    parser.add_argument('-I', dest='incdir', action='append', default=[], help='Additional include directories')
    parser.add_argument('-S', dest='sysdir', action='append', default=[], help='Additional system include directories')
    parser.add_argument('cppfile', nargs='+', help='C++ files to modify')
    args = parser.parse_args()

    if args.logpath:
        logging.basicConfig(filename=args.logpath, level=logging.DEBUG)

    LOGGER.info('pwd=%s args=%s', os.getcwd(), str(args))

    try:
        inc_dirs = IncludeDirs(args.incdir, args.sysdir)

        LOGGER.info('Scanning files to build include graph')
        graph = await build_file_graph(inc_dirs, args.cppfile, args.jobs)

        LOGGER.info('Determining visitation order')
        ordered_file_list = topological_sort(graph)

        LOGGER.info('Fixing files in order: %s', ', '.join(ordered_file_list))
        await fix_includes(graph, ordered_file_list, args.command, args.jobs)

    except Exception as e:
        LOGGER.exception(e)
        print('ERROR:', e)
        exit(1)

#### fix includes ####

async def fix_includes(graph: dict, ordered_file_list: list, command: str, jobs: int):
    while True:
        batch = pop_ready(graph, ordered_file_list)
        if batch:
            LOGGER.info('Fixing includes in batch: %s', str(batch))
            await fix_includes_batch(graph, batch, command, jobs)
        else:
            break

async def fix_includes_batch(graph: dict, batch: set, command: str, jobs: int):
    q = asyncio.Queue()
    for file in batch:
        q.put_nowait(file)
    tasks = [asyncio.create_task(fix_includes_batch_worker(graph, q, command)) for _ in range(jobs)]
    return await asyncio.gather(*tasks)

async def fix_includes_batch_worker(graph: dict, q: asyncio.Queue, command: str):
    while not q.empty():
        file = await q.get()
        hcfile = graph[file]
        # todo
        """
            - do a test compile
            - for each include in this file, add all the lines in file.h.rem for that include here. shorten the path based on -I
            - remove each include and try to compile each time
            - store successfully removed files in file.h.rem
        """
        orig = hcfile.fullpath
        LOGGER.debug(f'Starting test compile of {orig}')
        errmsg = await try_compile(command, orig)
        if errmsg:
            raise Exception(f'Failed to do a simple compile of {orig}:\n{errmsg}')

        # add removed parent files
        # inherited = set()
        # for hdr in hcfile.includes:
        #     hdr_file = graph[hdr.fullpath]
        #     for inc in hdr_file.removed_includes:
        #         inherited.add(inc.raw)
        # print(orig, inherited)
        # def line_modifier(lineno, line):
        #     if (len(hcfile.includes) == 0 and lineno == 0) or (len(hcfile.includes) > 0 and lineno == hcfile.includes[0].lineno):
        #         return ''.join(inherited) + line
        #     return line
        # bak = orig + '.bak'
        # os.rename(orig, bak)
        # await edit_file(bak, orig, line_modifier)
        # os.remove(bak)

        # compile without each header
        for hdr in reversed(hcfile.includes):
            def line_modifier(lineno, line):
                if lineno == hdr.lineno:
                    return '// ' + line
                return line
            bak = orig + '.bak'
            os.rename(orig, bak)
            await edit_file(bak, orig, line_modifier)
            errmsg = await try_compile(command, orig)
            if errmsg:
                # undo
                os.remove(orig)
                os.rename(bak, orig)
            else:
                # commit
                os.remove(bak)
                hcfile.removed_includes.append(hdr)


async def try_compile(command: str, fpath: str):
    cmd = command.format(fpath)
    LOGGER.debug(f'Running [{cmd}]')
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return stdout.decode()
    else:
        return None

async def edit_file(fromfile: str, tofile: str, line_modifier):
    with open(fromfile, 'r') as fdin:
        with open(tofile, 'w') as fdout:
            for i, line in enumerate(fdin):
                line = line_modifier(i+1, line)
                fdout.write(line)
    return fromfile

def pop_ready(graph: dict, ordered_file_list: list):
    result = set()
    while len(ordered_file_list):
        candidate = ordered_file_list[0]
        hcfile = graph[candidate]
        for inc in hcfile.includes:
            # if this one depends on something in the result set, exit
            if inc.fullpath in result:
                return result
        result.add(candidate)
        ordered_file_list.pop(0)
    return result


#### build file graph ####

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
    q = asyncio.Queue()
    for file in cppfiles:
        q.put_nowait(file)
    tasks = [asyncio.create_task(scan_for_includes_worker(q, inc_dirs)) for _ in range(jobs)]
    worker_results = await asyncio.gather(*tasks)
    return flatten_list_of_dicts(worker_results)


async def scan_for_includes_worker(q: asyncio.Queue, inc_dirs: IncludeDirs):
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

#### topological sort ####

def topological_sort(graph):
    visited = set()
    result = []
    for vertex in graph:
        topo_visit(graph, vertex, visited, result)
    return [x for x in reversed(result)]

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





#### main ####

if __name__ == "__main__":
    asyncio.run(main())
