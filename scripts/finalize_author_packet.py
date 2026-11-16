"""Build wave2 / final casebook only from actual records and author-confirmed labels."""
import argparse,json
from pathlib import Path
from src.audit.pilot_common import blind_view
from src.audit.pilot_selection import select_casebook
from scripts.prepare_author_packet import export_rows
O=Path('rebuttal/annotation/author_packet_20261108')
def post_rows(records):
 rows=[]
 for r in records:
  if r.get('label_status')=='pilot_provisional' or r.get('human_screened') is not True:raise ValueError('Author-screened actual injections only')
  pair=r['screening_authors']
  if len(set(pair))!=2:raise ValueError('Two screening authors required')
  for a in pair:
   rows.append({'task':'E2-A post-injection','item_id':r['item_id'],'assigned_annotator':a,'annotator_id':'','before_trace':blind_view(r['before_trace']),'after_trace':blind_view(r['after_trace']),'answers':{'exactly_one_critical_defect':'','other_critical_facts_unchanged':'','wrong_in_two_reruns':'','one_visible_step_changed_if_aggregation':'','uncertain_reason':'','source_citations':'','minutes_spent':''}})
 return rows

def casebook_rows(labels,pool):
 if any(r.get('label_source')!='human_adjudicated' for r in labels):raise ValueError('Human-confirmed classes required')
 counts={'extraction':4,'selection':4,'aggregation_musique':2,'aggregation_silobench':2};selection=select_casebook(labels,counts);ids={i for xs in selection.values() for i in xs}
 return selection,[r for r in pool if r['item_id'] in ids]
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['post','casebook'],required=True);p.add_argument('--input',required=True);a=p.parse_args();records=json.loads(Path(a.input).read_text())
 if a.mode=='post':export_rows(O/'E2A_post_wave2.jsonl',post_rows(records))
 else:
  pool=[json.loads(s) for s in (O/'E2C_class_confirmation_pool.jsonl').read_text().splitlines()];selection,rows=casebook_rows(records,pool);export_rows(O/'E2C_selected_confirmation.jsonl',rows)
  # Class labels stay in private pilot metadata, not in the confirmation sheets.
  Path('rebuttal/pilots/20261108_review4/casebook_selected_manifest.json').write_text(json.dumps(selection,indent=2)+'\n')
if __name__=='__main__':main()
