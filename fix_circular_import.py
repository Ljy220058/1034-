"""Fix circular import: move register_routes into startup event."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

path = PROJECT / 'backend' / 'app.py'
content = path.read_text()

# Remove the module-level register_routes call
old = """app.state.started_at = time.monotonic()
app.state.version = os.getenv('RUNNING_CLUB_VERSION', '0.1.0')

# Register API routes
from .routes import register_routes
register_routes(app)"""

new = """app.state.started_at = time.monotonic()
app.state.version = os.getenv('RUNNING_CLUB_VERSION', '0.1.0')"""

if old in content:
    content = content.replace(old, new)
    print('[OK] Removed module-level register_routes')

# Now add register_routes to the startup event
old_startup = """@app.on_event('startup')
def startup_event() -> None:
    initialize_database()"""

new_startup = """@app.on_event('startup')
def startup_event() -> None:
    initialize_database()
    # Register API routes (deferred to avoid circular imports)
    from .routes import register_routes
    register_routes(app)"""

if old_startup in content:
    content = content.replace(old_startup, new_startup)
    path.write_text(content)
    print('[OK] register_routes moved to startup event')
else:
    print('[WARN] startup event pattern not found')
    idx = content.find('startup_event')
    if idx > 0:
        print(content[idx:idx+200])
