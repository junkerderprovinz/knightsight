import ast
import os
import unittest

PACKAGE = os.path.join(os.path.dirname(__file__), "..", "knightsight")


def tree(name):
    with open(os.path.join(PACKAGE, name), encoding="utf-8") as f:
        return ast.parse(f.read())


def used(name, owner):
    """Every attribute the module reads from the desk, as self.desk.x or desk.x."""
    names = set()
    for node in ast.walk(tree(name)):
        if isinstance(node, ast.Attribute):
            base = node.value
            if getattr(base, "attr", None) == owner or getattr(base, "id", None) == owner:
                names.add(node.attr)
    return names


def offered(name):
    desk = next(n for n in tree(name).body if isinstance(n, ast.ClassDef) and n.name == "Desk")
    names = set()
    for node in desk.body:
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


class Desks(unittest.TestCase):
    def test_both_desks_offer_what_the_panel_and_the_protocol_use(self):
        needed = used("panel.py", "desk") | used("protocol.py", "desk")
        self.assertIn("hide", needed)
        for module in ("x11.py", "portal.py"):
            with self.subTest(module):
                self.assertEqual(needed - offered(module), set())


if __name__ == "__main__":
    unittest.main()
