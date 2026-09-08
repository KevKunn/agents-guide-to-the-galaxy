[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$Query,

    [ValidateSet("canonical", "jira", "all", "private")]
    [string]$Scope = "canonical",

    [ValidatePattern("^[a-z0-9][a-z0-9-]*$")]
    [string]$Project,

    [ValidateRange(1, 500)]
    [int]$MaxResults = 80,

    [string]$Root,

    [switch]$Regex
)

$ErrorActionPreference = "Stop"

if (-not $Root) {
    $Root = if ($env:KNOWLEDGEBASE_ROOT) {
        $env:KNOWLEDGEBASE_ROOT
    } else {
        "C:\Users\KevinCsele\Developer\KnowledgeBase"
    }
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$requiredIndex = Join-Path $rootPath "_meta\indexes\canonical-notes.md"
if (-not (Test-Path -LiteralPath $requiredIndex -PathType Leaf)) {
    throw "Not a structured KnowledgeBase root: $rootPath"
}

$targets = [System.Collections.Generic.List[string]]::new()
$globs = [System.Collections.Generic.List[string]]::new()

switch ($Scope) {
    "canonical" {
        $globs.Add("*.md")
        $targets.Add("_meta\indexes\canonical-notes.md")
        $targets.Add("_meta\indexes\state-review.md")
        if ($Project) {
            $projectPath = "10-projects\$Project"
            if (-not (Test-Path -LiteralPath (Join-Path $rootPath $projectPath) -PathType Container)) {
                throw "Unknown project slug: $Project"
            }
            $targets.Add($projectPath)
        } else {
            $targets.Add("05-plans")
            $targets.Add("10-projects")
        }
        $targets.Add("20-engineering")
        $targets.Add("30-ai-agents")
        $targets.Add("40-toolbox")
        $targets.Add("50-reference")
        $targets.Add("60-personal")
        $globs.Add("!**/work-items/jira/**")
        $globs.Add("!**/work-items/attachments/**")
        $globs.Add("!30-ai-agents/source-material/**")
    }
    "jira" {
        $globs.Add("*.md")
        $targets.Add("_meta\indexes\jira-tickets.md")
        if ($Project) {
            $projectPath = "10-projects\$Project\work-items\jira"
            if (-not (Test-Path -LiteralPath (Join-Path $rootPath $projectPath) -PathType Container)) {
                throw "No Jira mirror for project slug: $Project"
            }
            $targets.Add($projectPath)
        } else {
            foreach ($projectDirectory in (Get-ChildItem -LiteralPath (Join-Path $rootPath "10-projects") -Directory)) {
                $jiraPath = Join-Path $projectDirectory.FullName "work-items\jira"
                if (Test-Path -LiteralPath $jiraPath -PathType Container) {
                    $targets.Add("10-projects\$($projectDirectory.Name)\work-items\jira")
                }
            }
        }
    }
    "all" {
        $globs.Add("*.md")
        $targets.Add("_meta\indexes")
        $targets.Add("00-inbox")
        $targets.Add("05-plans")
        $targets.Add("10-projects")
        $targets.Add("20-engineering")
        $targets.Add("30-ai-agents")
        $targets.Add("40-toolbox")
        $targets.Add("50-reference")
        $targets.Add("60-personal")
        $targets.Add("90-archive")
    }
    "private" {
        $targets.Add("70-private")
    }
}

$rg = Get-Command rg -ErrorAction SilentlyContinue
$results = [System.Collections.Generic.List[string]]::new()

Push-Location $rootPath
try {
    if ($rg) {
        $arguments = @("--ignore-case", "--color", "never")
        if (-not $Regex) {
            $arguments += "--fixed-strings"
        }
        foreach ($glob in $globs) {
            $arguments += @("--glob", $glob)
        }
        if ($Scope -eq "private") {
            $arguments += "--files-with-matches"
        } else {
            $arguments += @("--line-number", "--no-heading")
        }
        $arguments += "--"
        $arguments += $Query
        $arguments += $targets

        foreach ($line in (& $rg.Source @arguments 2>$null)) {
            $results.Add([string]$line)
            if ($results.Count -ge $MaxResults) {
                break
            }
        }

        if ($Scope -eq "private" -and $results.Count -lt $MaxResults) {
            foreach ($path in (& $rg.Source --files -- "70-private" 2>$null)) {
                $pathText = [string]$path
                $pathMatches = if ($Regex) {
                    $pathText -match $Query
                } else {
                    $pathText.IndexOf($Query, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
                }
                if ($pathMatches -and -not $results.Contains($pathText)) {
                    $results.Add($pathText)
                }
                if ($results.Count -ge $MaxResults) {
                    break
                }
            }
        }
    } else {
        $files = foreach ($target in $targets) {
            $resolvedTarget = Join-Path $rootPath $target
            if (Test-Path -LiteralPath $resolvedTarget -PathType Leaf) {
                Get-Item -LiteralPath $resolvedTarget
            } elseif (Test-Path -LiteralPath $resolvedTarget -PathType Container) {
                if ($Scope -eq "private") {
                    Get-ChildItem -LiteralPath $resolvedTarget -Recurse -File
                } else {
                    Get-ChildItem -LiteralPath $resolvedTarget -Recurse -File -Filter "*.md"
                }
            }
        }
        $matches = $files | Select-String -Pattern $Query -SimpleMatch:(-not $Regex)
        foreach ($match in $matches) {
            $line = if ($Scope -eq "private") {
                $match.Path
            } else {
                "{0}:{1}:{2}" -f $match.Path, $match.LineNumber, $match.Line.Trim()
            }
            if (-not $results.Contains($line)) {
                $results.Add($line)
            }
            if ($results.Count -ge $MaxResults) {
                break
            }
        }
    }
} finally {
    Pop-Location
}

if ($Scope -eq "private") {
    Write-Output "Private search: paths only; do not print secret or raw-history contents."
}

if ($results.Count -eq 0) {
    Write-Output "No matches in scope '$Scope' for '$Query'."
} else {
    $results
}
