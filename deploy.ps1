# deploy.ps1 - Backend deploy script

# Optional: activate your virtual environment if needed
# Uncomment the line below if using Windows and your venv is named ".venv"
.\.venv\Scripts\Activate.ps1

# Add all changes
git add .

# Commit with timestamp
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
git commit -m "Backend update: $timestamp"

# Force push to main branch
git push -f origin main

Write-Host "✅ Backend deployed successfully at $timestamp"
