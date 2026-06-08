"""Fix: register_routes was never called in app.py."""
path = __import__('pathlib').Path('/root/autodl-tmp/projects/hermes-swarm-lab') / 'backend' / 'app.py'
content = path.read_text()

old = "app.state.started_at = time.monotonic()\napp.state.version = os.getenv('RUNNING_CLUB_VERSION', '0.1.0')"
new = "app.state.started_at = time.monotonic()\napp.state.version = os.getenv('RUNNING_CLUB_VERSION', '0.1.0')\n\n# Register API routes\nfrom .routes import register_routes\nregister_routes(app)"

if old in content:
    content = content.replace(old, new)
    path.write_text(content)
    print('[OK] app.py: register_routes(app) added')
else:
    print('[WARN] pattern not found')
    idx = content.find('started_at')
    if idx > 0:
        print(repr(content[idx:idx+200]))
