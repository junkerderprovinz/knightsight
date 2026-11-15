import CoreGraphics
import Foundation
import XCTest
@testable import KnightSightCore

final class PinboardTests: XCTestCase {
    let share = Share(area: CGRect(x: 100, y: 200, width: 800, height: 600), pixelsPerPoint: 2, reachable: true)

    func note(_ mark: CGRect, number: Int = 1, kind: NoteKind = .wish, text: String = "Here.", author: String = "") -> Note {
        Note(number: number, kind: kind, text: text, author: author, mark: mark)
    }

    func round(_ notes: [Note], number: Int = 1) -> Round {
        Round(number: number, sent: Date(timeIntervalSince1970: 0), title: "notes.txt", share: share, image: Data([7]), notes: notes) { _, _ in Data([9]) }
    }

    func testNumbersCountOnAcrossRoundsAndClearing() {
        let board = Board()
        board.add(.bug, "One", author: "", mark: .zero)
        board.add(.wish, "Two", author: "", mark: .zero)
        board.send(round(board.notes))
        XCTAssertEqual(board.add(.wish, "Three", author: "", mark: .zero).number, 3)
        board.clear()
        XCTAssertEqual(board.add(.wish, "Four", author: "", mark: .zero).number, 4)
        XCTAssertEqual(board.notes.map(\.number), [4])
    }

    func testSendingTakesOnlyItsOwnNotesOffTheBoard() {
        let board = Board()
        let first = board.add(.bug, "One", author: "", mark: .zero)
        board.add(.wish, "Two", author: "", mark: .zero)
        board.send(round([first]))
        XCTAssertEqual(board.notes.map(\.text), ["Two"])
    }

    func testRoundsCountUpAndOnlyTheLatestIsKept() {
        let board = Board()
        XCTAssertEqual(board.nextRound, 1)
        board.send(round([note(.zero)], number: board.nextRound))
        board.send(round([note(.zero, number: 2)], number: board.nextRound))
        XCTAssertEqual(board.nextRound, 3)
        let (number, latest) = board.fetch(unread: false)
        XCTAssertEqual(number, 2)
        XCTAssertEqual(latest?.entries.map(\.note.number), [2])
    }

    func testARoundCountsAsFetchedOnceHandedOut() {
        let board = Board()
        board.send(round([note(.zero)]))
        XCTAssertFalse(board.fetched(1))
        _ = board.fetch(unread: true)
        XCTAssertTrue(board.fetched(1))
        board.send(round([note(.zero, number: 2)], number: 2))
        XCTAssertFalse(board.fetched(2))
    }

    func testAnUpdateKeepsTheMarkAndTheNumber() {
        let board = Board()
        let mark = CGRect(x: 5, y: 6, width: 7, height: 8)
        let added = board.add(.wish, "Old", author: "A", mark: mark)
        board.update(added.number, kind: .question, text: "New", author: "B")
        XCTAssertEqual(board.notes, [Note(number: 1, kind: .question, text: "New", author: "B", mark: mark)])
    }

    func testARectangleCropsWithAMarginCutToTheShare() {
        XCTAssertEqual(share.cropBox(for: note(CGRect(x: 100, y: 100, width: 50, height: 20))), CGRect(x: 76, y: 76, width: 98, height: 68))
        XCTAssertEqual(share.cropBox(for: note(CGRect(x: 10, y: 590, width: 50, height: 10))), CGRect(x: 0, y: 566, width: 84, height: 34))
    }

    func testAPinCropsABoxAroundItCutToTheShare() {
        XCTAssertEqual(share.cropBox(for: note(CGRect(x: 400, y: 300, width: 0, height: 0))), CGRect(x: 280, y: 180, width: 240, height: 240))
        XCTAssertEqual(share.cropBox(for: note(CGRect(x: 790, y: 20, width: 0, height: 0))), CGRect(x: 670, y: 0, width: 130, height: 140))
    }

    func testAMarkOutsideTheShareHasNoCrop() {
        XCTAssertNil(share.cropBox(for: note(CGRect(x: 820, y: 10, width: 30, height: 30))))
        XCTAssertNil(share.cropBox(for: note(CGRect(x: 10, y: 600, width: 0, height: 0))))
    }

    func testCropsKeepTheScreenDensityUntilTheLongerEdgeHitsTheLimit() {
        XCTAssertEqual(share.cropScale(CGRect(x: 0, y: 0, width: 240, height: 240)), 2)
        XCTAssertEqual(share.cropScale(CGRect(x: 0, y: 0, width: 1568, height: 100)), 1)
    }

    func testMarksLandInPictureCoordinates() {
        let wide = Share(area: CGRect(x: 0, y: 0, width: 3136, height: 1000), pixelsPerPoint: 2, reachable: true)
        XCTAssertEqual(wide.picture(CGRect(x: 100, y: 50, width: 20, height: 10)), CGRect(x: 50, y: 25, width: 10, height: 5))
        let sharp = Share(area: CGRect(x: 0, y: 0, width: 784, height: 600), pixelsPerPoint: 2, reachable: true)
        XCTAssertEqual(sharp.picture(CGRect(x: 100, y: 50, width: 0, height: 0)), CGRect(x: 200, y: 100, width: 0, height: 0))
    }

    func testACardGoesRightOfTheSpotWhenTheScreenHasRoom() {
        let screen = CGRect(x: 0, y: 25, width: 1440, height: 875)
        let size = CGSize(width: 300, height: 200)
        XCTAssertEqual(Placement.beside(CGRect(x: 100, y: 100, width: 50, height: 50), size: size, within: screen), CGPoint(x: 162, y: 100))
        XCTAssertEqual(Placement.beside(CGRect(x: 1200, y: 800, width: 50, height: 50), size: size, within: screen), CGPoint(x: 888, y: 700))
        XCTAssertEqual(Placement.beside(CGRect(x: 0, y: 0, width: 1440, height: 400), size: size, within: screen), CGPoint(x: 0, y: 412))
    }

    func testSentCountsTheNotes() {
        XCTAssertEqual(Say(german: false).sent(1), "Sent 1 note. Your assistant can fetch it now.")
        XCTAssertEqual(Say(german: false).sent(3), "Sent 3 notes. Your assistant can fetch them now.")
        XCTAssertEqual(Say(german: true).sent(1), "1 Notiz gesendet. Dein Assistent kann sie abholen.")
        XCTAssertEqual(Say(german: true).sent(3), "3 Notizen gesendet. Dein Assistent kann sie abholen.")
    }

    func testTheFileCarriesItsPicturesAndEscapesWhatWasTyped() {
        let page = round([note(CGRect(x: 10, y: 10, width: 20, height: 20), kind: .bug, text: "<b>bold</b> & \"quoted\"", author: "Junker")]).page(Say(german: false))
        XCTAssertTrue(page.hasPrefix("<!doctype html>"))
        XCTAssertTrue(page.contains("<html lang=\"en\">"))
        XCTAssertTrue(page.contains("<h1>Pinboard notes on notes.txt</h1>"))
        XCTAssertTrue(page.contains("Round 1"))
        XCTAssertTrue(page.contains("src=\"data:image/png;base64,Bw==\""))
        XCTAssertTrue(page.contains("src=\"data:image/png;base64,CQ==\""))
        XCTAssertTrue(page.contains("&lt;b&gt;bold&lt;/b&gt; &amp; &quot;quoted&quot;"))
        XCTAssertTrue(page.contains(">Bug<"))
        XCTAssertTrue(page.contains(">from Junker<"))
        XCTAssertTrue(page.contains("background: #fa4d56"))
        XCTAssertFalse(page.contains("<b>"))
    }

    func testTheFileSpeaksThePersonsLanguage() {
        let page = round([note(CGRect(x: 10, y: 10, width: 0, height: 0), kind: .question, author: "Junker")]).page(Say(german: true))
        XCTAssertTrue(page.contains("<html lang=\"de\">"))
        XCTAssertTrue(page.contains("Pinnwand-Notizen zu notes.txt"))
        XCTAssertTrue(page.contains("Runde 1"))
        XCTAssertTrue(page.contains(">Frage<"))
        XCTAssertTrue(page.contains(">von Junker<"))
    }

    func testTheFileLeavesOutAnEmptyAuthor() {
        let page = round([note(CGRect(x: 10, y: 10, width: 20, height: 20))]).page(Say(german: false))
        XCTAssertFalse(page.contains("class=\"from\""))
    }
}
