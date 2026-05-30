import glob
import json
import os

seen = set()
content_examples = []
for path in glob.glob(os.path.join(r"F:\C++_Projects\Super_Mario_PYGAMECE\assets\levels", "*.json")):
    if path.endswith(".md"):
        continue
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        print("skip", path, exc)
        continue
    for tile in d.get("foreground", []):
        ttype = tile.get("type")
        if ttype in ("Question", "QuestionBlock"):
            seen.add(tuple(sorted(tile.keys())))
            for key in tile:
                if key not in ("x", "y", "type", "sprite") and len(content_examples) < 12:
                    content_examples.append((os.path.basename(path), tile))
                    break
print("Question-block key combos:")
for keys in sorted(seen):
    print(" ", keys)
print("Examples with extra fields:")
for example in content_examples:
    print(" ", example)
