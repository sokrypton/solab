# Paper corrections

Reading pages are generated, not written. Extraction is heuristic and gets
things wrong; this directory is where those wrongs are corrected, in a form
that survives re-running extraction.

```
.cache/pdf/<slug>.pdf      the paper                       (input, gitignored)
.cache/doc/<slug>.json     extracted nodes                 (generated, gitignored)
edits/<slug>.json          corrections, by node id         (tracked — the work)
edits/<slug>.md            what was wrong and why          (tracked — the record)
papers/<slug>/index.html   the page                        (generated)
```

Never edit `.cache/doc/*.json` or `papers/*/index.html`. Both are regenerated
and your work would vanish. Write an op instead.

## The loop

```sh
python3 scripts/extract_pdf.py --only SUBSTRING   # PDF  -> nodes + figure crops
python3 scripts/audit_papers.py --slug SUBSTRING  # what looks wrong, with ids
#   ... write edits/<slug>.json + edits/<slug>.md ...
python3 scripts/build_papers.py --only SUBSTRING  # nodes + ops -> page
```

`build_papers` prints `doc (3 edits)` when it applied an overlay, and
`doc (2 edits, 1 STALE)` when an op no longer matches any node — which means
extraction changed under it. Stale ops are never applied silently; go look.

## Ops

Every op names a node by `id`. Ids come from `audit_papers.py`, from
`.cache/doc/<slug>.json`, or from the page itself — each rendered element
carries its own `data-node` attribute, so you can read the HTML and point at
exactly what you saw.

```json
{
 "slug": "2024-scalable-protein-design-using-optimization-in-a-relaxed-sequence-space",
 "ops": [
  {"op": "drop",   "id": "p8-c9bc3d", "why": "Science's editor's summary, not the paper"},
  {"op": "set",    "id": "p6-44ab21", "text": "corrected text", "why": "ligature mangled"},
  {"op": "retype", "id": "p4-1c7d09", "to": "caption",  "why": "figure caption read as prose"},
  {"op": "level",  "id": "p2-aa1130", "to": 3,          "why": "subsection, not a section"},
  {"op": "after",  "id": "p3-cc3341", "node": {"type": "heading", "text": "Methods"},
                                      "why": "heading lost in extraction"}
 ]
}
```

| op | effect |
|----|--------|
| `drop` | node is not rendered |
| `set` | replaces `text` |
| `retype` | changes `type` — `prose`, `heading`, `caption`, `figure` |
| `level` | forces heading depth (2 or 3) |
| `after` | inserts a new node after this one |

`why` is required by convention, not by the parser. It is what makes the next
pass — human or agent — able to tell a deliberate decision from a guess.

## Node ids

An id is `p<page>-<hash of the first 200 characters of the text>`. It follows
the content, not the position, so inserting a paragraph earlier in the paper
does not shift anyone else's id. The trade-off is deliberate: if extraction
later changes a node's text, its id changes and the op goes stale rather than
landing on the wrong paragraph.

## Node types

Set by the extractor; `retype` overrides it.

| rendered | |
|---|---|
| `prose` | a paragraph |
| `heading` | section heading — `run_in: true` marks one lifted out of a paragraph |
| `figure` | artwork with a caption, cropped from the page |
| `caption` | a caption whose artwork could not be located |

| not rendered | |
|---|---|
| `small` | set below body size — axis labels, panel keys, footnotes |
| `figure-text` | text inside a figure's area |
| `furniture` | running heads and folios |
| `stamp` | preprint and copyright stamps |
| `rotated` | sideways text |
| `refs-head`, `apparatus-head` | back-matter headings |

Nodes also carry a `role`: `front` (cover furniture), `back` (acknowledgments,
availability statements), `references` (bibliography, rendered as a list).

## The changelog

`edits/<slug>.md` records what was wrong, in prose. It is not parsed. Its
purpose is that the next pass over this paper starts from what was already
learned rather than rediscovering it:

```markdown
# 2024-scalable-protein-design…

- Science prints an "Editor's summary" panel on the last page. Extraction reads
  it as a section because it is set as a heading. Dropped 3 nodes (p8-c9bc3d
  and the two following).
- Figures 2 and 3 crop correctly; figure 4's panel E legend sits outside the
  artwork cluster and is missing from the crop. Not fixable by an op — it needs
  the extractor's region growth to reach further. Left alone.
```

Distinguishing "fixed with an op" from "needs the extractor changed" is the
most useful thing a changelog entry can do: the second kind, seen three times
across three papers, is a bug to fix once in `extract_pdf.py` instead of three
overlays that paper over it.
