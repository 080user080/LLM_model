@echo off
setlocal

:: Налаштування
set REPO_PATH=%~dp0
set CURRENT_BRANCH=feature/gui-modular
set TARGET_BRANCH=main
set COMMIT_MSG=auto-merge: %date% %time%

cd /d "%REPO_PATH%"

echo === Step 1: Saving changes to %CURRENT_BRANCH% ===
git add -A
git commit -m "%COMMIT_MSG%"
git push origin %CURRENT_BRANCH%

echo === Step 2: Switching to %TARGET_BRANCH% ===
git checkout %TARGET_BRANCH%
git pull origin %TARGET_BRANCH%

echo === Step 3: Merging %CURRENT_BRANCH% into %TARGET_BRANCH% ===
git merge %CURRENT_BRANCH% --no-edit

echo === Step 4: Pushing to GitHub ===
git push origin %TARGET_BRANCH%

echo === Step 5: Returning to %CURRENT_BRANCH% ===
git checkout %CURRENT_BRANCH%

echo === Done! Everything is in %TARGET_BRANCH% ===
pause