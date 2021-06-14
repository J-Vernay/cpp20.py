# cpp20.py

`cpp20.py` is a Python script to compile C++20 code using modules.
It browses the source files to determine their dependencies.
Then, it compiles then in order using the correct flags.

## Dependencies:
- g++ >= 11 (for C++20 module implementations)
- Python >= 3.9 (for `graphlib.TopologicalSorter`)

## Usage:
The most basic usage is:
```
python3 cpp20.py
```
This will compile all source files found in the current directory (recursively) into an executable `myproj`.

You can specify what is the result of the compilation:
```
python3 cpp20.py --lib=abc --so=abc --exe=abc
```
- `--lib={}` will create the static library `lib{}.a`
- `--so={}` will create the shared library `lib{}.so`
- `--exe={}` will create the executable `{}`

You can specify which directories and patterns to look for:
```
python3 cpp20.py dir1 dir2 --patterns="*.hpp,*.cpp,*.h" --patterns+="*.cppm" --patterns-="*.h"
```
- `--patterns=` specifies the patterns of filenames to inspect. The default is
  `*.h,*.c,*.hxx,*.cxx,*.ixx,*.mxx,*.hpp,*.cpp,*.cppm`
- `--patterns+=` specifies additional patterns (useful if you want to keep default patterns)
- `--patterns-=` specifies patterns to exclude

You can display informations about browsed files:
```
python3 cpp20.py --show=list,deps,order,cmd
```
Any comma-separated list of either `list`, `deps`, `order` and `cmd` is allowed.
Each option will output a block of lines to the standard output.
By default, the project will still be built. You can pass `--nobuild`
to only output the informations without building the project.
By default, paths are displayed relatively to the current directory.
This works only if all involved files are inside the current directory (potentially recursively).
If this is not the case or if you want to display absolute paths, you can pass `--absolutepaths`.

`list` will output a CSV line per file, with their kind (one of
*primary-module-interface*, *module-partition-interface*, *module-partition*,
*module-unit*, *global-unit*, *header-unit* or *header*) and their module name (or empty).
```
...$python3 cpp20.py --show=list
"example/A.cppm", primary-module-interface, A
"example/A0.cpp", module-partition, A:p0
"example/A1.cppm", module-partition-interface, A:p1
"example/B.ixx", primary-module-interface, B
"example/B0.mxx", module-partition-interface, B:p0
"example/Bimpl.cxx", module-unit, B
"example/C.cpp", primary-module-interface, C
"example/H.hpp", header,
"example/H0.h", header-unit,
"example/H1.hxx", header,
"example/main.cpp", global-unit,
```
`deps` will show each file followed by their dependencies.
```
...$python3 cpp20.py --show=deps
"example/A.cppm", "example/A1.cppm"
"example/A0.cpp",
"example/A1.cppm",
"example/B.ixx",
"example/B0.mxx", "example/H0.h"
"example/Bimpl.cxx", "example/H.hpp", "example/A.cppm"
"example/C.cpp", "example/H.hpp", "example/A.cppm", "example/B.ixx"
"example/H.hpp", "example/H1.hxx"
"example/H0.h",
"example/H1.hxx", "example/H0.h"
"example/main.cpp", "example/C.cpp"
```
`order` will display lines of paths, such that each file is on a line after its dependencies.
```
...$python3 cpp20.py --show=order
"example/B.ixx", "example/H0.h", "example/A1.cppm", "example/A0.cpp"
"example/H1.hxx", "example/B0.mxx", "example/A.cppm"
"example/H.hpp"
"example/C.cpp", "example/Bimpl.cxx"
"example/main.cpp"
```
`cmd` will display commands to be executed. Each group of command can be executed in parallel.
```
...$python3 cpp20.py --show=cmd
mkdir -p obj/example

g++ -x c++ -std=c++20 -fmodule-header example/H0.h -c -o obj/example/H0.h.o
g++ -x c++ -std=c++20 -fmodules-ts example/A0.cpp -c -o obj/example/A0.cpp.o
g++ -x c++ -std=c++20 -fmodules-ts example/A1.cppm -c -o obj/example/A1.cppm.o
g++ -x c++ -std=c++20 -fmodules-ts example/B.ixx -c -o obj/example/B.ixx.o

g++ -x c++ -std=c++20 -fmodules-ts example/A.cppm -c -o obj/example/A.cppm.o
g++ -x c++ -std=c++20 -fmodules-ts example/B0.mxx -c -o obj/example/B0.mxx.o


g++ -x c++ -std=c++20 -fmodules-ts example/Bimpl.cxx -c -o obj/example/Bimpl.cxx.o
g++ -x c++ -std=c++20 -fmodules-ts example/C.cpp -c -o obj/example/C.cpp.o

g++ -x c++ -std=c++20 -fmodules-ts example/main.cpp -c -o obj/example/main.cpp.o

g++ obj/example/H0.h.o obj/example/B.ixx.o obj/example/A1.cppm.o obj/example/A0.cpp.o obj/example/B0.mxx.o obj/example/A.cppm.o obj/example/Bimpl.cxx.o obj/example/C.cpp.o obj/example/main.cpp.o -o myprog

rm -r obj gcm.cache
```

## Limitations
- Limitations inherited from `g++` implementation.
- The parser will recognize declarations inside multiline comments.
- Comments inside declarations (`module /*test*/ hello;`) are not supported.
