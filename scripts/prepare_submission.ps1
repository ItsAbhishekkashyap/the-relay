# Stage 8 Final Submission Package Preparation Script

$target = "submission"
if (Test-Path $target) {
    Remove-Item -Recurse -Force $target
}
New-Item -ItemType Directory -Path $target | Out-Null

# 1. Root configuration & documentation files
$rootFiles = @(
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    ".env.example",
    ".gitignore",
    "README.md"
)

foreach ($f in $rootFiles) {
    if (Test-Path $f) {
        Copy-Item $f "$target/$f"
    }
}

# 2. Directories to copy with robocopy (excluding caches and environments)
$dirs = @("app", "simulator", "scripts", "tests", "data", "papers", "experiments", "reports")

foreach ($d in $dirs) {
    if (Test-Path $d) {
        $dest = "$target/$d"
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        robocopy $d $dest /E /XD __pycache__ .pytest_cache .ruff_cache /XF *.pyc *.pyo *.log | Out-Null
    }
}

# 3. Frontend directory (excluding node_modules and dist)
if (Test-Path "frontend") {
    $dest = "$target/frontend"
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    robocopy "frontend" $dest /E /XD node_modules dist .vscode /XF *.log | Out-Null
}

Write-Host "Submission package assembled successfully in '$target/'."
