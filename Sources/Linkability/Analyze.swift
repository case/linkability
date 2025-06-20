import Foundation

// The actual Apple stdlib functionality (NSDataDetector) to check if the text is linked (or not)
public func isZoneLinked(_ zone: String) -> Bool {
    let detector = try! NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
    let testText = "nic.\(zone)"
    let range = NSRange(location: 0, length: testText.utf16.count)
    let matches = detector.matches(in: testText, options: [], range: range)
    return !matches.isEmpty
}

// Where the simple math happens, to create the summary info
public struct ZoneSummary {
    let totalZones: Int
    let ccTLDCount: Int
    let gTLDCount: Int
    let gTLDBrandCount: Int
    let gTLDNonBrandCount: Int
    let ccTLDLinked: Int
    let gTLDLinked: Int
    let gTLDBrandLinked: Int
    let gTLDNonBrandLinked: Int

    var ccTLDPercentageOfTotal: Double {
        totalZones > 0 ? Double(ccTLDCount) / Double(totalZones) * 100 : 0
    }

    var gTLDPercentageOfTotal: Double {
        totalZones > 0 ? Double(gTLDCount) / Double(totalZones) * 100 : 0
    }

    var gTLDBrandPercentageOfGTLD: Double {
        gTLDCount > 0 ? Double(gTLDBrandCount) / Double(gTLDCount) * 100 : 0
    }

    var gTLDBrandPercentageOfTotal: Double {
        totalZones > 0 ? Double(gTLDBrandCount) / Double(totalZones) * 100 : 0
    }

    var ccTLDLinkablePercentage: Double {
        ccTLDCount > 0 ? Double(ccTLDLinked) / Double(ccTLDCount) * 100 : 0
    }

    var gTLDNonBrandLinkablePercentage: Double {
        gTLDNonBrandCount > 0 ? Double(gTLDNonBrandLinked) / Double(gTLDNonBrandCount) * 100 : 0
    }

    var ccTLDLinkedPercentageOfTotal: Double {
        totalZones > 0 ? Double(ccTLDLinked) / Double(totalZones) * 100 : 0
    }

    var gTLDNonBrandLinkedPercentageOfTotal: Double {
        totalZones > 0 ? Double(gTLDNonBrandLinked) / Double(totalZones) * 100 : 0
    }

    var gTLDLinkablePercentage: Double {
        gTLDCount > 0 ? Double(gTLDLinked) / Double(gTLDCount) * 100 : 0
    }

    var gTLDLinkedPercentageOfTotal: Double {
        totalZones > 0 ? Double(gTLDLinked) / Double(totalZones) * 100 : 0
    }

    var totalLinkedZones: Int {
        ccTLDLinked + gTLDLinked
    }

    var totalLinkedPercentage: Double {
        totalZones > 0 ? Double(totalLinkedZones) / Double(totalZones) * 100 : 0
    }
}

public func analyzeSummary() -> ZoneSummary? {
    let zones = readZones(from: "Data-Zones/zones-full.txt")
    if zones.isEmpty {
        return nil
    }

    let brandZones = Set(readZones(from: "Data-Zones/zones-brand.txt"))

    var ccTLDCount = 0
    var gTLDCount = 0
    var gTLDBrandCount = 0
    var gTLDNonBrandCount = 0
    var ccTLDLinked = 0
    var gTLDLinked = 0
    var gTLDBrandLinked = 0
    var gTLDNonBrandLinked = 0

    for zone in zones {
        let isLinked = isZoneLinked(zone)

        if zone.count == 2 && zone.allSatisfy({ $0.isASCII }) {
            ccTLDCount += 1
            if isLinked { ccTLDLinked += 1 }
        } else {
            gTLDCount += 1
            if isLinked { gTLDLinked += 1 }
            if brandZones.contains(zone) {
                gTLDBrandCount += 1
                if isLinked { gTLDBrandLinked += 1 }
            } else {
                gTLDNonBrandCount += 1
                if isLinked { gTLDNonBrandLinked += 1 }
            }
        }
    }

    return ZoneSummary(
        totalZones: zones.count,
        ccTLDCount: ccTLDCount,
        gTLDCount: gTLDCount,
        gTLDBrandCount: gTLDBrandCount,
        gTLDNonBrandCount: gTLDNonBrandCount,
        ccTLDLinked: ccTLDLinked,
        gTLDLinked: gTLDLinked,
        gTLDBrandLinked: gTLDBrandLinked,
        gTLDNonBrandLinked: gTLDNonBrandLinked
    )
}

public enum ZoneType {
    case ccTLD
    case gTLDAll
    case gTLDBrand
    case gTLDNonBrand
}

public func getLinkedZones(type: ZoneType) {
    let zones = readZones(from: "Data-Zones/zones-full.txt")
    if zones.isEmpty {
        print("No zones found in Data-Zones/zones-full.txt")
        return
    }

    let brandZones = Set(readZones(from: "Data-Zones/zones-brand.txt"))
    var linkedZones: [String] = []

    for zone in zones {
        let isLinked = isZoneLinked(zone)
        if !isLinked { continue }

        let isCCTLD = zone.count == 2 && zone.allSatisfy({ $0.isASCII })
        let isBrand = brandZones.contains(zone)

        switch type {
        case .ccTLD:
            if isCCTLD {
                linkedZones.append(zone)
            }
        case .gTLDAll:
            if !isCCTLD {
                linkedZones.append(zone)
            }
        case .gTLDBrand:
            if !isCCTLD && isBrand {
                linkedZones.append(zone)
            }
        case .gTLDNonBrand:
            if !isCCTLD && !isBrand {
                linkedZones.append(zone)
            }
        }
    }

    let typeDescription =
        switch type {
        case .ccTLD: "ccTLD"
        case .gTLDAll: "gTLD"
        case .gTLDBrand: "brand gTLD"
        case .gTLDNonBrand: "non-brand gTLD"
        }

    let sortedZones = linkedZones.sorted()
    print("\nLinked \(typeDescription) zones (\(sortedZones.count)):")

    if sortedZones.isEmpty {
        print("No linked \(typeDescription) zones found")
    } else {
        print(sortedZones.joined(separator: " "))
    }
}

public func showMissingActiveBrands() {
    print("Checking for delegated brand zones not in root zone file...")

    let zones = readZones(from: "Data-Zones/zones-full.txt")
    if zones.isEmpty {
        print("❌ Error: No zones found in Data-Zones/zones-full.txt")
        return
    }

    // Read brand zones
    let brandZones = Set(readZones(from: "Data-Zones/zones-brand.txt"))
    let rootZones = Set(zones)

    // Find brand zones not in root zone
    let missingBrands = brandZones.subtracting(rootZones)

    print("")
    print("Delegated brand zones missing from root zone file:")
    print("Total delegated brand zones: \(brandZones.count)")
    print("Delegated brands in root zone: \(brandZones.intersection(rootZones).count)")
    print("Delegated brands missing from root zone: \(missingBrands.count)")
    print("")

    if !missingBrands.isEmpty {
        print("Missing delegated brand zones:")
        for brand in missingBrands.sorted() {
            print("  \(brand)")
        }
    } else {
        print("✅ All delegated brand zones are present in the root zone file!")
    }
}

public func testCCTLDBrands() {
    print("Testing: Verifying no ccTLDs are marked as brands...")

    // Read the CSV and check for any "ccTLD,true" combinations
    guard let csvData = FileManager.default.contents(atPath: "Reports/Report-Apple.csv"),
        let csvContent = String(data: csvData, encoding: .utf8)
    else {
        print("❌ Error: Could not read Report.csv")
        return
    }

    let lines = csvContent.components(separatedBy: .newlines)
    var ccTLDBrandCount = 0
    var ccTLDBrandExamples: [String] = []

    for (index, line) in lines.enumerated() {
        // Skip header and empty lines
        guard index > 0 && !line.isEmpty else { continue }

        let columns = line.components(separatedBy: ",")
        guard columns.count >= 4 else { continue }

        let zone = columns[0]
        let type = columns[1]
        let isBrand = columns[2]

        // Check if this is a ccTLD marked as brand
        if type == "ccTLD" && isBrand == "true" {
            ccTLDBrandCount += 1
            if ccTLDBrandExamples.count < 5 {
                ccTLDBrandExamples.append(zone)
            }
        }
    }

    if ccTLDBrandCount == 0 {
        print("✅ PASS: No ccTLDs are marked as brands")
    } else {
        print("❌ FAIL: Found \(ccTLDBrandCount) ccTLD(s) marked as brands:")
        for example in ccTLDBrandExamples {
            print("  - \(example)")
        }
        if ccTLDBrandCount > ccTLDBrandExamples.count {
            print("  ... and \(ccTLDBrandCount - ccTLDBrandExamples.count) more")
        }
    }
}
