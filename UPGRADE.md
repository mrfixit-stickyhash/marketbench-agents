# Upgrade an existing GitHub checkout to 0.2.0

The update archive contains the complete repository. To preserve the `.git` directory in your existing checkout, extract the archive beside the old folder and copy the new files over it.

Example Windows PowerShell paths:

```powershell
$update = "$HOME\Downloads\MarketBench_v0.2_GitHub_Update\marketbench"
$repo = "$HOME\Downloads\MarketBench_Agents_Complete\marketbench"

robocopy $update $repo /E /XD .git .venv runs data datasets checkpoints /XF .env

cd $repo
py -m pip install -e .
python -m unittest discover -s tests -v
marketbench demo
git status
git diff --stat
```

`robocopy` commonly returns exit code `1` when files were copied successfully. It is not an error unless the output reports failed files.

After reviewing the changes:

```powershell
git add .
git commit -m "Add objective research metrics and AutoResearch evaluator"
git push
```

Never copy a real `.env`, private Discord export, licensed dataset, model checkpoint or generated `runs/` directory into Git.
