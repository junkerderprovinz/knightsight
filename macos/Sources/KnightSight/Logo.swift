import AppKit
import ImageIO

/// A brass spyglass across a steel frame: someone looking at what is shared. Drawn on a 256
/// grid with the light from the top left, without smoothing at four times the size and then
/// scaled down, so the facets meet without hairlines and the edges come out soft.
enum Logo {
    static let grid: CGFloat = 256
    static let oversampling = 4

    // From eyepiece to hood: start, end and half width of each part, rings and tubes taking turns.
    static let parts: [(start: CGFloat, end: CGFloat, half: CGFloat)] = [
        (0, 12, 15), (12, 92, 13), (92, 104, 22), (104, 170, 19), (170, 182, 28), (182, 250, 25), (250, 264, 30),
    ]
    static let steelLit = Theme.rgb(184, 184, 184), steelShade = Theme.rgb(131, 131, 136), steelDark = Theme.rgb(102, 102, 107)
    static let brassLit = Theme.rgb(253, 216, 142), brass = Theme.rgb(233, 186, 87)
    static let brassShade = Theme.rgb(205, 147, 55), brassDark = Theme.rgb(145, 102, 49)

    static func render(_ size: Int) -> CGImage {
        let edge = size * oversampling
        let large = Bitmap.context(width: edge, height: edge)
        // The grid counts from the top left, like the drawing it was made from.
        large.translateBy(x: 0, y: CGFloat(edge))
        large.scaleBy(x: CGFloat(edge) / grid, y: -CGFloat(edge) / grid)
        large.setShouldAntialias(false)
        drawFrame(large)
        large.setBlendMode(.clear)
        large.addPath(tubeArea())
        large.fillPath()
        large.setBlendMode(.normal)
        drawTube(large)

        let small = Bitmap.context(width: size, height: size)
        small.interpolationQuality = .high
        small.draw(large.makeImage()!, in: CGRect(x: 0, y: 0, width: size, height: size))
        return small.makeImage()!
    }

    static func writeIconSet(to folder: URL) throws {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        for edge in [16, 32, 128, 256, 512] {
            try Bitmap.png(render(edge)).write(to: folder.appendingPathComponent("icon_\(edge)x\(edge).png"))
            try Bitmap.png(render(edge * 2)).write(to: folder.appendingPathComponent("icon_\(edge)x\(edge)@2x.png"))
        }
    }

    static var tubeAxis: CGAffineTransform {
        CGAffineTransform(translationX: 36, y: 220).rotated(by: -.pi / 4)
    }

    // Straight edges for the narrow and the wide half, so the rings leave no slivers of frame.
    static func tubeArea() -> CGPath {
        let path = CGMutablePath()
        let axis = tubeAxis
        path.addRect(CGRect(x: -7, y: -20, width: 118, height: 40), transform: axis)
        path.addRect(CGRect(x: 97, y: -35, width: 174, height: 70), transform: axis)
        return path
    }

    static func drawFrame(_ g: CGContext) {
        let outer0: CGFloat = 44, outer1: CGFloat = 212, step0: CGFloat = 58, step1: CGFloat = 198, inner0: CGFloat = 72, inner1: CGFloat = 184
        band(g, steelLit, [(outer0, outer0), (outer1, outer0), (step1, step0), (step0, step0)])
        band(g, steelLit, [(outer0, outer0), (step0, step0), (step0, step1), (outer0, outer1)])
        band(g, steelDark, [(outer1, outer0), (outer1, outer1), (step1, step1), (step1, step0)])
        band(g, steelDark, [(outer0, outer1), (step0, step1), (step1, step1), (outer1, outer1)])
        band(g, steelShade, [(step0, step0), (step1, step0), (inner1, inner0), (inner0, inner0)])
        band(g, steelShade, [(step0, step0), (inner0, inner0), (inner0, inner1), (step0, step1)])
        band(g, steelLit, [(step1, step0), (step1, step1), (inner1, inner1), (inner1, inner0)])
        band(g, steelLit, [(step0, step1), (inner0, inner1), (inner1, inner1), (step1, step1)])
    }

    static func band(_ g: CGContext, _ color: NSColor, _ corners: [(CGFloat, CGFloat)]) {
        g.setFillColor(color.cgColor)
        g.addLines(between: corners.map { CGPoint(x: $0.0, y: $0.1) })
        g.closePath()
        g.fillPath()
    }

    static func drawTube(_ g: CGContext) {
        g.saveGState()
        g.concatenate(tubeAxis)
        for (i, part) in parts.enumerated() {
            let ring = i % 2 == 0
            stripe(g, ring ? brassShade : brass, part, from: -1, to: 1)
            stripe(g, ring ? brass : brassLit, part, from: -1, to: ring ? -0.3 : -0.42)
            stripe(g, ring ? brassDark : brassShade, part, from: ring ? 0.45 : 0.38, to: 1)
        }
        g.restoreGState()
    }

    // A band along one part, its edges given as fractions of the half width.
    static func stripe(_ g: CGContext, _ color: NSColor, _ part: (start: CGFloat, end: CGFloat, half: CGFloat), from: CGFloat, to: CGFloat) {
        g.setFillColor(color.cgColor)
        g.fill(CGRect(x: part.start, y: from * part.half, width: part.end - part.start, height: (to - from) * part.half))
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
