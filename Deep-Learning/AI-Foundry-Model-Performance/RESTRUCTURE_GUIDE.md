# 📁 Repository Restructuring Guide

## Current Problem
When visitors land on the GitHub repository, they see a cluttered list of script files instead of a clean, professional structure.

## Proposed New Structure

```
AI-Foundry-Model-Performance/
├── README.md                    # Main documentation (stays at root)
├── requirements.txt             # Dependencies (stays at root)
├── LICENSE                      # License file (if you want to add)
├── .gitignore                   # Git ignore file (if you want to add)
│
├── 📁 scripts/                  # All scripts organized here
│   ├── deployment/              # Deployment scripts
│   │   ├── deploymodels-linux-20250405.py
│   │   ├── deploymodels-powershell-20250405.py
│   │   └── delete-endpoint-20250327.py
│   │
│   └── testing/                 # Performance testing scripts
│       ├── callaiinference-20250406.py
│       ├── concurrency_test.py
│       ├── press-phi4-0403.py
│       ├── press-phi35and0v-20250323.py
│       ├── press-phi35v-multi-imges-20250315.py
│       ├── press-llama3.211bv-20250407.py
│       ├── press-Mixtral-8x7B-20250323.py
│       ├── press-nemotron-3-8b-chat-4k-steerlm-20250324.py
│       ├── press-orca-20250324.py
│       ├── press-swinv2-20250322.py
│       ├── press-whisper-20250323.py
│       └── press.financial-reports-analysis-20250321.py
│
├── 📁 docs/                     # Additional documentation
│   └── muse.md
│
├── 📁 images/                   # Images for README (already exists)
│   └── ...
│
├── 📁 testlogs/                 # Test results (already exists)
│   └── ...
│
└── 📁 assets/                   # Other assets
    └── 1.m4a                    # Audio files
```

## How to Restructure (PowerShell Commands)

### Step 1: Move Deployment Scripts
```powershell
Move-Item -Path ".\deploymodels-linux-20250405.py" -Destination ".\scripts\deployment\"
Move-Item -Path ".\deploymodels-powershell-20250405.py" -Destination ".\scripts\deployment\"
Move-Item -Path ".\delete-endpoint-20250327.py" -Destination ".\scripts\deployment\"
```

### Step 2: Move Testing Scripts
```powershell
Move-Item -Path ".\callaiinference-20250406.py" -Destination ".\scripts\testing\"
Move-Item -Path ".\concurrency_test.py" -Destination ".\scripts\testing\"
Move-Item -Path ".\press-*.py" -Destination ".\scripts\testing\"
```

### Step 3: Move Documentation
```powershell
Move-Item -Path ".\muse.md" -Destination ".\docs\"
```

### Step 4: Move Assets
```powershell
New-Item -ItemType Directory -Path ".\assets" -Force
Move-Item -Path ".\1.m4a" -Destination ".\assets\"
```

### Step 5: Update README.md References

After moving files, update the README.md to reflect new paths:

**Before:**
```bash
python deploymodels-linux-20250405.py
```

**After:**
```bash
python scripts/deployment/deploymodels-linux-20250405.py
```

## Benefits

✅ **Cleaner Root Directory**: Only essential files visible (README, requirements.txt)  
✅ **Professional Appearance**: Looks like a well-maintained project  
✅ **Better Organization**: Scripts grouped by function  
✅ **Easier Navigation**: Users can find what they need quickly  
✅ **README Takes Center Stage**: First thing visitors see  

## Git Commit Message After Restructuring

```bash
git add .
git commit -m "refactor: reorganize project structure for better clarity

- Move deployment scripts to scripts/deployment/
- Move testing scripts to scripts/testing/
- Move documentation to docs/
- Update README with new file paths
- Improve repository appearance for GitHub visitors"
git push
```

## Alternative: Quick Fix Without Moving Files

If you don't want to move files now, you can:

1. **Add a .gitattributes file** to mark certain files as linguist-documentation
2. **Create a prominent header in README** with badges and hero image
3. **Pin README in GitHub repository settings**

But the restructuring approach is the **most professional and maintainable** long-term solution.
