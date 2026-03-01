// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AppleCheck",
    platforms: [.macOS(.v10_15)],
    targets: [
        .executableTarget(
            name: "AppleCheck",
            path: "Sources/AppleCheck"
        )
    ]
)
