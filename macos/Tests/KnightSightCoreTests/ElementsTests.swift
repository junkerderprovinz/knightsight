import CoreGraphics
import XCTest
@testable import KnightSightCore

final class ElementsTests: XCTestCase {
    // Two picture pixels to the point, as on a Retina screen.
    let share = Share(area: CGRect(x: 100, y: 200, width: 784, height: 600), pixelsPerPoint: 2, reachable: true)

    func box(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat = 40, _ height: CGFloat = 20) -> CGRect {
        CGRect(x: x, y: y, width: width, height: height)
    }

    func testRolesMapOntoTheClosedSet() {
        let roles: [(Node, String?)] = [
            (Node(role: "AXButton", frame: .zero), "button"),
            (Node(role: "AXButton", subrole: "AXCloseButton", frame: .zero), "button"),
            (Node(role: "AXDisclosureTriangle", frame: .zero), "button"),
            (Node(role: "AXLink", frame: .zero), "link"),
            (Node(role: "AXTextField", frame: .zero), "edit"),
            (Node(role: "AXTextArea", frame: .zero), "edit"),
            (Node(role: "AXTextField", subrole: "AXSecureTextField", frame: .zero), "edit"),
            (Node(role: "AXCheckBox", subrole: "AXSwitch", frame: .zero), "checkbox"),
            (Node(role: "AXRadioButton", frame: .zero), "radio"),
            (Node(role: "AXRadioButton", parent: "AXTabGroup", frame: .zero), "tab"),
            (Node(role: "AXRadioButton", subrole: "AXTabButton", frame: .zero), "tab"),
            (Node(role: "AXPopUpButton", frame: .zero), "combobox"),
            (Node(role: "AXComboBox", frame: .zero), "combobox"),
            (Node(role: "AXMenuItem", frame: .zero), "menuitem"),
            (Node(role: "AXRow", frame: .zero), "listitem"),
            (Node(role: "AXRow", subrole: "AXOutlineRow", frame: .zero), "treeitem"),
            (Node(role: "AXSlider", frame: .zero), "slider"),
            (Node(role: "AXStaticText", frame: .zero), "text"),
            (Node(role: "AXGroup", frame: .zero), nil),
            (Node(role: "AXScrollArea", frame: .zero), nil),
            (Node(role: "AXWindow", frame: .zero), nil),
            (Node(role: "AXImage", label: "Logo", frame: .zero), nil),
            (Node(role: "AXWebArea", frame: .zero), nil),
        ]
        for (node, role) in roles {
            XCTAssertEqual(Elements.role(of: node), role, "\(node.role) \(node.subrole ?? "")")
        }
    }

    func testANameIsTrimmedOntoOneLineAndCut() {
        XCTAssertEqual(Elements.name(of: Node(role: "AXButton", title: "  Save\n now ", frame: .zero), role: "button"), "Save now")
        XCTAssertEqual(Elements.name(of: Node(role: "AXButton", title: "", label: "Close", frame: .zero), role: "button"), "Close")
        let long = String(repeating: "word ", count: 40)
        XCTAssertEqual(Elements.name(of: Node(role: "AXLink", title: long, frame: .zero), role: "link")?.count, 80)
        XCTAssertNil(Elements.name(of: Node(role: "AXButton", title: " \n ", frame: .zero), role: "button"))
    }

    func testStaticTextIsNamedByItsWords() {
        XCTAssertEqual(Elements.name(of: Node(role: "AXStaticText", text: "Quest Log", frame: .zero), role: "text"), "Quest Log")
    }

    func testAnEditFieldNeverNamesWhatIsTypedAndAPasswordFieldGivesNothing() {
        XCTAssertNil(Elements.name(of: Node(role: "AXTextField", text: "my draft", frame: .zero), role: "edit"))
        XCTAssertEqual(Elements.name(of: Node(role: "AXTextField", label: "Search", text: "my draft", frame: .zero), role: "edit"), "Search")
        let password = Node(role: "AXTextField", subrole: "AXSecureTextField", title: "Password", label: "Password", frame: box(110, 210))
        XCTAssertNil(Elements.name(of: password, role: "edit"))
        XCTAssertEqual(Elements.list([password], in: share).map(\.role), ["edit"])
        XCTAssertEqual(Elements.list([password], in: share).map(\.name), [nil])
    }

    func testElementsComeTopToBottomThenLeftToRightNumberedInThatOrder() {
        let list = Elements.list([
            Node(role: "AXButton", title: "Lower", frame: box(110, 400)),
            Node(role: "AXButton", title: "Right", frame: box(500, 210)),
            Node(role: "AXButton", title: "Left", frame: box(110, 210)),
        ], in: share)
        XCTAssertEqual(list.map(\.ref), ["e1", "e2", "e3"])
        XCTAssertEqual(list.map(\.name), ["Left", "Right", "Lower"])
    }

    func testElementsAreInPictureCoordinatesAndCutToTheShare() {
        let list = Elements.list([
            Node(role: "AXButton", title: "Inside", frame: box(110, 210, 40, 20)),
            Node(role: "AXButton", title: "Across", frame: box(860, 780, 50, 50)),
        ], in: share)
        XCTAssertEqual(list, [
            Element(ref: "e1", role: "button", name: "Inside", x: 20, y: 20, width: 80, height: 40),
            Element(ref: "e2", role: "button", name: "Across", x: 1520, y: 1160, width: 48, height: 40),
        ])
        XCTAssertEqual(list[0].centre.x, 60)
        XCTAssertEqual(list[0].centre.y, 40)
    }

    func testLeavesOutWhatCannotBeClickedOrSeen() {
        let list = Elements.list([
            Node(role: "AXGroup", title: "Pane", frame: box(110, 210)),
            Node(role: "AXButton", title: "Outside", frame: box(900, 210)),
            Node(role: "AXButton", title: "Flat", frame: box(110, 210, 0, 20)),
            Node(role: "AXButton", frame: box(110, 210), enabled: false),
            Node(role: "AXStaticText", frame: box(110, 210)),
            Node(role: "AXButton", title: "Greyed", frame: box(110, 300), enabled: false),
            Node(role: "AXButton", frame: box(110, 400)),
        ], in: share)
        XCTAssertEqual(list.map(\.name), ["Greyed", nil])
    }

    func testAtMostAHundredAndFiftyElements() {
        let nodes = (0..<200).map { Node(role: "AXButton", title: "B\($0)", frame: box(110, 210 + CGFloat($0 * 2), 40, 2)) }
        let list = Elements.list(nodes, in: share)
        XCTAssertEqual(list.count, 150)
        XCTAssertEqual(list.last?.ref, "e150")
        XCTAssertEqual(list.last?.name, "B149")
    }

    func testAWindowBelongsToTheProcessItWasChosenIn() {
        let owner = Owner(pid: 412, started: 1_700_000_000_123_456)
        let starts: [Int32: Int64] = [412: 1_700_000_000_123_456, 413: 1_700_000_000_123_456]
        XCTAssertTrue(owner.owns(412) { starts[$0] })
        XCTAssertFalse(owner.owns(413) { starts[$0] }, "a window of another process")
        XCTAssertFalse(owner.owns(412) { _ in 1_700_000_999_000_000 }, "a later process with the same id")
        XCTAssertFalse(owner.owns(412) { _ in nil }, "a process that is gone")
    }
}
