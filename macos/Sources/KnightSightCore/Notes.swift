import CoreGraphics
import Foundation

public enum NoteKind: String, CaseIterable, Codable {
    case bug, wish, question

    /// As 0xRRGGBB. A wish wears the app's accent.
    public var color: Int {
        switch self {
        case .bug: return 0xFA4D56
        case .wish: return 0xFCC419
        case .question: return 0x1D99F3
        }
    }
}

/// A note on the pinboard with one mark or more, in the order they were made. Marks count in
/// points from the share's top left, and a pin is a mark of zero size.
public struct Note: Equatable, Codable {
    static let letters = Array("abcdefghijklmnopqrstuvwxyz")
    public static let maxMarks = letters.count

    public let number: Int
    public var kind: NoteKind
    public var text: String
    public var author: String
    public var marks: [CGRect]

    public init(number: Int, kind: NoteKind, text: String, author: String, marks: [CGRect]) {
        self.number = number
        self.kind = kind
        self.text = text
        self.author = author
        self.marks = marks
    }

    /// The number alone for a note with one mark, with a letter in mark order for several.
    public func label(_ i: Int) -> String {
        marks.count == 1 ? "\(number)" : "\(number)\(Note.letters[i])"
    }

    public var labels: [String] { marks.indices.map(label) }
}

/// A note as the editor holds it, which reaches the board on Save: the note it was opened
/// from, nil for a new one, and its marks as they stand.
public struct Draft: Equatable {
    public let number: Int?
    public private(set) var marks: [CGRect]

    public init(number: Int?, marks: [CGRect]) {
        self.number = number
        self.marks = marks
    }

    /// Refused once every letter labels a mark.
    @discardableResult
    public mutating func add(_ mark: CGRect) -> Bool {
        guard marks.count < Note.maxMarks else { return false }
        marks.append(mark)
        return true
    }

    /// Refused for the last mark, as a note needs one.
    @discardableResult
    public mutating func remove(at i: Int) -> Bool {
        guard marks.count > 1 else { return false }
        marks.remove(at: i)
        return true
    }
}

/// What Done sends: the share as look pictures it with every mark drawn on it, and per mark
/// its place in that picture and a crop around it.
public struct Round: Codable {
    public struct Entry: Codable {
        public let note: Note
        public let marks: [Mark]
    }

    public struct Mark: Codable {
        public let label: String
        /// In the round's picture.
        public let place: CGRect
        /// Nil when the mark lies outside the share.
        public let image: Data?
    }

    public let number: Int
    public let sent: Date
    public let title: String
    public let width: Int
    public let height: Int
    public let image: Data
    public let entries: [Entry]

    /// Crop gets a note, the index of one of its marks and the box that mark's crop shows, in
    /// points from the share's top left.
    public init(number: Int, sent: Date, title: String, share: Share, image: Data, notes: [Note], crop: (Note, Int, CGRect) -> Data) {
        self.number = number
        self.sent = sent
        self.title = title
        let size = share.pictureSize
        width = Int(size.width)
        height = Int(size.height)
        self.image = image
        entries = notes.sorted { $0.number < $1.number }.map { note in
            Entry(note: note, marks: note.marks.indices.map { i in
                let mark = note.marks[i]
                return Mark(label: note.label(i), place: share.picture(mark), image: share.cropBox(for: mark).map { crop(note, i, $0) })
            })
        }
    }
}

extension Share {
    public static let cropMargin: CGFloat = 24
    public static let pinCrop: CGFloat = 240

    /// A rectangle in points from the share's top left, in picture coordinates.
    public func picture(_ r: CGRect) -> CGRect {
        CGRect(x: r.minX * scale, y: r.minY * scale, width: r.width * scale, height: r.height * scale)
    }

    /// The part of the share a mark's crop shows, in points from its top left: the mark with
    /// a margin, or a box around a pin, cut to the share.
    public func cropBox(for mark: CGRect) -> CGRect? {
        let bounds = CGRect(origin: .zero, size: area.size)
        let around: CGRect
        if mark.size == .zero {
            guard bounds.contains(mark.origin) else { return nil }
            around = CGRect(x: mark.minX - Share.pinCrop / 2, y: mark.minY - Share.pinCrop / 2, width: Share.pinCrop, height: Share.pinCrop)
        } else {
            guard mark.intersects(bounds) else { return nil }
            around = mark.insetBy(dx: -Share.cropMargin, dy: -Share.cropMargin)
        }
        return around.intersection(bounds)
    }

    /// Crop pixels per point: the screen's own density, scaled down until the longer edge
    /// fits into maxEdge.
    public func cropScale(_ box: CGRect) -> CGFloat {
        min(pixelsPerPoint, Share.maxEdge / max(box.width, box.height))
    }
}

/// The unsent notes and the latest round. The panel writes, the threads serving the
/// port read. A round not fetched yet also waits in the file, so KnightSight ending or
/// crashing before the assistant asks does not lose it.
public final class Board {
    private let lock = NSLock()
    private let file: URL?
    private var stored: [Note] = []
    private var lastNumber = 0
    private var latest: Round?
    private var read = false

    public init(file: URL? = nil) {
        self.file = file
        if let file, let data = try? Data(contentsOf: file) {
            latest = try? JSONDecoder().decode(Round.self, from: data)
        }
    }

    /// Written beside the file and then swapped in, so a crash in between leaves the old round
    /// or the new one, never half of one. Should the disk refuse, the round still waits in memory.
    private func keep(_ round: Round) {
        guard let file, let data = try? JSONEncoder().encode(round) else { return }
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: file, options: .atomic)
    }

    private func drop() {
        guard let file else { return }
        try? FileManager.default.removeItem(at: file)
    }

    private func locked<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    /// By number.
    public var notes: [Note] { locked { stored } }

    /// Numbers count on for as long as the app runs, across rounds.
    @discardableResult
    public func add(_ kind: NoteKind, _ text: String, author: String, marks: [CGRect]) -> Note {
        locked {
            lastNumber += 1
            let note = Note(number: lastNumber, kind: kind, text: text, author: author, marks: marks)
            stored.append(note)
            return note
        }
    }

    public func update(_ number: Int, kind: NoteKind, text: String, author: String, marks: [CGRect]) {
        locked {
            guard let i = stored.firstIndex(where: { $0.number == number }) else { return }
            stored[i].kind = kind
            stored[i].text = text
            stored[i].author = author
            stored[i].marks = marks
        }
    }

    public func remove(_ number: Int) {
        locked { stored.removeAll { $0.number == number } }
    }

    /// Drops the unsent notes. Their numbers stay used.
    public func clear() {
        locked { stored.removeAll() }
    }

    public var nextRound: Int { locked { (latest?.number ?? 0) + 1 } }

    /// Keeps the round as the latest one, unread, and takes its notes off the board. A note
    /// added while the round was being pictured stays.
    public func send(_ round: Round) {
        locked {
            let sent = Set(round.entries.map(\.note.number))
            stored.removeAll { sent.contains($0.number) }
            latest = round
            read = false
            keep(round)
        }
    }

    public func fetched(_ round: Int) -> Bool {
        locked { latest?.number == round && read }
    }

    /// The latest round's number, 0 before the first, and the round itself unless only an
    /// unread one is wanted and this one was handed out before. Handing it out marks it read.
    public func fetch(unread: Bool) -> (number: Int, round: Round?) {
        locked {
            guard let latest else { return (0, nil) }
            if unread && read { return (latest.number, nil) }
            if !read { drop() }
            read = true
            return (latest.number, latest)
        }
    }
}

/// Where a card goes beside a spot: to its right when the screen has room, else to its left,
/// else below it, and always on the screen. Everything counts from the top left.
public enum Placement {
    public static let gap: CGFloat = 12

    public static func beside(_ spot: CGRect, size: CGSize, within screen: CGRect) -> CGPoint {
        let y = min(max(spot.minY, screen.minY), screen.maxY - size.height)
        if spot.maxX + gap + size.width <= screen.maxX { return CGPoint(x: spot.maxX + gap, y: y) }
        if spot.minX - gap - size.width >= screen.minX { return CGPoint(x: spot.minX - gap - size.width, y: y) }
        let x = min(max(spot.minX, screen.minX), screen.maxX - size.width)
        return CGPoint(x: x, y: min(spot.maxY + gap, screen.maxY - size.height))
    }
}
