$minimumMajorVersion = 5

if ($PSVersionTable.PSVersion.Major -lt $minimumMajorVersion) {
    exit 10
}

exit 0
