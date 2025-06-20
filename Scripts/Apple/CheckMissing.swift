import Foundation
import Punycode

// Read zones-brand.txt
let brandZones = try String(contentsOfFile: "../Data-Zones/zones-brand.txt")
    .components(separatedBy: .newlines)
    .compactMap { line in
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        return trimmed.isEmpty ? nil : trimmed.lowercased()
    }

// Read zones-full.txt with Punycode conversion
let fullZones: [String] = try String(contentsOfFile: "../Data-Zones/zones-full.txt")
    .components(separatedBy: .newlines)
    .compactMap { line in
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty && !trimmed.hasPrefix("#") else { return nil }

        let lowercased = trimmed.lowercased()

        // Convert xn-- domains to Unicode
        if lowercased.hasPrefix("xn--") {
            if let unicode = lowercased.idnaDecoded {
                return unicode
            }
        }

        return lowercased
    }

let fullZonesSet = Set(fullZones)
let brandZonesSet = Set(brandZones)

let missingZones = brandZonesSet.subtracting(fullZonesSet)

print("Total brand zones: \(brandZones.count)")
print("Total full zones: \(fullZones.count)")
print("Brand zones found in full zones: \(brandZonesSet.intersection(fullZonesSet).count)")
print("Brand zones missing from full zones: \(missingZones.count)")

if !missingZones.isEmpty {
    print("\nMissing zones:")
    for zone in missingZones.sorted() {
        print("  \(zone)")
    }
}
