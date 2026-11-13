import XCTest
@testable import KnightSightCore

final class KeyComboTests: XCTestCase {
    func parse(_ combo: String) throws -> KeyCombo {
        try KeyCombo(parsing: combo, layout: TestLayout())
    }

    func assertRefused(_ combo: String, _ message: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertThrowsError(try parse(combo), file: file, line: line) { error in
            XCTAssertEqual((error as? Refused)?.message, message, file: file, line: line)
        }
    }

    func testModifiersAndALetter() throws {
        XCTAssertEqual(try parse("ctrl+l"), KeyCombo(modifiers: .control, key: 0x25))
        XCTAssertEqual(try parse("cmd+shift+z"), KeyCombo(modifiers: [.command, .shift], key: 0x06))
        XCTAssertEqual(try parse("strg+c"), KeyCombo(modifiers: .control, key: 0x08))
        XCTAssertEqual(try parse("meta+a"), KeyCombo(modifiers: .command, key: 0x00))
        XCTAssertEqual(try parse("opt+1"), KeyCombo(modifiers: .option, key: 0x12))
    }

    func testCaseAndSpacesDoNotMatter() throws {
        XCTAssertEqual(try parse(" Ctrl + Alt + Delete "), KeyCombo(modifiers: [.control, .option], key: 0x75))
        XCTAssertEqual(try parse("CMD+L"), KeyCombo(modifiers: .command, key: 0x25))
    }

    func testNamedKeys() throws {
        XCTAssertEqual(try parse("enter"), KeyCombo(modifiers: [], key: 0x24))
        XCTAssertEqual(try parse("return"), KeyCombo(modifiers: [], key: 0x24))
        XCTAssertEqual(try parse("shift+tab"), KeyCombo(modifiers: .shift, key: 0x30))
        XCTAssertEqual(try parse("escape"), KeyCombo(modifiers: [], key: 0x35))
        XCTAssertEqual(try parse("backspace"), KeyCombo(modifiers: [], key: 0x33))
        XCTAssertEqual(try parse("pagedown"), KeyCombo(modifiers: [], key: 0x79))
        XCTAssertEqual(try parse("up"), KeyCombo(modifiers: [], key: 0x7E))
    }

    func testFunctionKeysUpToTwenty() throws {
        XCTAssertEqual(try parse("f1"), KeyCombo(modifiers: [], key: 0x7A))
        XCTAssertEqual(try parse("F5"), KeyCombo(modifiers: [], key: 0x60))
        XCTAssertEqual(try parse("shift+f20"), KeyCombo(modifiers: .shift, key: 0x5A))
        assertRefused("f21", "This keyboard has no such key: f21")
        assertRefused("f25", "Unknown key: f25")
        assertRefused("f0", "Unknown key: f0")
    }

    func testACharacterBringsTheModifiersItNeeds() throws {
        XCTAssertEqual(try parse("?"), KeyCombo(modifiers: .shift, key: 0x2C))
        XCTAssertEqual(try parse("cmd+?"), KeyCombo(modifiers: [.command, .shift], key: 0x2C))
        XCTAssertEqual(try parse("shift+?"), KeyCombo(modifiers: .shift, key: 0x2C))
        XCTAssertEqual(try parse("ctrl+@"), KeyCombo(modifiers: [.control, .option], key: 0x25))
    }

    func testRefusesTheWindowsKey() {
        assertRefused("win+r", "A Mac has no Windows key. App shortcuts use cmd.")
        assertRefused("windows", "A Mac has no Windows key. App shortcuts use cmd.")
    }

    func testRefusesWhatCannotBePressed() {
        assertRefused("ctrl+a+c", "Only one key besides Ctrl, Option, Shift and Cmd: ctrl+a+c")
        assertRefused("ctrl+shift", "The key itself is missing: ctrl+shift")
        assertRefused("", "Unknown key: ")
        assertRefused("ctrl++", "Unknown key: ")
        assertRefused("insert", "This keyboard has no such key: insert")
        assertRefused("é", "This keyboard has no such key: é")
        assertRefused("hyper+x", "Unknown key: hyper")
    }
}
