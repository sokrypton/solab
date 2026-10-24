#!/usr/bin/env python3
"""Retire the corrections that extraction has made unnecessary.

Every time extract_pdf.py gets better — or a paper switches to a publisher's
own conversion — some ops in edits/<slug>.json stop being needed. Three ways:

  stale       the node id no longer exists (its text changed, or the paper is
              now sourced from somewhere else entirely)
  redundant   the node exists but is already hidden by classification, so the
              op is a no-op that only looks like work
  live        the op still changes what a reader sees

Retired ops are moved to a "retired" list rather than deleted: the reason
someone wrote an op is worth keeping even when the op itself is obsolete, and
it is the record that stops a later pass rediscovering the same defect.

    python3 scripts/prune_edits.py            report only
    python3 scripts/prune_edits.py --apply    rewrite the overlays
"""

import argparse
import datetime
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_DIR = os.path.join(REPO, '.cache', 'doc')
EDIT_DIR = os.path.join(REPO, 'edits')

sys.path.insert(0, os.path.join(REPO, 'scripts'))
from build_papers import (DOC_HIDDEN, already_present,      # noqa: E402
                          fingerprint, resolve)

HIDDEN_ROLES = ('front', 'back', 'references')


def renders_from_doc(slug):
    """Does this paper's page actually come from its extracted document?

    Where a publisher supplies JATS the builder prefers it, and the overlay
    cannot reach the page at all — so every op against it is dead weight,
    however well it matches a node.
    """
    page = os.path.join(REPO, 'papers', slug, 'index.html')
    if not os.path.exists(page):
        return True
    return 'data-node' in open(page, encoding='utf-8').read()


def classify(spec, doc):
    """Split an overlay's ops into live, redundant and stale.

    Resolution has to be the builder's, not a simpler version of it: the
    builder can now re-find a target whose id changed, and judging staleness by
    id alone would retire ops that still land on the page.
    """
    by_id, by_fp = {}, {}
    for node in doc['nodes']:
        by_id.setdefault(node['id'], []).append(node)
        by_fp.setdefault(fingerprint(node), []).append(node)
    live, redundant, stale = [], [], []
    remap = {}
    for op in spec.get('ops', []):
        if already_present(op, doc['nodes']):
            redundant.append(op)         # the extractor now supplies this text
            continue
        targets, _ = resolve(op, by_id, by_fp, remap, doc['nodes'])
        if not targets:
            stale.append(op)
            continue
        node = targets[0]
        if node['type'] in DOC_HIDDEN or node.get('role') in HIDDEN_ROLES:
            redundant.append(op)
        else:
            live.append(op)
    return live, redundant, stale


def note_for(source, live, redundant, stale):
    today = datetime.date.today().isoformat()
    lines = ['', '## %s — corrections pruned' % today, '']
    if source == 'jats':
        lines.append(
            'This paper renders from the publisher\'s JATS XML, which the '
            'builder prefers over the extracted PDF document, so no op here '
            'could ever reach the page. The defects described below are real '
            'but live in a document nothing reads.')
    elif source == 'biorxiv':
        lines.append(
            'This paper now renders from bioRxiv\'s own full-text conversion '
            'rather than from its PDF, so every op below was written against '
            'nodes that no longer exist. They described PDF extraction '
            'artefacts — page furniture, fragmented paragraphs, figure labels '
            '— which the publisher\'s conversion does not have.')
    else:
        lines.append(
            'Extraction improved underneath these ops. %d still change the '
            'page and were kept; %d now target nodes the classifier already '
            'hides, and %d no longer match any node.'
            % (len(live), len(redundant), len(stale)))
    lines.append('')
    lines.append('Retired ops are kept in the `retired` list in the JSON, with '
                 'their original reasons, so the defects they describe stay on '
                 'record.')
    lines.append('')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    total = {'live': 0, 'redundant': 0, 'stale': 0}
    for path in sorted(glob.glob(os.path.join(EDIT_DIR, '*.json'))):
        slug = os.path.basename(path)[:-5]
        doc_path = os.path.join(DOC_DIR, slug + '.json')
        if not os.path.exists(doc_path):
            print('  --   %-44s no extracted document' % slug[:44])
            continue
        doc = json.load(open(doc_path, encoding='utf-8'))
        spec = json.load(open(path, encoding='utf-8'))
        live, redundant, stale = classify(spec, doc)
        source = 'biorxiv' if doc.get('source') == 'biorxiv' else 'pdf'
        if not renders_from_doc(slug):
            # the page comes from JATS: nothing in the overlay can affect it
            redundant += live
            live, source = [], 'jats'
        for key, value in (('live', live), ('redundant', redundant),
                           ('stale', stale)):
            total[key] += len(value)
        print('  %-44s %-8s live %-4d retire %-4d (%d redundant, %d stale)'
              % (slug[:44], source, len(live), len(redundant) + len(stale),
                 len(redundant), len(stale)))

        if not args.apply or not (redundant or stale):
            continue
        retired = spec.get('retired', [])
        for op in redundant:
            retired.append(dict(op, retired_because='node already hidden by '
                                                    'extraction'))
        for op in stale:
            retired.append(dict(op, retired_because='node id no longer exists'))
        spec['ops'] = live
        spec['retired'] = retired
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(spec, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        md = os.path.join(EDIT_DIR, slug + '.md')
        with open(md, 'a', encoding='utf-8') as fh:
            fh.write(note_for(source, live, redundant, stale))

    print('\nops: %d live, %d redundant, %d stale%s'
          % (total['live'], total['redundant'], total['stale'],
             '' if args.apply else '   (report only — pass --apply to rewrite)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
