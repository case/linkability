import Foundation
import Linkability

func showHelp() {
    print("Linkability - Which zones is the Apple stdlib auto-linking?")
    print("")
    print("Usage: swift run LinkabilityCLI [OPTION]")
    print("")
    print("Help:")
    print("  --help                    Show this help message")
    print("")
    print("Download:")
    print("  --download-zones          Download latest TLD zones from IANA")
    print("  --download-brand-zones    Fetch the brand zones list from the local ZoneDB CLI")
    print("")
    print("Test:")
    print(
        "  --show-missing-brands     Show delegated brand zones not in the root zone (should be 0)")
    print("  --test-cctld-brands       Test that no ccTLDs are marked as brands (should be 0)")
    print("")
    print("Report:")
    print("  --report-csv       Generate CSV report of zone linkability")
    print("  --report-summary                 Show zone summary statistics")
    print("  --show-linked-brands             Show space-delimited list of linked brand zones")
    print("  --show-linked-cctlds             Show space-delimited list of linked ccTLD zones")
    print("  --show-linked-gtlds              Show space-delimited list of linked gTLD zones")
}

@main
struct LinkabilityTool {
    static func main() {
        // Command line argument handling
        if CommandLine.arguments.contains("--help") || CommandLine.arguments.contains("-h") {
            showHelp()
        } else if CommandLine.arguments.contains("--report-csv") {
            generateCSVReport()
        } else if CommandLine.arguments.contains("--download-brand-zones") {
            downloadBrandZones()
        } else if CommandLine.arguments.contains("--download-zones") {
            downloadIanaZones()
            RunLoop.main.run()
        } else if CommandLine.arguments.contains("--show-missing-brands") {
            showMissingActiveBrands()
        } else if CommandLine.arguments.contains("--report-summary") {
            generateSummary()
        } else if CommandLine.arguments.contains("--show-linked-brands") {
            getLinkedZones(type: .gTLDBrand)
        } else if CommandLine.arguments.contains("--show-linked-cctlds") {
            getLinkedZones(type: .ccTLD)
        } else if CommandLine.arguments.contains("--show-linked-gtlds") {
            getLinkedZones(type: .gTLDAll)
        } else if CommandLine.arguments.contains("--test-cctld-brands") {
            testCCTLDBrands()
        } else {
            // Default to showing Help if no arguments provided
            showHelp()
        }
    }
}
