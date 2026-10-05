"""What more than one noun's checker needs. No noun owns it, so it has its own home.

`lib/<noun>/` holds one noun's implementation, and the test is the entry that runs it:
`lib/packaging/` is what `check_packaging.py` does, `lib/lexicon/` is what `lexicon.py`
does.

  `_root`          find the repo root; decide whether two paths are the same repository
  `_files`         list what git tracks, and scope it
  `_constants`     the delivered records and the names a repo may not carry
  `_readme_block`  splice a generated block between its markers, or leave the file alone
  `_slug`          the repo's own short name, and the brief that should carry it
  `_spec`          where a package keeps `surface.jsonl`, and its rows
  `_commits`       COMMITS.md's rules: type to bump, the subject, the version home
  `_agent_docs`    the filenames that carry agent instructions
  `_frontmatter`   the `---` block at the top of a markdown file, and what it declares
  `_markdown`      which lines of a markdown document are fenced code
  `_report`        a checker's findings, and printing them as `<prog>: <severity>: ...`
  `_switches`      how `RACECAR_STRICT` is read
  `_as_json`       `--json` for a verb that prints as it works
  `_imports`       walk the `@path` import chain an instruction file declares
  `_templates`     mirror a template tree into an output tree, substituting placeholders
  `_results`       read JUnit XML test records, and say what they add up to
  `_test_files`    which files are tests, per language, by each runner's naming rule

Each is a leaf: they import from the standard library and from nothing here, with one
exception. Any of them may import `_root`, the most basic of them: where the repo is and what
it declares it is called (`project_name`). `_root` itself imports nothing here, so the
exception adds one floor beneath the others and cannot make a cycle. Otherwise the rule is
the admission test -- a module that needs a sibling is doing a noun's work and belongs under
that noun. Adding any other import between two of these files is the signal to move one out,
not to let the layer grow.

Named `shared` and not `common` because `lib/packaging/_common.py` already exists and
means something else: packaging's OWN helpers, TOML loading and audit rendering, private
to that checker. Two spellings of one word for two different scopes is the collision
worth one letter to avoid.

Delivered whole, like every other package under `lib/`.

Complexity: O(1) -- seventeen leaves and the rule that keeps them leaves
"""
