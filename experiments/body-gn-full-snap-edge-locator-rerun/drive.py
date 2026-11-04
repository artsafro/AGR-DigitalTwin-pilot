"""Run a Blender script N times headless; print exit code + wall time per run."""
import subprocess, sys, time
B = r"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
script, tag, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
for i in range(1, n + 1):
    out = f"C:/x/t_c2691740/{tag}_{i}.json"
    t = time.perf_counter()
    with open(f"C:/x/t_c2691740/{tag}_{i}.log", "w", encoding="utf-8") as log:
        ec = subprocess.call([B, "--background", "--factory-startup", "--python-exit-code", "1",
                              "--python", script, "--", out], stdout=log, stderr=subprocess.STDOUT)
    print(f"{tag} run {i} ec={ec} wall={time.perf_counter() - t:.1f}s", flush=True)
