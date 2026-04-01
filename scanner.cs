using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;

class csproj_scanner
{
    static readonly (string Label, string Pattern)[] Patterns = new[]
    {
        ("Exec command",           @"<Exec\s+Command="),
        ("PowerShell launch",      @"powershell(\.exe)?"),
        ("VBScript/cscript",       @"(cscript|wscript|\.vbs)"),
        ("Writes to TEMP",         @"%TEMP%|%tmp%|\$env:TEMP|\$env:TMP"),
        ("Base64 blob",            @"[A-Za-z0-9+/]{200,}={0,2}"),
        ("ExecutionPolicy Bypass", @"ExecutionPolicy\s+Bypass"),
        ("cmd.exe shell",          @"cmd(\.exe)?\s+/[cCkK]"),
        ("LOLBin",                 @"(mshta|rundll32|regsvr32)(\.exe)?"),
        ("certutil abuse",         @"certutil(\.exe)?"),
        ("bitsadmin abuse",        @"bitsadmin(\.exe)?"),
        ("IEX/Invoke-Expression",  @"(Invoke-Expression|iex\s*[\(\$])"),
        ("Download call",          @"(DownloadFile|DownloadString|WebClient|Invoke-WebRequest)"),
        ("Hidden window",          @"WindowStyle\s+Hidden|CreateNoWindow|0,\s*False"),
        ("ADODB stream",           @"ADODB\.(Stream|Recordset)"),
        ("MSXml2 base64 trick",    @"MSXml2\.DOMDocument"),
        ("FileSystemObject",       @"Scripting\.FileSystemObject"),
        ("WScript.Shell",          @"WScript\.Shell"),
        ("Temp file drop",         @"%[Tt][Ee][Mm][Pp]%\\[A-Za-z0-9]{6,}\.(vbs|ps1|bat|cmd)"),
        ("UsingTask inline",       @"<UsingTask\b"),
    };

    static void Main()
    {
        EnsureAdmin();

        var scanRoots = GetUserRoots();

        if (scanRoots.Count == 0)
        {
            Console.WriteLine("No user folders found.");
            Pause();
            return;
        }

        Console.WriteLine("Scanning:");
        foreach (var root in scanRoots)
            Console.WriteLine(root);

        Console.WriteLine();

        var infected = new List<string>();
        int total = 0;

        foreach (var root in scanRoots)
        {
            foreach (var file in Walk(root))
            {
                total++;
                var hits = GetHits(file);

                if (hits.Count > 0)
                {
                    infected.Add(file);
                    WriteLineColor("[INFECTED] " + file, ConsoleColor.Red);
                    foreach (var hit in hits)
                    {
                        Console.WriteLine("line " + hit.Line + " [" + hit.Label + "]");
                        Console.WriteLine(hit.Snippet);
                    }
                    Console.WriteLine();
                }
                else
                {
                    WriteLineColor("[CLEAN] " + file, ConsoleColor.Green);
                }
            }
        }

        Console.WriteLine();
        Console.WriteLine(total + " file(s) scanned, " + infected.Count + " infected.");
        Console.WriteLine();

        if (infected.Count == 0)
        {
            Console.WriteLine("Nothing to clean.");
            Pause();
            return;
        }

        Console.WriteLine("Files with hits:");
        foreach (var f in infected)
            Console.WriteLine(f);

        Console.WriteLine();
        Console.Write("Clean these files? (yes/no): ");
        string answer = (Console.ReadLine() ?? "").Trim().ToLowerInvariant();

        if (answer == "yes" || answer == "y")
        {
            Console.WriteLine();
            foreach (var f in infected)
                CleanFile(f);
        }
        else
        {
            Console.WriteLine("No changes made.");
        }

        Pause();
    }

    static void EnsureAdmin()
    {
        if (IsAdministrator())
            return;

        try
        {
            var exePath = Process.GetCurrentProcess().MainModule.FileName;
            var startInfo = new ProcessStartInfo
            {
                FileName = exePath,
                UseShellExecute = true,
                Verb = "runas"
            };
            Process.Start(startInfo);
        }
        catch
        {
            Console.WriteLine("Administrator access is required.");
            Pause();
        }

        Environment.Exit(0);
    }

    static bool IsAdministrator()
    {
        using (var identity = WindowsIdentity.GetCurrent())
        {
            var principal = new WindowsPrincipal(identity);
            return principal.IsInRole(WindowsBuiltInRole.Administrator);
        }
    }

    static List<string> GetUserRoots()
    {
        var roots = new List<string>();
        string usersPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "..");
        usersPath = Path.GetFullPath(usersPath);

        if (!Directory.Exists(usersPath))
            return roots;

        string[] dirs;
        try
        {
            dirs = Directory.GetDirectories(usersPath);
        }
        catch
        {
            return roots;
        }

        foreach (var dir in dirs)
        {
            string name = Path.GetFileName(dir);

            if (string.Equals(name, "All Users", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(name, "Default", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(name, "Default User", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(name, "Public", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            roots.Add(dir);
        }

        return roots;
    }

    static List<Hit> GetHits(string path)
    {
        var hits = new List<Hit>();

        try
        {
            var lines = File.ReadAllLines(path, Encoding.UTF8);
            var seen = new HashSet<string>();

            for (int i = 0; i < lines.Length; i++)
            {
                foreach (var pattern in Patterns)
                {
                    if (!Regex.IsMatch(lines[i], pattern.Pattern, RegexOptions.IgnoreCase | RegexOptions.Singleline))
                        continue;

                    string key = pattern.Label + ":" + i;
                    if (!seen.Add(key))
                        continue;

                    string snippet = lines[i].Trim();
                    if (snippet.Length > 110)
                        snippet = snippet.Substring(0, 110) + "...";

                    hits.Add(new Hit
                    {
                        Label = pattern.Label,
                        Line = i + 1,
                        Snippet = snippet
                    });
                }
            }
        }
        catch
        {
        }

        return hits;
    }

    static void CleanFile(string path)
    {
        try
        {
            string original = File.ReadAllText(path, Encoding.UTF8);

            string cleaned = Regex.Replace(
                original,
                @"<Target\b[^>]*>[\s\S]*?</Target>",
                delegate (Match match)
                {
                    string block = match.Value;
                    foreach (var pattern in Patterns)
                    {
                        if (Regex.IsMatch(block, pattern.Pattern, RegexOptions.IgnoreCase))
                            return string.Empty;
                    }
                    return block;
                },
                RegexOptions.IgnoreCase
            );

            if (cleaned == original)
            {
                WriteLineColor("[SKIP] " + path, ConsoleColor.Yellow);
                return;
            }

            string backup = path + ".bak";
            File.Copy(path, backup, true);
            File.WriteAllText(path, cleaned, Encoding.UTF8);

            WriteLineColor("[CLEANED] " + path, ConsoleColor.Green);
            Console.WriteLine("Backup: " + backup);
        }
        catch (Exception ex)
        {
            WriteLineColor("[ERROR] " + path + " - " + ex.Message, ConsoleColor.Red);
        }
    }

    static IEnumerable<string> Walk(string root)
    {
        var queue = new Queue<string>();
        queue.Enqueue(root);

        while (queue.Count > 0)
        {
            string dir = queue.Dequeue();

            string[] files = Array.Empty<string>();
            try
            {
                files = Directory.GetFiles(dir);
            }
            catch
            {
            }

            foreach (var f in files)
            {
                string name = Path.GetFileName(f);

                if (name.EndsWith(".csproj", StringComparison.OrdinalIgnoreCase) ||
                    name.EndsWith(".csproj.tmp", StringComparison.OrdinalIgnoreCase))
                {
                    if (!name.EndsWith(".csproj.bak", StringComparison.OrdinalIgnoreCase))
                        yield return f;
                }
            }

            string[] subs = Array.Empty<string>();
            try
            {
                subs = Directory.GetDirectories(dir);
            }
            catch
            {
            }

            foreach (var s in subs)
                queue.Enqueue(s);
        }
    }

    static void WriteLineColor(string text, ConsoleColor color)
    {
        Console.ForegroundColor = color;
        Console.WriteLine(text);
        Console.ResetColor();
    }

    static void Pause()
    {
        Console.WriteLine();
        Console.Write("Press Enter to exit...");
        Console.ReadLine();
    }

    class Hit
    {
        public string Label;
        public int Line;
        public string Snippet;
    }
}