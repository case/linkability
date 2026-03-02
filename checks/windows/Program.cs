// Minimal Windows check: reads zone names from stdin, tests each with
// RichEdit EM_AUTOURLDETECT, outputs JSON results to stdout.
//
// Uses the RICHEDIT50W control (msftedit.dll) in a message-only window
// so no GUI or display is needed — suitable for headless CI runners.
// A message pump (PeekMessage/DispatchMessage) is required because
// RichEdit processes URL detection asynchronously via posted messages.

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

class WindowsCheck
{
    // Window messages
    const uint WM_SETTEXT = 0x000C;
    const uint WM_USER = 0x0400;
    const uint EM_SETSEL = 0x00B1;
    const uint EM_AUTOURLDETECT = WM_USER + 91;
    const uint EM_GETCHARFORMAT = WM_USER + 58;

    // EM_AUTOURLDETECT flags
    const int AURL_ENABLEURL = 1;
    const int AURL_ENABLEEAURLS = 8;

    // EM_GETCHARFORMAT flags
    const int SCF_SELECTION = 0x0001;

    // CHARFORMAT2W masks and effects
    const uint CFM_LINK = 0x00000020;
    const uint CFE_LINK = 0x00000020;

    // CHARFORMAT2W struct size (always 116 bytes, all platforms)
    const int CHARFORMAT2W_SIZE = 116;
    // Field offsets within CHARFORMAT2W
    const int CF_OFFSET_CBSIZE = 0;
    const int CF_OFFSET_DWMASK = 4;
    const int CF_OFFSET_DWEFFECTS = 8;

    // Window styles
    const uint WS_CHILD = 0x40000000;

    // PeekMessage flags
    const uint PM_REMOVE = 0x0001;

    // HWND_MESSAGE: message-only window (invisible, no display needed)
    static readonly IntPtr HWND_MESSAGE = new IntPtr(-3);

    [StructLayout(LayoutKind.Sequential)]
    struct MSG
    {
        public IntPtr hwnd;
        public uint message;
        public IntPtr wParam;
        public IntPtr lParam;
        public uint time;
        public int pt_x;
        public int pt_y;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr LoadLibrary(string lpFileName);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateWindowEx(
        uint dwExStyle, string lpClassName, string lpWindowName, uint dwStyle,
        int x, int y, int nWidth, int nHeight,
        IntPtr hWndParent, IntPtr hMenu, IntPtr hInstance, IntPtr lpParam);

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool DestroyWindow(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, string lParam);

    [DllImport("user32.dll")]
    static extern bool PeekMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin,
        uint wMsgFilterMax, uint wRemoveMsg);

    [DllImport("user32.dll")]
    static extern bool TranslateMessage(ref MSG lpMsg);

    [DllImport("user32.dll")]
    static extern IntPtr DispatchMessage(ref MSG lpMsg);

    /// <summary>
    /// Drain the message queue so RichEdit can process any pending URL
    /// detection messages posted after text was set.
    /// </summary>
    static void PumpMessages()
    {
        while (PeekMessage(out MSG msg, IntPtr.Zero, 0, 0, PM_REMOVE))
        {
            TranslateMessage(ref msg);
            DispatchMessage(ref msg);
        }
    }

    /// <summary>
    /// Test whether a given text string is detected as a link by checking
    /// CFE_LINK on the first character's formatting.
    /// </summary>
    static bool TestLink(IntPtr hwnd, IntPtr pCf, string text)
    {
        // Set the control text — triggers URL detection scan.
        SendMessage(hwnd, WM_SETTEXT, IntPtr.Zero, text);

        // Pump messages to let RichEdit process the URL detection.
        PumpMessages();

        // Select just the first character (avoids mixed-format ambiguity
        // if only part of the text is detected as a URL).
        SendMessage(hwnd, EM_SETSEL, IntPtr.Zero, (IntPtr)1);

        // Zero the buffer and set required fields.
        for (int i = 0; i < CHARFORMAT2W_SIZE; i++)
            Marshal.WriteByte(pCf, i, 0);
        Marshal.WriteInt32(pCf, CF_OFFSET_CBSIZE, CHARFORMAT2W_SIZE);

        // Query character format for the selection.
        SendMessage(hwnd, EM_GETCHARFORMAT, (IntPtr)SCF_SELECTION, pCf);

        // Read dwMask and dwEffects.
        int mask = Marshal.ReadInt32(pCf, CF_OFFSET_DWMASK);
        int effects = Marshal.ReadInt32(pCf, CF_OFFSET_DWEFFECTS);
        return (mask & CFM_LINK) != 0 && (effects & CFE_LINK) != 0;
    }

    static void Main()
    {
        // Use UTF-8 for stdin/stdout to handle IDN zone names (e.g. 日本).
        Console.InputEncoding = Encoding.UTF8;
        Console.OutputEncoding = Encoding.UTF8;

        // Load msftedit.dll to register the RICHEDIT50W window class.
        IntPtr hMod = LoadLibrary("msftedit.dll");
        if (hMod == IntPtr.Zero)
        {
            Console.Error.WriteLine("Error: Could not load msftedit.dll");
            Environment.Exit(1);
        }

        // Create an invisible RichEdit control as a child of HWND_MESSAGE.
        IntPtr hwnd = CreateWindowEx(
            0, "RICHEDIT50W", "", WS_CHILD,
            0, 0, 100, 100,
            HWND_MESSAGE, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);

        if (hwnd == IntPtr.Zero)
        {
            Console.Error.WriteLine("Error: Could not create RichEdit control");
            Environment.Exit(1);
        }

        // Enable automatic URL detection.
        IntPtr urlResult = SendMessage(hwnd, EM_AUTOURLDETECT,
            (IntPtr)(AURL_ENABLEURL | AURL_ENABLEEAURLS), IntPtr.Zero);
        Console.Error.WriteLine($"EM_AUTOURLDETECT returned: {urlResult}");

        // Allocate CHARFORMAT2W buffer once and reuse.
        IntPtr pCf = Marshal.AllocHGlobal(CHARFORMAT2W_SIZE);

        // Canary tests: verify the detection mechanism works with known URLs.
        // These results go to stderr for diagnostics, not into the zone results.
        string[] canaries = {
            "http://example.com",   // Scheme-prefixed (always detected)
            "https://example.com",  // HTTPS variant
            "www.example.com",      // www-prefixed (RichEdit 3.0+)
            "ftp.example.com",      // ftp-prefixed (RichEdit 3.0+)
            "example.com",          // Bare domain with .com
            "nic.com",              // Our actual test format
            "nic.xyz",              // New gTLD test
        };
        Console.Error.WriteLine("Canary tests:");
        foreach (string canary in canaries)
        {
            bool linked = TestLink(hwnd, pCf, canary);
            Console.Error.WriteLine($"  {canary,-30} => {(linked ? "LINKED" : "not linked")}");
        }

        // Process zones from stdin.
        var results = new Dictionary<string, bool>();
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            line = line.Trim();
            if (string.IsNullOrEmpty(line))
                continue;

            results[line] = TestLink(hwnd, pCf, $"nic.{line}");
        }

        Marshal.FreeHGlobal(pCf);
        DestroyWindow(hwnd);

        // Output JSON matching the Apple check contract.
        var output = new Dictionary<string, object> { ["results"] = results };
        string json = JsonSerializer.Serialize(output);
        Console.WriteLine(json);
    }
}
