# Renders the logo from the drawing code in src/KnightSight.cs, so the README and the
# program show the same picture: logo.png cut to its ink for the banners, and icon.png
# on white.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing, System.Web.Extensions
$refs = @(
    [System.Windows.Forms.Form].Assembly.Location
    [System.Drawing.Bitmap].Assembly.Location
    [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location
)
$source = Join-Path $PSScriptRoot '..\..\src\KnightSight.cs'
Add-Type -TypeDefinition (Get-Content -Raw -Encoding UTF8 $source) -ReferencedAssemblies $refs

$full = [KnightSight.Logo]::Render(1024)
$left = $full.Width; $top = $full.Height; $right = -1; $bottom = -1
for ($y = 0; $y -lt $full.Height; $y++) {
    for ($x = 0; $x -lt $full.Width; $x++) {
        if ($full.GetPixel($x, $y).A -gt 8) {
            if ($x -lt $left) { $left = $x }; if ($x -gt $right) { $right = $x }
            if ($y -lt $top) { $top = $y }; if ($y -gt $bottom) { $bottom = $y }
        }
    }
}
$ink = New-Object System.Drawing.Rectangle $left, $top, ($right - $left + 1), ($bottom - $top + 1)
$full.Clone($ink, $full.PixelFormat).Save((Join-Path $PSScriptRoot 'logo.png'), [System.Drawing.Imaging.ImageFormat]::Png)

$icon = New-Object System.Drawing.Bitmap 512, 512
$g = [System.Drawing.Graphics]::FromImage($icon)
$g.Clear([System.Drawing.Color]::White)
$g.DrawImage([KnightSight.Logo]::Render(512), 0, 0, 512, 512)
$g.Dispose()
$icon.Save((Join-Path $PSScriptRoot 'icon.png'), [System.Drawing.Imaging.ImageFormat]::Png)
"logo.png $($ink.Width) x $($ink.Height), icon.png 512 x 512"
