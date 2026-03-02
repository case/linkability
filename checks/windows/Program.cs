// Minimal Windows check: reads zone names from stdin, tests each with
// RichEdit EM_AUTOURLDETECT, outputs JSON results to stdout.
//
// Uses the RICHEDIT50W control (msftedit.dll) in a message-only window
// so no GUI or display is needed — suitable for headless CI runners.

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
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

    // HWND_MESSAGE: message-only window (invisible, no display needed)
    static readonly IntPtr HWND_MESSAGE = new IntPtr(-3);

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

    static void Main()
    {
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
        SendMessage(hwnd, EM_AUTOURLDETECT,
            (IntPtr)(AURL_ENABLEURL | AURL_ENABLEEAURLS), IntPtr.Zero);

        // Allocate CHARFORMAT2W buffer once and reuse for each zone.
        IntPtr pCf = Marshal.AllocHGlobal(CHARFORMAT2W_SIZE);

        var results = new Dictionary<string, bool>();
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            line = line.Trim();
            if (string.IsNullOrEmpty(line))
                continue;

            string testText = $"nic.{line}";

            // Set the control text — triggers URL detection scan.
            SendMessage(hwnd, WM_SETTEXT, IntPtr.Zero, testText);

            // Select all text.
            SendMessage(hwnd, EM_SETSEL, IntPtr.Zero, (IntPtr)(-1));

            // Zero the buffer and set required fields.
            for (int i = 0; i < CHARFORMAT2W_SIZE; i++)
                Marshal.WriteByte(pCf, i, 0);
            Marshal.WriteInt32(pCf, CF_OFFSET_CBSIZE, CHARFORMAT2W_SIZE);
            Marshal.WriteInt32(pCf, CF_OFFSET_DWMASK, (int)CFM_LINK);

            // Query character format for the selection.
            SendMessage(hwnd, EM_GETCHARFORMAT, (IntPtr)SCF_SELECTION, pCf);

            // Read dwEffects and check for CFE_LINK.
            int effects = Marshal.ReadInt32(pCf, CF_OFFSET_DWEFFECTS);
            results[line] = (effects & CFE_LINK) != 0;
        }

        Marshal.FreeHGlobal(pCf);
        DestroyWindow(hwnd);

        // Output JSON matching the Apple check contract.
        var output = new Dictionary<string, object> { ["results"] = results };
        string json = JsonSerializer.Serialize(output);
        Console.WriteLine(json);
    }
}
