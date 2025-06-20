import Foundation
import Punycode

public func downloadIanaZones() {
    let url = URL(string: "https://data.iana.org/TLD/tlds-alpha-by-domain.txt")!

    let task = URLSession.shared.dataTask(with: url) { data, response, error in
        guard let data = data, error == nil else {
            print("Error downloading zones: \(error?.localizedDescription ?? "Unknown error")")
            exit(1)
        }

        let filename = "Data-Zones/zones-full.txt"
        let fileURL = URL(fileURLWithPath: filename)

        // Convert downloaded data to string
        guard let newContent = String(data: data, encoding: .utf8) else {
            print("Error: Could not decode downloaded data as UTF-8")
            exit(1)
        }

        // Extract content after first line (skip version/timestamp line)
        let newLines = newContent.components(separatedBy: .newlines)
        let newZoneData = Array(newLines.dropFirst()).joined(separator: "\n")

        // Check if file exists and compare zone data (excluding first line)
        var shouldUpdate = true
        if FileManager.default.fileExists(atPath: filename) {
            do {
                let existingContent = try String(contentsOf: fileURL, encoding: .utf8)
                let existingLines = existingContent.components(separatedBy: .newlines)
                let existingZoneData = Array(existingLines.dropFirst()).joined(separator: "\n")

                if newZoneData == existingZoneData {
                    shouldUpdate = false
                    print("Zone data unchanged (only timestamp updated). Skipping file write.")
                }
            } catch {
                print(
                    "Warning: Could not read existing file, will update: \(error.localizedDescription)"
                )
            }
        }

        if shouldUpdate {
            do {
                try data.write(to: fileURL)
                print("Zones updated and saved to \(filename)")
            } catch {
                print("Error saving file: \(error.localizedDescription)")
                exit(1)
            }
        }

        exit(0)
    }

    task.resume()
}

// This assumes you have the ZoneDB CLI installed, it's not downloading this info from the Internet.
// FIXME: Rename this so that it doesn't imply that it's "downloading" something from the Internet.
public func downloadBrandZones() {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
    process.arguments = [
        "zonedb", "--tlds", "--delegated", "--tags", "brand", "--json", "--dir",
        "\(homeDir)/git/domainr/zonedb",
    ]

    let pipe = Pipe()
    let errorPipe = Pipe()
    process.standardOutput = pipe
    process.standardError = errorPipe

    do {
        try process.run()
        process.waitUntilExit()

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()

        // Try stdout first, then stderr if stdout is empty
        let jsonData = data.isEmpty ? errorData : data

        guard !jsonData.isEmpty else {
            print("Error: No output from zonedb command")
            return
        }

        // Parse JSON output
        do {
            if let json = try JSONSerialization.jsonObject(with: jsonData, options: [])
                as? [String: Any],
                let zonesObject = json["zones"] as? [String: Any],
                let filteredZones = zonesObject["filtered"] as? [String]
            {

                // Save zones to file
                let zonesContent = filteredZones.sorted().joined(separator: "\n")
                let fileURL = URL(fileURLWithPath: "Data-Zones/zones-brand.txt")

                do {
                    try zonesContent.write(to: fileURL, atomically: true, encoding: .utf8)
                    print(
                        "Brand zones saved to Data-Zones/zones-brand.txt (\(filteredZones.count) zones)"
                    )
                } catch {
                    print("Error saving brand zones file: \(error.localizedDescription)")
                }
            } else {
                print("Error: Invalid JSON format from zonedb command")
            }
        } catch {
            print("Error parsing JSON from zonedb: \(error.localizedDescription)")
        }

    } catch {
        print("Error running zonedb command: \(error.localizedDescription)")
    }
}

public func readZones(from filename: String) -> [String] {
    guard let data = FileManager.default.contents(atPath: filename),
        let content = String(data: data, encoding: .utf8)
    else {
        print("Error reading file: \(filename)")
        return []
    }

    return
        content
        .components(separatedBy: .newlines)
        .compactMap { line in
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty && !trimmed.hasPrefix("#") else { return nil }

            let lowercased = trimmed.lowercased()

            // Convert xn-- (Punycode) domains to Unicode using PunycodeSwift
            if lowercased.hasPrefix("xn--") {
                if let unicode = lowercased.idnaDecoded {
                    return unicode
                }
                // If conversion fails, return the original
                return lowercased
            }

            return lowercased
        }
}
