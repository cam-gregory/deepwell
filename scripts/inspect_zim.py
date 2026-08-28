# save as inspect_zim.py, run: python inspect_zim.py
from libzim.reader import Archive
from collections import Counter

archive = Archive("data/sources/zim/zimgit-medicine_en_2024-08.zim")
count = getattr(archive, "all_entry_count", None) or archive.entry_count
get = getattr(archive, "get_entry_by_id", None) or archive._get_entry_by_id
print("total entries:", count)

mimes, samples = Counter(), {}
for i in range(count):
    e = get(i)
    if e.is_redirect:
        continue
    try:
        m = e.get_item().mimetype or "?"
    except Exception:
        m = "ERR"
    mimes[m] += 1
    samples.setdefault(m, e.path)

for m, c in mimes.most_common():
    print(f"{c:6d}  {m}   e.g. {samples[m]}")
