#Requires -Version 7.4
<#
.SYNOPSIS
Capture a verified lab document from Edge LaQuantistica, excluding browser chrome.
.DESCRIPTION
Uses window-only PrintWindow, never the desktop. An exact visible document title and expected feature text
are required. Crop offsets are document-relative pixels; review the resulting image before publication.
Accessibility text can be stale during navigation, so wait for rendering and inspect the actual pixels.
Account headers, deployment identities and unrelated data must not be included in published screenshots.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$DocumentName,
    [Parameter(Mandatory)][string]$ExpectedText,
    [Parameter(Mandatory)][string]$OutputPath,
    [ValidateRange(0, 1600)][int]$CropTop = 0,
    [ValidateRange(0, 1600)][int]$CropLeft = 0,
    [ValidateRange(0, 1600)][int]$CropRight = 0,
    [ValidateRange(0, 1600)][int]$CropBottom = 0
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\CommandJournal.ps1"
$invocation = [guid]::NewGuid().ToString()
Write-CommandRecord -Operation 'Save-LabScreenshot' -Status Started -InvocationId $invocation `
    -Details @{
        document = $DocumentName; expectedText = $ExpectedText
        crop = @($CropLeft, $CropTop, $CropRight, $CropBottom)
    }
try {
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing
    $windows = @(Get-Process msedge | Where-Object { $_.MainWindowTitle -like '*LaQuantistica*' })
    if ($windows.Count -ne 1) { throw 'Expected one visible Edge LaQuantistica window.' }
    $root = [Windows.Automation.AutomationElement]::FromHandle($windows[0].MainWindowHandle)
    $scope = [Windows.Automation.TreeScope]::Descendants
    $documents = @($root.FindAll($scope, [Windows.Automation.PropertyCondition]::new(
        [Windows.Automation.AutomationElement]::ControlTypeProperty,
        [Windows.Automation.ControlType]::Document
    )) | Where-Object { $_.Current.Name -eq $DocumentName -and -not $_.Current.IsOffscreen })
    if ($documents.Count -ne 1) { throw 'Expected exactly one visible document with the requested title.' }
    $document = $documents[0]
    $matches = @($document.FindAll($scope, [Windows.Automation.Condition]::TrueCondition) |
        Where-Object { $_.Current.Name.Contains($ExpectedText, [StringComparison]::OrdinalIgnoreCase) })
    if (-not $matches) { throw 'Expected feature text is absent; refusing a loading/error-page screenshot.' }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LabFeatureCapture {
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
}
'@
    $windowBounds = $root.Current.BoundingRectangle
    $bounds = $document.Current.BoundingRectangle
    $documentLeft = [math]::Max(0, [int]($bounds.Left - $windowBounds.Left))
    $left = $documentLeft + $CropLeft
    $top = [math]::Max(0, [int]($bounds.Top - $windowBounds.Top)) + $CropTop
    $width = [math]::Min([int]$bounds.Width - $CropLeft - $CropRight,
        [int]$windowBounds.Width - $left)
    $height = [math]::Min([int]$bounds.Height - $CropTop - $CropBottom,
        [int]$windowBounds.Height - $top)
    if ($width -lt 300 -or $height -lt 200) { throw 'Document capture bounds are unexpectedly small.' }
    $bitmap = [Drawing.Bitmap]::new([int]$windowBounds.Width, [int]$windowBounds.Height)
    try {
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $hdc = $graphics.GetHdc()
        try {
            if (-not [LabFeatureCapture]::PrintWindow($windows[0].MainWindowHandle, $hdc, 2)) {
                throw 'Window capture failed; no desktop capture fallback is allowed.'
            }
        }
        finally { $graphics.ReleaseHdc($hdc); $graphics.Dispose() }
        $crop = $bitmap.Clone([Drawing.Rectangle]::new($left, $top, $width, $height), $bitmap.PixelFormat)
        try {
            $path = [IO.Path]::GetFullPath($OutputPath)
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
            $crop.Save($path, [Drawing.Imaging.ImageFormat]::Png)
        }
        finally { $crop.Dispose() }
    }
    finally { $bitmap.Dispose() }
    Write-CommandRecord -Operation 'Save-LabScreenshot' -Status Succeeded -InvocationId $invocation `
        -Details @{ document = $DocumentName; width = $width; height = $height; output = $path }
    $path
}
catch {
    Write-CommandRecord -Operation 'Save-LabScreenshot' -Status Failed -InvocationId $invocation `
        -Details @{ errorType = $_.Exception.GetType().FullName }
    throw
}
