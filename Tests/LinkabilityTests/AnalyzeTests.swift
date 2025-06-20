import Foundation
import Testing
@testable import Linkability

struct AnalyzeTests {
    
    @Test func isZoneLinkedTest() {
        // Test known linked zones
        #expect(isZoneLinked("com"), "nic.com should be detected as a link")
        #expect(isZoneLinked("org"), "nic.org should be detected as a link")
        #expect(isZoneLinked("net"), "nic.net should be detected as a link")
        
        // Test some ccTLDs that should link
        #expect(isZoneLinked("uk"), "nic.uk should be detected as a link")
        #expect(isZoneLinked("de"), "nic.de should be detected as a link")
        
        // Test zones that likely won't link
        #expect(!isZoneLinked("example"), "nic.example should not be detected as a link")
        #expect(!isZoneLinked("test"), "nic.test should not be detected as a link")
        #expect(!isZoneLinked("invalid"), "nic.invalid should not be detected as a link")
    }
    
    @Test func zoneSummaryPercentageCalculations() {
        let summary = ZoneSummary(
            totalZones: 100,
            ccTLDCount: 20,
            gTLDCount: 80,
            gTLDBrandCount: 30,
            gTLDNonBrandCount: 50,
            ccTLDLinked: 10,
            gTLDLinked: 15,
            gTLDBrandLinked: 5,
            gTLDNonBrandLinked: 10
        )
        
        // Test basic percentages
        #expect(abs(summary.ccTLDPercentageOfTotal - 20.0) < 0.1)
        #expect(abs(summary.gTLDPercentageOfTotal - 80.0) < 0.1)
        #expect(abs(summary.gTLDBrandPercentageOfGTLD - 37.5) < 0.1) // 30/80 * 100
        #expect(abs(summary.gTLDBrandPercentageOfTotal - 30.0) < 0.1)
        
        // Test linkability percentages
        #expect(abs(summary.ccTLDLinkablePercentage - 50.0) < 0.1) // 10/20 * 100
        #expect(abs(summary.gTLDLinkablePercentage - 18.75) < 0.1) // 15/80 * 100
        #expect(abs(summary.gTLDNonBrandLinkablePercentage - 20.0) < 0.1) // 10/50 * 100
        
        // Test totals
        #expect(summary.totalLinkedZones == 25) // 10 + 15
        #expect(abs(summary.totalLinkedPercentage - 25.0) < 0.1) // 25/100 * 100
    }
    
    @Test func zoneSummaryZeroDivisionHandling() {
        let summary = ZoneSummary(
            totalZones: 0,
            ccTLDCount: 0,
            gTLDCount: 0,
            gTLDBrandCount: 0,
            gTLDNonBrandCount: 0,
            ccTLDLinked: 0,
            gTLDLinked: 0,
            gTLDBrandLinked: 0,
            gTLDNonBrandLinked: 0
        )
        
        // All percentages should be 0 when counts are 0
        #expect(summary.ccTLDPercentageOfTotal == 0.0)
        #expect(summary.gTLDPercentageOfTotal == 0.0)
        #expect(summary.gTLDBrandPercentageOfGTLD == 0.0)
        #expect(summary.ccTLDLinkablePercentage == 0.0)
        #expect(summary.gTLDLinkablePercentage == 0.0)
        #expect(summary.totalLinkedPercentage == 0.0)
    }
    
    @Test func zoneSummaryConsistency() {
        let summary = ZoneSummary(
            totalZones: 100,
            ccTLDCount: 25,
            gTLDCount: 75,
            gTLDBrandCount: 30,
            gTLDNonBrandCount: 45,
            ccTLDLinked: 12,
            gTLDLinked: 18,
            gTLDBrandLinked: 8,
            gTLDNonBrandLinked: 10
        )
        
        // Verify structural consistency
        #expect(summary.ccTLDCount + summary.gTLDCount == summary.totalZones,
               "ccTLD + gTLD should equal total zones")
        #expect(summary.gTLDBrandCount + summary.gTLDNonBrandCount == summary.gTLDCount,
               "Brand gTLDs + Non-brand gTLDs should equal total gTLDs")
        #expect(summary.gTLDBrandLinked + summary.gTLDNonBrandLinked == summary.gTLDLinked,
               "Linked brand gTLDs + Linked non-brand gTLDs should equal total linked gTLDs")
        #expect(summary.ccTLDLinked + summary.gTLDLinked == summary.totalLinkedZones,
               "Linked ccTLDs + Linked gTLDs should equal total linked zones")
    }
    
    @Test func zoneSummaryEdgeCases() {
        // Test case where all zones are linked
        let allLinked = ZoneSummary(
            totalZones: 10,
            ccTLDCount: 4,
            gTLDCount: 6,
            gTLDBrandCount: 2,
            gTLDNonBrandCount: 4,
            ccTLDLinked: 4,
            gTLDLinked: 6,
            gTLDBrandLinked: 2,
            gTLDNonBrandLinked: 4
        )
        
        #expect(abs(allLinked.ccTLDLinkablePercentage - 100.0) < 0.1)
        #expect(abs(allLinked.gTLDLinkablePercentage - 100.0) < 0.1)
        #expect(abs(allLinked.totalLinkedPercentage - 100.0) < 0.1)
        
        // Test case where no zones are linked
        let noneLinked = ZoneSummary(
            totalZones: 10,
            ccTLDCount: 4,
            gTLDCount: 6,
            gTLDBrandCount: 2,
            gTLDNonBrandCount: 4,
            ccTLDLinked: 0,
            gTLDLinked: 0,
            gTLDBrandLinked: 0,
            gTLDNonBrandLinked: 0
        )
        
        #expect(abs(noneLinked.ccTLDLinkablePercentage - 0.0) < 0.1)
        #expect(abs(noneLinked.gTLDLinkablePercentage - 0.0) < 0.1)
        #expect(abs(noneLinked.totalLinkedPercentage - 0.0) < 0.1)
    }
    
    @Test func readZonesFromTestData() {
        let testPath = "Tests/LinkabilityTests/TestData/test-zones-full.txt"
        let zones = readZones(from: testPath)
        
        // Should read 14 zones (excluding comments and empty lines)
        #expect(zones.count == 14, "Should read 14 zones from test data")
        
        // Should contain expected zones
        #expect(zones.contains("com"), "Should contain com")
        #expect(zones.contains("org"), "Should contain org")
        #expect(zones.contains("au"), "Should contain au (ccTLD)")
        #expect(zones.contains("uk"), "Should contain uk (ccTLD)")
        #expect(zones.contains("audi"), "Should contain audi (brand)")
        #expect(zones.contains("vermögensberater"), "Should contain decoded Punycode zone")
        #expect(zones.contains("コム"), "Should contain Japanese zone")
        
        // Should not contain comments or empty lines
        #expect(!zones.contains("# Version"), "Should not contain comment lines")
        #expect(!zones.contains(""), "Should not contain empty strings")
    }
    
    @Test func readBrandZonesFromTestData() {
        let testPath = "Tests/LinkabilityTests/TestData/test-zones-brand.txt"
        let brandZones = readZones(from: testPath)
        
        // Should read 5 brand zones
        #expect(brandZones.count == 5, "Should read 5 brand zones from test data")
        
        // Should contain expected brand zones
        #expect(brandZones.contains("audi"), "Should contain audi brand")
        #expect(brandZones.contains("bmw"), "Should contain bmw brand")
        #expect(brandZones.contains("google"), "Should contain google brand")
        #expect(brandZones.contains("microsoft"), "Should contain microsoft brand")
        #expect(brandZones.contains("nike"), "Should contain nike brand")
    }
    
    @Test func analyzeSummaryWithTestData() {
        // Create a test version of analyzeSummary that uses test data
        let zones = readZones(from: "Tests/LinkabilityTests/TestData/test-zones-full.txt")
        let brandZones = Set(readZones(from: "Tests/LinkabilityTests/TestData/test-zones-brand.txt"))
        
        #expect(!zones.isEmpty, "Should read zones from test data")
        #expect(!brandZones.isEmpty, "Should read brand zones from test data")
        
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
        
        let summary = ZoneSummary(
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
        
        // Validate expected structure based on test data:
        // ccTLDs: au, de, uk (3 total)
        // gTLDs: audi, bmw, com, google, microsoft, net, nike, org, test, vermögensberater, コム (11 total)
        // Brand gTLDs: audi, bmw, google, microsoft, nike (5 total)
        // Non-brand gTLDs: com, net, org, test, vermögensberater, コム (6 total)
        
        #expect(summary.totalZones == 14, "Should have 14 total zones")
        #expect(summary.ccTLDCount == 3, "Should have 3 ccTLDs (au, de, uk)")
        #expect(summary.gTLDCount == 11, "Should have 11 gTLDs")
        #expect(summary.gTLDBrandCount == 5, "Should have 5 brand gTLDs")
        #expect(summary.gTLDNonBrandCount == 6, "Should have 6 non-brand gTLDs")
        
        // Validate consistency
        #expect(summary.ccTLDCount + summary.gTLDCount == summary.totalZones, "ccTLD + gTLD should equal total")
        #expect(summary.gTLDBrandCount + summary.gTLDNonBrandCount == summary.gTLDCount, "Brand + non-brand should equal gTLD total")
        #expect(summary.gTLDBrandLinked + summary.gTLDNonBrandLinked == summary.gTLDLinked, "Brand linked + non-brand linked should equal gTLD linked")
        
        // Test percentage calculations
        let expectedCCTLDPercentage = 3.0 / 14.0 * 100.0  // ~21.43%
        let expectedGTLDPercentage = 11.0 / 14.0 * 100.0  // ~78.57%
        #expect(abs(summary.ccTLDPercentageOfTotal - expectedCCTLDPercentage) < 0.1, "ccTLDs should be ~21% of total (3/14)")
        #expect(abs(summary.gTLDPercentageOfTotal - expectedGTLDPercentage) < 0.1, "gTLDs should be ~79% of total (11/14)")
    }
    
    @Test func punycodeDecodingInTestData() {
        let zones = readZones(from: "Tests/LinkabilityTests/TestData/test-zones-full.txt")
        
        // Should contain the decoded Punycode domain
        #expect(zones.contains("vermögensberater"), "Should decode xn--vermgensberater-ctb to vermögensberater")
        #expect(!zones.contains("xn--vermgensberater-ctb"), "Should not contain the original Punycode form after decoding")
    }
}