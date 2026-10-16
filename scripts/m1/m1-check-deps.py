# -*- coding: utf-8 -*-
mods = ["yaml", "opencc", "pypinyin", "datasketch", "openai", "jieba"]
for m in mods:
    try:
        __import__(m)
        print(f"{m}: ok")
    except ImportError:
        print(f"{m}: MISSING")
