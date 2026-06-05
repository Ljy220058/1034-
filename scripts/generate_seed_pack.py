from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.seed_data import build_seed_pack, export_seed_pack


OUTPUT_PATH = Path(__file__).resolve().parents[1] / 'seed-data-pack.json'


def main() -> None:
    pack = build_seed_pack()
    export_seed_pack(OUTPUT_PATH)
    print(f'Wrote deterministic fixture pack to {OUTPUT_PATH}')
    print(
        f"members={len(pack.members)} activities={len(pack.activities)} registrations={len(pack.registrations)} "
        f"attendances={len(pack.attendances)} announcements={len(pack.announcements)}"
    )


if __name__ == '__main__':
    main()
