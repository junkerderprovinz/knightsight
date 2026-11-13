import CoreGraphics
import Foundation
import XCTest
@testable import KnightSightCore

struct TestLayout: KeyLayout {
    static let keys: [Character: (UInt16, Modifiers)] = [
        "a": (0x00, []), "c": (0x08, []), "l": (0x25, []), "r": (0x0F, []), "z": (0x06, []),
        "1": (0x12, []), "?": (0x2C, .shift), "@": (0x25, .option),
    ]

    func key(for character: Character) -> (code: UInt16, modifiers: Modifiers)? {
        guard let found = TestLayout.keys[character] else { return nil }
        return (code: found.0, modifiers: found.1)
    }
}

final class FakeDesk: Desk {
    enum Call: Equatable {
        case look(CGSize)
        case click(CGPoint, right: Bool, double: Bool)
        case scroll(CGPoint, Int)
        case type(String)
        case press(KeyCombo)
    }

    var share: Share? = Share(area: CGRect(x: 100, y: 200, width: 784, height: 600), pixelsPerPoint: 2, reachable: true)
    var refusal: Refused?
    var calls: [Call] = []
    var labels: [String] = []
    let layout: KeyLayout = TestLayout()

    func currentShare() -> Share? { share }

    func began(_ doing: String) { labels.append(doing) }

    func look(size: CGSize) throws -> Picture {
        calls.append(.look(size))
        return Picture(png: Data([1, 2, 3]), title: "Notes\nDraft", note: nil)
    }

    func click(at point: CGPoint, right: Bool, double: Bool) throws -> String {
        if let refusal { throw refusal }
        calls.append(.click(point, right: right, double: double))
        return "Clicked."
    }

    func scroll(at point: CGPoint, notches: Int) throws -> String {
        calls.append(.scroll(point, notches))
        return "Scrolled."
    }

    func type(_ text: String) throws -> String {
        calls.append(.type(text))
        return "Typed."
    }

    func press(_ combo: KeyCombo) throws -> String {
        calls.append(.press(combo))
        return "Pressed."
    }
}

final class ResponderTests: XCTestCase {
    var desk: FakeDesk!
    var responder: Responder!

    override func setUp() {
        desk = FakeDesk()
        responder = Responder(desk: desk, say: Say(german: false))
    }

    func reply(_ line: String) throws -> [String: Any] {
        let text = responder.answer(line)
        XCTAssertFalse(text.contains("\n"), "a reply is one line")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any])
    }

    func ask(_ request: [String: Any]) throws -> [String: Any] {
        let data = try JSONSerialization.data(withJSONObject: request)
        return try reply(String(decoding: data, as: UTF8.self))
    }

    func assertRefused(_ request: [String: Any], _ message: String, file: StaticString = #filePath, line: UInt = #line) throws {
        let r = try ask(request)
        XCTAssertEqual(r["ok"] as? Bool, false, file: file, line: line)
        XCTAssertEqual(r["error"] as? String, message, file: file, line: line)
    }

    func testRefusesEverythingWhileNothingIsShared() throws {
        desk.share = nil
        try assertRefused(["cmd": "look"], "Nothing is shared right now. Choose a window or a region in the KnightSight window and start sharing.")
        try assertRefused(["cmd": "click", "x": 10, "y": 10], Refused.nothingShared.message)
        XCTAssertEqual(desk.calls, [])
    }

    func testRefusesAWindowOutOfReach() throws {
        desk.share?.reachable = false
        try assertRefused(["cmd": "type", "text": "hi"], "The shared window is minimized, hidden or on another desktop.")
        XCTAssertEqual(desk.calls, [])
    }

    func testRefusesALineThatIsNoJSONObject() throws {
        for line in ["not json", "[1, 2]", "\"look\"", ""] {
            let r = try reply(line)
            XCTAssertEqual(r["ok"] as? Bool, false)
            XCTAssertEqual(r["error"] as? String, "The request is not a JSON object.")
        }
    }

    func testNamesWhatIsMissing() throws {
        try assertRefused(["x": 1], "Missing cmd.")
        try assertRefused(["cmd": "click", "y": 1], "Missing x.")
        try assertRefused(["cmd": "click", "x": "5", "y": 1], "Missing x.")
        try assertRefused(["cmd": "scroll", "x": 1, "y": 1], "Missing amount.")
        try assertRefused(["cmd": "type"], "Missing text.")
        try assertRefused(["cmd": "key"], "Missing keys.")
    }

    func testRefusesAnUnknownCommand() throws {
        try assertRefused(["cmd": "dance"], "Unknown command: dance")
        XCTAssertEqual(desk.labels, ["dance"])
    }

    func testLookReturnsThePictureAndItsSize() throws {
        let r = try ask(["cmd": "look"])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["image"] as? String, "AQID")
        XCTAssertEqual(r["width"] as? Int, 1568)
        XCTAssertEqual(r["height"] as? Int, 1200)
        XCTAssertEqual(r["title"] as? String, "Notes\nDraft")
        XCTAssertNil(r["note"])
        XCTAssertNil(r["error"])
        XCTAssertEqual(desk.calls, [.look(CGSize(width: 1568, height: 1200))])
        XCTAssertEqual(desk.labels, ["Taking a screenshot"])
    }

    func testPictureKeepsItsLongerEdgeWithinTheLimit() {
        let wide = Share(area: CGRect(x: 0, y: 0, width: 3136, height: 1000), pixelsPerPoint: 2, reachable: true)
        XCTAssertEqual(wide.pictureSize, CGSize(width: 1568, height: 500))
        let small = Share(area: CGRect(x: 0, y: 0, width: 800, height: 600), pixelsPerPoint: 1, reachable: true)
        XCTAssertEqual(small.pictureSize, CGSize(width: 800, height: 600))
    }

    func testClickTurnsPictureCoordinatesIntoScreenPoints() throws {
        let r = try ask(["cmd": "click", "x": 200, "y": 100])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["message"] as? String, "Clicked.")
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 200, y: 250), right: false, double: false)])
        XCTAssertEqual(desk.labels, ["Clicking"])
    }

    func testRefusesAPointOutsideTheShare() throws {
        for (x, y) in [(-2, 10), (1568, 10), (10, 1200), (10, -1)] {
            try assertRefused(["cmd": "click", "x": x, "y": y], "The point lies outside the share.")
            try assertRefused(["cmd": "scroll", "x": x, "y": y, "amount": 1], "The point lies outside the share.")
        }
        XCTAssertEqual(desk.calls, [])
    }

    func testTheTopLeftCornerBelongsToTheShare() throws {
        _ = try ask(["cmd": "click", "x": 0, "y": 0])
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 100, y: 200), right: false, double: false)])
    }

    func testRightAndDoubleClicks() throws {
        _ = try ask(["cmd": "click", "x": 2, "y": 2, "right": true])
        _ = try ask(["cmd": "click", "x": 2, "y": 2, "double": true])
        XCTAssertEqual(desk.calls, [
            .click(CGPoint(x: 101, y: 201), right: true, double: false),
            .click(CGPoint(x: 101, y: 201), right: false, double: true),
        ])
        XCTAssertEqual(desk.labels, ["Right-clicking", "Double-clicking"])
    }

    func testOnlyTrueCountsAsAFlag() throws {
        _ = try ask(["cmd": "click", "x": 2, "y": 2, "right": 1, "double": "yes"])
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 101, y: 201), right: false, double: false)])
    }

    func testScrollRoundsAndBoundsTheAmount() throws {
        for amount in [2.5, -1.5, 3.4, 1e9, -1e9] {
            _ = try ask(["cmd": "scroll", "x": 0, "y": 0, "amount": amount])
        }
        let notches = desk.calls.map { call -> Int in
            guard case .scroll(_, let n) = call else { return 0 }
            return n
        }
        XCTAssertEqual(notches, [2, -2, 3, 100, -100])
    }

    func testTypePassesTheTextUnchanged() throws {
        let r = try ask(["cmd": "type", "text": "Grüße\nzweite Zeile"])
        XCTAssertEqual(r["message"] as? String, "Typed.")
        XCTAssertEqual(desk.calls, [.type("Grüße\nzweite Zeile")])
    }

    func testKeyIsParsedBeforeItReachesTheDesk() throws {
        let r = try ask(["cmd": "key", "keys": "cmd+shift+z"])
        XCTAssertEqual(r["message"] as? String, "Pressed.")
        XCTAssertEqual(desk.calls, [.press(KeyCombo(modifiers: [.command, .shift], key: 0x06))])
        XCTAssertEqual(desk.labels, ["Pressing Cmd+Shift+Z"])
    }

    func testRefusedKeysNeverReachTheDesk() throws {
        try assertRefused(["cmd": "key", "keys": "win+r"], "A Mac has no Windows key. App shortcuts use cmd.")
        XCTAssertEqual(desk.calls, [])
    }

    func testARefusalFromTheDeskIsPassedOn() throws {
        desk.refusal = Refused("No window that takes input lies at this point.")
        try assertRefused(["cmd": "click", "x": 2, "y": 2], "No window that takes input lies at this point.")
    }

    func testLabelsFollowTheLanguage() throws {
        responder = Responder(desk: desk, say: Say(german: true))
        _ = try ask(["cmd": "key", "keys": "ctrl+alt+delete"])
        _ = try ask(["cmd": "look"])
        _ = try ask(["cmd": "key", "keys": "shift+pageup"])
        XCTAssertEqual(desk.labels, ["Drücke Ctrl+Alt+Entf", "Mache Screenshot", "Drücke Umschalt+Bild auf"])
    }

    func testRepliesStayEnglishInGerman() throws {
        responder = Responder(desk: desk, say: Say(german: true))
        desk.share = nil
        try assertRefused(["cmd": "look"], Refused.nothingShared.message)
    }
}
