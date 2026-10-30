"""Executed only by the approved human-host trial, after fixed-source verification."""
import argparse
import json
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['check','encode','decode'])
    p.add_argument('--source',required=True);p.add_argument('--gguf',required=True)
    p.add_argument('--pack',required=True);p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();sys.path.insert(0,a.source)
    from tools.strata_tokenizer import Tokenizer
    if a.mode=='check':
        from serve.frontend import ChatTemplate
        from tools import strata_pack
        with Path(a.output).open('x') as f:json.dump({'status':'IMPORTS_CHECKED_NO_MODEL_LOAD','generation_requests':0},f)
        return
    tk=Tokenizer.from_gguf(a.gguf)
    data=json.loads(Path(a.input).read_text())
    stops=[]
    for literal in ['<|im_end|>','<|endoftext|>']:
        encoded=tk.encode(literal,parse_special=True)
        if len(encoded)!=1 or not 0<=encoded[0]<len(tk.tokens):raise ValueError('Verified single stop token required')
        stops.append(encoded[0])
    if set(stops)!={248044,248046}:raise ValueError('Pinned Flash stop-token identity differs')
    if a.mode=='encode':
        from serve.frontend import ChatTemplate
        template=Path(a.pack)/'tokenizer/chat_template.jinja'
        rendered=ChatTemplate(template).render(data['messages'],tools=None,add_generation_prompt=True,enable_thinking=False)
        ids=tk.encode(rendered,parse_special=True)
        if not ids or len(ids)+128>8192 or any(type(n)is not int or not 0<=n<len(tk.tokens) for n in ids):
            raise ValueError('Prompt token bound violated')
        out={'rendered_prompt':rendered,'prompt_ids':ids,'vocabulary_size':len(tk.tokens),'stop_ids':sorted(set(stops))}
    else:
        ids=data['token_ids']
        if len(ids)>128 or any(type(n)is not int or not 0<=n<len(tk.tokens) for n in ids):raise ValueError('Invalid generated IDs')
        if any(n in stops for n in ids[:-1]):raise ValueError('Stop token before final record')
        presentation=list(ids);removed=None
        if data.get('finish')=='stop':
            if not ids or ids[-1] not in stops:raise ValueError('DONE stop without verified final stop token')
            removed=presentation.pop()
        out={'content':tk.decode(presentation,errors='strict'),'raw_decoded':tk.decode(ids,errors='strict'),
             'token_ids':ids,'removed_terminal_stop_id':removed}
    with Path(a.output).open('x') as f:json.dump(out,f,ensure_ascii=False)


if __name__=='__main__':main()
