import test from "node:test";
import assert from "node:assert/strict";
import { MarkdownAtomizer } from "../../src/cognitive/markdown-atomizer.js";

test("Markdown atomization preserves structure, Unicode, exact content and line positions", () => {
  const source = [
    "# Titre", "", "Paragraphe éthique", "sur deux lignes.", "", "- Élément", "- Élément", "", "> Citation", "> suite", "",
    "```ts", "const été = true;", "```", "", "---", "", "Ligne isolée",
  ].join("\n");
  const result = new MarkdownAtomizer().atomize("SRC-0001", source, "EXE", "2026-01-01T00:00:00.000Z");
  assert.deepEqual(result.atoms.map((atom) => atom.atom_type), ["heading", "paragraph", "list_item", "list_item", "blockquote", "code_block", "separator", "isolated_line"]);
  assert.equal(result.atoms[1]?.content, "Paragraphe éthique\nsur deux lignes.");
  assert.deepEqual(result.atoms[1]?.source_position, { start_line: 3, end_line: 4 });
  assert.notEqual(result.atoms[2]?.atom_id, result.atoms[3]?.atom_id, "repeated content remains addressable by occurrence");
  assert.equal(result.report.ignored_blank_lines, 6);
});

test("stable ids survive identical input and unaffected atoms survive a partial change", () => {
  const atomizer = new MarkdownAtomizer();
  const first = atomizer.atomize("SRC-0001", "# Stable\n\nPremier\n\nSecond", "A").atoms;
  const second = atomizer.atomize("SRC-0001", "# Stable\n\nPremier modifié\n\nSecond", "B").atoms;
  const repeat = atomizer.atomize("SRC-0001", "# Stable\n\nPremier\n\nSecond", "C").atoms;
  assert.deepEqual(first.map((atom) => atom.atom_id), repeat.map((atom) => atom.atom_id));
  assert.equal(first[0]?.atom_id, second[0]?.atom_id);
  assert.equal(first[2]?.atom_id, second[2]?.atom_id);
  assert.notEqual(first[1]?.atom_id, second[1]?.atom_id);
  assert.throws(() => atomizer.atomize("SRC-0001", " \n", "D"), /empty/);
});
