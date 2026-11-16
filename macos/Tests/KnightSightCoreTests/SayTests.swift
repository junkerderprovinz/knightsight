import XCTest
@testable import KnightSightCore

final class SayTests: XCTestCase {
    func testAScreenIsNamedByItsNumberAndSize() {
        XCTAssertEqual(Say(german: false).screen(1, width: 2560, height: 1440), "Screen 1 (2560 x 1440)")
        XCTAssertEqual(Say(german: true).screen(2, width: 1440, height: 900), "Bildschirm 2 (1440 x 900)")
    }
}
