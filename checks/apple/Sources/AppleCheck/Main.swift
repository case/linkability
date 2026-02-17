import Foundation

// Minimal Apple check: reads zone names from stdin, tests each with NSDataDetector,
// outputs JSON results to stdout.

struct AppleCheck {
    static func main() {
        let input = readLine(strippingNewline: false) ?? ""
        let allInput: String
        if let data = FileHandle.standardInput.readDataToEndOfFile() as Data?,
           let rest = String(data: data, encoding: .utf8) {
            allInput = input + rest
        } else {
            allInput = input
        }

        let zones = allInput
            .components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }

        let detector = try! NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        var results: [String: Bool] = [:]

        for zone in zones {
            let testText = "nic.\(zone)"
            let range = NSRange(location: 0, length: testText.utf16.count)
            let matches = detector.matches(in: testText, options: [], range: range)
            results[zone] = !matches.isEmpty
        }

        let output: [String: Any] = ["results": results]
        if let jsonData = try? JSONSerialization.data(withJSONObject: output, options: []),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            print(jsonString)
        }
    }
}

AppleCheck.main()
