"""Offline pinned Strata tokenizer/protocol adapter. No network or tool use."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    config = json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0, config['strata_source'])
    from tools.strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate
    command = config['strata_command']
    tokenizer = Tokenizer.from_gguf(command[command.index('--native') + 1])
    template = ChatTemplate(Path(command[command.index('--pack') + 1]) / 'tokenizer/chat_template.jinja')
    stops = [tokenizer.encode(t, parse_special=True) for t in ['<|im_end|>', '<|endoftext|>']]
    if sorted(x[0] for x in stops if len(x) == 1) != [248044, 248046]:
        raise ValueError('pinned stop tokens do not match')
    env = {**os.environ, 'OMP_NUM_THREADS': '8', 'STRATA_IO_PREFETCH': '0',
           'STRATA_PREFILL_WARM': '0', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    engine = subprocess.Popen(command, cwd=config['strata_source'], env=env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    try:
        for line in engine.stdout:
            if line.startswith('READY'):
                print(json.dumps({'ready': True}), flush=True)
                break
        else:
            raise RuntimeError('Strata exited before READY')
        for line in sys.stdin:
            body = json.loads(line)
            rendered = template.render(body['messages'], tools=None, add_generation_prompt=True, enable_thinking=False)
            ids = tokenizer.encode(rendered, parse_special=True)
            n = body['max_tokens']
            if len(ids) + n + 8 > 8192:
                print(json.dumps({'error': 'context budget exceeded'}), flush=True)
                continue
            engine.stdin.write('GEN ' + str(n) + ' temperature=0 ' + ','.join(map(str, ids)) + '\n')
            engine.stdin.flush()
            tokens = []
            for output in engine.stdout:
                if output.startswith('T '):
                    tokens.append(int(output.split()[1]))
                    if len(tokens) > n:
                        raise RuntimeError('Strata output exceeded token limit')
                elif output.startswith('ERR'):
                    raise RuntimeError('Strata generation error')
                elif output.startswith('DONE '):
                    fields = output.split()
                    finish = fields[5]
                    if int(fields[1]) != len(tokens) or finish not in {'stop', 'length'}:
                        raise RuntimeError('invalid terminal protocol')
                    if any(x in [248044, 248046] for x in tokens[:-1]):
                        raise RuntimeError('embedded terminal token')
                    presentation = tokens[:]
                    if finish == 'stop':
                        if not presentation or presentation.pop() not in [248044, 248046]:
                            raise RuntimeError('stop without stop token')
                    print(json.dumps({'content': tokenizer.decode(presentation, errors='strict'),
                                      'finish_reason': finish, 'prompt_tokens': len(ids),
                                      'completion_tokens': len(tokens)}), flush=True)
                    break
            else:
                raise RuntimeError('Strata exited during generation')
    finally:
        if engine.poll() is None:
            engine.terminate()
            try:
                engine.wait(timeout=3)
            except subprocess.TimeoutExpired:
                engine.kill()
                engine.wait()

if __name__ == '__main__':
    main()
