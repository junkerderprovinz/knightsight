import AppKit
import CoreMedia
import KnightSightCore
import ScreenCaptureKit
import VideoToolbox

/// Pictures through ScreenCaptureKit, which renders only the windows it is asked for. A
/// shared window comes out whole even while something lies on top of it.
enum Capture {
    /// The shared window with the menus and sheets it has open.
    static func window(_ shared: WindowInfo, size: CGSize) throws -> CGImage {
        let content = try shareable()
        let popups = Set(Windows.visible().filter { Windows.isPopup($0, of: shared) }.map(\.id))
        let included = content.windows.filter { $0.windowID == shared.id || popups.contains($0.windowID) }
        guard included.contains(where: { $0.windowID == shared.id }) else {
            throw Refused("The shared window cannot be captured right now.")
        }
        let display = try screen(for: shared.bounds, in: content)
        return try grab(SCContentFilter(display: display, including: included), on: display, area: shared.bounds, size: size)
    }

    /// Whatever shows in the region, without KnightSight's own frame and badge.
    static func region(_ area: CGRect, skipping marks: Set<CGWindowID>, size: CGSize) throws -> CGImage {
        let content = try shareable()
        let display = try screen(for: area, in: content)
        let filter = SCContentFilter(display: display, excludingWindows: content.windows.filter { marks.contains($0.windowID) })
        return try grab(filter, on: display, area: area, size: size)
    }

    static func shareable() throws -> SCShareableContent {
        try blocking { try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true) }
    }

    static func screen(for area: CGRect, in content: SCShareableContent) throws -> SCDisplay {
        let id = Screens.display(for: area)
        guard let display = content.displays.first(where: { $0.displayID == id }) else {
            throw Refused("The share lies on no screen right now.")
        }
        return display
    }

    /// Takes the part of the area that lies on the display and lays it into a picture of the
    /// given size. Whatever reaches onto another display stays blank.
    static func grab(_ filter: SCContentFilter, on display: SCDisplay, area: CGRect, size: CGSize) throws -> CGImage {
        let bounds = CGDisplayBounds(display.displayID)
        let visible = area.intersection(bounds)
        guard !visible.isEmpty else { throw Refused("The share lies on no screen right now.") }
        let density = Screens.density(of: display.displayID)
        let config = SCStreamConfiguration()
        config.sourceRect = visible.offsetBy(dx: -bounds.minX, dy: -bounds.minY)
        config.width = Int((visible.width * density).rounded())
        config.height = Int((visible.height * density).rounded())
        config.showsCursor = false
        let shot = try snapshot(filter, config)

        let k = size.width / area.width
        let picture = Bitmap.context(width: Int(size.width), height: Int(size.height))
        picture.interpolationQuality = .high
        picture.draw(shot, in: CGRect(
            x: (visible.minX - area.minX) * k, y: (area.maxY - visible.maxY) * k,
            width: visible.width * k, height: visible.height * k))
        return picture.makeImage()!
    }

    static func snapshot(_ filter: SCContentFilter, _ config: SCStreamConfiguration) throws -> CGImage {
        if #available(macOS 14, *) {
            return try blocking { try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config) }
        }
        return try OneFrame(filter: filter, configuration: config).take()
    }
}

/// The way to a single picture on macOS 13, which has no screenshot call yet: a stream that
/// ends after its first complete frame.
final class OneFrame: NSObject, SCStreamOutput {
    private let capture: SCStream
    private let queue = DispatchQueue(label: "KnightSight.frame")
    private let arrived = DispatchSemaphore(value: 0)
    private var image: CGImage?

    init(filter: SCContentFilter, configuration: SCStreamConfiguration) {
        capture = SCStream(filter: filter, configuration: configuration, delegate: nil)
    }

    func take() throws -> CGImage {
        try capture.addStreamOutput(self, type: .screen, sampleHandlerQueue: queue)
        try blocking { try await self.capture.startCapture() }
        let waited = arrived.wait(timeout: .now() + 3)
        _ = try? blocking { try await self.capture.stopCapture() }
        guard waited == .success, let image else { throw Refused("The share could not be captured in time.") }
        return image
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard image == nil, type == .screen, let pixels = sampleBuffer.imageBuffer,
              let info = (CMSampleBufferGetSampleAttachmentsArray(sampleBuffer, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]])?.first,
              let status = info[.status] as? Int, SCFrameStatus(rawValue: status) == .complete
        else { return }
        var picture: CGImage?
        VTCreateCGImageFromCVPixelBuffer(pixels, options: nil, imageOut: &picture)
        guard let picture else { return }
        image = picture
        arrived.signal()
    }
}

/// Waits for async work on a thread that may block, such as one serving the port.
func blocking<T>(_ work: @escaping () async throws -> T) throws -> T {
    let box = ResultBox<T>()
    let done = DispatchSemaphore(value: 0)
    Task.detached {
        do {
            box.result = .success(try await work())
        } catch {
            box.result = .failure(error)
        }
        done.signal()
    }
    done.wait()
    return try box.result!.get()
}

final class ResultBox<T>: @unchecked Sendable {
    var result: Result<T, Error>?
}
