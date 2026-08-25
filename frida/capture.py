#!/usr/bin/env python3
"""Spawn QQMusic under Frida, hook ekey/cipher, capture to notes/captures.jsonl.

Usage:
  1) Run this (it spawns + resumes QQMusic, then waits).
  2) In the QQMusic window, play one of the target songs.
  3) Captures are printed and appended to notes/captures.jsonl.
  4) Ctrl+C to stop.
"""
import frida, sys, json, time, os

HERE = os.path.dirname(os.path.abspath(__file__))
APP  = '/Applications/QQMusic.app/Contents/MacOS/QQMusic'
JS   = os.path.join(HERE, 'hooks.js')
OUT  = os.path.join(HERE, '..', 'notes', 'captures.jsonl')

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(JS) as f:
        js = f.read()
    d = frida.get_local_device()
    print('[*] spawning', APP, flush=True)
    pid = d.spawn([APP])
    s = d.attach(pid)

    def on_msg(m, data):
        if m.get('type') == 'send':
            p = m['payload']
            t = p.get('type', '?')
            brief = {k: p.get(k) for k in ('type','N','path','rateType','ekeyLen','valid','offset','size') if k in p}
            print('[+] ' + t + ' ' + json.dumps(brief, ensure_ascii=False), flush=True)
            with open(OUT, 'a') as fo:
                fo.write(json.dumps(p, ensure_ascii=False) + '\n')
        elif m.get('type') == 'error':
            print('[!] JS error:', m.get('description',''), flush=True)
        else:
            print('[?] ' + json.dumps(m, ensure_ascii=False)[:300], flush=True)

    s.on('message', on_msg)
    sc = s.create_script(js)
    sc.load()
    d.resume(pid)
    print('[*] resumed pid %d — NOW PLAY A SONG in QQMusic' % pid, flush=True)
    print('[*] waiting for captures... (Ctrl+C to stop)', flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n[*] stopping', flush=True)
    finally:
        try: s.detach()
        except Exception: pass

if __name__ == '__main__':
    main()
