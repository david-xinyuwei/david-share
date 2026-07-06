import pandas as pd

print("DEMO=known_dependency")
print("pandas_version=" + pd.__version__)
print(pd.DataFrame({"category": ["pc", "tablet"], "revenue": [100, 40]}).sort_values("revenue", ascending=False).iloc[0]["category"])
