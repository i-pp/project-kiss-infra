"""Synthetic tokenizer/template only; never imports Strata source."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import strata_shim


class Tokenizer:
    tokens=range(248500)
    @classmethod
    def from_gguf(cls,path):return cls()
    def encode(self,text,parse_special=False):
        return {'<|im_end|>':[248046],'<|endoftext|>':[248044]}.get(text,[4,5])
    def decode(self,ids,errors='strict'):
        return ''.join({99:'ACEIS_STRATA_FLASH_ACK',248046:'<|im_end|>',248044:'<|endoftext|>'}.get(n,'x') for n in ids)


class PromptTests(unittest.TestCase):
    def invoke(self,mode,data,tokenizer=Tokenizer):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inp=root/'input.json';out=root/'output.json';inp.write_text(json.dumps(data))
            def render(messages,**kw):
                self.assertIs(kw['enable_thinking'],False)
                self.assertIs(kw['add_generation_prompt'],True)
                return 'fixture rendered'
            fake={'tools.strata_tokenizer':SimpleNamespace(Tokenizer=tokenizer),
                  'serve.frontend':SimpleNamespace(ChatTemplate=lambda _:SimpleNamespace(render=render))}
            argv=['strata_shim.py',mode,'--source',t,'--gguf',str(root/'fixture.gguf'),'--pack',t,'--input',str(inp),'--output',str(out)]
            with patch.dict(sys.modules,fake),patch.object(sys,'argv',argv):strata_shim.main()
            return json.loads(out.read_text())
    def test_model_template_and_explicit_stop_ids(self):
        r=self.invoke('encode',{'messages':[{'role':'user','content':'fixture'}]})
        self.assertEqual(r['stop_ids'],[248044,248046]);self.assertEqual(r['rendered_prompt'],'fixture rendered')
    def test_only_terminal_verified_stop_removed_raw_preserved(self):
        r=self.invoke('decode',{'token_ids':[99,248046],'finish':'stop'})
        self.assertEqual(r['content'],'ACEIS_STRATA_FLASH_ACK');self.assertEqual(r['raw_decoded'],'ACEIS_STRATA_FLASH_ACK<|im_end|>')
        self.assertEqual(r['token_ids'],[99,248046])
    def test_middle_stop_or_done_stop_without_stop_token_rejected(self):
        for ids in [[248046,99],[99]]:
            with self.assertRaises(ValueError):self.invoke('decode',{'token_ids':ids,'finish':'stop'})
    def test_length_does_not_strip_or_fake_complete_output(self):
        r=self.invoke('decode',{'token_ids':[99],'finish':'length'})
        self.assertIsNone(r['removed_terminal_stop_id']);self.assertEqual(r['content'],'ACEIS_STRATA_FLASH_ACK')
    def test_unexpected_source_stop_identity_rejected(self):
        class Different(Tokenizer):
            def encode(self,text,parse_special=False):return [7]
        with self.assertRaises(ValueError):self.invoke('encode',{'messages':[]},Different)


if __name__=='__main__':unittest.main()
