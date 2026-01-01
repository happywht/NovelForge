import os

search_str = "No generations found in stream"
root_dir = r"C:\Users\Hitao\AppData\Local\Programs\Python\Python312\Lib\site-packages"

matches = []
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    if search_str in f.read():
                        matches.append(path)
            except Exception:
                pass

if matches:
    print("Found matches:")
    for m in matches:
        print(m)
else:
    print("No matches found.")
