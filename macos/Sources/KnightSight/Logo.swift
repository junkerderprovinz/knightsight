import AppKit
import ImageIO

/// A brass spyglass across a split steel ring: someone looking at what is shared. The shapes come
/// from the masters in .github/assets through gen-logo-shapes.mjs. They are filled without
/// smoothing at four times the size and then scaled down, so neighbouring shapes meet without
/// hairlines and the edges still come out soft.
enum Logo {
    static let oversampling = 4

    struct Shape {
        let fill: CGColor
        let steps: String

        init(_ rgb: Int, _ steps: String) {
            fill = Theme.rgb(CGFloat(rgb >> 16), CGFloat(rgb >> 8 & 0xFF), CGFloat(rgb & 0xFF)).cgColor
            self.steps = steps
        }

        /// The generator's M, L, C and Z steps, each followed by its absolute points.
        var path: CGPath {
            let path = CGMutablePath()
            var tokens = steps.split(separator: " ")[...]
            func point() -> CGPoint {
                let x = Double(tokens.popFirst()!)!, y = Double(tokens.popFirst()!)!
                return CGPoint(x: x, y: y)
            }
            while let step = tokens.popFirst() {
                switch step {
                case "M":
                    path.move(to: point())
                case "L":
                    path.addLine(to: point())
                case "C":
                    let control1 = point(), control2 = point(), end = point()
                    path.addCurve(to: end, control1: control1, control2: control2)
                default:
                    path.closeSubpath()
                }
            }
            return path
        }
    }

    struct Drawing {
        let width: CGFloat, height: CGFloat
        let shapes: [Shape]
    }

    /// The drawing keeps its proportions and sits in the middle, `inset` being the margin on each
    /// side as a fraction of the edge.
    static func render(_ size: Int, _ drawing: Drawing = Logo.bare, inset: CGFloat = 0) -> CGImage {
        let edge = CGFloat(size * oversampling)
        let large = Bitmap.context(width: size * oversampling, height: size * oversampling)
        let scale = edge * (1 - 2 * inset) / max(drawing.width, drawing.height)
        // The shapes count from the top left, like the SVG they come from.
        large.translateBy(x: (edge - drawing.width * scale) / 2, y: (edge + drawing.height * scale) / 2)
        large.scaleBy(x: scale, y: -scale)
        large.setShouldAntialias(false)
        for shape in drawing.shapes {
            large.setFillColor(shape.fill)
            large.addPath(shape.path)
            large.fillPath()
        }

        let small = Bitmap.context(width: size, height: size)
        small.interpolationQuality = .high
        small.draw(large.makeImage()!, in: CGRect(x: 0, y: 0, width: size, height: size))
        return small.makeImage()!
    }

    /// The app icon is the tile, where every other place shows the bare logo. macOS gives the body
    /// of an app icon 824 of its 1024 points, so the tile leaves the same margin.
    static func writeIconSet(to folder: URL) throws {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let inset: CGFloat = 100.0 / 1024
        for edge in [16, 32, 128, 256, 512] {
            try Bitmap.png(render(edge, tile, inset: inset)).write(to: folder.appendingPathComponent("icon_\(edge)x\(edge).png"))
            try Bitmap.png(render(edge * 2, tile, inset: inset)).write(to: folder.appendingPathComponent("icon_\(edge)x\(edge)@2x.png"))
        }
    }
}

enum Bitmap {
    static func context(width: Int, height: Int) -> CGContext {
        CGContext(
            data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    }

    static func png(_ image: CGImage) -> Data {
        let data = NSMutableData()
        let destination = CGImageDestinationCreateWithData(data, "public.png" as CFString, 1, nil)!
        CGImageDestinationAddImage(destination, image, nil)
        CGImageDestinationFinalize(destination)
        return data as Data
    }
}
