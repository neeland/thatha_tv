# Puts a "Thatha TV" icon on the desktop that starts the server and locks the PC
# into the full-screen remote (runs start.ps1). Use -Startup to also run it at sign-in.
param([switch]$Startup)
Set-Location $PSScriptRoot
Add-Type -AssemblyName System.Drawing

# Draw a little TV and save it as a multi-size .ico (PNG images inside an ICO container)
function TvPng([int]$size) {
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $s = $size / 64.0
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(40, 40, 40)), (3 * $s)
    $pen.StartCap = $pen.EndCap = 'Round'
    $g.DrawLine($pen, 22 * $s, 6 * $s, 32 * $s, 16 * $s)      # antennas
    $g.DrawLine($pen, 42 * $s, 6 * $s, 32 * $s, 16 * $s)
    $body = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = 8 * $s; $x = 4 * $s; $y = 16 * $s; $w = 56 * $s; $h = 42 * $s
    $body.AddArc($x, $y, $r * 2, $r * 2, 180, 90)
    $body.AddArc($x + $w - $r * 2, $y, $r * 2, $r * 2, 270, 90)
    $body.AddArc($x + $w - $r * 2, $y + $h - $r * 2, $r * 2, $r * 2, 0, 90)
    $body.AddArc($x, $y + $h - $r * 2, $r * 2, $r * 2, 90, 90)
    $body.CloseFigure()
    $g.FillPath((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(230, 120, 30))), $body)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(30, 60, 110))),
                     10 * $s, 22 * $s, 44 * $s, 30 * $s)       # screen
    $font = New-Object System.Drawing.Font 'Segoe UI', (13 * $s), ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
    $fmt = New-Object System.Drawing.StringFormat
    $fmt.Alignment = $fmt.LineAlignment = 'Center'
    $g.DrawString('TV', $font, [System.Drawing.Brushes]::White,
                  (New-Object System.Drawing.RectangleF (10 * $s), (22 * $s), (44 * $s), (30 * $s)), $fmt)
    $g.Dispose()
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    , $ms.ToArray()
}

$iconPath = Join-Path $PSScriptRoot "thatha_tv.ico"
$sizes = 16, 32, 48, 256
$images = $sizes | ForEach-Object { , (TvPng $_) }
$out = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter $out
$bw.Write([uint16]0); $bw.Write([uint16]1); $bw.Write([uint16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $dim = if ($sizes[$i] -ge 256) { 0 } else { $sizes[$i] }   # 0 means 256 in an ICO entry
    $bw.Write([byte]$dim); $bw.Write([byte]$dim); $bw.Write([byte]0); $bw.Write([byte]0)
    $bw.Write([uint16]1); $bw.Write([uint16]32)
    $bw.Write([uint32]$images[$i].Length); $bw.Write([uint32]$offset)
    $offset += $images[$i].Length
}
$images | ForEach-Object { $bw.Write($_) }
$bw.Flush()
[System.IO.File]::WriteAllBytes($iconPath, $out.ToArray())

function MakeShortcut($path) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
    $lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $lnk.Arguments = "-ExecutionPolicy Bypass -NoProfile -File `"$PSScriptRoot\start.ps1`""
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = "$iconPath,0"
    $lnk.Description = "Start Thatha TV and lock the PC to the remote"
    $lnk.Save()
    Write-Host "Created $path"
}

MakeShortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) "Thatha TV.lnk")

# Move the desktop icon to the top-right corner, away from the usual icons on the left.
# The desktop is a list view inside Explorer, so its item names are read through Explorer's memory.
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class DesktopIcons {
    [DllImport("user32.dll")] static extern IntPtr FindWindow(string c, string n);
    [DllImport("user32.dll")] static extern IntPtr FindWindowEx(IntPtr p, IntPtr a, string c, string n);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint a, bool i, uint pid);
    [DllImport("kernel32.dll")] static extern IntPtr VirtualAllocEx(IntPtr p, IntPtr a, int s, uint t, uint pr);
    [DllImport("kernel32.dll")] static extern bool VirtualFreeEx(IntPtr p, IntPtr a, int s, uint t);
    [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr p, IntPtr a, byte[] b, int s, out IntPtr r);
    [DllImport("kernel32.dll")] static extern bool WriteProcessMemory(IntPtr p, IntPtr a, byte[] b, int s, out IntPtr r);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    const int LVM_GETITEMCOUNT = 0x1004, LVM_GETITEMPOSITION = 0x1010, LVM_SETITEMPOSITION = 0x100F,
              LVM_GETITEMSPACING = 0x1033, LVM_GETITEMTEXTW = 0x1073;

    static IntPtr ListView() {
        IntPtr view = FindWindowEx(FindWindow("Progman", null), IntPtr.Zero, "SHELLDLL_DefView", null);
        IntPtr w = IntPtr.Zero;
        while (view == IntPtr.Zero && (w = FindWindowEx(IntPtr.Zero, w, "WorkerW", null)) != IntPtr.Zero)
            view = FindWindowEx(w, IntPtr.Zero, "SHELLDLL_DefView", null);
        return FindWindowEx(view, IntPtr.Zero, "SysListView32", null);
    }

    // Returns false if the icon is not on the desktop yet
    public static bool MoveTopRight(string name) {
        IntPtr lv = ListView();
        if (lv == IntPtr.Zero) return false;
        uint pid; GetWindowThreadProcessId(lv, out pid);
        IntPtr proc = OpenProcess(0x0038, false, pid);   // VM_OPERATION | VM_READ | VM_WRITE
        IntPtr mem = VirtualAllocEx(proc, IntPtr.Zero, 4096, 0x3000, 0x04);
        try {
            int count = (int)SendMessage(lv, LVM_GETITEMCOUNT, IntPtr.Zero, IntPtr.Zero);
            int target = -1;
            IntPtr r;
            for (int i = 0; i < count && target < 0; i++) {
                // LVITEMW (64-bit): mask, iItem, iSubItem, state, stateMask, pad, pszText @24, cchTextMax @32
                byte[] item = new byte[88];
                BitConverter.GetBytes((long)mem + 512).CopyTo(item, 24);
                BitConverter.GetBytes(260).CopyTo(item, 32);
                WriteProcessMemory(proc, mem, item, item.Length, out r);
                int len = (int)SendMessage(lv, LVM_GETITEMTEXTW, (IntPtr)i, mem);
                byte[] text = new byte[len * 2];
                ReadProcessMemory(proc, mem + 512, text, text.Length, out r);
                if (System.Text.Encoding.Unicode.GetString(text) == name) target = i;
            }
            if (target < 0) return false;
            RECT rc; GetClientRect(lv, out rc);
            int spacing = (int)SendMessage(lv, LVM_GETITEMSPACING, IntPtr.Zero, IntPtr.Zero);
            int cx = spacing & 0xFFFF;
            int x = rc.R - cx, y = 2;
            SendMessage(lv, LVM_SETITEMPOSITION, (IntPtr)target, (IntPtr)((y << 16) | (x & 0xFFFF)));
            return true;
        } finally {
            VirtualFreeEx(proc, mem, 0, 0x8000);
            CloseHandle(proc);
        }
    }
}
"@
for ($i = 0; $i -lt 10 -and -not [DesktopIcons]::MoveTopRight("Thatha TV"); $i++) { Start-Sleep 1 }

if ($Startup) { MakeShortcut (Join-Path ([Environment]::GetFolderPath('Startup')) "Thatha TV.lnk") }
