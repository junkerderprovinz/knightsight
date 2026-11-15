import CoreGraphics
import Foundation

public enum NoteKind: String, CaseIterable, Encodable {
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

/// A note on the pinboard. Its mark counts in points from the share's top left, and a pin is
/// a mark of zero size.
public struct Note: Equatable {
    public let number: Int
    public var kind: NoteKind
    public var text: String
    public var author: String
    public var mark: CGRect

    public init(number: Int, kind: NoteKind, text: String, author: String, mark: CGRect) {
        self.number = number
        self.kind = kind
        self.text = text
        self.author = author
        self.mark = mark
    }

    public var isPin: Bool { mark.size == .zero }
}

/// What Done sends: the share as look pictures it with every mark drawn on it, and per note
/// the place of its mark in that picture and a crop around it.
public struct Round {
    public struct Entry {
        public let note: Note
        /// The mark in the round's picture.
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

    /// Crop gets each note with the box its crop shows, in points from the share's top left.
    public init(number: Int, sent: Date, title: String, share: Share, image: Data, notes: [Note], crop: (Note, CGRect) -> Data) {
        self.number = number
        self.sent = sent
        self.title = title
        let size = share.pictureSize
        width = Int(size.width)
        height = Int(size.height)
        self.image = image
        entries = notes.sorted { $0.number < $1.number }.map { note in
            Entry(note: note, place: share.picture(note.mark), image: share.cropBox(for: note).map { crop(note, $0) })
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

    /// The part of the share a note's crop shows, in points from its top left: the mark with
    /// a margin, or a box around a pin, cut to the share.
    public func cropBox(for note: Note) -> CGRect? {
        let bounds = CGRect(origin: .zero, size: area.size)
        let m = note.mark
        let around: CGRect
        if note.isPin {
            guard bounds.contains(m.origin) else { return nil }
            around = CGRect(x: m.minX - Share.pinCrop / 2, y: m.minY - Share.pinCrop / 2, width: Share.pinCrop, height: Share.pinCrop)
        } else {
            guard m.intersects(bounds) else { return nil }
            around = m.insetBy(dx: -Share.cropMargin, dy: -Share.cropMargin)
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
/// port read.
public final class Board {
    private let lock = NSLock()
    private var stored: [Note] = []
    private var lastNumber = 0
    private var latest: Round?
    private var read = false

    public init() {}

    private func locked<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    /// By number.
    public var notes: [Note] { locked { stored } }

    /// Numbers count on for as long as the app runs, across rounds.
    @discardableResult
    public func add(_ kind: NoteKind, _ text: String, author: String, mark: CGRect) -> Note {
        locked {
            lastNumber += 1
            let note = Note(number: lastNumber, kind: kind, text: text, author: author, mark: mark)
            stored.append(note)
            return note
        }
    }

    public func update(_ number: Int, kind: NoteKind, text: String, author: String) {
        locked {
            guard let i = stored.firstIndex(where: { $0.number == number }) else { return }
            stored[i].kind = kind
            stored[i].text = text
            stored[i].author = author
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
