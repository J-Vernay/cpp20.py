#!/usr/bin/env python3

#========= COMMAND LINE INTERFACE =========

import argparse
from pathlib import Path

DESCRIPTION = """Browse C++20 sources and build it.

Examples:
  ./cpp20.py --exe=myprog
       Use default compiler, browse current directory recursively and output 'myprog'
  ./cpp20.py src --gcc=g++-11 --so=libabc.so --exe=abc
       Use g++-11, browse recursively 'src', builds a shared library 'libabc.so' and an executable 'abc'
  ./build.py --flags="-O2 -Wall" --patterns+=*.C --exe=prog
       Use default compiler, adds -O2 and -Wall flags to all commands, browse also files ending with .C
  ./build.py --lib=libabc.a --patterns-=tests/*,examples/*
       Build a static library 'libabc.a', without inspecting tests/* and examples/*
  ./build.py --show=list,deps
       Do not compile. Prints the list of files (and their kind), and their dependencies.
"""

parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('src', help='Source files and directories to inspect recursively.', nargs='*')
parser.add_argument('--cache', action='store_true', help='Will not generate commands for uptodate objects. Implies --keep .')
parser.add_argument('--gcc', help='Specifies gcc executable for compilation.', default='g++')
parser.add_argument('--keep', action='store_true', help='Keep object and precompiled modules.')
parser.add_argument('--show', help='Prints various info.', default='')
parser.add_argument('--absolutepaths', action='store_true', help='Whether paths should be displayed as absolute.')
parser.add_argument('--nobuild', action='store_true', help='Do not run commands. Can be combined with --show.')
parser.add_argument('--obj', help='Directory for intermediate objects.', default='obj')
parser.add_argument('--lib', help='Creates a static library.')
parser.add_argument('--so', help='Creates a shared library.')
parser.add_argument('--exe', help='Creates an executable.')
parser.add_argument('--flags', help='Provides additional flags to all commands.', default='')
parser.add_argument('--linkflags', help='Provides additional flags to dynamic link command.', default='')
parser.add_argument('--patterns', help='Patterns used for recognizing files to be inspected.',
                    default='*.h,*.c,*.hxx,*.cxx,*.ixx,*.mxx,*.hpp,*.cpp,*.cppm')
parser.add_argument('--patterns+', dest='patternsPlus', help='Additional patterns (to not replace default ones).', default='')
parser.add_argument('--patterns-', dest='patternsMinus', help='Patterns to exclude files from inspection.', default='')
parser.add_argument('--headers', help='Patterns to determine which files are not for compilation. (headers)',
                    default='*.h,*.hpp,*.hxx')
parser.add_argument('--headers+', dest='headersPlus', help='Additional patterns for headers.', default='')

args = parser.parse_args()

if not args.src:
    args.src = ['.']

SOURCE_PATTERNS = set(args.patterns.split(',') + args.patternsPlus.split(',')) - set([''])
SOURCE_PATTERNS_MINUS = set(args.patternsMinus.split(',')) - set([''])

HEADER_PATTERNS = set(args.headers.split(',') + args.headersPlus.split(',')) - set([''])

if not args.lib and not args.so and not args.exe:
    args.exe = "myprog"

if args.absolutepaths:
    args.obj = Path(args.obj).resolve()
else:
    args.obj = Path(args.obj)

if args.cache:
    args.keep = True

cmd_dir = 'mkdir -p {}'
cmd_rm = 'rm -r {}'
cmd_hu    = args.gcc + ' -std=c++20 -fmodules-ts -x c++-header {src} ' + args.flags
cmd_syshu = args.gcc + ' -std=c++20 -fmodules-ts -x c++-system-header {src} ' + args.flags
cmd_obj   = args.gcc + ' -std=c++20 -fmodules-ts -x c++ {src} -c -o {obj} ' + args.flags
cmd_lib = 'ar rvs lib{out}.a {objs}'
cmd_so  = args.gcc + ' {objs} -shared -o lib{out}.so ' + args.flags + ' ' + args.linkflags
cmd_exe = args.gcc + ' {objs} -o {out} ' + args.flags + ' ' + args.linkflags
if args.so: # shared objects require Position-Independent Code
    cmd_obj += ' -fPIC'

#========= ACTUAL SCRIPT =========


### SEARCHING SOURCE FILES ###

def matchesSourcePatterns(path):
    if all(not path.match(pattern) for pattern in SOURCE_PATTERNS):
        return False
    return all(not path.match(pattern) for pattern in SOURCE_PATTERNS_MINUS)


SOURCE_PATHS = set()
current_path = Path().resolve()

for path in args.src:
    path = Path(path).resolve()
    if not args.absolutepaths:
        path = path.relative_to(current_path)
    if path.is_dir():
        SOURCE_PATHS.update(p for p in path.rglob('*') if matchesSourcePatterns(p))
    else:
        if matchesSourcePatterns(path):
            SOURCE_PATHS.add(path)

### SEARCHING DEPENDENCIES ###

import re
from collections import defaultdict
from dataclasses import dataclass

REGEX_RELATIVE_PATH = re.compile(r'^\"([\w/\.\-\\]+)\"') # group(1) is path
REGEX_SYSTEM_PATH = re.compile(r'^\<([\w/\.\-\\]+)\>') # group(1) is path
REGEX_MODULE_NAME = re.compile(r'^([\w\.\:]+)') # group(1) is module name

def matchRegexes(text, regexes): # -> (which, result)
    for regex in regexes:
        match = regex.match(text)
        if match is not None:
            return regex, match.group(1)
    return None, ''

@dataclass
class SourceInfo:
    kind: str = None
    module_name: str = ''

SOURCE_INFOS = defaultdict(SourceInfo)
DEPENDENCIES = {} # path -> [path|modulename...]

MODULE_PARTITIONS = defaultdict(list) # module_name -> # module_partitions
MODULE_NAMES_TO_PATH = {}

if not args.absolutepaths:
    to_path = lambda p: p.resolve().relative_to(current_path)
else:
    to_path = lambda p: p.resolve()

for path in SOURCE_PATHS:
    kind, module_name, dependencies = 'global-unit', '', [] # global-unit by default

    if any(path.match(pattern) for pattern in HEADER_PATTERNS):
        kind = 'header'

    with open(path) as file:
        content = file.read()


    for line in content.splitlines():
        words = line.split(maxsplit=3)
        if not words:
            continue

        if words[0] == '#include':
            # include declaration
            which, match = matchRegexes(words[1], [REGEX_SYSTEM_PATH, REGEX_RELATIVE_PATH])
            if which is REGEX_RELATIVE_PATH:
                include_path = to_path(path.parent / match)
                dependencies.append(include_path)
            elif which is REGEX_SYSTEM_PATH:
                if SOURCE_INFOS['_sys_'+match].kind is None:
                    SOURCE_INFOS['_sys_'+match].kind = 'header'
                dependencies.append('_sys_'+match)
            # else invalid #include

        elif words[0] == 'import' or (words[0] == 'export' and words[1] == 'import'):
            imported_word = words[1] if words[0] == 'import' else words[2];
            which, match = matchRegexes(imported_word, [REGEX_SYSTEM_PATH, REGEX_RELATIVE_PATH, REGEX_MODULE_NAME])

            if which is REGEX_RELATIVE_PATH:
                # header-unit found
                import_path = to_path(path.parent / match)
                SOURCE_INFOS[import_path].kind = 'header-unit'
                dependencies.append(import_path)
            elif which is REGEX_SYSTEM_PATH:
                # system-header-unit found
                SOURCE_INFOS['_sys_'+match].kind = 'system-header-unit'
                dependencies.append('_sys_'+match)
            elif which is REGEX_MODULE_NAME:
                # import module found
                if match.startswith(':'):
                    match = module_name.split(':',maxsplit=1)[0] + match
                dependencies.append(match)

        elif module_name is not None:
            match = None
            export = False
            if words[0] == 'module':
                # module-partition or module-unit
                match = REGEX_MODULE_NAME.match(words[1])
            elif words[0] == 'export' and words[1] == 'module':
                # primary-module-interface or module-partition-interface
                match = REGEX_MODULE_NAME.match(words[2])
                export = True

            if match is not None:
                module_name = match.group(1)
                main_module, *partition = module_name.split(':', maxsplit=1)
                if partition:
                    kind = 'module-partition-interface' if export else 'module-partition'
                    MODULE_PARTITIONS[main_module].append(module_name)
                    MODULE_NAMES_TO_PATH[module_name] = path
                else:
                    kind = 'primary-module-interface' if export else 'module-unit'
                    if export:
                        MODULE_NAMES_TO_PATH[module_name] = path

    if SOURCE_INFOS[path].kind is None:
        # may be not None if already set to 'header-unit'
        SOURCE_INFOS[path].kind = kind

    SOURCE_INFOS[path].module_name = module_name
    DEPENDENCIES[path] = dependencies


### RESOLVING MODULE NAME DEPENDENCIES ###

for path in DEPENDENCIES:
    DEPENDENCIES[path] = [
        dep if isinstance(dep, Path) else MODULE_NAMES_TO_PATH.get(dep, dep)
        for dep in DEPENDENCIES[path]
    ]

### SORTING DEPENDENCIES ###
from graphlib import TopologicalSorter

ORDER = [] # list of steps, each step being a list of paths dependent on the previous steps only

topological_sorter = TopologicalSorter(DEPENDENCIES)
topological_sorter.prepare()
while topological_sorter.is_active():
    step = topological_sorter.get_ready()
    ORDER.append(step)
    for path in step:
        topological_sorter.done(path)

### BUILDING COMMANDS ###
COMMANDS = []

OUTDIRS = set() # must be created before command runned

objs = []

to_be_build = set()

if args.cache:
    def uptodate(path, deps):
        if not path.is_file():
            return False
        mytime = path.stat().st_mtime
        return all((not d in to_be_build and d.stat().st_mtime < mytime) for d in deps if isinstance(d, Path))
else:
    def uptodate(path, deps):
        return False

for step in ORDER:
    stepcmds = []
    for path in step:
        kind = SOURCE_INFOS[path].kind
        if kind == 'header':
            continue # not compiling header and header-units
        elif kind == 'header-unit':
            # potential gcm cache
            header_unit_path = (Path('gcm.cache/') / ('./'+str(path)+'.gcm')).resolve()
            if uptodate(header_unit_path, DEPENDENCIES.get(path, [])+[path]):
                continue
            to_be_build.add(path)
            stepcmds.append(cmd_hu.format(src=path))
        elif kind == 'system-header-unit':
            if args.cache and len(list(Path('gcm.cache').glob(f'**/{path.removeprefix("_sys_")}.*'))) > 0:
                continue
            to_be_build.add(path)
            stepcmds.append(cmd_syshu.format(src=path.removeprefix('_sys_')))
        else:
            obj = str((args.obj / ('./'+str(path))).resolve()) + '.o'
            objs.append(obj)
            obj = Path(obj)
            OUTDIRS.add(obj.parent)
            if uptodate(obj, DEPENDENCIES.get(path, [])+[path]):
                continue
            to_be_build.add(path)
            stepcmds.append(cmd_obj.format(src=path,obj=obj))
    COMMANDS.append(sorted(stepcmds))
# append final link command
if args.lib:
    COMMANDS.append([cmd_lib.format(objs=' '.join(objs), out=args.lib)])
if args.so:
    COMMANDS.append([cmd_so.format(objs=' '.join(objs), out=args.so)])
if args.exe:
    COMMANDS.append([cmd_exe.format(objs=' '.join(objs), out=args.exe)])
# prepend mkdir commands
COMMANDS = [[cmd_dir.format(dir) for dir in OUTDIRS]] + COMMANDS


### SHOWING DESIRED INFOS ###

for showoption in args.show.split(','):
    if showoption == '':
        continue
    elif showoption == 'list':
        for path, sourceinfo in sorted(SOURCE_INFOS.items(), key=lambda p:str(p[0])):
            print(f'"{path}", {sourceinfo.kind}, {sourceinfo.module_name}')
    elif showoption == 'deps':
        for path, deps in sorted(DEPENDENCIES.items(), key=lambda p:str(p[0])):
            deps = [ f'"{dep}"' for dep in deps]
            print(f'"{path}",', ', '.join(deps))
    elif showoption == 'order':
        for step in ORDER:
            print(', '.join(f'"{path}"' for path in step))
    elif showoption == 'cmd':
        for stepcmds in COMMANDS:
            for cmd in stepcmds:
                print(cmd)
            print()
    print()


if args.nobuild:
    exit()

### RUNNING COMMANDS ###
import subprocess
try:
    if not args.cache:
        # not reusing objects and header units
        subprocess.run(cmd_rm.format(f'{args.obj} gcm.cache'), shell=True, capture_output=True)

    for stepcmds in COMMANDS:
        for cmd in stepcmds:
            result = subprocess.run(cmd, shell=True,capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(f'Command returned status {result.returncode}: {cmd}\n{result.stderr.decode()}')
finally:
    if not args.keep:
        subprocess.run(cmd_rm.format(f'{args.obj} gcm.cache'), shell=True)
