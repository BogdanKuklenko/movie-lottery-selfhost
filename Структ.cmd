@echo off
setlocal EnableExtensions

rem Timestamp + paths
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "TS=%%I"

set "ROOT=%CD%"
set "TEMP_OEM=%TEMP%\tree_oem_%RANDOM%.tmp"
set "REPORT=%ROOT%\Report_%TS%.txt"

rem 1) Dump tree in OEM (as tree.exe prints)
tree /f > "%TEMP_OEM%" 2>nul

rem 2) Do all heavy lifting in a single PowerShell run (no temp .ps1 needed)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$root='%ROOT%'; $out='%REPORT%'; $temp='%TEMP_OEM%';" ^
  "$tree = Get-Content -Raw -Encoding OEM $temp;" ^
  "$items = Get-ChildItem -LiteralPath $root -Force -Recurse;" ^
  "$files = $items | Where-Object { -not $_.PSIsContainer };" ^
  "$dirs  = $items | Where-Object { $_.PSIsContainer };" ^
  "$dirCount = ($dirs | Measure-Object).Count + 1;" ^
  "$fileCount = ($files | Measure-Object).Count;" ^
  "$totalBytes = ($files | Measure-Object Length -Sum).Sum;" ^
  "$top = $files | Sort-Object Length -Descending | Select-Object -First 50 FullName,Length,LastWriteTime;" ^
  "$ext = $files | ForEach-Object { $e=$_.Extension; if ([string]::IsNullOrEmpty($e)) { $k='' } else { $k=$e.ToLowerInvariant() }; [pscustomobject]@{ Ext=$k; Size=$_.Length } } | Group-Object Ext | ForEach-Object { [pscustomobject]@{ Extension=$_.Name; Count=$_.Count; Size=($_.Group | Measure-Object Size -Sum).Sum } } | Sort-Object Size -Descending;" ^
  "[IO.File]::WriteAllText($out,'',[Text.UTF8Encoding]::new($true));" ^
  "Add-Content -Path $out -Encoding UTF8 ('REPORT FOR: ' + $root);" ^
  "Add-Content -Path $out -Encoding UTF8 ('Generated: ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'));" ^
  "Add-Content -Path $out -Encoding UTF8 ('Total directories: ' + $dirCount);" ^
  "Add-Content -Path $out -Encoding UTF8 ('Total files: ' + $fileCount);" ^
  "Add-Content -Path $out -Encoding UTF8 ('Total size (bytes): ' + ($totalBytes -as [int64]));" ^
  "Add-Content -Path $out -Encoding UTF8 '';" ^
  "Add-Content -Path $out -Encoding UTF8 '=== TREE ===';" ^
  "Add-Content -Path $out -Encoding UTF8 $tree;" ^
  "Add-Content -Path $out -Encoding UTF8 '';" ^
  "Add-Content -Path $out -Encoding UTF8 '=== TOP 50 LARGEST FILES ===';" ^
  "$top | ForEach-Object { Add-Content -Path $out -Encoding UTF8 ('{0,12} bytes  {1:yyyy-MM-dd HH:mm:ss}  {2}' -f $_.Length, $_.LastWriteTime, $_.FullName) };" ^
  "Add-Content -Path $out -Encoding UTF8 '';" ^
  "Add-Content -Path $out -Encoding UTF8 '=== BY EXTENSION (size desc) ===';" ^
  "$ext | ForEach-Object { Add-Content -Path $out -Encoding UTF8 ('{0,-12}  count={1,7}  size={2,14}' -f ($_.Extension), $_.Count, $_.Size) };" ^
  "Add-Content -Path $out -Encoding UTF8 '';" ^
  "Add-Content -Path $out -Encoding UTF8 '=== FULL INVENTORY (CSV) ===';" ^
  "Add-Content -Path $out -Encoding UTF8 'Path,Type,SizeBytes,LastWrite,Created,Attributes,Owner';" ^
  "Get-ChildItem -LiteralPath $root -Force -Recurse | ForEach-Object { $type= if ($_.PSIsContainer) {'Directory'} else {'File'}; $size= if ($_.PSIsContainer) {''} else {$_.Length}; $lw=$_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'); $cr=$_.CreationTime.ToString('yyyy-MM-dd HH:mm:ss'); try { $owner=(Get-Acl -LiteralPath $_.FullName).Owner } catch { $owner='' }; $path=$_.FullName.Replace('\"','\"\"'); $attr=($_.Attributes.ToString()).Replace('\"','\"\"'); $owner=$owner.Replace('\"','\"\"'); Add-Content -Path $out -Encoding UTF8 ( '\"{0}\",{1},{2},{3},{4},\"{5}\",\"{6}\"' -f $path,$type,$size,$lw,$cr,$attr,$owner) }"

if errorlevel 1 goto :ps_error

del "%TEMP_OEM%" >nul 2>&1

echo Report ready:
echo   %REPORT%
exit /b 0

:ps_error
echo PowerShell failed. See above for errors.
exit /b 1
