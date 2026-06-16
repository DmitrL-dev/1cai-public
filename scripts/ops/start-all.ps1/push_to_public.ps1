# Push to public repository
$desktop = [Environment]::GetFolderPath("Desktop")
$package = Join-Path $desktop "package (1)"
$public = Join-Path $package "1cai-public"

Set-Location $public

git config user.email "dmitrl-dev@github.com"
git config user.name "DmitrL-dev"

git add -A
git commit -m "feat: технический долг сокращен" -m "Rate limiting, тесты, CI улучшения"
git branch -M main
git push -u origin main

Write-Host "Done!"

