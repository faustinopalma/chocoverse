#Requires -Version 7.4
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$FilePath,
    [string[]]$Arguments = @()
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\CommandJournal.ps1"
Invoke-RecordedNative -FilePath $FilePath -Arguments $Arguments
