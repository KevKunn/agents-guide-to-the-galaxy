#requires -Version 7.0
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('guide-tests-' + [guid]::NewGuid().ToString('N'))
$repo = Join-Path $testRoot 'repo with spaces'
$profile = Join-Path $testRoot 'profile'
$state = Join-Path $testRoot 'state'
New-Item -ItemType Directory -Path $repo -Force | Out-Null
Copy-Item -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'install.ps1') -Destination (Join-Path $repo 'install.ps1')
$installer = Join-Path $repo 'install.ps1'
$passed = 0
function Assert([bool]$Condition, [string]$Message) { if (-not $Condition) { throw "FAIL: $Message" }; $script:passed++; Write-Output "PASS: $Message" }
function Write-Manifest($Value) { $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $script:repo 'manifest.json') }
function Run([string]$Mode='Apply', [switch]$Adopt) { & $script:installer -Mode $Mode -ProfileRoot $script:profile -StateRoot $script:state -AdoptExisting:$Adopt | Out-Null }
function Must-Fail([scriptblock]$Block, [string]$Pattern) {
    $caught = $null
    try { & $Block | Out-Null } catch { $caught = $_.Exception.Message }
    Assert ($null -ne $caught -and $caught -match $Pattern) "Rejects $Pattern"
}
function Is-Junction([string]$Path, [string]$Target) { $item = Get-Item -LiteralPath $Path; return $item.LinkType -eq 'Junction' -and $item.Target -eq $Target }
$manifest = @{schemaVersion=1;repositoryId='agents-guide-to-the-galaxy';skills=@(@{name='alpha';agents=@('codex','claude')});legacyCopies=@(@{name='alpha';location='codexLegacy'})}
$source = Join-Path $repo 'skills/alpha'
New-Item -ItemType Directory -Path (Join-Path $source 'references') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $source 'SKILL.md') -Value "---`nname: alpha`ndescription: Fixture`n---`nOriginal"
Set-Content -LiteralPath (Join-Path $source 'references/note.txt') -Value 'Supporting content'
$codex = Join-Path $profile '.agents/skills/alpha'
$claude = Join-Path $profile '.claude/skills/alpha'
$legacy = Join-Path $profile '.codex/skills/alpha'
foreach ($path in @($codex,$claude,$legacy)) { New-Item -ItemType Directory -Path (Split-Path $path) -Force | Out-Null }
Copy-Item -LiteralPath $source -Destination $codex -Recurse
New-Item -ItemType Junction -Path $claude -Target $codex | Out-Null
Copy-Item -LiteralPath $source -Destination $legacy -Recurse
$unmanaged = Join-Path $profile '.claude/skills/unmanaged'
New-Item -ItemType Directory -Path $unmanaged | Out-Null
Set-Content -LiteralPath (Join-Path $unmanaged 'sentinel.txt') -Value 'Leave me alone'
Write-Manifest $manifest
Run -Mode Plan -Adopt
Assert (-not (Test-Path -LiteralPath $state)) 'Dry run creates no installation state'
Assert (-not (Get-Item -LiteralPath $codex).LinkType) 'Dry run leaves original directory untouched'
Must-Fail { Run } 'Unmanaged path exists'
Set-Content -LiteralPath (Join-Path $codex 'references/note.txt') -Value 'Different'
Must-Fail { Run -Adopt } 'content differs'
Assert (-not (Get-Item -LiteralPath $codex).LinkType) 'Conflict preflight makes no partial changes'
Copy-Item -LiteralPath (Join-Path $source 'references/note.txt') -Destination (Join-Path $codex 'references/note.txt')
Run -Adopt
Assert (Is-Junction $codex $source) 'Adopts a matching directory as a junction'
Assert (Is-Junction $claude $source) 'Replaces an indirect junction with a direct junction'
Assert (-not (Test-Path -LiteralPath $legacy)) 'Retires duplicate legacy copy'
$installed = Get-Content -LiteralPath (Join-Path $state 'state.json') -Raw | ConvertFrom-Json
Assert ($installed.records.Count -eq 3) 'Records active links and the retired legacy copy'
Assert (@($installed.records | Where-Object backup).Count -eq 3) 'Preserves all three original entries in backups'
$before = (Get-FileHash -LiteralPath (Join-Path $state 'state.json')).Hash
Run
Assert ($before -eq (Get-FileHash -LiteralPath (Join-Path $state 'state.json')).Hash) 'Second apply is idempotent, including state'
Set-Content -LiteralPath (Join-Path $source 'references/note.txt') -Value 'Edited in repository'
Assert ((Get-Content -LiteralPath (Join-Path $codex 'references/note.txt') -Raw).Trim() -eq 'Edited in repository') 'Repository edit is visible through Codex link'
Set-Content -LiteralPath (Join-Path $claude 'references/note.txt') -Value 'Edited through Claude'
Assert ((Get-Content -LiteralPath (Join-Path $source 'references/note.txt') -Raw).Trim() -eq 'Edited through Claude') 'Editing a linked skill changes the canonical source'
& $installer -Mode Configure -Skill alpha -Agents codex -ProfileRoot $profile -StateRoot $state | Out-Null
Run
Assert (-not (Test-Path -LiteralPath $claude)) 'Changing targets removes only the deselected managed link'
Assert (Test-Path -LiteralPath (Join-Path $unmanaged 'sentinel.txt')) 'Unmanaged neighboring skills survive reconciliation'
& $installer -Mode Configure -Skill alpha -Agents codex,claude -ProfileRoot $profile -StateRoot $state | Out-Null
Run
Assert (Is-Junction $claude $source) 'Re-enabling a target reinstalls its junction'
& $installer -Mode Configure -Skill alpha -Agents @() -ProfileRoot $profile -StateRoot $state | Out-Null
Run
Assert (-not (Test-Path -LiteralPath $codex) -and -not (Test-Path -LiteralPath $claude)) 'Selecting neither removes both managed links'
& $installer -Mode Configure -Skill alpha -Agents codex,claude -ProfileRoot $profile -StateRoot $state | Out-Null
Run
[IO.Directory]::Delete($claude, $false)
New-Item -ItemType Directory -Path $claude | Out-Null
Must-Fail { Run } 'replaced or retargeted'
[IO.Directory]::Delete($claude, $false)
New-Item -ItemType Junction -Path $claude -Target $source | Out-Null
$manifest.skills[0].agents = @('codex','claude')
$manifest.skills += @{name='../escape';agents=@('codex')}
Write-Manifest $manifest
Must-Fail { Run } 'Invalid skill name'
$manifest.skills = @($manifest.skills | Where-Object name -eq alpha)
Write-Manifest $manifest
Run -Mode Restore
Assert (-not (Get-Item -LiteralPath $codex).LinkType) 'Restore recovers original ordinary directory'
Assert (Is-Junction $claude $codex) 'Restore recovers original indirect junction'
Assert ((Get-Content -LiteralPath (Join-Path $codex 'references/note.txt') -Raw).Trim() -eq 'Supporting content') 'Restore preserves pre-migration file content'
Assert (Test-Path -LiteralPath (Join-Path $legacy 'SKILL.md')) 'Restore recovers legacy copy'
Assert ((Get-Content -LiteralPath (Join-Path $source 'references/note.txt') -Raw).Trim() -eq 'Edited through Claude') 'Restore does not discard repository edits'
# Fresh install with no existing entries, followed by source removal and manifest retirement.
$profile = Join-Path $testRoot 'fresh profile'
$state = Join-Path $testRoot 'fresh state'
Run
$freshCodex = Join-Path $profile '.agents/skills/alpha'
Assert (Is-Junction $freshCodex $source) 'Installs on a fresh machine profile'
$retired = Join-Path $repo 'skills/retired-alpha'
# Both paths are fixed children of this test repository.
Move-Item -LiteralPath $source -Destination $retired
$manifest.skills = @()
$manifest.legacyCopies = @()
Write-Manifest $manifest
Run
Assert (@(Get-ChildItem -LiteralPath (Split-Path $freshCodex) -Force).Count -eq 0) 'Retires dangling managed links after source removal'
Assert (Test-Path -LiteralPath (Join-Path $retired 'SKILL.md')) 'Unlinking never deletes a junction target'
# Exercise failure after a real mutation by making the second link operation fail.
$profile = Join-Path $testRoot 'rollback profile'
$state = Join-Path $testRoot 'rollback state'
$source = $retired
$manifest.skills = @(@{name='retired-alpha';agents=@('codex','claude')})
Write-Manifest $manifest
$claudeRoot = Join-Path $profile '.claude/skills'
New-Item -ItemType Directory -Path $claudeRoot -Force | Out-Null
Copy-Item -LiteralPath $source -Destination (Join-Path $claudeRoot 'retired-alpha') -Recurse
# Isolated fault injection: only the fixture installer receives this injected failure.
$originalInstaller = Get-Content -LiteralPath $installer -Raw
$faulty = $originalInstaller.Replace("Invoke-Step 'Link' `$item.destination `$item.target", "if (`$item.location -eq 'codex') { throw 'fixture injected failure' }; Invoke-Step 'Link' `$item.destination `$item.target")
Set-Content -LiteralPath $installer -Value $faulty
Must-Fail { Run -Adopt } 'rolled back'
Assert (-not (Get-Item -LiteralPath (Join-Path $claudeRoot 'retired-alpha')).LinkType) 'Failure rolls adopted folder back to original form'
Assert (-not (Test-Path -LiteralPath (Join-Path $state 'pending.json'))) 'Successful rollback clears the pending journal'
Set-Content -LiteralPath $installer -Value $originalInstaller
Run -Adopt
Assert (Is-Junction (Join-Path $claudeRoot 'retired-alpha') $source) 'Retry succeeds after rollback'
Set-Content -LiteralPath (Join-Path $state 'pending.json') -Value '{}'
Must-Fail { Run } 'interrupted operation'
Remove-Item -LiteralPath (Join-Path $state 'pending.json')
# Move an entire checkout and retarget existing owned junctions from the new path.
$movedRepo = Join-Path $testRoot 'moved checkout'
Move-Item -LiteralPath $repo -Destination $movedRepo
$repo = $movedRepo
$installer = Join-Path $repo 'install.ps1'
$source = Join-Path $repo 'skills/retired-alpha'
Run
Assert (Is-Junction (Join-Path $claudeRoot 'retired-alpha') $source) 'Moving the checkout retargets existing owned links'
# Discover a skill in an empty manifest, then verify Configure dry run stays read-only.
$manifest.skills = @()
Write-Manifest $manifest
$manifestHash = (Get-FileHash -LiteralPath (Join-Path $repo 'manifest.json')).Hash
& $installer -Mode Configure -Skill retired-alpha -Agents codex -DryRun -ProfileRoot $profile -StateRoot $state | Out-Null
Assert ($manifestHash -eq (Get-FileHash -LiteralPath (Join-Path $repo 'manifest.json')).Hash) 'Configure dry run preserves the manifest'
& $installer -Mode Configure -Skill retired-alpha -Agents codex -ProfileRoot $profile -StateRoot $state | Out-Null
$configured = Get-Content -LiteralPath (Join-Path $repo 'manifest.json') -Raw | ConvertFrom-Json
Assert ($configured.skills.Count -eq 1 -and $configured.skills[0].agents[0] -eq 'codex') 'Configure discovers new skills even from an empty manifest'
# A discovery root redirected by a junction must not be modified.
$redirectProfile = Join-Path $testRoot 'redirect profile'
New-Item -ItemType Directory -Path $redirectProfile -Force | Out-Null
New-Item -ItemType Junction -Path (Join-Path $redirectProfile '.agents') -Target (Join-Path $profile '.agents') | Out-Null
Must-Fail { & $installer -Mode Plan -ProfileRoot $redirectProfile -StateRoot (Join-Path $testRoot 'redirect state') } 'Parent path is a link'
Write-Output "Completed $passed assertions. Fixtures retained at $testRoot"
