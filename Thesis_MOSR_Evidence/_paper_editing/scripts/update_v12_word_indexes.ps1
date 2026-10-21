$ErrorActionPreference = 'Stop'

$documentPath = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v12.docx'
$backupPath = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\_paper_editing\qa\v12_before_index_refresh.docx'

Copy-Item -LiteralPath $documentPath -Destination $backupPath -Force

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($documentPath, $false, $false, $false)

    if ($document.ReadOnly) {
        throw 'The v12 document opened read-only, so indexes could not be refreshed safely.'
    }

    foreach ($toc in @($document.TablesOfContents)) {
        $toc.Update()
    }
    foreach ($tof in @($document.TablesOfFigures)) {
        $tof.Update()
    }

    foreach ($storyType in @(
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17
    )) {
        try {
            $range = $document.StoryRanges.Item($storyType)
            while ($null -ne $range) {
                $null = $range.Fields.Update()
                $range = $range.NextStoryRange
            }
        } catch {
            # This story type is not present in the document.
        }
    }

    $document.Repaginate()
    foreach ($toc in @($document.TablesOfContents)) {
        $toc.UpdatePageNumbers()
    }
    foreach ($tof in @($document.TablesOfFigures)) {
        $tof.UpdatePageNumbers()
    }
    $document.Repaginate()

    $tocCount = $document.TablesOfContents.Count
    $tofCount = $document.TablesOfFigures.Count
    $fieldCount = $document.Fields.Count
    $pageCount = $document.ComputeStatistics(2)
    $document.Save()

    [pscustomobject]@{
        Document = $documentPath
        Backup = $backupPath
        TablesOfContents = $tocCount
        TablesOfFigures = $tofCount
        MainStoryFields = $fieldCount
        WordPages = $pageCount
    } | ConvertTo-Json -Depth 2
}
finally {
    if ($null -ne $document) {
        try { $document.Close($false) } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
