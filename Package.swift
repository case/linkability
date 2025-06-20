// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Linkability",
    platforms: [.macOS(.v10_15)],
    dependencies: [
        .package(url: "https://github.com/gumob/PunycodeSwift.git", from: "3.0.0")
    ],
    targets: [
        .target(
            name: "Linkability",
            dependencies: [
                .product(name: "Punycode", package: "PunycodeSwift")
            ]
        ),
        .executableTarget(
            name: "LinkabilityCLI",
            dependencies: ["Linkability"],
            path: "Sources/LinkabilityCLI"
        ),
        .testTarget(
            name: "LinkabilityTests",
            dependencies: ["Linkability"],
            resources: [.copy("TestData")]
        ),
        .executableTarget(
            name: "TestPunycode",
            dependencies: [
                .product(name: "Punycode", package: "PunycodeSwift")
            ],
            path: "scripts/Apple",
            exclude: ["CheckMissing.swift"],
            sources: ["TestPunycode.swift"]
        ),
        .executableTarget(
            name: "CheckMissing",
            dependencies: [
                .product(name: "Punycode", package: "PunycodeSwift")
            ],
            path: "scripts/Apple",
            exclude: ["TestPunycode.swift"],
            sources: ["CheckMissing.swift"]
        ),
    ]
)
