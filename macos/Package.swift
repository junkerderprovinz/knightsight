// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "KnightSight",
    platforms: [.macOS(.v13)],
    targets: [
        .target(name: "KnightSightCore"),
        .executableTarget(name: "KnightSight", dependencies: ["KnightSightCore"]),
        .testTarget(name: "KnightSightCoreTests", dependencies: ["KnightSightCore"]),
    ]
)
