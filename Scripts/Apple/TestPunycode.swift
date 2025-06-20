import Foundation
import Punycode

let testDomains = ["xn--11b4c3d", "xn--1ck2e1b", "xn--1qqw23a"]

print("Testing Punycode conversion:")
for domain in testDomains {
    print("Original: \(domain)")
    if let decoded = domain.punycodeDecoded {
        print("  Decoded: \(decoded)")
    } else {
        print("  Failed to decode")
    }
}

// Test Unicode domains from zones-brand.txt
let unicodeDomains = ["アマゾン", "グーグル", "中信", "亚马逊", "嘉里", "谷歌", "삼성"]
print("\nTesting Unicode domain encoding:")
for domain in unicodeDomains {
    print("Original: \(domain)")
    if let encoded = domain.punycodeEncoded {
        print("  Encoded: \(encoded)")
    }
}