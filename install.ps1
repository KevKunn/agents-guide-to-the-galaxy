#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Configure', 'Apply', 'Restore')][string]$Mode = 'Plan',
    [string]$ProfileRoot = [Environment]::GetFolderPath('UserProfile'),
    [string]$StateRoot,
    [switch]$AdoptExisting,
    [switch]$DryRun,
    [string]$Skill,
    [ValidateSet('codex', 'claude')][string[]]$Agents
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'This installer uses Windows directory junctions. Run it in PowerShell 7 on Windows.' }
$repoRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$ProfileRoot = [IO.Path]::GetFullPath($ProfileRoot).TrimEnd('\', '/')
if (-not $StateRoot) { $StateRoot = Join-Path $ProfileRoot 'AppData/Local/agents-guide-to-the-galaxy' }
$StateRoot = [IO.Path]::GetFullPath($StateRoot).TrimEnd('\', '/')
$manifestPath = Join-Path $repoRoot 'manifest.json'
$statePath = Join-Path $StateRoot 'state.json'
$journalPath = Join-Path $StateRoot 'pending.json'
$locations = @{codex='.agents/skills'; claude='.claude/skills'; codexLegacy='.codex/skills'}

function Get-Entry([string]$Path) {
    # Enumerating the parent also detects dangling junctions.
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { return $null }
    $leaf = Split-Path -Leaf $Path
    return Get-ChildItem -LiteralPath $parent -Force | Where-Object { $_.Name -eq $leaf } | Select-Object -First 1
}
function Assert-Within([string]$Path, [string]$Root) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes its expected root: $Path" }
}
function Assert-PlainAncestors([string]$Path) {
    $current = [IO.Path]::GetFullPath($Path)
    while ($current) {
        $entry = Get-Entry $current
        if ($entry -and ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Parent path is a link: $current" }
        $next = Split-Path -Parent $current
        if ($next -eq $current) { break }
        $current = $next
    }
}
function Get-Destination([string]$Location, [string]$Name) {
    if (-not $locations.ContainsKey($Location)) { throw "Unknown location: $Location" }
    if ($Name -notmatch '^[a-z0-9][a-z0-9_-]{0,63}$') { throw "Invalid skill name: $Name" }
    $root = Join-Path $ProfileRoot $locations[$Location]
    Assert-PlainAncestors $root
    $path = Join-Path $root $Name
    Assert-Within $path $root
    return $path
}
function Get-LinkTarget($Entry) {
    if (-not $Entry -or $Entry.LinkType -ne 'Junction') { return $null }
    return [IO.Path]::GetFullPath([string]$Entry.Target).TrimEnd('\', '/')
}
function Get-Fingerprint([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { throw "Missing skill folder: $Path" }
    $items = @(Get-ChildItem -LiteralPath $Path -Recurse -Force)
    if (@($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Nested links are not supported inside skill content: $Path" }
    $rows = @(foreach ($item in ($items | Sort-Object FullName)) {
        $relative = $item.FullName.Substring($Path.Length).TrimStart('\', '/').Replace('\', '/')
        if ($item.PSIsContainer) { "D:$relative"; continue }
        $bytes = [IO.File]::ReadAllBytes($item.FullName)
        # Git may normalize text line endings. Compare text semantically across a pull.
        if ($item.Extension -in @('.md','.txt','.yaml','.yml','.json','.ps1','.sh','.toml','.py')) {
            $utf8 = [Text.UTF8Encoding]::new($false, $true)
            try { $bytes = $utf8.GetBytes($utf8.GetString($bytes).TrimStart([char]0xfeff).Replace("`r`n", "`n")) } catch [Text.DecoderFallbackException] { }
        }
        "F:${relative}:$([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)))"
    })
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes(($rows -join "`n"))))
}
function Write-Json([string]$Path, $Value) {
    $temporary = "$Path.tmp"
    [IO.File]::WriteAllText($temporary, (($Value | ConvertTo-Json -Depth 30) + "`n"), [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($temporary, $Path, $true)
}
function Assert-Manifest($Manifest) {
    if ($Manifest.schemaVersion -ne 1 -or $Manifest.repositoryId -ne 'agents-guide-to-the-galaxy') { throw 'Unsupported manifest.' }
    $seen = @{}
    foreach ($item in $Manifest.skills) {
        if ($seen.ContainsKey($item.name)) { throw "Duplicate skill: $($item.name)" }
        $seen[$item.name] = $true
        $null = Get-Destination 'codex' $item.name
        if ($item.agents -isnot [array]) { throw "Agents must be an array: $($item.name)" }
        if (@($item.agents | Sort-Object -Unique).Count -ne $item.agents.Count) { throw "Duplicate agent: $($item.name)" }
        foreach ($agent in $item.agents) { if ($agent -notin @('codex','claude')) { throw "Unknown agent: $agent" } }
        $source = Join-Path $repoRoot "skills/$($item.name)"
        Assert-PlainAncestors $source
        if ($Mode -ne 'Restore') {
            if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md') -PathType Leaf)) { throw "Missing SKILL.md: $source. Remove its manifest entry if retiring this skill." }
            $null = Get-Fingerprint $source
        }
    }
    $legacySeen = @{}
    foreach ($item in $Manifest.legacyCopies) {
        if ($item.location -ne 'codexLegacy' -or -not $seen.ContainsKey($item.name) -or $legacySeen.ContainsKey($item.name)) { throw 'Invalid or duplicate legacy copy entry.' }
        $legacySeen[$item.name] = $true
    }
}

Assert-PlainAncestors $repoRoot
Assert-PlainAncestors $StateRoot
if ($StateRoot -eq $repoRoot -or $StateRoot.StartsWith($repoRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Installation state and backups must live outside the repository.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
Assert-Manifest $manifest
if ($Mode -eq 'Configure') {
    foreach ($folder in (Get-ChildItem -LiteralPath (Join-Path $repoRoot 'skills') -Directory)) {
        if ((Test-Path -LiteralPath (Join-Path $folder.FullName 'SKILL.md')) -and $folder.Name -notin @($manifest.skills | ForEach-Object { $_.name })) {
            $manifest.skills += @{name=$folder.Name; agents=@()}
        }
    }
    if ($Skill -and $Skill -notin @($manifest.skills | ForEach-Object { $_.name })) { throw "Unknown skill: $Skill" }
    if ($PSBoundParameters.ContainsKey('Agents') -and -not $Skill) { throw '-Agents requires -Skill.' }
    foreach ($item in ($manifest.skills | Sort-Object name)) {
        if ($Skill -and $item.name -ne $Skill) { continue }
        if ($PSBoundParameters.ContainsKey('Agents')) { $item.agents = @($Agents | Sort-Object -Unique); continue }
        $choice = Read-Host "$($item.name) [$($item.agents -join ', ')] - 1 both, 2 Codex, 3 Claude, 4 neither, Enter keep, q cancel"
        switch ($choice) {
            '1' { $item.agents = @('codex','claude') }
            '2' { $item.agents = @('codex') }
            '3' { $item.agents = @('claude') }
            '4' { $item.agents = @() }
            '' { }
            'q' { Write-Output 'Cancelled; manifest unchanged.'; return }
            default { throw 'Invalid choice; manifest unchanged.' }
        }
    }
    Assert-Manifest $manifest
    if ($DryRun) { $manifest.skills | Select-Object name, agents; return }
    Write-Json $manifestPath $manifest
    Write-Output 'Saved manifest. Run -Mode Plan to review the resulting installation changes.'
    return
}
if ($Skill -or $PSBoundParameters.ContainsKey('Agents')) { throw '-Skill and -Agents are only supported in Configure mode.' }
if (Test-Path -LiteralPath $journalPath) { throw "An interrupted operation needs recovery. Read $journalPath and docs/installation.md before retrying. No changes made." }
$state = @{schemaVersion=1;repositoryId=$manifest.repositoryId;profileRoot=$ProfileRoot;records=@()}
$stateBefore = if (Test-Path -LiteralPath $statePath) { [IO.File]::ReadAllText($statePath) } else { $null }
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -AsHashtable
    if ($state.schemaVersion -ne 1 -or $state.repositoryId -ne $manifest.repositoryId -or $state.profileRoot -ne $ProfileRoot) { throw 'Installation state belongs to a different profile or repository.' }
}
$records = @{}
foreach ($record in $state.records) {
    $destination = Get-Destination $record.location $record.name
    $key = "$($record.location)/$($record.name)"
    if ($record.destination -ne $destination -or $records.ContainsKey($key)) { throw 'Invalid installation state path or duplicate record.' }
    if ($record.backup) { Assert-Within $record.backup (Join-Path $StateRoot 'backups'); Assert-PlainAncestors (Split-Path -Parent $record.backup) }
    $records[$key] = $record
}
$desired = @{}
if ($Mode -ne 'Restore') {
    foreach ($item in $manifest.skills) {
        foreach ($agent in $item.agents) { $desired["$agent/$($item.name)"] = @{name=$item.name;location=$agent;target=(Join-Path $repoRoot "skills/$($item.name)")} }
    }
}
$keys = @($desired.Keys) + @($records.Keys)
if ($Mode -ne 'Restore') { $keys += @($manifest.legacyCopies | ForEach-Object { "$($_.location)/$($_.name)" }) }
$plan = @()
$conflicts = @()
foreach ($key in ($keys | Sort-Object -Unique)) {
    $location, $name = $key -split '/', 2
    $destination = Get-Destination $location $name
    $entry = Get-Entry $destination
    $record = $records[$key]
    $wanted = $desired[$key]
    $action = 'Keep'
    $reason = ''
    $target = if ($wanted) { $wanted.target } else { $null }
    $fingerprint = $null
    if ($record) {
        if ($record.active) {
            if ($entry -and (Get-LinkTarget $entry) -ne $record.target) { $reason = 'Managed path was replaced or retargeted outside this installer.' }
        } elseif ($entry) { $reason = 'An unmanaged entry now occupies a previously managed path.' }
        if ($record.backup -and -not (Get-Entry $record.backup)) { $reason = 'Recorded original backup is missing.' }
        if (-not $reason) {
            if ($wanted) { if (-not $entry -or (Get-LinkTarget $entry) -ne $target) { $action = 'Link' } }
            elseif ($Mode -eq 'Restore') { $action = 'Restore' }
            elseif ($entry) { $action = 'Unlink' }
        }
    } elseif ($wanted -or ($location -eq 'codexLegacy' -and $Mode -ne 'Restore')) {
        if ($entry) {
            if (-not $AdoptExisting) { $reason = 'Unmanaged path exists. Review and rerun with -AdoptExisting to back up identical content.' }
            elseif (-not $entry.PSIsContainer -or ($entry.LinkType -and $entry.LinkType -ne 'Junction')) { $reason = 'Existing path is not an ordinary folder or directory junction.' }
            else {
                $source = Join-Path $repoRoot "skills/$name"
                try {
                    $fingerprint = Get-Fingerprint $destination
                    if ($fingerprint -ne (Get-Fingerprint $source)) { $reason = 'Existing content differs from the repository; merge it before adoption.' }
                } catch { $reason = $_.Exception.Message }
                if (-not $reason) { $action = if ($wanted) { 'Adopt' } else { 'RetireLegacy' } }
            }
        } elseif ($wanted) { $action = 'Link' }
        else { continue }
    }
    if ($reason) { $action = 'Conflict'; $conflicts += "$key`: $reason" }
    $plan += @{key=$key;name=$name;location=$location;destination=$destination;target=$target;action=$action;reason=$reason;fingerprint=$fingerprint}
}
$plan | ForEach-Object { [pscustomobject]@{Action=$_.action;Skill=$_.name;Location=$_.location;Reason=$_.reason} } | Format-Table -AutoSize | Out-Host
if ($conflicts.Count) { throw ($conflicts -join "`n") }
if ($Mode -eq 'Plan' -or $DryRun) { Write-Output 'Dry run only; no files, links, or state changed.'; return }
$changes = @($plan | Where-Object { $_.action -ne 'Keep' })
if (-not $changes.Count) { Write-Output 'Already up to date; no changes.'; return }

# Journal each primitive before executing it. Normal failures undo primitives in
# reverse order; an interrupted process leaves the journal for explicit recovery.
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
$lockStream = [IO.File]::Open((Join-Path $StateRoot 'install.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
$stateNow = if (Test-Path -LiteralPath $statePath) { [IO.File]::ReadAllText($statePath) } else { $null }
if ($stateNow -cne $stateBefore -or (Test-Path -LiteralPath $journalPath)) { throw 'Installation state changed while planning. Rerun to make a fresh plan.' }
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$journal = @{schemaVersion=1;runId=$runId;mode=$Mode;originalState=$state;steps=@()}
$undo = [Collections.Generic.List[object]]::new()
$newState = ($state | ConvertTo-Json -Depth 30 | ConvertFrom-Json -AsHashtable)
$newRecords = @{}
foreach ($record in $newState.records) { $newRecords["$($record.location)/$($record.name)"] = $record }
Write-Json $journalPath $journal
function Invoke-Step([string]$Kind, [string]$Path, [string]$Other) {
    $step = @{kind=$Kind;path=$Path;other=$Other;done=$false}
    $script:journal.steps += $step
    Write-Json $script:journalPath $script:journal
    switch ($Kind) {
        'Move' {
            Assert-PlainAncestors (Split-Path -Parent $Path)
            Assert-PlainAncestors (Split-Path -Parent $Other)
            if (Get-Entry $Other) { throw "Backup or restoration destination already exists: $Other" }
            New-Item -ItemType Directory -Path (Split-Path -Parent $Other) -Force | Out-Null
            Move-Item -LiteralPath $Path -Destination $Other
        }
        'Unlink' {
            $entry = Get-Entry $Path
            if ((Get-LinkTarget $entry) -ne $Other) { throw "Refusing to remove a changed junction: $Path" }
            Assert-PlainAncestors (Split-Path -Parent $Path)
            [IO.Directory]::Delete($Path, $false)
        }
        'Link' {
            Assert-PlainAncestors (Split-Path -Parent $Path)
            if (Get-Entry $Path) { throw "Link destination appeared during installation: $Path" }
            if (-not (Test-Path -LiteralPath (Join-Path $Other 'SKILL.md'))) { throw "Link source disappeared: $Other" }
            New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
            New-Item -ItemType Junction -Path $Path -Target $Other | Out-Null
        }
    }
    $script:undo.Add($step)
    $step.done = $true
    Write-Json $script:journalPath $script:journal
}
try {
    foreach ($item in $changes) {
        $record = $newRecords[$item.key]
        if (-not $record) {
            $record = @{name=$item.name;location=$item.location;destination=$item.destination;backup=$null;target=$null;active=$false}
            $newRecords[$item.key] = $record
        }
        if ($item.action -in @('Adopt','RetireLegacy')) {
            if ((Get-Fingerprint $item.destination) -ne $item.fingerprint) { throw "Source changed after planning: $($item.destination)" }
            $backup = Join-Path $StateRoot "backups/$runId/$($item.location)/$($item.name)"
            Assert-Within $backup (Join-Path $StateRoot 'backups')
            Assert-Within $item.destination (Join-Path $ProfileRoot $locations[$item.location])
            Invoke-Step 'Move' $item.destination $backup
            $record.backup = $backup
        }
        $entry = Get-Entry $item.destination
        if ($entry -and $record.active) { Invoke-Step 'Unlink' $item.destination $record.target }
        if ($item.action -in @('Link','Adopt')) {
            Invoke-Step 'Link' $item.destination $item.target
            $record.target = $item.target
            $record.active = $true
        } else { $record.active = $false }
        if ($item.action -eq 'Restore') {
            if ($record.backup) { Invoke-Step 'Move' $record.backup $item.destination }
            $newRecords.Remove($item.key)
        }
    }
    $newState.records = @($newRecords.Values | Sort-Object location,name)
    $newState.repoRoot = $repoRoot
    Write-Json $statePath $newState
} catch {
    $originalError = $_
    $rollbackError = $null
    for ($index = $undo.Count - 1; $index -ge 0; $index--) {
        $step = $undo[$index]
        try {
            switch ($step.kind) {
                'Link' { if ((Get-LinkTarget (Get-Entry $step.path)) -ne $step.other) { throw "Rollback link changed: $($step.path)" }; [IO.Directory]::Delete($step.path, $false) }
                'Unlink' { if (Get-Entry $step.path) { throw "Rollback path occupied: $($step.path)" }; New-Item -ItemType Junction -Path $step.path -Target $step.other | Out-Null }
                'Move' { if (Get-Entry $step.path) { throw "Rollback path occupied: $($step.path)" }; Move-Item -LiteralPath $step.other -Destination $step.path }
            }
        } catch { $rollbackError = $_; break }
    }
    if ($rollbackError) { throw "Installation failed: $originalError. Rollback needs attention: $rollbackError. Journal: $journalPath" }
    Remove-Item -LiteralPath $journalPath
    throw "Installation failed and changes were rolled back: $originalError"
}
Remove-Item -LiteralPath $journalPath
Write-Output "$($changes.Count) changes applied. State and original backups: $StateRoot"
} finally { $lockStream.Dispose() }
