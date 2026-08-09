import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { CognitiveStore } from "../../src/cognitive/cognitive-store.js";
import { MarkdownAtomizer } from "../../src/cognitive/markdown-atomizer.js";
import { TileBuilder } from "../../src/cognitive/tile-builder.js";
import { ProvenanceGraphBuilder } from "../../src/cognitive/provenance-graph.js";
import { stableId } from "../../src/cognitive/ids.js";
import type { CognitiveRelation, Tile } from "../../src/cognitive/types.js";

test("SQLite ingestion is idempotent, persistent and rejects orphan provenance", () => {
  const database = join(mkdtempSync(join(tmpdir(), "aione-cog-store-")), "state.db");
  const parsed = new MarkdownAtomizer().atomize("SRC-0001", "Alpha dépend de Beta.\n\nBeta est distinct.", "EXE");
  let store = new CognitiveStore(database);
  const first = store.ingest("SRC-0001", "sources/test.md", parsed.atoms, parsed.report);
  const second = store.ingest("SRC-0001", "sources/test.md", parsed.atoms, parsed.report);
  assert.equal(first.atoms.length, 2); assert.equal(second.atoms.length, 2); assert.equal(second.report.idempotent, true);
  store.close(); store = new CognitiveStore(database); assert.equal(store.atoms("SRC-0001").length, 2);
  const tiles = new TileBuilder(["Alpha", "Beta"]).build("SRC-0001", store.atoms("SRC-0001"));
  store.saveTiles("SRC-0001", tiles); assert.equal(store.tiles("SRC-0001").length, 2);
  const withoutProvenance = { ...tiles[0]! } as Partial<Tile>; delete withoutProvenance.provenance;
  assert.throws(() => store.saveTiles("SRC-0001", [withoutProvenance as Tile]), /no provenance/);
  assert.throws(() => store.saveTiles("SRC-0001", [{ ...tiles[0]!, tile_id: "TILE-FFFFFFFFFFFFFFFF", atom_ids: ["ATM-ORPHAN"], provenance: { ...tiles[0]!.provenance, atom_ids: ["ATM-ORPHAN"] } }]), /orphan atom/);
  store.close();
});

test("provenance graph stores valid endpoints and rejects unauthorized dependency cycles", () => {
  const database = join(mkdtempSync(join(tmpdir(), "aione-cog-graph-")), "state.db");
  const store = new CognitiveStore(database);
  const parsed = new MarkdownAtomizer().atomize("SRC-0001", "Alpha et Beta.", "EXE");
  store.ingest("SRC-0001", "sources/test.md", parsed.atoms, parsed.report);
  const tiles = new TileBuilder(["Alpha", "Beta"]).build("SRC-0001", parsed.atoms); store.saveTiles("SRC-0001", tiles);
  const graph = new ProvenanceGraphBuilder().build("SRC-0001", parsed.atoms, tiles); store.saveRelations(graph);
  assert.ok(store.relations().some((relation) => relation.relation_type === "supports"));
  const make = (from: string, to: string): CognitiveRelation => ({
    schema_version: 1, relation_id: stableId("REL", from, "depends_on", to), from, to, relation_type: "depends_on",
    provenance: { method: "test" }, confidence: "medium", justification: "test dependency", status: "inferred", created_at: new Date().toISOString(),
  });
  store.saveRelations([make(tiles[0]!.tile_id, tiles[1]!.tile_id)]);
  assert.throws(() => store.saveRelations([make(tiles[1]!.tile_id, tiles[0]!.tile_id)]), /circular/);
  store.close();
});

test("a locked database fails explicitly instead of hiding persistence errors", () => {
  const database = join(mkdtempSync(join(tmpdir(), "aione-cog-lock-")), "state.db");
  const store = new CognitiveStore(database);
  const parsed = new MarkdownAtomizer().atomize("SRC-0001", "Alpha", "EXE");
  const locker = new DatabaseSync(database); locker.exec("BEGIN EXCLUSIVE");
  assert.throws(() => store.ingest("SRC-0001", "sources/test.md", parsed.atoms, parsed.report), /locked|busy/i);
  locker.exec("ROLLBACK"); locker.close(); store.close();
});
