import re
import sys
from pathlib import Path


# -----------------------------
# FIND FILES
# -----------------------------
def find_files(th_file):
    th_file = Path(th_file)
    root = th_file.parent

    cavename = th_file.stem

    xvi_plan = root / f"{cavename}-map.xvi"
    xvi_coupe = root / f"{cavename}-coupe.xvi"

    th2_plan = root / f"{cavename}-plan.th2"
    th2_coupe = root / f"{cavename}-coupe.th2"

    maps_th = root / ".." / f"{cavename}-maps.th"

    return cavename, th_file, xvi_plan, xvi_coupe, th2_plan, th2_coupe, maps_th


# -----------------------------
# PARSE SURVEY NAME
# -----------------------------
def parse_survey_name(th_file):
    with open(th_file, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*survey\s+([A-Za-z0-9_-]+)", line)
            if m:
                return m.group(1)

    raise ValueError("No survey found in .th")


# -----------------------------
# PARSE XVI STATIONS (FIXED)
# -----------------------------
def parse_xvi(xvi_path):
    stations = []
    seen = set()

    with open(xvi_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. isoler le bloc set XVIstations { ... }
    m = re.search(r"set\s+XVIstations\s+\{(.*?)\}\s*set", content, re.S)
    if not m:
        # fallback si dernier bloc du fichier
        m = re.search(r"set\s+XVIstations\s+\{(.*)\}", content, re.S)

    if not m:
        raise ValueError("Impossible de trouver XVIstations")

    block = m.group(1)

    # 2. extraire toutes les stations {x y id}
    pattern = re.compile(r"\{\s*([-0-9.]+)\s+([-0-9.]+)\s+(\d+)\s*\}")

    for match in pattern.finditer(block):
        x = float(match.group(1))
        y = float(match.group(2))
        name = match.group(3)

        key = (x, y, name)
        if key in seen:
            continue

        seen.add(key)
        stations.append({
            "x": x,
            "y": y,
            "name": name
        })

    if not stations:
        raise ValueError("Aucune station trouvée dans XVIstations")

    return stations


# -----------------------------
# CHUNK
# -----------------------------
def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# -----------------------------
# SCRAP GENERATOR (NO DUPLICATES INSIDE SCRAP)
# -----------------------------
def make_scrap(name, projection, survey, stations):
    lines = []
    seen = set()

    lines.append(
        f"scrap {name} -projection {projection} --station-names \"\" \"@{survey}\""
    )

    for s in stations:
        key = s["name"]
        if key in seen:
            continue
        seen.add(key)

        lines.append(f"  point {s['x']} {s['y']} station -name {s['name']}")

    lines.append("endscrap\n")
    return "\n".join(lines)


# -----------------------------
# APPEND TH2
# -----------------------------
def append(file, content):
    with open(file, "a", encoding="utf-8") as f:
        f.write("\n" + content + "\n")


# -----------------------------
# UPDATE MAPS
# -----------------------------
def update_maps(maps_file, plan_scraps, coupe_scraps):
    with open(maps_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    inserted_plan = False
    inserted_coupe = False

    for line in lines:
        out.append(line)

        if "map MP" in line and not inserted_plan:
            for s in plan_scraps:
                out.append(f"  {s}\n")
            inserted_plan = True

        if "map MC" in line and not inserted_coupe:
            for s in coupe_scraps:
                out.append(f"  {s}\n")
            inserted_coupe = True

    with open(maps_file, "w", encoding="utf-8") as f:
        f.writelines(out)


# -----------------------------
# MAIN
# -----------------------------
def main():
    if len(sys.argv) != 2:
        print("Usage: python gen_scraps.py path/to/CAVENAME.th")
        sys.exit(1)

    th_file = sys.argv[1]

    cavename, th_file, xvi_plan, xvi_coupe, th2_plan, th2_coupe, maps_th = find_files(th_file)
    print(f"[INFO] Found files for {cavename}")

    survey = parse_survey_name(th_file)
    print(f"[INFO] Parsed survey name: {survey}")
    print(f"[INFO] Parsing XVI files...")
    stations_plan = parse_xvi(xvi_plan)
    stations_coupe = parse_xvi(xvi_coupe)
    print(f"[INFO] Found {len(stations_plan)} stations in plan and {len(stations_coupe)} stations in coupe")
    CHUNK_SIZE = 10

    plan_scraps = []
    coupe_scraps = []

    plan_out = []
    coupe_out = []

    for i, group in enumerate(chunk(stations_plan, CHUNK_SIZE)):
        name = f"SP-{cavename}-{i+1}"
        plan_scraps.append(name)
        plan_out.append(make_scrap(name, "plan", survey, group))
    print(f"[INFO] Generated {len(plan_scraps)} plan scraps")

    for i, group in enumerate(chunk(stations_coupe, CHUNK_SIZE)):
        name = f"SC-{cavename}-{i+1}"
        coupe_scraps.append(name)
        coupe_out.append(make_scrap(name, "extended", survey, group))
    print(f"[INFO] Generated {len(coupe_scraps)} coupe scraps")
    append(th2_plan, "\n".join(plan_out))
    append(th2_coupe, "\n".join(coupe_out))

    update_maps(maps_th, plan_scraps, coupe_scraps)

    print(f"[OK] Generated scraps for {cavename}")


if __name__ == "__main__":
    main()