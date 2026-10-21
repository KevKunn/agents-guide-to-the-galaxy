# Backup / compare / restore of XAF per-user model differences (ModelDifferenceAspect.Xml) around a sweep.
#   -Mode Backup   before the first browser opens
#   -Mode Compare  any time; lists changed, added and missing aspects (-DumpDir writes before/now XML of changed ones)
#   -Mode Restore  writes the backed-up Xml back into changed aspects (ask the user first)
param(
  [Parameter(Mandatory)][ValidateSet('Backup','Compare','Restore')][string]$Mode,
  [Parameter(Mandatory)][string[]]$Databases,
  [string]$Server = '(localdb)\MSSQLLocalDB',
  [string]$Dir = $PSScriptRoot,
  [string]$DumpDir
)
$ErrorActionPreference = 'Stop'
$query = @"
SELECT CAST(a.Oid AS nvarchar(50)) AspectOid, CAST(d.Oid AS nvarchar(50)) MdOid, d.UserId, d.ContextId, a.Name, CAST(a.Xml AS nvarchar(max)) Xml
FROM ModelDifferenceAspect a JOIN ModelDifference d ON d.Oid = a.Owner
WHERE a.GCRecord IS NULL AND d.GCRecord IS NULL
"@
foreach ($db in $Databases) {
  $file = Join-Path $Dir "ui-state-before-$db.csv"
  $cn = New-Object System.Data.SqlClient.SqlConnection "Server=$Server;Database=$db;Integrated Security=true"
  $cn.Open()
  try {
    $cmd = $cn.CreateCommand(); $cmd.CommandText = $query
    $r = $cmd.ExecuteReader(); $rows = @()
    while ($r.Read()) { $rows += [pscustomobject]@{ AspectOid = $r['AspectOid'].ToLower(); MdOid = $r['MdOid'].ToLower(); UserId = "$($r['UserId'])"; ContextId = "$($r['ContextId'])"; Name = "$($r['Name'])"; Xml = "$($r['Xml'])" } }
    $r.Close()
    if ($Mode -eq 'Backup') {
      if (Test-Path $file) { throw "$file exists; refusing to overwrite an earlier backup" }
      $rows | Export-Csv $file -NoTypeInformation -Encoding UTF8
      "== $db backed up $($rows.Count) aspects -> $file"
      continue
    }
    $backup = @{}; foreach ($b in (Import-Csv $file -Encoding UTF8)) { $backup[$b.AspectOid] = $b }
    $cur = @{}; foreach ($x in $rows) { $cur[$x.AspectOid] = $x }
    $changed = @($backup.Keys | Where-Object { $cur.ContainsKey($_) -and $cur[$_].Xml -ne $backup[$_].Xml })
    $added = @($cur.Keys | Where-Object { -not $backup.ContainsKey($_) })
    $missing = @($backup.Keys | Where-Object { -not $cur.ContainsKey($_) })
    "== $db backup=$($backup.Count) current=$($cur.Count) changed=$($changed.Count) added=$($added.Count) missing=$($missing.Count)"
    foreach ($k in $changed) { $b = $backup[$k]; "  changed $($b.UserId) | $($b.ContextId) | $($b.Name) | $($b.Xml.Length) -> $($cur[$k].Xml.Length)" }
    foreach ($k in $added) { "  added $k $($cur[$k].UserId) $($cur[$k].ContextId) $($cur[$k].Name) len=$($cur[$k].Xml.Length)" }
    foreach ($k in $missing) { "  missing $k" }
    if ($DumpDir) {
      foreach ($k in $changed) {
        $b = $backup[$k]; $n = ($db + '_' + $b.UserId + '_' + $b.ContextId + '_' + $b.Name) -replace '[^\w\-]', '_'
        Set-Content -LiteralPath (Join-Path $DumpDir "$n.before.xml") -Value $b.Xml -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $DumpDir "$n.now.xml") -Value $cur[$k].Xml -Encoding UTF8
      }
    }
    if ($Mode -eq 'Restore' -and $changed.Count) {
      $tx = $cn.BeginTransaction()
      foreach ($k in $changed) {
        $u = $cn.CreateCommand(); $u.Transaction = $tx
        $u.CommandText = 'UPDATE ModelDifferenceAspect SET Xml = @x WHERE Oid = @o'
        [void]$u.Parameters.Add('@x', [System.Data.SqlDbType]::NVarChar, -1); $u.Parameters['@x'].Value = $backup[$k].Xml
        [void]$u.Parameters.AddWithValue('@o', [guid]$k)
        if ($u.ExecuteNonQuery() -ne 1) { $tx.Rollback(); throw "update failed for $k" }
      }
      $tx.Commit(); "  restored $($changed.Count) aspects"
    }
  } finally { $cn.Close() }
}
