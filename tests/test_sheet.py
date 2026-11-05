"""Tests of fairtox.sheet: building the curation workbook and reading it back."""
import copy
import csv
import os
from unittest import mock

from openpyxl import load_workbook

from fairtox import cli, fairsharing, fip, model, sheet
from test_fairtox import ROOT, TempDir, fixture


class SheetTest(TempDir):
    def build(self, doc, **kw):
        p = self.path('curation.xlsx')
        sheet.build(doc, p, **kw)
        return p

    def edit(self, p, column, key, value, tab='Resources'):
        wb = load_workbook(p)
        ws = wb[tab]
        head = {c.value: c.column for c in ws[1]}
        row = next(c.row for c in ws['A'] if c.value == key)
        cell = ws.cell(row=row, column=head[column], value=value).coordinate
        wb.save(p)
        return cell

    def add(self, p, cells, tab='Resources'):
        wb = load_workbook(p)
        ws = wb[tab]
        head = {c.value: c.column for c in ws[1]}
        n = next((c.row for c in ws['A'][1:] if c.value is None), ws.max_row + 1)
        for column, value in cells.items():
            ws.cell(row=n, column=head[column], value=value)
        wb.save(p)

    def test_every_list_is_named_after_the_column_it_fills(self):
        lists = {(head, kind[5:]) for head, _, kind, *_ in sheet.RESOURCE_COLUMNS + sheet.RELATION_COLUMNS
                 if kind.startswith('list:')}
        self.assertLessEqual({name for _, name in lists}, set(sheet.LISTS))
        self.assertEqual([(head, name) for head, name in sorted(lists) if head != name], [])

    def test_principles_tab_counts_from_the_resources_tab(self):
        ws = load_workbook(self.build(model.normalise(fixture())))['Principles']
        rows = [[c.value for c in r] for r in ws.iter_rows(max_row=18)]
        self.assertEqual(rows[0], ['Principle', 'FSR type', 'Toxicology', 'Life sciences', 'Generic'])
        self.assertEqual([r[0] for r in rows[1:]], [x for g, ps in model.PRINCIPLES.items() for x in [g, *ps]])
        by = {r[0]: r for r in rows}
        self.assertEqual((by['F1'][1], by['F4'][1]), ('Identifier service', 'Registry'))   # its own type only
        col = {h: c.column_letter for h, c in zip([h for h, *_ in sheet.RESOURCE_COLUMNS], ws.parent['Resources'][1])}
        f = by['F4'][2]   # Toxicology: included, the origin, a type that enables F4 (subclasses too), not set aside
        for part in (f'Resources!${col["Decision"]}$2:${col["Decision"]}="include"', '="Toxicology"',
                     'Domain-specific registry', 'Generalist registry', 'exposome|eco-toxicology', '=FALSE'):
            self.assertIn(part, f)

    def test_round_trip_without_edits_changes_nothing(self):
        doc = model.normalise(fixture())
        new, changes, problems, notes, _ = sheet.ingest(doc, self.build(doc))
        self.assertEqual(problems, [])
        self.assertEqual(changes, [])

    def test_one_edit_gives_one_change(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'First published', 'ctd', '2003')
        self.edit(p, 'Reviewed by', 'ctd', 'JH')
        new, changes, problems, _, reviewers = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertEqual(changes, [('ctd', 'datePublished', '2004', '2003'), ('ctd', 'reviewedBy', '', 'JH')])
        self.assertEqual(reviewers, {'ctd': 'JH'})

    def test_date_basis_moves_the_date_to_its_field(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Date basis', 'ctd', 'release')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertEqual(changes, [('ctd', 'datePublished', '2004', ''), ('ctd', 'dateReleased', '', '2004')])

    def test_identifier_column_and_plain_explanations(self):
        wb = load_workbook(self.build(model.normalise(fixture())))
        ws = wb['Resources']
        head = {c.value: c for c in ws[1]}
        self.assertNotIn('Type', head)
        row = next(c.row for c in ws['A'] if c.value == 'exo')
        self.assertEqual(ws.cell(row=row, column=head['Identifier'].column).value,
                         'https://doi.org/10.25504/FAIRsharing.6hna78')
        texts = [c.comment.text for tab in ('Resources', 'Relations') for c in wb[tab][1] if c.comment]
        texts += [c.value for tab in ('Instructions', 'Lists') for row in wb[tab].iter_rows() for c in row
                  if isinstance(c.value, str)]
        for text in texts:                                  # plain words for curators: no vocabulary terms or IRIs
            self.assertNotRegex(text, r'\b(schema|dct|dcat|prov|skos):|Term:|\bIRI\b|w3id\.org|ontology', text)

    def test_tasks_come_first_and_the_context_follows_folded(self):
        doc = fairsharing.enrich(model.normalise(fixture()), fairsharing.read(None, None, offline=True))
        next(r for r in doc['hasPart'] if r['key'] == 'exo')['fsr'] = ['http://purl.org/np/RAexo#ExO']
        ws = load_workbook(self.build(doc))['Resources']
        head = [c.value for c in ws[1]]
        self.assertEqual(head[:7], ['Key', 'Name', 'URL', 'Reviewed by', 'Sub-domains', 'Source', 'Decision'])
        self.assertEqual(head[head.index('Note') + 1:], list(sheet.FOLDED))   # all context after Note, folded
        row = next(c.row for c in ws['A'] if c.value == 'exo')
        self.assertEqual(ws.cell(row=row, column=head.index('Sub-domains') + 1).value, 'exposome')
        s = head.index('Origin')                             # FAIRsharing's tags beside the fields they help check
        self.assertEqual(head[s:s + 4], ['Origin', 'FAIRsharing subjects', 'Phase', 'FAIRsharing domains'])
        self.assertEqual({c.fill.fgColor.rgb for c in ws[1]}, {sheet.HEAD.fgColor.rgb})   # one header colour
        row = next(c.row for c in ws['A'] if c.value == 'exo')
        value = lambda h: ws.cell(row=row, column=head.index(h) + 1).value
        self.assertEqual([value(h) for h in ('FIP identifiers', 'FAIRsharing subjects', 'FAIRsharing domains')],
                         ['http://purl.org/np/RAexo#ExO', 'Toxicogenomics', 'study design; exposure'])
        self.assertIn('FAIRsharing subjects', [h for h, f, k, *_ in sheet.RESOURCE_COLUMNS if k in sheet.GREY_KINDS])

    def test_grey_columns_say_what_grey_means(self):
        for columns in (sheet.RESOURCE_COLUMNS, sheet.RELATION_COLUMNS):
            for head, field, kind, _, note in columns:
                if kind in sheet.GREY_KINDS:                # each grey note opens the same way and gives a purpose
                    self.assertTrue(note.startswith(sheet.GREY_NOTE), head)
                    self.assertGreater(len(note), len(sheet.GREY_NOTE) + 20, head)
        self.assertRegex(sheet.INSTRUCTIONS[0].lower(), r'grey (is|means) read-only')   # what grey is, first
        self.assertIn('cannot break', sheet.INSTRUCTIONS[0].lower())

    def test_columns_without_curator_information_are_folded(self):
        ws = load_workbook(self.build(model.normalise(fixture())))['Resources']
        for c in ws[1]:
            dim = ws.column_dimensions[c.column_letter]
            self.assertEqual((dim.outline_level, bool(dim.hidden)), (1, True) if c.value in sheet.FOLDED else (0, False),
                             c.value)

    def test_a_row_read_back_earlier_can_be_edited_again(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'First published', 'ctd', '2003')
        doc = sheet.ingest(doc, p)[0]                       # read back: the sheet's row version is now behind
        self.edit(p, 'First published', 'ctd', '2002')
        self.assertTrue(sheet.ingest(doc, p)[2])            # a dataset row changed elsewhere waits,
        new, changes, problems, _, _ = sheet.ingest(doc, p, read_back={'ctd'})
        self.assertEqual(problems, [])                      # one whose latest change came from the sheet does not
        self.assertEqual(changes, [('ctd', 'datePublished', '2003', '2002')])

    def test_bad_value_is_reported_with_its_cell(self):
        doc = model.normalise(fixture())
        for column, value in (('Origin', 'Toxicologie'), ('FSR type', 'Databank'),
                              ('Phase', 'Data generation, Data integratoin'), ('Sub-domains', 'exposome, ecotox')):
            p = self.build(doc)
            cell = self.edit(p, column, 'ctd', value)
            new, changes, problems, _, _ = sheet.ingest(doc, p)
            self.assertIsNotNone(new)                           # the row waits; the rest of the sheet is read
            self.assertEqual(changes, [])
            self.assertEqual([(x['sheet'], x['cell'], x['column']) for x in problems], [('Resources', cell, column)])
            self.assertIn('allowed values', problems[0]['problem'])

    def test_fsr_types_span_and_read_only_fip_rows(self):
        doc = model.normalise(fixture())
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'], by['ctd']['fsrType'] = [model.FIP + 'Structured-vocabulary'], [model.FIP + 'Editor']
        p = self.build(fip.enrich(copy.deepcopy(doc), fip.read(offline=True)))   # tool and oecd_gd declare exo
        wb = load_workbook(p)
        tab = lambda name: [dict(zip([c.value for c in wb[name][1]], r))
                            for r in wb[name].iter_rows(min_row=2, values_only=True) if r[0]]
        exo, ctd = (next(r for r in tab('Resources') if r['Key'] == k) for k in ('exo', 'ctd'))
        self.assertEqual([exo[h] for h in ('FSR type', 'Class', 'Principles', 'Declared in', 'Phase')],
                         ['Structured vocabulary', 'FAIR-Enabling Resource', 'I2',   # I2: what the type enables
                          'OECD guidance on research data (F1-D); A FAIR tool (F1-D)', 'Data integration'])
        self.assertEqual(ctd['Phase'], 'Data integration, Regulatory assessment')   # every phase, in phase order
        self.assertEqual([(x['Resource'], x['Relation'], x['Target'], x['Vocabulary'], x['Question'], x['Use'])
                          for x in tab('Relations') if x['Evidence'] == 'FIP'],
                         [('oecd_gd', 'declares-current-use-of', 'exo', 'FIP ontology', 'F1-D', 'current use'),
                          ('tool', 'declares-current-use-of', 'exo', 'FIP ontology', 'F1-D', 'current use')])
        self.assertEqual({x['Vocabulary'] for x in tab('Relations') if x['Evidence'] != 'FIP'}, {'FAIRsharing'})
        self.assertEqual(sheet.ingest(doc, p)[1:3], ([], []))                  # no changes, no problems
        self.edit(p, 'Target', 'tool', 'ctd', tab='Relations')                 # a FIP row: ignored
        self.edit(p, 'FSR type', 'ctd', 'Registry')
        self.edit(p, 'Phase', 'exo', 'Regulatory assessment, Data integration')   # in the order clicked
        self.assertEqual(sheet.ingest(doc, p)[1:3], ([
            ('ctd', 'fsrType', model.FIP + 'Editor', model.FIP + 'Registry'),
            ('exo', 'span', 'Data integration', 'Data integration; Regulatory assessment')], []))
        by['exo']['fsrType'] = [model.FIP + 'Semantic-model']                  # changed after the sheet was made
        self.assertIn('changed in the dataset', sheet.ingest(doc, p)[2][0]['problem'])

    def test_the_earliest_phase_chosen_is_the_phase(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Phase', 'ctd', 'Regulatory assessment,Data generation')   # any order, with or without a space
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, problems), ([
            ('ctd', 'phase', 'Data integration', 'Data generation'),
            ('ctd', 'span', 'Data integration; Regulatory assessment', 'Data generation; Regulatory assessment')], []))
        self.assertEqual(sheet.ingest(new, p)[1:3], ([], []))                  # read back once

    def test_sub_domains_are_chosen_in_one_cell(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Sub-domains', 'ctd', 'regulatory toxicology, exposome')   # in the order clicked
        self.edit(p, 'Sub-domains', 'exo', '')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, problems), ([
            ('ctd', 'subdomains', '', 'exposome; regulatory toxicology'),            # in the list's order
            ('exo', 'subdomains', 'exposome', '')], []))
        self.assertEqual(sheet.ingest(new, p)[1:3], ([], []))

    def test_fsr_types_are_chosen_in_one_cell(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'FSR type', 'ctd', 'Registry, Editor')                    # in the order clicked
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, problems), ([('ctd', 'fsrType', '', f'{model.FIP}Editor; {model.FIP}Registry')], []))
        ws = load_workbook(self.build(new))['Resources']
        head = [c.value for c in ws[1]]
        ctd = next(dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == 'ctd')
        self.assertEqual((ctd['FSR type'], ctd['Class']), ('Editor, Registry', 'FAIR-Enabling Resource'))
        self.assertEqual(sheet.ingest(new, self.path('curation.xlsx'))[1:3], ([], []))   # read back once

    def test_contacts_are_orcid_or_ror_links(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        links = 'https://orcid.org/0000-0002-1825-0097; https://ror.org/044rwnt51'
        self.edit(p, 'Contact', 'ctd', links)
        self.edit(p, 'Contact', 'exo', 'someone@example.org')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [('ctd', 'contactPoint', '', links)])
        self.assertEqual([x['problem'] for x in problems], ["exo: contact 'someone@example.org' must be an ORCID or ROR link"])
        self.assertEqual(sheet.ingest(new, self.build(new))[1:3], ([], []))   # read back once

    def test_a_column_a_curator_adds_is_ignored(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        wb = load_workbook(p)
        ws = wb['Resources']
        ws.cell(row=1, column=ws.max_column + 1, value='exposome')               # even one named after a sub-domain
        ws.cell(row=2, column=ws.max_column, value='x')
        wb.save(p)
        self.assertEqual(sheet.ingest(doc, p)[1:3], ([], []))

    def test_stale_row_is_refused_unless_forced(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        moved = copy.deepcopy(doc)
        next(r for r in moved['hasPart'] if r['key'] == 'ctd')['note'] = 'changed elsewhere'
        self.edit(p, 'Name', 'ctd', 'CTD database')
        self.assertTrue(sheet.ingest(moved, p)[2])
        new, changes, problems, _, _ = sheet.ingest(moved, p, force=True)
        self.assertEqual(problems, [])
        self.assertIn(('ctd', 'name', 'Comparative Toxicogenomics Database', 'CTD database'), changes)

    def test_new_row_and_relation_removal(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.add(p, {'Name': 'New Resource', 'Aliases': 'NewRes', 'Decision': 'undecided'})
        self.edit(p, 'Keep', 'ctd', 'remove', tab='Relations')
        new, changes, problems, notes, _ = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertIn(('newres', '(row)', '(new)', 'New Resource'), changes)
        self.assertIn(('ctd', 'relation', 'implements exo', '(removed)', ''), changes)   # unsigned

    def test_each_relation_line_carries_its_version(self):
        doc = model.normalise(fixture())
        ws = load_workbook(self.build(doc))['Relations']
        head = [c.value for c in ws[1]]
        versions = [dict(zip(head, r))['Line version'] for r in ws.iter_rows(min_row=2, values_only=True)]
        self.assertEqual([v for v in versions if v], [model.relation_hash(x) for x in model.relation_rows(doc)])

    def test_a_relation_changed_in_the_dataset_after_the_sheet_waits(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Note', 'ctd', 'Checked in the sheet.', tab='Relations')
        moved = copy.deepcopy(doc)
        next(r for r in moved['hasPart'] if r['key'] == 'ctd')['qualifiedRelation'][0]['note'] = 'Changed elsewhere.'
        new, changes, problems, _, _ = sheet.ingest(moved, p)
        self.assertEqual((changes, [x['value'] for x in problems]), ([], ['ctd implements exo']))
        self.assertIn('changed in the dataset', problems[0]['problem'])
        self.assertEqual(sheet.ingest(moved, p, read_back={('ctd', 'implements', 'exo')})[1],   # last read back here
                         [('ctd', 'relation implements exo note', 'Changed elsewhere.', 'Checked in the sheet.', '')])
        next(r for r in moved['hasPart'] if r['key'] == 'ctd')['qualifiedRelation'] = []      # removed elsewhere
        self.assertEqual([x['value'] for x in sheet.ingest(moved, p)[2]], ['ctd implements exo'])
        self.edit(p, 'Keep', 'ctd', 'remove', tab='Relations')                     # the sheet shows the removal
        self.assertEqual(sheet.ingest(moved, p)[1:3], ([], []))

    def test_a_relation_line_edited_again_after_its_read_back_replaces_again(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Relation', 'ctd', 'related_to', tab='Relations')
        doc = sheet.ingest(doc, p)[0]                           # read back and merged; the line keeps its version
        self.edit(p, 'Target', 'ctd', 'tool', tab='Relations')
        new, changes, problems, _, _ = sheet.ingest(doc, p, read_back={('ctd', 'implements', 'exo'),
                                                                       ('ctd', 'related_to', 'exo')})
        self.assertEqual((sorted(changes), problems), ([('ctd', 'relation', '(new)', 'related_to tool', ''),
                                                        ('ctd', 'relation', 'related_to exo', '(removed)', '')], []))
        self.edit(p, 'Relation', 'ctd', 'implements', tab='Relations')     # and back to what the sheet first showed
        self.edit(p, 'Target', 'ctd', 'exo', tab='Relations')
        changes = sheet.ingest(new, p, read_back={('ctd', 'implements', 'exo'), ('ctd', 'related_to', 'tool')})[1]
        self.assertEqual(sorted(changes), [('ctd', 'relation', '(new)', 'implements exo', ''),
                                           ('ctd', 'relation', 'related_to tool', '(removed)', '')])

    def test_a_relation_line_moved_onto_one_added_elsewhere_waits(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        added = copy.deepcopy(doc)
        by = {r['key']: r for r in added['hasPart']}
        by['ctd']['qualifiedRelation'].append({'relation': by['exo']['@id'], 'hadRole': 'related_to',
                                               'evidence': 'literature', 'source': 'L120', 'reviewedBy': 'MM'})
        self.edit(p, 'Relation', 'ctd', 'related_to', tab='Relations')
        new, changes, problems, notes, _ = sheet.ingest(added, p)
        self.assertEqual((changes, [x['value'] for x in problems], notes), ([], ['ctd related_to exo'], []))

    def test_a_relation_signed_with_its_edit_is_not_reported_under_other_initials(self):
        doc = model.normalise(fixture())
        os.makedirs(self.path('data'))
        model.save(doc, self.path(model.DATASET))
        with open(self.path(model.CHANGES), 'w', encoding='utf-8') as f:
            f.write('date,round,key,field,old,new,by,source\n')
        p = self.build(doc)
        self.edit(p, 'Relation', 'ctd', 'related_to', tab='Relations')
        self.edit(p, 'Reviewed by', 'ctd', 'IM', tab='Relations')
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        with mock.patch.object(model, 'FIP_ONTOLOGY', os.path.join(ROOT, model.FIP_ONTOLOGY)), \
                mock.patch('builtins.print'), self.assertRaises(SystemExit):
            cli.main(['ingest', p, '--report', 'report.md'])
        with open('report.md', encoding='utf-8') as f:
            self.assertNotIn('changed under the initials', f.read())

    def test_a_relation_line_edited_in_place_replaces_its_relation(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Relation', 'ctd', 'related_to', tab='Relations')
        self.edit(p, 'Reviewed by', 'ctd', 'IM', tab='Relations')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(changes), [('ctd', 'relation', '(new)', 'related_to exo', 'IM'),
                                           ('ctd', 'relation', 'implements exo', '(removed)', 'IM')])

    def test_an_edited_copy_of_a_relation_line_adds_and_keeps_the_original(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        ws = load_workbook(p)['Relations']
        head = [c.value for c in ws[1]]
        line = next(dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == 'ctd')
        self.add(p, {**{h: line[h] for h in ('Resource', 'Target', 'Evidence', 'Line version')},
                     'Relation': 'related_to'}, tab='Relations')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, problems), ([('ctd', 'relation', '(new)', 'related_to exo', '')], []))

    def test_a_deleted_relation_line_leaves_the_relation_and_says_so(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        wb = load_workbook(p)
        wb['Relations'].delete_rows(next(c.row for c in wb['Relations']['A'] if c.value == 'ctd'))
        wb.save(p)
        new, changes, problems, notes, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, problems), ([], []))
        self.assertIn('1 relations are not in the sheet and were left unchanged: ctd implements exo', notes[-1])

    def test_source_and_community_document_ticks(self):
        doc = fip.enrich(fairsharing.enrich(model.normalise(fixture()), fairsharing.read(None, None, offline=True)),
                         fip.read(offline=True))                 # the FIPs tool and oecd_gd declare exo
        by = {r['key']: r for r in doc['hasPart']}
        by['tool']['declared-by'] = by['parc']['@id']             # parc is the community behind tool
        by['exo']['mentionedIn'] = ['Whitepaper']
        doc.setdefault('sources', {})['inventory'] = {'name': 'repository list', 'resources': ['ctd', 'exo']}
        wb = load_workbook(self.build(doc, added={'ctd'}))
        ws = wb['Resources']
        head = [c.value for c in ws[1]]
        rows = {r[0]: dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}
        self.assertEqual({k: r['Source'] for k, r in rows.items()}, {
            'exo': 'Manuscript draft; FAIRsharing Toxicology collection; A FAIR tool; OECD guidance on research data; '
                   'Co-author repository inventory',
            'ctd': 'Co-author repository inventory', 'oecd_gd': 'Manuscript draft', 'parc': 'Manuscript draft; A FAIR tool',
            'tool': None})
        self.assertIn(('inventory', 'name: repository list; resources: ctd, exo',
                       'Repositories listed by a co-author, added as rows; the Source column names them.'),
                      [tuple(r[:3]) for r in wb['Sources'].iter_rows(min_row=2, values_only=True)])
        self.assertEqual([rows['exo'][f'ETC: {d}'] for d in model.ETC_DOCUMENTS],
                         [d == 'Whitepaper' for d in model.ETC_DOCUMENTS])
        self.assertEqual(head.index('Note') - head.index(f'ETC: {next(iter(model.ETC_DOCUMENTS))}'),
                         len(model.ETC_DOCUMENTS))                # the tick boxes come right before Note
        self.assertNotIn('In FAIRsharing collection', head)

    def test_ticks_and_a_new_row_are_read_back_once(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        wb = load_workbook(p)
        ws = wb['Resources']
        head = {c.value: c.column for c in ws[1]}
        ws.cell(row=next(c.row for c in ws['A'] if c.value == 'exo'), column=head['ETC: INTOXICOM 4'], value=True)
        n = next(c.row for c in ws['B'] if c.row > 1 and c.value is None)
        ws.cell(row=n, column=head['Name'], value='New Resource')   # no key, decision or manuscript status
        for d in model.ETC_DOCUMENTS:                               # unticked boxes leave a spare row empty
            ws.cell(row=n + 1, column=head[f'ETC: {d}'], value=False)
        wb.save(p)
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertEqual(changes, [('new_resource', '(row)', '(new)', 'New Resource'),
                                   ('exo', 'mentionedIn', '', 'INTOXICOM 4')])
        self.assertEqual(sheet.ingest(new, p)[1:3], ([], []))     # the next read-back adds nothing twice

    def test_a_row_with_a_problem_waits_and_the_rest_is_read_back(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'First published', 'ctd', '2003')         # ctd keeps its older warning; that holds nothing back
        self.edit(p, 'Decision', 'tool', 'exclude')             # no exclusion reason
        self.edit(p, 'Reviewed by', 'ctd', 'IM', tab='Relations')
        self.add(p, {'Resource': 'ctd', 'Relation': 'related_to', 'Target': 'tool', 'Evidence': 'Literature'},
                 tab='Relations')                               # a bad cell waits on its own line
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [('ctd', 'datePublished', '2004', '2003'),
                                   ('ctd', 'relation implements exo reviewedBy', '', 'IM', 'IM')])
        self.assertEqual([(x['sheet'], x['value']) for x in problems],
                         [('Relations', 'Literature'), ('Resources', 'tool')])
        self.assertEqual(next(r for r in new['hasPart'] if r['key'] == 'tool')['decision'], 'undecided')

    def test_a_note_in_reviewed_by_waits_on_its_cell(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Description', 'tool', 'Edited.')
        self.edit(p, 'Reviewed by', 'tool', 'IM see ChemAgora')    # a note, not initials
        self.edit(p, 'Reviewed by', 'ctd', 'IM, JH', tab='Relations')
        self.edit(p, 'Reviewed by', 'exo', 'Marvin')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [('exo', 'reviewedBy', '', 'Marvin')])
        self.assertEqual([(x['sheet'], x['column'], x['value']) for x in problems],
                         [('Resources', 'Reviewed by', 'IM see ChemAgora'), ('Relations', 'Reviewed by', 'IM, JH')])

    def test_a_relation_that_would_add_a_warning_waits(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.add(p, {'Resource': 'ctd', 'Relation': 'extends', 'Target': 'exo', 'Evidence': 'literature'},
                 tab='Relations')
        self.edit(p, 'First published', 'ctd', '2003')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [('ctd', 'datePublished', '2004', '2003')])   # ctd (2003) extends exo (2012) waits
        self.assertEqual([(x['sheet'], x['value']) for x in problems], [('Relations', 'ctd extends exo')])

    def test_a_date_that_would_make_a_relation_warn_waits(self):
        doc = fixture()
        next(r for r in doc['hasPart'] if r['key'] == 'exo')['qualifiedRelation'] = [
            {'relation': '#ctd', 'hadRole': 'extends', 'evidence': 'curator'}]     # ExO (2012) extends CTD (2004)
        doc = model.normalise(doc)
        p = self.build(doc)
        self.edit(p, 'First published', 'exo', '2000')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, sorted(x['value'] for x in problems)), ([], ['exo', 'exo extends ctd']))

    def test_a_relation_that_is_not_possible_waits_on_its_line(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.add(p, {'Resource': 'oecd_gd', 'Relation': 'implements', 'Target': 'exo', 'Evidence': 'literature'},
                 tab='Relations')
        self.edit(p, 'Note', 'oecd_gd', 'Checked.')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [('oecd_gd', 'note', '', 'Checked.')])          # the row is read back
        self.assertEqual([(x['sheet'], x['value']) for x in problems], [('Relations', 'oecd_gd implements exo')])

    def test_a_type_that_would_make_a_relation_impossible_waits(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'FAIRsharing type', 'ctd', 'Policy: project')                # ctd implements exo
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, sorted(x['value'] for x in problems)), ([], ['ctd', 'ctd implements exo']))

    def test_two_lines_with_one_key_or_one_relation_both_wait(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Description', 'ctd', 'Edited.')
        self.add(p, {'Key': 'ctd', 'Name': 'CTD copy'})
        for note in ('', 'again'):
            self.add(p, {'Resource': 'exo', 'Relation': 'related_to', 'Target': 'tool', 'Note': note}, tab='Relations')
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [])
        self.assertEqual(sorted(x['value'] for x in problems),
                         ['ctd', 'ctd', 'exo related_to tool', 'exo related_to tool'])

    def test_of_two_lines_with_one_relation_the_signed_one_decides(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Keep', 'ctd', 'remove', tab='Relations')                  # ctd implements exo, signed: remove
        self.edit(p, 'Reviewed by', 'ctd', 'MM', tab='Relations')
        self.add(p, {'Resource': 'ctd', 'Relation': 'implements', 'Target': 'exo'}, tab='Relations')   # a bare copy
        new, changes, problems, notes, _ = sheet.ingest(doc, p)
        self.assertEqual((changes, problems), ([('ctd', 'relation', 'implements exo', '(removed)', 'MM')], []))
        self.assertEqual([n for n in notes if 'copy' in n], ['Relations!A3: an unsigned copy of the signed line 2, ignored'])
        p = self.build(doc)                                                     # signed: keep; the copy says remove
        self.edit(p, 'Reviewed by', 'ctd', 'MM', tab='Relations')
        self.add(p, {'Resource': 'ctd', 'Relation': 'implements', 'Target': 'exo', 'Keep': 'remove'}, tab='Relations')
        self.assertEqual(sheet.ingest(doc, p)[1:3], ([('ctd', 'relation implements exo reviewedBy', '', 'MM', 'MM')], []))
        self.add(p, {'Resource': 'ctd', 'Relation': 'implements', 'Target': 'exo', 'Reviewed by': 'IM'}, tab='Relations')
        self.assertEqual(sorted(x['value'] for x in sheet.ingest(doc, p)[2]),  # two signed lines: they all wait
                         ['ctd implements exo'] * 3)

    def test_a_row_added_in_the_sheet_and_changed_elsewhere_waits(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.add(p, {'Key': 'newres', 'Name': 'New Resource'})
        doc = sheet.ingest(doc, p)[0]                           # read back; the sheet row has no Row version
        next(r for r in doc['hasPart'] if r['key'] == 'newres')['description'] = 'Proposed elsewhere.'
        new, changes, problems, _, _ = sheet.ingest(doc, p)
        self.assertEqual(changes, [])
        self.assertIn('changed in the dataset', problems[0]['problem'])

    def test_the_ingest_command_logs_who_and_reports_what_waits(self):
        doc = model.normalise(fixture())
        os.makedirs(self.path('data'))
        model.save(doc, self.path(model.DATASET))
        with open(self.path(model.CHANGES), 'w', encoding='utf-8') as f:
            f.write('date,round,key,field,old,new,by,source\n')
        p = self.build(doc)
        self.edit(p, 'First published', 'ctd', '2003')
        self.edit(p, 'Reviewed by', 'ctd', 'JH')
        self.edit(p, 'Reviewed by', 'ctd', 'IM', tab='Relations')
        self.edit(p, 'Decision', 'tool', 'exclude')
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)                                      # the command works on data/ in the current folder
        ontology = os.path.join(ROOT, model.FIP_ONTOLOGY)
        with mock.patch.object(model, 'FIP_ONTOLOGY', ontology), mock.patch('builtins.print'):
            with self.assertRaises(SystemExit) as stop:
                cli.main(['ingest', p, '--report', 'report.md'])
            self.assertEqual(stop.exception.code, 0)
            with open(model.CHANGES, newline='', encoding='utf-8') as f:
                self.assertEqual({(r['key'], r['field'], r['by']) for r in csv.DictReader(f)},
                                 {('ctd', 'datePublished', 'JH'), ('ctd', 'reviewedBy', 'JH'),
                                  ('ctd', 'relation implements exo reviewedBy', 'IM')})
            # The relation was last read back from this sheet: edited again, its older line version does not hold it.
            self.edit(p, 'Note', 'ctd', 'Checked twice.', tab='Relations')
            with self.assertRaises(SystemExit):
                cli.main(['ingest', p])
            self.assertEqual(next(x for x in model.relation_rows(model.load()) if x['subject'] == 'ctd')['note'],
                             'Checked twice.')
            # A process changes ctd, then a relation of ctd is signed: ctd's stale line must not undo the proposal.
            later = model.load()
            next(r for r in later['hasPart'] if r['key'] == 'ctd')['description'] = 'Proposed by research.'
            model.save(later)
            model.log_changes([('ctd', 'description', '', 'Proposed by research.')], 'research', 'web',
                              {'ctd': 'research'})
            model.log_changes([('ctd', 'relation implements exo note', '', 'Signed.', 'IM')], 'sheet', 'curation.xlsx')
            with self.assertRaises(SystemExit):
                cli.main(['ingest', p])
            self.assertEqual(next(r for r in model.load()['hasPart'] if r['key'] == 'ctd')['description'],
                             'Proposed by research.')
            wb = load_workbook(p)
            next(c for c in wb['Relations'][1] if c.value == 'Reviewed by').value = 'Checked by'
            wb.save(p)
            with self.assertRaises(SystemExit) as stop:
                cli.main(['ingest', p, '--report', 'report.md'])
            self.assertEqual(stop.exception.code, 1)            # a sheet that cannot be read changes nothing
        with open('report.md', encoding='utf-8') as f:
            report = f.read()
        for text in ('tool: tool: an exclusion reason is required', 'columns missing',
                     'signed by a curator: 1 of 3 included rows, 1 of 1 relations'):
            self.assertIn(text, report)
