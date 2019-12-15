@echo off
setlocal

bison -d -ra -Ssrc/lalr1.cc -o%1/mhmakeparser.cpp src/mhmakeParser.y
COPY /Y b4_spec_defines_file %1\mhmakeparser.hpp
python2 addstdafxh.py %1/mhmakeparser.cpp

endlocal
