// Regenerates lib/api-types.ts from the FastAPI app's OpenAPI schema.
// Imports api.main with the repo's .venv Python and calls app.openapi()
// directly: no server, and no database is opened.
import { execFileSync } from "node:child_process"
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

const repoRoot = resolve(import.meta.dirname, "..", "..")
const python = [
  join(repoRoot, ".venv", "Scripts", "python.exe"),
  join(repoRoot, ".venv", "bin", "python"),
].find(existsSync)
if (!python) throw new Error(`No .venv Python found under ${repoRoot}`)

const schema = execFileSync(
  python,
  ["-c", "import json; from api.main import app; print(json.dumps(app.openapi()))"],
  { cwd: repoRoot, encoding: "utf-8", maxBuffer: 64 * 1024 * 1024 }
)

const dir = mkdtempSync(join(tmpdir(), "rebel-openapi-"))
const schemaPath = join(dir, "openapi.json")
try {
  writeFileSync(schemaPath, schema)
  // --default-non-nullable=false: a request field with a default (e.g.
  // OrderCreate.packaging_kit_id = "default") stays optional instead of
  // becoming required. No response schema has optional defaulted fields.
  execFileSync(
    "npx",
    [
      "openapi-typescript",
      schemaPath,
      "-o",
      "lib/api-types.ts",
      "--default-non-nullable=false",
    ],
    { cwd: resolve(import.meta.dirname, ".."), stdio: "inherit", shell: true }
  )
} finally {
  rmSync(dir, { recursive: true, force: true })
}
