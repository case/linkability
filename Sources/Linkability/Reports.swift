import Foundation

public func generateCSVReport() {
    let zones = readZones(from: "Data-Zones/zones-full.txt")
    if zones.isEmpty {
        print("No zones found in data-zones/zones-full.txt")
        return
    }

    // Read brand zones
    let brandZones = Set(readZones(from: "Data-Zones/zones-brand.txt"))

    var csvContent = "Zone,Type,Is a Brand?,Is linked?,NIC URL\n"
    // Example rows:
    // ai	cc	FALSE	❌	nic.ai
    // ar	cc	FALSE	✅	nic.ar
    // com	g	FALSE	✅	nic.com

    for zone in zones {
        // Determine the zone type: ccTLD (2 ASCII chars) or gTLD (everything else)
        let type = (zone.count == 2 && zone.allSatisfy { $0.isASCII }) ? "cc" : "g"

        // Check if the zone is in the brand zones list (returns true/false)
        let isBrand = brandZones.contains(zone)

        // Test if "nic.{zone}" is detected as a link by NSDataDetector (returns true/false)
        let isLinked = isZoneLinked(zone)

        // Create the nic.{zone} format for the CSV report links
        let nicUrl = "nic.\(zone)"

        // Convert boolean to emoji symbol for CSV display
        let linkedSymbol = isLinked ? "✅" : "❌"

        // Add this zone's data as a CSV row
        csvContent += "\(zone),\(type),\(isBrand),\(linkedSymbol),\(nicUrl)\n"
    }

    do {
        // Create Reports directory if it doesn't exist
        try FileManager.default.createDirectory(
            atPath: "Reports", withIntermediateDirectories: true, attributes: nil)
        try csvContent.write(toFile: "Reports/Report-Apple.csv", atomically: true, encoding: .utf8)
        print("CSV saved to Reports/Report-Apple.csv")
    } catch {
        print("Error saving CSV: \(error.localizedDescription)")
    }
}

public func generateSummary() {
    guard let summary = analyzeSummary() else {
        print("No zones found in Data-Zones/zones-full.txt")
        return
    }

    // Calculate brand gTLD linkable percentage
    let gTLDBrandLinkablePercentage =
        summary.gTLDBrandCount > 0
        ? Double(summary.gTLDBrandLinked) / Double(summary.gTLDBrandCount) * 100 : 0
    let gTLDBrandLinkedPercentageOfTotal =
        summary.totalZones > 0
        ? Double(summary.gTLDBrandLinked) / Double(summary.totalZones) * 100 : 0

    // Create number formatter for human-readable numbers with commas
    let numberFormatter = NumberFormatter()
    numberFormatter.numberStyle = .decimal

    func formatNumber(_ number: Int) -> String {
        return numberFormatter.string(from: NSNumber(value: number)) ?? "\(number)"
    }

    print("\n** Apple platforms stdlib + auto-linking summary **")
    print("")
    print("Summary of all zones:")
    print("- \(formatNumber(summary.totalZones))\t Total IANA zones")
    print(
        "- \(formatNumber(summary.gTLDCount))\t gTLDs, \(String(format: "%.1f", summary.gTLDPercentageOfTotal))% of total"
    )
    print(
        "- \(formatNumber(summary.gTLDBrandCount))\t - Brand gTLDs, \(String(format: "%.1f", summary.gTLDBrandPercentageOfGTLD))% of gTLDs and \(String(format: "%.1f", summary.gTLDBrandPercentageOfTotal))% of all zones"
    )
    print(
        "- \(formatNumber(summary.ccTLDCount))\t ccTLDs, \(String(format: "%.1f", summary.ccTLDPercentageOfTotal))% of total"
    )
    print("")
    print("Auto-linked zones:")
    print(
        "- \(formatNumber(summary.totalLinkedZones))\t \(String(format: "%.1f", summary.totalLinkedPercentage))% of all zones total"
    )
    print(
        "- \(formatNumber(summary.ccTLDLinked))\t \(String(format: "%.1f", summary.ccTLDLinkablePercentage))% of ccTLDs and \(String(format: "%.1f", summary.ccTLDLinkedPercentageOfTotal))% of all zones"
    )
    print(
        "- \(formatNumber(summary.gTLDLinked))\t \(String(format: "%.1f", summary.gTLDLinkablePercentage))% of gTLDs and \(String(format: "%.1f", summary.gTLDLinkedPercentageOfTotal))% of all zones"
    )
    print(
        "- \(formatNumber(summary.gTLDNonBrandLinked))\t \(String(format: "%.1f", summary.gTLDNonBrandLinkablePercentage))% of non-brand gTLDs and \(String(format: "%.1f", summary.gTLDNonBrandLinkedPercentageOfTotal))% of all zones"
    )
    print(
        "- \(formatNumber(summary.gTLDBrandLinked))\t \(String(format: "%.1f", gTLDBrandLinkablePercentage))% of brand gTLDs and \(String(format: "%.1f", gTLDBrandLinkedPercentageOfTotal))% of all zones"
    )

}
