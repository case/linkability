// swift-tools-version: 5.10
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
