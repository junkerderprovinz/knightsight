# Builds KnightSight.exe with the .NET Framework compiler that ships with Windows, so
# nothing needs installing. Noto Sans is fetched once and embedded, and the icon is
# drawn by the same code as the logo in the window.
param([string]$Out = (Join-Path $PSScriptRoot 'dist\KnightSight.exe'))
$ErrorActionPreference = 'Stop'

$source = Join-Path $PSScriptRoot 'src\KnightSight.cs'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$work = Join-Path $PSScriptRoot 'obj'
New-Item -ItemType Directory -Force $work, (Split-Path -Parent ([IO.Path]::GetFullPath($Out))) | Out-Null

# Pinned to one commit of the Noto release site, so a rebuild gets the same files.
$noto = 'https://raw.githubusercontent.com/notofonts/notofonts.github.io/5c3913063bb189df4edc94b766584dfb4c04a187/fonts/NotoSans/hinted/ttf'
$fonts = foreach ($name in 'NotoSans-Regular.ttf', 'NotoSans-SemiBold.ttf') {
    $path = Join-Path $work $name
    if (-not (Test-Path $path)) { Invoke-WebRequest "$noto/$name" -OutFile $path -UseBasicParsing }
    $path
}

Add-Type -AssemblyName System.Windows.Forms, System.Drawing, System.Web.Extensions
$refs = @(
    [System.Windows.Forms.Form].Assembly.Location
    [System.Drawing.Bitmap].Assembly.Location
    [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location
)
Add-Type -TypeDefinition (Get-Content -Raw -Encoding UTF8 $source) -ReferencedAssemblies $refs
$sizes = 16, 24, 32, 48, 64, 256
$images = foreach ($size in $sizes) {
    $ms = New-Object System.IO.MemoryStream
    ([KnightSight.Logo]::Render($size)).Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    , $ms.ToArray()
}
$ico = Join-Path $work 'knightsight.ico'
$w = New-Object System.IO.BinaryWriter ([System.IO.File]::Create($ico))
$w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    # Width and height 0 stand for 256.
    $edge = [byte]($sizes[$i] % 256)
    $w.Write($edge); $w.Write($edge); $w.Write([byte]0); $w.Write([byte]0)
    $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$images[$i].Length); $w.Write([uint32]$offset)
    $offset += $images[$i].Length
}
foreach ($image in $images) { $w.Write($image) }
$w.Close()

# AnyCPU without a preference for 32 bit, so one file runs on x64 and on ARM64 alike.
$resources = $fonts | ForEach-Object { "/resource:$_,$(Split-Path $_ -Leaf)" }
& $csc /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 "/out:$Out" "/win32icon:$ico" /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll @resources $source
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
"built $Out"
