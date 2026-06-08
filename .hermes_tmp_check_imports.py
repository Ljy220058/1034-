import importlib.util
for name in ['fastapi','uvicorn']:
    print(name, bool(importlib.util.find_spec(name)))
