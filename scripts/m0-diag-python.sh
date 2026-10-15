#!/bin/bash
echo "--- 1. urllib.parse urlparse ---"
python3 -c "import urllib.parse as u; print(u.urlparse('https://a.com/b'))"
echo "exit1=$?"
echo "--- 2. NamedTuple subclass ---"
python3 -c "
from typing import NamedTuple
class P(NamedTuple):
    x: int
print(P(1))
"
echo "exit2=$?"
echo "--- 3. urllib.parse internals ---"
python3 -c "
import urllib.parse as u
print('ParseResult mro:', [c.__name__ for c in u.ParseResult.__mro__])
print('isinstance tuple subclass:', issubclass(u.ParseResult, tuple))
"
echo "exit3=$?"
echo "--- 4. versions ---"
python3 -V
ldd --version | head -1
