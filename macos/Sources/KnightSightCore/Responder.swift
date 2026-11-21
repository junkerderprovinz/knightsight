import CoreGraphics
import Foundation

/// A request the panel turns down, with the reason the assistant reads.
public struct Refused: Error, Equatable {
    public let message: String
    /// Set when the refusal came after input went out, so some of it may have arrived.
    public let delivered: Bool

    public init(_ message: String, delivered: Bool = false) {
        self.message = message
        self.delivered = delivered
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
    /// Counts up with every new share and every newly chosen target, so refs from a look at
    /// an earlier one are not taken for this one.
    public var serial: Int
    /// KnightSight's own windows that a click in the share could land on, in screen points.
    public var own: [CGRect]

    public init(area: CGRect, pixelsPerPoint: CGFloat, reachable: Bool, serial: Int = 0, own: [CGRect] = []) {
        self.area = area
        self.pixelsPerPoint = pixelsPerPoint
        self.reachable = reachable
        self.serial = serial
        self.own = own
    }

    public static let maxEdge: CGFloat = 1568

    /// Picture pixels per screen point: the screen's own density, scaled down until the
    /// longer edge fits into maxEdge.
    public var scale: CGFloat {
        min(pixelsPerPoint, Share.maxEdge / max(area.width, area.height))
    }

    public var pictureSize: CGSize {
        CGSize(width: max(1, (area.width * scale).rounded()), height: max(1, (area.height * scale).rounded()))
    }

    /// Picture coordinates back to the screen, refused outside the share.
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
    var board: Board { get }
    /// The share while sharing is on, nil otherwise.
    func currentShare() -> Share?
    /// Brings a minimized shared window back behind the others and tells whether it came.
    func bringBack() -> Bool
    func began(_ doing: String)
    func look(size: CGSize) throws -> Screenshot
    /// The controls in the area as accessibility reports them, or nil when they cannot be read.
    func controls(in area: CGRect) -> [Node]?
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
    private var lastLook: (serial: Int, elements: [Element])?
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
            if refused.delivered { reply.delivered = "maybe" }
        } catch {
            reply = Reply(ok: false, error: "\(type(of: error)): \(error.localizedDescription)")
        }
        return String(decoding: try! encoder.encode(reply), as: UTF8.self)
    }

    private func respond(to line: String) throws -> Reply {
        guard let request = Request(line) else { throw Refused("The request is not a JSON object.") }
        // The person sent the notes on purpose, so they go out whether or not anything is
        // shared. Fetching them is no work to show, as the MCP server asks every second.
        if (try? request.text("cmd")) == "notes" {
            guard let read = try? request.number("read") else { return notes(unread: request.flag("unread"), confirms: request.flag("confirm")) }
            desk.board.confirm(Int(read))
            return Reply()
        }
        guard var share = desk.currentShare() else { throw Refused.nothingShared }
        if !share.reachable, desk.bringBack(), let back = desk.currentShare() { share = back }
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
            reply.elements = desk.controls(in: share.area).map { Elements.list($0, in: share) }
            lastLook = (share.serial, reply.elements ?? [])
        case "click":
            let at = try point(request, in: share, for: "Click")
            reply.message = try desk.click(at: at, right: request.flag("right"), double: request.flag("double"))
        case "scroll":
            let at = try point(request, in: share, for: "Scroll")
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

    /// Where a click or scroll goes: a point in the picture, or the middle of an element from
    /// the last look at this share. The assistant may look at KnightSight but not work it.
    private func point(_ request: Request, in share: Share, for action: String) throws -> CGPoint {
        let p = try aim(request, in: share, for: action)
        guard !share.own.contains(where: { $0.contains(p) }) else { throw Refused("That point lies on KnightSight itself.") }
        return p
    }

    private func aim(_ request: Request, in share: Share, for action: String) throws -> CGPoint {
        if request.fields["ref"] != nil {
            let ref = try request.text("ref")
            guard let last = lastLook, last.serial == share.serial, let element = last.elements.first(where: { $0.ref == ref }) else {
                throw Refused("There is no element \(ref) from the last look. Take a new look.")
            }
            return try share.screenPoint(x: element.centre.x, y: element.centre.y)
        }
        guard request.fields["x"] != nil || request.fields["y"] != nil else {
            throw Refused("\(action) needs x and y or a ref from look.")
        }
        return try share.screenPoint(x: request.number("x"), y: request.number("y"))
    }

    private func notes(unread: Bool, confirms: Bool) -> Reply {
        let (number, latest) = desk.board.fetch(unread: unread, confirms: confirms)
        var reply = Reply()
        reply.round = number
        guard let round = latest else { return reply }
        reply.sent = ISO8601DateFormatter().string(from: round.sent)
        reply.title = round.title
        reply.width = round.width
        reply.height = round.height
        reply.image = round.image.base64EncodedString()
        reply.notes = round.entries.map { NoteReply($0) }
        return reply
    }
}

struct Reply: Encodable {
    var ok = false
    var error: String?
    var delivered: String?
    var message: String?
    var image: String?
    var title: String?
    var width: Int?
    var height: Int?
    var note: String?
    var elements: [Element]?
    var round: Int?
    var sent: String?
    var notes: [NoteReply]?
}

struct NoteReply: Encodable {
    let number: Int
    let kind: NoteKind
    let text: String
    let author: String
    let marks: [MarkReply]

    init(_ entry: Round.Entry) {
        number = entry.note.number
        kind = entry.note.kind
        text = entry.note.text
        author = entry.note.author
        marks = entry.marks.map(MarkReply.init)
    }
}

/// A mark in picture coordinates. A pin has no size.
struct MarkReply: Encodable {
    let label: String
    let x: Int
    let y: Int
    let width: Int?
    let height: Int?
    let pin: Bool?
    let image: String?

    init(_ mark: Round.Mark) {
        let place = mark.place, pin = place.size == .zero
        label = mark.label
        x = Int(place.minX.rounded())
        y = Int(place.minY.rounded())
        width = pin ? nil : Int(place.width.rounded())
        height = pin ? nil : Int(place.height.rounded())
        self.pin = pin ? true : nil
        image = mark.image?.base64EncodedString()
    }
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
