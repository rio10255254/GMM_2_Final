$fixedArgs = foreach ($argument in $args) {
    $prefix = '-env:UserInstallation=file://'
    if ($argument.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $profilePath = $argument.Substring($prefix.Length).Replace('\', '/')
        if ($profilePath -match '^[A-Za-z]:/') {
            '-env:UserInstallation=file:///' + $profilePath
        }
        else {
            $argument
        }
    }
    else {
        $argument
    }
}

& 'C:\Program Files\LibreOffice\program\soffice.com' @fixedArgs
exit $LASTEXITCODE
