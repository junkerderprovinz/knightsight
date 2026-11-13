import CoreGraphics
import Foundation

/// A request the panel turns down, with the reason the assistant reads.
public struct Refused: Error, Equatable {
    public let message: String

    public init(_ message: String) {
        self.message = message
    }

    public static let nothingShared = Refused("Nothing is shared right now. Choose a window or a region in the KnightSight window and start sharing.")
}

/// The share as it is at the moment of a request.
public struct Share {
    /// In screen points, with the origin at the top left of the main display.
    public var area: CGRect
    public var pixelsPerPoint: CGFloat
    /// False while a shared window is minimized, hidden or on another desktop.
    public var reachable: Bool

    public init(area: CGRect, pixelsPerPoint: CGFloat, reachable: Bool) {
        self.area = area
        self.pixelsPerPoint = pixelsPerPoint
        self.reachable = reachable
    }

    public static let maxEdge: CGFloat = 1568

    /// Screenshot pixels per screen point: the screen's own density, scaled down until the
    /// longer edge fits into maxEdge.
    public var scale: CGFloat {
        min(pixelsPerPoint, Share.maxEdge / max(area.width, area.height))
    }

    public var pictureSize: CGSize {
        CGSize(width: max(1, (area.width * scale).rounded()), height: max(1, (area.height * scale).rounded()))
    }

    /// Screenshot coordinates back to the screen, refused outside the share.
    public func screenPoint(x: Double, y: Double) throws -> CGPoint {
        let p = CGPoint(x: area.minX + CGFloat(x) / scale, y: area.minY + CGFloat(y) / scale)
        guard area.contains(p) else { throw Refused("The point lies outside the share.") }
        return p
    }
}

public struct Screenshot {
    public var png: Data
    public var title: String
    public var note: String?

    public init(png: Data, title: String, note: String?) {
        self.png = png
        self.title = title
        self.note = note
    }
}

/// The platform side of the panel: the share as it is right now, and the hands that act in it.
public protocol Desk: AnyObject {
    var layout: KeyLayout { get }
    /// The share while sharing is on, nil otherwise.
    func currentShare() -> Share?
    func began(_ doing: String)
    func look(size: CGSize) throws -> Screenshot
    func click(at point: CGPoint, right: Bool, double: Bool) throws -> String
    func scroll(at point: CGPoint, notches: Int) throws -> String
    func type(_ text: String) throws -> String
    func press(_ combo: KeyCombo) throws -> String
}

/// Turns one JSON line from the MCP server into one JSON line back. Replies stay English,
/// since an assistant reads them.
public final class Responder {
    public static let port: UInt16 = 47613

    private let desk: Desk
    private let say: Say
    private let gate = NSLock()
    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = .withoutEscapingSlashes
        return encoder
    }()

    public init(desk: Desk, say: Say) {
        self.desk = desk
        self.say = say
    }

    /// One request at a time, whichever connection it comes from.
    public func answer(_ line: String) -> String {
        gate.lock()
        defer { gate.unlock() }
        var reply: Reply
        do {
            reply = try respond(to: line)
            reply.ok = true
        } catch let refused as Refused {
            reply = Reply(ok: false, error: refused.message)
        } catch {
            reply = Reply(ok: false, error: "\(type(of: error)): \(error.localizedDescription)")
        }
        return String(decoding: try! encoder.encode(reply), as: UTF8.self)
    }

    private func respond(to line: String) throws -> Reply {
        guard let request = Request(line) else { throw Refused("The request is not a JSON object.") }
        guard let share = desk.currentShare() else { throw Refused.nothingShared }
        guard share.reachable else { throw Refused("The shared window is minimized, hidden or on another desktop.") }
        let cmd = try request.text("cmd")
        desk.began(say.describe(cmd, request))
        var reply = Reply()
        switch cmd {
        case "look":
            let size = share.pictureSize
            let picture = try desk.look(size: size)
            reply.image = picture.png.base64EncodedString()
            reply.width = Int(size.width)
            reply.height = Int(size.height)
            reply.title = picture.title
            reply.note = picture.note
        case "click":
            let at = try share.screenPoint(x: request.number("x"), y: request.number("y"))
            reply.message = try desk.click(at: at, right: request.flag("right"), double: request.flag("double"))
        case "scroll":
            let at = try share.screenPoint(x: request.number("x"), y: request.number("y"))
            let amount = try request.number("amount")
            // A wild amount would scroll for minutes, and one past Int would trap.
            let notches = Int(min(max(amount, -100), 100).rounded(.toNearestOrEven))
            reply.message = try desk.scroll(at: at, notches: notches)
        case "type":
            reply.message = try desk.type(request.text("text"))
        case "key":
            reply.message = try desk.press(KeyCombo(parsing: request.text("keys"), layout: desk.layout))
        default:
            throw Refused("Unknown command: \(cmd)")
        }
        return reply
    }
}

struct Reply: Encodable {
    var ok = false
    var error: String?
    var message: String?
    var image: String?
    var title: String?
    var width: Int?
    var height: Int?
    var note: String?
}

enum Value: Decodable {
    case text(String)
    case number(Double)
    case flag(Bool)
    case other

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let flag = try? container.decode(Bool.self) {
            self = .flag(flag)
        } else if let number = try? container.decode(Double.self) {
            self = .number(number)
        } else if let text = try? container.decode(String.self) {
            self = .text(text)
        } else {
            self = .other
        }
    }
}

struct Request {
    let fields: [String: Value]

    init?(_ line: String) {
        guard let fields = try? JSONDecoder().decode([String: Value].self, from: Data(line.utf8)) else { return nil }
        self.fields = fields
    }

    func text(_ key: String) throws -> String {
        guard case .text(let value)? = fields[key] else { throw Refused("Missing \(key).") }
        return value
    }

    func number(_ key: String) throws -> Double {
        guard case .number(let value)? = fields[key] else { throw Refused("Missing \(key).") }
        return value
    }

    func flag(_ key: String) -> Bool {
        if case .flag(true)? = fields[key] { return true }
        return false
    }
}
